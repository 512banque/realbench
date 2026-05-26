package contextprop

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// resetCounters is called at the start of each test to make them independent.
func resetCounters(t *testing.T, dur time.Duration) {
	t.Helper()
	WorkCompletedCount.Store(0)
	WorkAbortedCount.Store(0)
	SlowWorkDuration = dur
}

func TestSlowHandlerHappyPath(t *testing.T) {
	resetCounters(t, 50*time.Millisecond)

	srv := httptest.NewServer(NewServer())
	defer srv.Close()

	req, err := http.NewRequest(http.MethodGet, srv.URL+"/slow", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("client do: %v", err)
	}
	resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}
	if got := WorkCompletedCount.Load(); got != 1 {
		t.Fatalf("expected 1 completion, got %d", got)
	}
}

// TestSlowHandlerClientCancelStopsWork is the discriminating test. The
// client cancels after 50ms while SlowWorkDuration is 2s. A correct
// handler observes r.Context().Done() and returns early, leaving
// WorkCompletedCount at 0. The buggy handler keeps sleeping; we wait
// long enough for it to finish (which it would, after 2s) and assert
// the counter is still 0.
func TestSlowHandlerClientCancelStopsWork(t *testing.T) {
	resetCounters(t, 2*time.Second)

	srv := httptest.NewServer(NewServer())
	defer srv.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, srv.URL+"/slow", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}

	start := time.Now()
	_, err = http.DefaultClient.Do(req)
	clientElapsed := time.Since(start)

	if err == nil {
		t.Fatalf("expected client error (deadline exceeded), got nil")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		// Some Go versions wrap differently; tolerate any context-flavoured
		// error but require it to be context-related.
		if !isContextErr(err) {
			t.Fatalf("expected context error, got %v", err)
		}
	}
	if clientElapsed > 500*time.Millisecond {
		t.Fatalf("client took too long to bail out: %s", clientElapsed)
	}

	// Wait beyond the buggy sleep so a buggy handler has time to finish
	// its work and bump the counter, exposing the leak.
	time.Sleep(2500 * time.Millisecond)

	if got := WorkCompletedCount.Load(); got != 0 {
		t.Fatalf("handler kept running after client cancel: WorkCompletedCount=%d", got)
	}
	if got := WorkAbortedCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 aborted work, got %d", got)
	}
}

func isContextErr(err error) bool {
	for e := err; e != nil; {
		if e == context.Canceled || e == context.DeadlineExceeded {
			return true
		}
		u, ok := e.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		e = u.Unwrap()
	}
	return false
}
