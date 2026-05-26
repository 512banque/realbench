//! In-memory bank with per-account locks and concurrent transfers.
//!
//! The contract:
//! - `Account` owns its balance, protected by its own `Mutex`.
//! - `transfer(from, to, amount)` debits `from` and credits `to` atomically.
//! - Multiple transfers happening in parallel — including in opposite
//!   directions between the same two accounts — must all eventually
//!   succeed, with the total money preserved.
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

/// Transfer `amount` from `from` to `to`. The locks are acquired in the
/// order of the arguments — first `from`, then `to`. A small sleep between
/// the two acquires mirrors the latency of a real "debit then credit"
/// operation (network call, log write, etc.) and gives a contending thread
/// a chance to grab the second lock in between.
pub fn transfer(
    from: &AccountHandle,
    to: &AccountHandle,
    amount: u64,
) -> Result<(), TransferError> {
    let mut from_guard = from.lock().expect("from mutex poisoned");
    thread::sleep(Duration::from_micros(200));
    let mut to_guard = to.lock().expect("to mutex poisoned");

    if from_guard.balance < amount {
        return Err(TransferError::InsufficientFunds);
    }
    from_guard.balance -= amount;
    to_guard.balance += amount;
    Ok(())
}

pub fn balance(account: &AccountHandle) -> u64 {
    account.lock().expect("mutex poisoned").balance
}

pub fn total(accounts: &[AccountHandle]) -> u64 {
    accounts.iter().map(balance).sum()
}
