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

func process(j Job) Result {
	return Result{JobID: j.ID, Output: j.Value * 2}
}

// RunWorkers launches n goroutines that consume jobs and collect results.
// On ctx.Done() every worker exits promptly: each one selects on
// (jobs, ctx.Done()) instead of blocking on the channel read alone. The
// collector also selects on ctx.Done() and on the workers' completion.
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
				select {
				case <-ctx.Done():
					return
				case j, ok := <-jobs:
					if !ok {
						return
					}
					select {
					case results <- process(j):
					case <-ctx.Done():
						return
					}
				}
			}
		}()
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	collected := make([]Result, 0)
	for {
		select {
		case r, ok := <-results:
			if !ok {
				if err := ctx.Err(); err != nil {
					return collected, err
				}
				return collected, nil
			}
			collected = append(collected, r)
		case <-ctx.Done():
			// Drain remaining results so the close-er goroutine can finish,
			// then return. Workers themselves observe ctx.Done() and exit.
			for r := range results {
				collected = append(collected, r)
			}
			return collected, ctx.Err()
		}
	}
}
