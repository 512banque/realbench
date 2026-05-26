The `src/lib.rs` module exposes `transfer(from, to, amount)` which hangs on
concurrent crossed transfers: two threads doing `transfer(A, B)` and
`transfer(B, A)` in parallel deadlock each other. The tests in
`tests/integration.rs` detect the deadlock and kill the process via
`std::process::exit` after 5s.

Fix `src/lib.rs` so no deadlock is possible, without modifying the tests,
`Cargo.toml`, or `Cargo.lock`.
