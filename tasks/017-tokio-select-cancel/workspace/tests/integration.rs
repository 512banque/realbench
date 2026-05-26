//! Integration tests for `process_with_timeout`.
//!
//! We deliberately spawn the call onto the runtime (instead of awaiting it
//! inline) so that an outer `tokio::time::timeout` can run on a *different*
//! worker thread and observe the call's wall time even when the inner work
//! refuses to yield. Without that, a non-cooperative CPU loop inside the
//! call would block the very worker that owns the outer timeout, masking
//! the bug.
use std::time::{Duration, Instant};

use futures::future::join_all;
use tokio_select_cancel::{process_with_timeout, Error};

/// The whole work, given enough budget, must complete and return a value.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn test_completes_when_budget_is_large_enough() {
    // A 30-second budget is far more than the synthetic work needs.
    let result = process_with_timeout(Duration::from_secs(30)).await;
    assert!(result.is_ok(), "expected Ok(_), got {:?}", result);
}

/// A short timeout must be respected: the call must return within a wall
/// time close to the requested deadline, regardless of the inner work.
///
/// We assert from outside via `tokio::time::timeout` on a `JoinHandle`, so
/// that a non-cooperative inner loop cannot also block the assertion site.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn test_respects_short_timeout() {
    let handle = tokio::spawn(async {
        process_with_timeout(Duration::from_millis(100)).await
    });

    let start = Instant::now();
    let outer = tokio::time::timeout(Duration::from_millis(800), handle).await;
    let elapsed = start.elapsed();

    let join_res = outer.unwrap_or_else(|_| {
        panic!(
            "process_with_timeout did not return within 800ms (elapsed {:?}); \
             the timeout branch of select! is being starved by non-cooperative work",
            elapsed
        );
    });
    let inner = join_res.expect("spawned task panicked");
    assert_eq!(inner, Err(Error::Timeout), "expected Err(Timeout) when deadline elapses first");
    assert!(
        elapsed < Duration::from_millis(500),
        "process_with_timeout returned but only after {:?}; deadline was 100ms",
        elapsed
    );
}

/// Many concurrent calls must all finish quickly. In a cooperative
/// implementation the work runs on blocking-aware threads (or yields), so
/// the runtime workers stay available and every short-deadline call returns
/// well before the global budget below.
///
/// In a non-cooperative implementation, each call pins one worker thread
/// until its CPU loop completes; with 4 workers and 10 calls, this serializes
/// into batches and blows past the budget.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn test_concurrent_calls_do_not_starve_each_other() {
    const N: usize = 10;
    let handles: Vec<_> = (0..N)
        .map(|_| tokio::spawn(async { process_with_timeout(Duration::from_millis(100)).await }))
        .collect();

    let start = Instant::now();
    let outer = tokio::time::timeout(Duration::from_millis(1500), join_all(handles)).await;
    let elapsed = start.elapsed();

    let results = outer.unwrap_or_else(|_| {
        panic!(
            "{} concurrent process_with_timeout calls did not all finish within 1500ms \
             (elapsed {:?}); workers are being starved by non-cooperative CPU work",
            N, elapsed
        );
    });

    for (i, r) in results.into_iter().enumerate() {
        let inner = r.unwrap_or_else(|_| panic!("task {} panicked", i));
        assert_eq!(inner, Err(Error::Timeout), "task {}: expected Err(Timeout)", i);
    }
    assert!(
        elapsed < Duration::from_millis(1500),
        "concurrent calls took {:?} for {} tasks with a 100ms deadline each",
        elapsed,
        N
    );
}
