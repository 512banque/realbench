package channeldeadlock

import (
	"sync"
)

// WorkFunc is the per-item computation. Tests swap this out (via the
// exported PanicAt hook) to force a panic on a specific item without having
// to monkey-patch internals.
type WorkFunc func(int) int

// PanicAt, if non-negative, makes the default work function panic when it
// receives this exact item value. Tests use this to deterministically
// reproduce the "worker panics before writing its result" scenario.
var PanicAt = -1

// defaultWork doubles the input, panicking on the configured PanicAt value.
func defaultWork(v int) int {
	if PanicAt >= 0 && v == PanicAt {
		panic("forced worker panic")
	}
	return v * 2
}

// Process spawns one worker per item, distributes the work over an
// unbuffered jobs channel, collects exactly len(items) results via an
// unbuffered results channel, and recovers panics so the caller never
// crashes.
//
// BUG: the recover() inside the worker swallows the panic, so the caller
// process survives, but the panicking worker exits *before* writing to the
// results channel. The collector then keeps reading len(items) values and
// blocks forever on the missing one. Because there are still other
// goroutines alive (the producer goroutine is gone but the collector is
// blocked on a non-receiver-less channel only one party reads from), the
// Go runtime's "all goroutines asleep" deadlock detector may or may not
// trigger depending on what else is running. The tests force the issue
// with a per-test timeout.
func Process(items []int) ([]int, error) {
	if len(items) == 0 {
		return nil, nil
	}

	jobs := make(chan int)
	results := make(chan int)

	var wg sync.WaitGroup
	for range items {
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer func() {
				_ = recover() // BUG: swallows panic; no result is written.
			}()
			v := <-jobs
			out := defaultWork(v)
			results <- out
		}()
	}

	go func() {
		for _, v := range items {
			jobs <- v
		}
		close(jobs)
	}()

	collected := make([]int, 0, len(items))
	for i := 0; i < len(items); i++ {
		// BUG: blocks forever if a worker panicked before writing.
		collected = append(collected, <-results)
	}

	wg.Wait()
	return collected, nil
}
