import threading
import time

from debounce import debounce


DELAY = 0.05  # 50ms — small enough for fast tests, large enough to be stable


class Recorder:
    """Thread-safe call recorder with a signalling Event."""

    def __init__(self, expected=1):
        self._lock = threading.Lock()
        self.calls = []
        self._expected = expected
        self.event = threading.Event()

    def __call__(self, *args, **kwargs):
        with self._lock:
            self.calls.append((args, kwargs))
            if len(self.calls) >= self._expected:
                self.event.set()

    def count(self):
        with self._lock:
            return len(self.calls)

    def last_args(self):
        with self._lock:
            return self.calls[-1] if self.calls else None


def test_single_call_fires_once():
    rec = Recorder(expected=1)
    debounced = debounce(rec, DELAY)

    debounced("hello")

    # Wait for the call to fire (with margin).
    rec.event.wait(timeout=DELAY * 5)
    # Give a tiny extra window to catch any spurious extra calls.
    time.sleep(DELAY)

    assert rec.count() == 1, f"expected 1 call, got {rec.count()}"
    assert rec.last_args() == (("hello",), {})


def test_burst_collapses_to_one_call():
    """The key test: 10 rapid calls within < delay must collapse to a single
    invocation. This is the test that fails on the buggy implementation."""
    rec = Recorder(expected=1)
    debounced = debounce(rec, DELAY)

    for i in range(10):
        debounced(i)
        time.sleep(0.001)  # 1ms between calls, total burst < 50ms

    rec.event.wait(timeout=DELAY * 5)
    # Wait well past the delay to catch any stray late timers.
    time.sleep(DELAY * 3)

    assert rec.count() == 1, (
        f"expected exactly 1 call after burst, got {rec.count()} "
        f"(debounce is leaking timers)"
    )


def test_last_args_win():
    rec = Recorder(expected=1)
    debounced = debounce(rec, DELAY)

    for i in range(5):
        debounced(i)
        time.sleep(0.001)

    rec.event.wait(timeout=DELAY * 5)
    time.sleep(DELAY * 2)

    assert rec.count() == 1, f"expected 1 call, got {rec.count()}"
    assert rec.last_args() == ((4,), {}), (
        f"expected last args to be (4,), got {rec.last_args()}"
    )


def test_spaced_calls_trigger_separately():
    rec = Recorder(expected=3)
    debounced = debounce(rec, DELAY)

    debounced("a")
    time.sleep(DELAY * 3)
    debounced("b")
    time.sleep(DELAY * 3)
    debounced("c")

    rec.event.wait(timeout=DELAY * 5)
    time.sleep(DELAY * 2)

    assert rec.count() == 3, f"expected 3 calls, got {rec.count()}"


def test_cancel_before_fire():
    rec = Recorder(expected=1)
    debounced = debounce(rec, DELAY)

    debounced("hello")
    # Cancel well before the delay expires.
    time.sleep(DELAY / 5)
    debounced.cancel()

    # Wait past when it would have fired.
    time.sleep(DELAY * 3)

    assert rec.count() == 0, (
        f"expected 0 calls after cancel, got {rec.count()}"
    )


def test_cancel_after_fire_is_noop():
    rec = Recorder(expected=1)
    debounced = debounce(rec, DELAY)

    debounced("hello")
    rec.event.wait(timeout=DELAY * 5)
    time.sleep(DELAY)

    # Should not raise.
    debounced.cancel()

    assert rec.count() == 1, f"expected 1 call, got {rec.count()}"
