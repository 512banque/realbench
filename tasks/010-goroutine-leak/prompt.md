The `RunWorkers(ctx, jobs, n)` function in `workers.go` spawns `n` goroutines
that consume the `jobs` channel. When `ctx` is cancelled, `RunWorkers` returns
but leaves the goroutines blocked reading from `jobs` — the leak is caught by
the tests via `go.uber.org/goleak`.

Fix `workers.go` so the goroutines shut down cleanly on context cancellation.
Do not modify the tests.
