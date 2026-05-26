//! `process_with_timeout` runs a CPU-intensive computation with a deadline.
//!
//! It is expected to (a) return the computed value when the work finishes
//! before the deadline, (b) return `Err(Error::Timeout)` quickly when the
//! deadline elapses first, and (c) cooperate with the tokio runtime so that
//! multiple concurrent invocations on a multi-thread runtime do not starve
//! each other.
use std::time::Duration;

#[derive(Debug, PartialEq, Eq)]
pub enum Error {
    Timeout,
}

/// Total number of "chunks" of synthetic CPU work. Each chunk is calibrated
/// to take a few hundred microseconds in release mode on a modern machine,
/// so the whole computation runs in the ~2-4 second range — well above the
/// short timeouts used by the tests.
const TOTAL_CHUNKS: u64 = 8_000;

/// One chunk of synthetic CPU work. Pure compute, no I/O, no awaits.
#[inline(never)]
fn compute_chunk(seed: u64) -> u64 {
    // Some integer mixing that the optimizer cannot trivially fold away,
    // tuned to take roughly the same time on each call.
    let mut acc: u64 = seed;
    for i in 0..200_000u64 {
        acc = acc.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(i ^ 0x9E37_79B9_7F4A_7C15);
        acc ^= acc >> 17;
    }
    acc
}

/// Synthetic CPU-bound async function. It iterates `TOTAL_CHUNKS` chunks of
/// CPU work in a single tight loop. Despite being `async`, it never yields
/// to the runtime.
async fn do_work() -> u64 {
    let mut acc: u64 = 0xDEAD_BEEF;
    for i in 0..TOTAL_CHUNKS {
        acc = compute_chunk(acc.wrapping_add(i));
    }
    acc
}

/// Run `do_work()` with a deadline of `timeout`. Returns `Ok(value)` if the
/// work finishes first, `Err(Error::Timeout)` if the deadline elapses first.
pub async fn process_with_timeout(timeout: Duration) -> Result<u64, Error> {
    tokio::select! {
        value = do_work() => Ok(value),
        _ = tokio::time::sleep(timeout) => Err(Error::Timeout),
    }
}
