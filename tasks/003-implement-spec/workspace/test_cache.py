import threading

import pytest

from cache import TTLCache


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def test_set_then_get():
    c = TTLCache(ttl=10)
    c.set("a", 1)
    assert c.get("a") == 1


def test_get_missing_returns_none():
    c = TTLCache(ttl=10)
    assert c.get("nope") is None


def test_size_grows_with_set():
    c = TTLCache(ttl=10)
    assert c.size() == 0
    c.set("a", 1)
    c.set("b", 2)
    assert c.size() == 2


def test_delete_removes_entry():
    c = TTLCache(ttl=10)
    c.set("a", 1)
    c.delete("a")
    assert c.get("a") is None
    assert c.size() == 0


def test_delete_missing_is_noop():
    c = TTLCache(ttl=10)
    c.delete("nope")  # must not raise


def test_entries_expire_after_ttl():
    clock = FakeClock()
    c = TTLCache(ttl=5, clock=clock)
    c.set("a", 1)
    clock.advance(4)
    assert c.get("a") == 1
    clock.advance(2)  # now t=6, beyond ttl=5
    assert c.get("a") is None


def test_size_excludes_expired_entries():
    clock = FakeClock()
    c = TTLCache(ttl=5, clock=clock)
    c.set("a", 1)
    c.set("b", 2)
    clock.advance(10)
    assert c.size() == 0


def test_overwrite_resets_ttl():
    clock = FakeClock()
    c = TTLCache(ttl=5, clock=clock)
    c.set("a", 1)
    clock.advance(4)
    c.set("a", 2)
    clock.advance(4)  # t=8, but last write was at t=4, so still valid
    assert c.get("a") == 2


def test_thread_safety_concurrent_writes():
    c = TTLCache(ttl=60)
    errors = []

    def worker(prefix):
        try:
            for i in range(100):
                c.set(f"{prefix}-{i}", i)
                assert c.get(f"{prefix}-{i}") == i
        except Exception as e:  # pragma: no cover - reported below
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(p,)) for p in "abcdefgh"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert c.size() == 800
