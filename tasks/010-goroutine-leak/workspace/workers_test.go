package goroutineleak

import (
	"context"
	"testing"
	"time"

	"go.uber.org/goleak"
)

// TestMain runs goleak.VerifyTestMain to fail the test binary if any
// goroutine is still alive after all tests have finished. This is the only
// way to detect the bug: a leaked goroutine blocked on `<-jobs` does not
// cause any test assertion to fail on its own, since the main goroutine
// returns and would normally exit the process.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(m)
}

func TestRunWorkersBasic(t *testing.T) {
	ctx := context.Background()
	jobs := make(chan Job, 10)
	for i := 0; i < 10; i++ {
		jobs <- Job{ID: i, Value: i}
	}
	close(jobs)

	results, err := RunWorkers(ctx, jobs, 3)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 10 {
		t.Fatalf("expected 10 results, got %d", len(results))
	}
}

// TestRunWorkersCancelStopsGoroutines is the key test: we send a few jobs,
// then cancel the context while workers are likely blocked waiting for more
// jobs (the channel is never closed). The buggy implementation returns
// quickly with ctx.Err(), but its goroutines stay parked on `<-jobs`. goleak
// fires at the end of the test binary.
func TestRunWorkersCancelStopsGoroutines(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())

	// Unbuffered to maximize the chance workers block on the read.
	jobs := make(chan Job)

	// Cancel shortly after start so RunWorkers must abort.
	go func() {
		time.Sleep(50 * time.Millisecond)
		cancel()
	}()

	_, err := RunWorkers(ctx, jobs, 4)
	if err == nil {
		t.Fatalf("expected non-nil error when ctx is cancelled, got nil")
	}

	// Give any properly-cleaned goroutines a chance to exit before goleak
	// inspects the runtime in TestMain. A correct implementation finishes
	// here; the buggy one leaks and goleak will fail.
	time.Sleep(100 * time.Millisecond)
}

func TestRunWorkersCancelWithPartialWork(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())

	jobs := make(chan Job, 100)
	for i := 0; i < 5; i++ {
		jobs <- Job{ID: i, Value: i}
	}

	go func() {
		time.Sleep(20 * time.Millisecond)
		cancel()
	}()

	_, err := RunWorkers(ctx, jobs, 3)
	if err == nil {
		t.Fatalf("expected non-nil error when ctx is cancelled, got nil")
	}

	time.Sleep(100 * time.Millisecond)
}

func TestRunWorkersZeroWorkers(t *testing.T) {
	ctx := context.Background()
	jobs := make(chan Job)
	close(jobs)

	results, err := RunWorkers(ctx, jobs, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 0 {
		t.Fatalf("expected 0 results, got %d", len(results))
	}
}
