The `process_with_timeout` function in `src/lib.rs` is supposed to honor a
timeout and free up the tokio runtime during the work. When several calls
run in parallel, the tests in `tests/integration.rs` detect that the runtime
is blocked: concurrent tasks starve each other and blow well past their
deadline.

Fix `src/lib.rs` so the timeout is honored and concurrent calls do not block
each other. Do not modify the tests, `Cargo.toml`, or `Cargo.lock`.
