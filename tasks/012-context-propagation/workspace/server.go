package contextprop

import (
	"net/http"
	"sync/atomic"
	"time"
)

// SlowWorkDuration is the simulated work duration. Tests set this to a
// small value (e.g. 200ms) and then cancel the client well before it
// elapses. A correct handler observes the cancellation and stops early.
var SlowWorkDuration = 5 * time.Second

// WorkCompletedCount counts the number of times SlowHandler ran the full
// work to completion. A correct (context-aware) handler should NOT
// increment this counter when the client cancels mid-flight.
var WorkCompletedCount atomic.Int64

// WorkAbortedCount counts cancellation-driven early returns.
var WorkAbortedCount atomic.Int64

// SlowHandler simulates a slow upstream call.
//
// BUG: time.Sleep is not context-aware. The handler keeps sleeping for
// SlowWorkDuration even after the client has cancelled, then increments
// WorkCompletedCount. Tests detect this by cancelling early and asserting
// that WorkCompletedCount stays at 0 while WorkAbortedCount goes up.
func SlowHandler(w http.ResponseWriter, r *http.Request) {
	time.Sleep(SlowWorkDuration) // BUG: ignores r.Context().Done()
	WorkCompletedCount.Add(1)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("done"))
}

// NewServer builds the HTTP server used by tests.
func NewServer() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/slow", SlowHandler)
	return mux
}
