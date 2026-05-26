`src/EventBus.ts` exposes `subscribe(event, handler)` which returns an `unsubscribe()`, but
the latter does not properly clean up handlers: after unsubscribing N handlers,
`listenerCount()` still reports N. Find and fix the bug so handlers are actually
removed. Do not modify the tests.
