Implement `RetryOrchestrator` in `orchestrator.py`.

The code calls backend services (`services.py`) that may fail
transiently (raise `TransientError`) or permanently (raise
`PermanentError`). On transient, retry **with your own strategy**:
your call (exponential backoff, jitter, fixed delay, retry budget,
circuit breaker, etc.). On permanent, give up immediately and
propagate the exception.

API:

- `RetryOrchestrator(max_total_retries: int = 10)` — `max_total_retries`
  bounds the number of retries per `call()` (so at most
  `1 + max_total_retries` service calls per invocation).
- `call(service, *args, **kwargs)` — calls `service.call(*args, **kwargs)`,
  applies your retry policy on `TransientError`, returns the
  result. If all attempts failed, raises `RetryExhausted`
  (already defined in `services.py`).

Constraints:

- Be efficient: don't retry forever, don't hang.
- Document your strategy in a class docstring (≥ 50
  meaningful characters).
- Python stdlib only. No `tenacity` or other external
  library.
- Must support concurrent calls (multiple threads calling
  `call()` in parallel).

Do not modify `test_orchestrator.py` or `services.py`.
