import random
import threading
import time

from services import TransientError, PermanentError, RetryExhausted


class RetryOrchestrator:
    """Retry orchestrator using exponential backoff with full jitter.

    Strategy: on a TransientError, sleep for `base * 2**attempt * U(0.5, 1.5)`
    seconds (capped at `cap`), then retry. Up to `max_total_retries` retries
    per `call()`. PermanentError is propagated immediately, never retried.
    `RetryExhausted` is raised once the budget is spent.

    Thread-safety: the orchestrator is stateless across `call()` invocations
    (each `call()` keeps its retry counter in a local variable), so
    concurrent `call()`s from multiple threads share nothing mutable.
    """

    _BASE_DELAY_SEC = 0.001
    _CAP_DELAY_SEC = 0.050

    def __init__(self, max_total_retries: int = 10):
        if max_total_retries < 0:
            raise ValueError("max_total_retries must be >= 0")
        self._max_total_retries = max_total_retries
        # Per-thread RNG so concurrent calls don't contend on a single
        # random.Random instance.
        self._tls = threading.local()

    def _rng(self) -> random.Random:
        rng = getattr(self._tls, "rng", None)
        if rng is None:
            rng = random.Random()
            self._tls.rng = rng
        return rng

    def call(self, service, *args, **kwargs):
        attempt = 0
        last_exc: BaseException | None = None
        while attempt <= self._max_total_retries:
            try:
                return service.call(*args, **kwargs)
            except PermanentError:
                raise
            except TransientError as exc:
                last_exc = exc
                if attempt == self._max_total_retries:
                    break
                delay = self._BASE_DELAY_SEC * (2 ** attempt)
                if delay > self._CAP_DELAY_SEC:
                    delay = self._CAP_DELAY_SEC
                delay *= self._rng().uniform(0.5, 1.5)
                time.sleep(delay)
                attempt += 1
        raise RetryExhausted(
            f"gave up after {self._max_total_retries + 1} attempts; "
            f"last error: {last_exc!r}"
        )
