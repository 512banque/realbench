package channeldeadlock

import (
	"sync"
)

type WorkFunc func(int) int

var PanicAt = -1

func defaultWork(v int) int {
	if PanicAt >= 0 && v == PanicAt {
		panic("forced worker panic")
	}
	return v * 2
}

// Process spawns one worker per item and collects exactly len(items)
// results. Each worker is guaranteed to send exactly one value on the
// results channel — including when it panics — so the collector never
// blocks. The jobs and results channels stay unbuffered; the contract
// is enforced by sending the sentinel inside the deferred recover().
//
// A second guarantee: we close the results channel after all workers
// have finished, which makes a future "range over results" pattern safe
// too if the function is extended.
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
			var out int
			func() {
				defer func() {
					if r := recover(); r != nil {
						// Sentinel value on panic so the collector sees
						// exactly one result per worker.
						out = -1
					}
				}()
				v := <-jobs
				out = defaultWork(v)
			}()
			results <- out
		}()
	}

	go func() {
		for _, v := range items {
			jobs <- v
		}
		close(jobs)
	}()

	go func() {
		wg.Wait()
		close(results)
	}()

	collected := make([]int, 0, len(items))
	for r := range results {
		collected = append(collected, r)
	}
	return collected, nil
}
