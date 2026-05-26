//! In-memory bank with per-account locks and concurrent transfers.
//!
//! The fix relative to the buggy workspace: `transfer` always acquires the
//! two account locks in a globally consistent order, derived from the
//! pointer identity of the `Arc<Mutex<Account>>`. Acquiring locks in a
//! consistent order across all threads breaks the cyclic-wait condition,
//! so two threads transferring in opposite directions can no longer
//! deadlock.
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

#[derive(Debug, PartialEq, Eq)]
pub enum TransferError {
    InsufficientFunds,
}

pub struct Account {
    pub id: u64,
    pub balance: u64,
}

impl Account {
    pub fn new(id: u64, balance: u64) -> Self {
        Account { id, balance }
    }
}

pub type AccountHandle = Arc<Mutex<Account>>;

pub fn new_account(id: u64, balance: u64) -> AccountHandle {
    Arc::new(Mutex::new(Account::new(id, balance)))
}

pub fn transfer(
    from: &AccountHandle,
    to: &AccountHandle,
    amount: u64,
) -> Result<(), TransferError> {
    // Same account: a single acquire is enough and avoids re-entering a
    // non-reentrant `std::sync::Mutex` (which would deadlock with itself).
    if Arc::ptr_eq(from, to) {
        let g = from.lock().expect("mutex poisoned");
        if g.balance < amount {
            return Err(TransferError::InsufficientFunds);
        }
        // Self-transfer is a no-op.
        return Ok(());
    }

    // Globally consistent lock ordering: by pointer identity. Two threads
    // operating on the same pair of accounts will always acquire the locks
    // in the same order, regardless of the direction of transfer, so they
    // cannot form a cycle.
    let from_ptr = Arc::as_ptr(from) as usize;
    let to_ptr = Arc::as_ptr(to) as usize;

    if from_ptr < to_ptr {
        let mut from_g = from.lock().expect("from mutex poisoned");
        thread::sleep(Duration::from_micros(200));
        let mut to_g = to.lock().expect("to mutex poisoned");
        if from_g.balance < amount {
            return Err(TransferError::InsufficientFunds);
        }
        from_g.balance -= amount;
        to_g.balance += amount;
        Ok(())
    } else {
        // Lock `to` first to respect canonical order, but operate on the
        // balances in the original from/to roles.
        let mut to_g = to.lock().expect("to mutex poisoned");
        thread::sleep(Duration::from_micros(200));
        let mut from_g = from.lock().expect("from mutex poisoned");
        if from_g.balance < amount {
            return Err(TransferError::InsufficientFunds);
        }
        from_g.balance -= amount;
        to_g.balance += amount;
        Ok(())
    }
}

pub fn balance(account: &AccountHandle) -> u64 {
    account.lock().expect("mutex poisoned").balance
}

pub fn total(accounts: &[AccountHandle]) -> u64 {
    accounts.iter().map(balance).sum()
}
