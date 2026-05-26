"""
Mock backend services with deterministic failure profiles.

All services expose a `call()` method that may raise:
- `TransientError`: retryable error (think 5xx, timeout, etc.)
- `PermanentError`: non-retryable error (think 4xx, schema mismatch)

Determinism: each service has its own `random.Random` instance, seeded
at construction so test runs are reproducible across machines. Tests
that need a specific failure profile can pass `seed=...` to pin the
sequence.

Each service exposes:
- `call(*args, **kwargs)` — does the work, increments `call_count`
- `call_count` (int) — total number of invocations
- `reset()` — resets `call_count` (does NOT reset the RNG; the failure
  sequence continues from where it left off)

The point of these services is to give the orchestrator three quite
different shapes of flakiness:

- `FlakyServiceFast`  : 30% transient, fast → many cheap retries OK
- `FlakyServiceSlow`  : 5%  transient, slow → fewer retries preferable
- `BurstyService`     : alternates "calm" and "bursty" windows where
                        almost every call fails → favors a circuit
                        breaker but does not require one.
"""

from __future__ import annotations

import random
import threading
import time


class TransientError(Exception):
    """Retryable error. The orchestrator should retry (per its policy)."""


class PermanentError(Exception):
    """Non-retryable error. The orchestrator must NOT retry."""


class RetryExhausted(Exception):
    """Raised by the orchestrator when its retry budget is spent."""


class _ServiceBase:
    """Common bookkeeping: thread-safe call_count + deterministic RNG."""

    def __init__(self, seed: int = 0, latency_sec: float = 0.0):
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._latency = latency_sec
        self.call_count = 0

    def _tick(self):
        with self._lock:
            self.call_count += 1
        if self._latency > 0:
            time.sleep(self._latency)

    def reset(self):
        with self._lock:
            self.call_count = 0


class FlakyServiceFast(_ServiceBase):
    """~30% transient error rate, fast. Friendly to many cheap retries."""

    def __init__(self, seed: int = 0, fail_rate: float = 0.30):
        super().__init__(seed=seed, latency_sec=0.0)
        self._fail_rate = fail_rate

    def call(self, *args, **kwargs):
        self._tick()
        # Sample under lock so concurrent callers see a deterministic
        # sequence (per the RNG, not per arrival order — but the RNG
        # is consumed in a serializable way).
        with self._lock:
            roll = self._rng.random()
        if roll < self._fail_rate:
            raise TransientError(f"fast: transient on call {self.call_count}")
        return ("fast-ok", args, kwargs)


class FlakyServiceSlow(_ServiceBase):
    """~5% transient error rate, ~5ms latency. Retries are costly."""

    def __init__(self, seed: int = 0, fail_rate: float = 0.05,
                 latency_sec: float = 0.005):
        super().__init__(seed=seed, latency_sec=latency_sec)
        self._fail_rate = fail_rate

    def call(self, *args, **kwargs):
        self._tick()
        with self._lock:
            roll = self._rng.random()
        if roll < self._fail_rate:
            raise TransientError(f"slow: transient on call {self.call_count}")
        return ("slow-ok", args, kwargs)


class BurstyService(_ServiceBase):
    """
    Alternates calm and bursty windows.

    - Calm window  (length `calm_n`)  : ~5% transient error rate.
    - Bursty window (length `burst_n`): ~80% transient error rate.

    Use case: a circuit breaker would short-circuit during the burst
    window and probe before re-opening. Other strategies still work
    (exponential backoff will eventually wait out the burst), so this
    service is NOT a hard requirement on circuit breakers — it just
    rewards them.
    """

    def __init__(self, seed: int = 0,
                 calm_n: int = 20, burst_n: int = 20,
                 calm_rate: float = 0.05, burst_rate: float = 0.80):
        super().__init__(seed=seed, latency_sec=0.0)
        self._calm_n = calm_n
        self._burst_n = burst_n
        self._calm_rate = calm_rate
        self._burst_rate = burst_rate

    def _is_burst_phase(self, n: int) -> bool:
        period = self._calm_n + self._burst_n
        return (n % period) >= self._calm_n

    def call(self, *args, **kwargs):
        self._tick()
        with self._lock:
            n = self.call_count
            roll = self._rng.random()
        rate = self._burst_rate if self._is_burst_phase(n) else self._calm_rate
        if roll < rate:
            raise TransientError(f"bursty: transient on call {n} "
                                 f"(phase={'burst' if self._is_burst_phase(n) else 'calm'})")
        return ("bursty-ok", args, kwargs)


# --- Test helpers (not the orchestrator's concern) -------------------------

class _AlwaysFailTransient(_ServiceBase):
    """Always raises TransientError. Used by tests for 'give up' behavior."""

    def call(self, *args, **kwargs):
        self._tick()
        raise TransientError(f"always-fail on call {self.call_count}")


class _AlwaysFailPermanent(_ServiceBase):
    """Always raises PermanentError. Used by tests for 'no retry' check."""

    def call(self, *args, **kwargs):
        self._tick()
        raise PermanentError(f"hard-fail on call {self.call_count}")


class _AlwaysOk(_ServiceBase):
    """Never fails. Used by tests for the trivial happy path."""

    def call(self, *args, **kwargs):
        self._tick()
        return ("ok", args, kwargs)


class _FailNThenOk(_ServiceBase):
    """Fails transiently the first N times, then succeeds forever."""

    def __init__(self, n: int):
        super().__init__(seed=0, latency_sec=0.0)
        self._n = n

    def call(self, *args, **kwargs):
        self._tick()
        if self.call_count <= self._n:
            raise TransientError(f"will-fail-{self._n}: call {self.call_count}")
        return ("after-fail", args, kwargs)


class _FixedRateService(_ServiceBase):
    """Fixed transient fail rate, deterministic via seed. Used by invariant tests."""

    def __init__(self, fail_rate: float, seed: int = 0):
        super().__init__(seed=seed, latency_sec=0.0)
        self._fail_rate = fail_rate

    def call(self, *args, **kwargs):
        self._tick()
        with self._lock:
            roll = self._rng.random()
        if roll < self._fail_rate:
            raise TransientError("rate")
        return "ok"
