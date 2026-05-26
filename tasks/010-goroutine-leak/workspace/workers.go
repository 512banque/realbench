package goroutineleak

import (
	"context"
	"sync"
)

// Job is a unit of work passed into the worker pool.
type Job struct {
	ID    int
	Value int
}

// Result is the output produced by a worker for a Job.
type Result struct {
	JobID  int
	Output int
}

// process performs the per-job computation. Kept tiny: the bug we care about
// is in the worker loop, not in here.
func process(j Job) Result {
	return Result{JobID: j.ID, Output: j.Value * 2}
}

// RunWorkers launches n goroutines that consume jobs and collect results.
//
// BUG: when ctx is cancelled, the worker loop is only checked between channel
// reads. A worker already blocked in `<-jobs` will stay blocked forever
// because the caller never closes `jobs` on cancellation. RunWorkers returns
// promptly (the goroutine count goes up, then it returns), but the worker
// goroutines leak. Tests detect this via goleak.
func RunWorkers(ctx context.Context, jobs <-chan Job, n int) ([]Result, error) {
	if n <= 0 {
		return nil, nil
	}

	results := make(chan Result, n)
	var wg sync.WaitGroup

	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				// BUG: no select on ctx.Done(); worker blocks here forever
				// if `jobs` is never closed.
				j, ok := <-jobs
				if !ok {
					return
				}
				results <- process(j)
			}
		}()
	}

	collected := make([]Result, 0)
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(results)
		close(done)
	}()

	for {
		select {
		case r, ok := <-results:
			if !ok {
				return collected, nil
			}
			collected = append(collected, r)
		case <-ctx.Done():
			// BUG: we return without unblocking the workers. They are still
			// reading from `jobs`, which we don't own and won't close.
			return collected, ctx.Err()
		}
	}
}
