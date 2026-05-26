The `SlowHandler` handler in `server.go` simulates long-running work
(~5 seconds) without honoring the request `Context`. When the client
cancels (timeout, ctrl-c), the server keeps grinding to completion and
burns resources.

Change `SlowHandler` so it bails out as soon as `r.Context()` is cancelled
(stay deterministic: the `WorkCompletedCount` counter must reflect that
choice). Do not modify the tests.
