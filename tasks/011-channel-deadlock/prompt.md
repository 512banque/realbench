The `Process(items []int)` function in `pipeline.go` fans work out to several
workers over an unbuffered channel, recovers panics, and collects the results.
Under stress (a worker randomly panics before writing its result) the function
deadlocks — the collector waits for a result that will never come.

Fix `pipeline.go` so every path (success, panic) emits exactly one signal to
the collector, without blocking. Do not modify the tests.
