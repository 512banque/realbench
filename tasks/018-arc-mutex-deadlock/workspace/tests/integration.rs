//! Integration tests for `transfer`.
//!
//! Detecting a deadlock from inside a Rust `#[test]` is tricky: there is
//! no `JoinHandle::join_timeout` in the standard library, and panicking
//! from the test thread does not unblock threads that are stuck on a
//! `Mutex::lock()`. We use an mpsc channel as a heartbeat: each worker
//! sends a "done" message when it finishes its transfer loop. The main
//! test thread waits for two heartbeats with a deadline; if either fails
//! to arrive, we declare deadlock and force-exit the test process so
//! cargo does not hang for the full verify timeout.
use std::sync::{mpsc, Arc, Barrier};
use std::thread;
use std::time::Duration;

use arc_mutex_deadlock::{balance, new_account, total, transfer};

/// Hard deadline for any concurrent scenario. If a heartbeat doesn't
/// arrive in time, we treat it as a deadlock and abort the test process.
const DEADLINE: Duration = Duration::from_secs(5);

/// Force-exit the test process with a non-zero code after printing a
/// message. Used when a deadlock pins worker threads on `Mutex::lock()`
/// and we cannot recover (no way to interrupt a blocked lock acquire from
/// outside in stable Rust without unsafe + platform-specific hacks).
fn abort_on_deadlock(msg: &str) -> ! {
    eprintln!("\n--- deadlock detected: {} ---", msg);
    eprintln!("forcibly exiting the test process so cargo doesn't hang.");
    std::process::exit(101);
}

#[test]
fn test_single_thread_transfer_success() {
    let a = new_account(1, 100);
    let b = new_account(2, 0);
    transfer(&a, &b, 30).unwrap();
    assert_eq!(balance(&a), 70);
    assert_eq!(balance(&b), 30);
}

#[test]
fn test_single_thread_insufficient_funds() {
    let a = new_account(1, 10);
    let b = new_account(2, 0);
    let result = transfer(&a, &b, 50);
    assert!(result.is_err());
    assert_eq!(balance(&a), 10);
    assert_eq!(balance(&b), 0);
}

#[test]
fn test_total_conservation_same_direction() {
    let a = new_account(1, 1_000);
    let b = new_account(2, 0);
    let accounts = vec![a.clone(), b.clone()];

    let n_threads = 8;
    let barrier = Arc::new(Barrier::new(n_threads));
    let (tx, rx) = mpsc::channel::<()>();

    let mut handles = Vec::new();
    for _ in 0..n_threads {
        let a_c = a.clone();
        let b_c = b.clone();
        let b_arrier = barrier.clone();
        let tx_c = tx.clone();
        handles.push(thread::spawn(move || {
            b_arrier.wait();
            transfer(&a_c, &b_c, 1).unwrap();
            tx_c.send(()).ok();
        }));
    }
    drop(tx);

    for i in 0..n_threads {
        if rx.recv_timeout(DEADLINE).is_err() {
            abort_on_deadlock(&format!(
                "same-direction transfers: only {}/{} heartbeats received within {:?}",
                i, n_threads, DEADLINE
            ));
        }
    }
    for h in handles {
        h.join().unwrap();
    }
    assert_eq!(total(&accounts), 1_000);
    assert_eq!(balance(&a), 1_000 - n_threads as u64);
    assert_eq!(balance(&b), n_threads as u64);
}

/// Two threads transferring in opposite directions between the same pair
/// of accounts. With naive `from`-then-`to` lock ordering this deadlocks
/// almost immediately; with consistent ordering by identity it cannot.
#[test]
fn test_cross_transfers_do_not_deadlock() {
    let a = new_account(1, 100_000);
    let b = new_account(2, 100_000);
    let accounts = vec![a.clone(), b.clone()];

    let iterations = 500u64;
    let barrier = Arc::new(Barrier::new(2));
    let (tx, rx) = mpsc::channel::<&'static str>();

    let a1 = a.clone();
    let b1 = b.clone();
    let bar1 = barrier.clone();
    let tx1 = tx.clone();
    let h1 = thread::spawn(move || {
        bar1.wait();
        for _ in 0..iterations {
            transfer(&a1, &b1, 1).unwrap();
        }
        tx1.send("A->B").ok();
    });

    let a2 = a.clone();
    let b2 = b.clone();
    let bar2 = barrier.clone();
    let tx2 = tx.clone();
    let h2 = thread::spawn(move || {
        bar2.wait();
        for _ in 0..iterations {
            transfer(&b2, &a2, 1).unwrap();
        }
        tx2.send("B->A").ok();
    });
    drop(tx);

    let mut got = Vec::new();
    for _ in 0..2 {
        match rx.recv_timeout(DEADLINE) {
            Ok(label) => got.push(label),
            Err(_) => abort_on_deadlock(&format!(
                "cross transfers: only got heartbeats {:?} within {:?} (the other direction is stuck)",
                got, DEADLINE
            )),
        }
    }
    h1.join().unwrap();
    h2.join().unwrap();
    assert_eq!(total(&accounts), 200_000, "money was not conserved");
}

/// Many accounts, many cross-transfer pairs concurrently. Exercises the
/// general deadlock-avoidance guarantee, not just the two-account case.
#[test]
fn test_many_accounts_many_cross_pairs() {
    let accounts: Vec<_> = (0..4).map(|i| new_account(i, 5_000)).collect();

    let iterations = 200u64;
    let pairs: Vec<(usize, usize)> = vec![
        (0, 1), (1, 0),
        (2, 3), (3, 2),
        (0, 2), (2, 0),
        (1, 3), (3, 1),
    ];
    let n = pairs.len();
    let barrier = Arc::new(Barrier::new(n));
    let (tx, rx) = mpsc::channel::<()>();

    let mut handles = Vec::new();
    for (src, dst) in pairs.iter().copied() {
        let a_src = accounts[src].clone();
        let a_dst = accounts[dst].clone();
        let bar = barrier.clone();
        let tx_c = tx.clone();
        handles.push(thread::spawn(move || {
            bar.wait();
            for _ in 0..iterations {
                transfer(&a_src, &a_dst, 1).unwrap();
            }
            tx_c.send(()).ok();
        }));
    }
    drop(tx);

    for i in 0..n {
        if rx.recv_timeout(DEADLINE).is_err() {
            abort_on_deadlock(&format!(
                "many-pairs transfers: only {}/{} heartbeats received within {:?}",
                i, n, DEADLINE
            ));
        }
    }
    for h in handles {
        h.join().unwrap();
    }
    assert_eq!(total(&accounts), 4 * 5_000, "money was not conserved");
}
