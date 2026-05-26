package channeldeadlock

import (
	"math/rand"
	"testing"
	"time"
)

// runWithTimeout enforces a deterministic ceiling on each call. If Process
// deadlocks, the test fails (rather than the whole binary hanging).
func runWithTimeout(t *testing.T, items []int, timeout time.Duration) ([]int, error) {
	t.Helper()
	type out struct {
		res []int
		err error
	}
	ch := make(chan out, 1)
	go func() {
		r, e := Process(items)
		ch <- out{r, e}
	}()
	select {
	case o := <-ch:
		return o.res, o.err
	case <-time.After(timeout):
		t.Fatalf("Process deadlocked after %s (items=%v, PanicAt=%d)", timeout, items, PanicAt)
		return nil, nil
	}
}

func TestProcessHappyPath(t *testing.T) {
	prev := PanicAt
	PanicAt = -1
	defer func() { PanicAt = prev }()

	res, err := runWithTimeout(t, []int{1, 2, 3, 4, 5}, 2*time.Second)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != 5 {
		t.Fatalf("expected 5 results, got %d", len(res))
	}
}

func TestProcessSinglePanic(t *testing.T) {
	prev := PanicAt
	PanicAt = 3
	defer func() { PanicAt = prev }()

	// The buggy implementation hangs here: worker for value 3 panics
	// before writing to results, the collector keeps waiting for the
	// 5th result. runWithTimeout fires after 2s and fails the test.
	res, err := runWithTimeout(t, []int{1, 2, 3, 4, 5}, 2*time.Second)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// A correct implementation produces a result for every input. The
	// panicked worker may produce a sentinel value; we only check the
	// total count to leave room for reasonable design choices.
	if len(res) != 5 {
		t.Fatalf("expected 5 results, got %d", len(res))
	}
}

func TestProcessStressRandomPanics(t *testing.T) {
	prev := PanicAt
	defer func() { PanicAt = prev }()

	rng := rand.New(rand.NewSource(1))
	for i := 0; i < 50; i++ {
		size := 5 + rng.Intn(10) // 5..14 items
		items := make([]int, size)
		for j := range items {
			items[j] = j
		}
		PanicAt = rng.Intn(size) // panic on a deterministic but varied index

		res, err := runWithTimeout(t, items, 2*time.Second)
		if err != nil {
			t.Fatalf("iter %d: unexpected error: %v", i, err)
		}
		if len(res) != size {
			t.Fatalf("iter %d: expected %d results, got %d", i, size, len(res))
		}
	}
}

func TestProcessEmptyInput(t *testing.T) {
	prev := PanicAt
	PanicAt = -1
	defer func() { PanicAt = prev }()

	res, err := runWithTimeout(t, nil, 2*time.Second)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != 0 {
		t.Fatalf("expected 0 results, got %d", len(res))
	}
}
