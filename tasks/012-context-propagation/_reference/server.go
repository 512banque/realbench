package contextprop

import (
	"net/http"
	"sync/atomic"
	"time"
)

var SlowWorkDuration = 5 * time.Second

var WorkCompletedCount atomic.Int64
var WorkAbortedCount atomic.Int64

// SlowHandler simulates a slow upstream call but respects the request's
// context. As soon as r.Context() is cancelled (timeout, client hangup,
// shutdown), the handler bails out without bumping WorkCompletedCount.
func SlowHandler(w http.ResponseWriter, r *http.Request) {
	select {
	case <-time.After(SlowWorkDuration):
		WorkCompletedCount.Add(1)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("done"))
	case <-r.Context().Done():
		WorkAbortedCount.Add(1)
		// The connection is likely already closed; write best-effort.
		// We deliberately do NOT call w.WriteHeader after the client is
		// gone — Go logs a noisy warning, and net/http will drop it
		// anyway. The test asserts counters, not response bodies, on the
		// cancelled path.
		return
	}
}

func NewServer() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/slow", SlowHandler)
	return mux
}
