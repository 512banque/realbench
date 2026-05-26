//! `process_with_timeout` runs a CPU-intensive computation with a deadline.
//!
//! The fix relative to the buggy workspace: the inner CPU loop now yields
//! to the runtime at every chunk via `tokio::task::yield_now().await`. That
//! makes the future cooperative: between chunks, the runtime can poll the
//! `select!`'s sleep branch, fire timers, and progress other tasks. When
//! the timeout branch wins, the `select!` drops the work future, the
//! cooperative loop's drop short-circuits the remaining chunks, and the
//! whole call returns within roughly the requested deadline.
use std::time::Duration;

#[derive(Debug, PartialEq, Eq)]
pub enum Error {
    Timeout,
}

const TOTAL_CHUNKS: u64 = 8_000;

#[inline(never)]
fn compute_chunk(seed: u64) -> u64 {
    let mut acc: u64 = seed;
    for i in 0..200_000u64 {
        acc = acc.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(i ^ 0x9E37_79B9_7F4A_7C15);
        acc ^= acc >> 17;
    }
    acc
}

/// Cooperative async version of the CPU computation: yields control to the
/// runtime between chunks so that the timeout branch and concurrent tasks
/// can make progress.
async fn do_work_cooperative() -> u64 {
    let mut acc: u64 = 0xDEAD_BEEF;
    for i in 0..TOTAL_CHUNKS {
        acc = compute_chunk(acc.wrapping_add(i));
        // Yield to let the runtime drive timers and other tasks. Without
        // this, the `select!` timeout branch would never get polled.
        tokio::task::yield_now().await;
    }
    acc
}

pub async fn process_with_timeout(timeout: Duration) -> Result<u64, Error> {
    tokio::select! {
        value = do_work_cooperative() => Ok(value),
        _ = tokio::time::sleep(timeout) => Err(Error::Timeout),
    }
}
