import threading

from cache import LRUCache


def test_basic_put_get():
    c = LRUCache(3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert c.get("a") == 1
    assert c.get("b") == 2
    assert c.get("c") == 3
    assert c.get("missing") is None
    assert len(c) == 3


def test_lru_eviction_order():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    # Insert third -> evicts 'a' (LRU).
    c.put("c", 3)
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3
    assert len(c) == 2


def test_get_promotes_to_mru():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    # Access 'a' -> 'a' becomes MRU, 'b' becomes LRU.
    assert c.get("a") == 1
    # Insert 'c' -> must evict 'b', not 'a'.
    c.put("c", 3)
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3
    assert len(c) == 2


def test_keys_ordering():
    c = LRUCache(3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    # Touch 'a' -> moves to MRU.
    c.get("a")
    ks = c.keys()
    assert ks[-1] == "a"
    assert set(ks) == {"a", "b", "c"}
    assert len(ks) == 3


def _invariants_hold(cache, capacity):
    """Return (ok, reason). Checks core invariants on the cache."""
    keys_list = cache.keys()
    if len(cache) > capacity:
        return False, f"len(cache)={len(cache)} exceeds capacity={capacity}"
    if len(keys_list) > capacity:
        return False, f"len(keys())={len(keys_list)} exceeds capacity={capacity}"
    if len(keys_list) != len(set(keys_list)):
        return False, f"duplicate keys in order list: {keys_list}"
    # Every key reported by keys() should be retrievable.
    for k in keys_list:
        if cache.get(k) is None:
            return False, f"key {k!r} present in keys() but get() returned None"
    return True, ""


def test_concurrent_put_respects_capacity():
    """N threads put distinct keys concurrently; len(cache) must stay <= capacity."""
    capacity = 5
    c = LRUCache(capacity)
    # Pre-fill so every put triggers an eviction path.
    for i in range(capacity):
        c.put(f"seed-{i}", i)

    n_threads = 16
    barrier = threading.Barrier(n_threads)

    def worker(i):
        barrier.wait()
        c.put(f"k-{i}", i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(c) <= capacity, (
        f"capacity overflow: len(cache)={len(c)} > capacity={capacity}"
    )
    ok, reason = _invariants_hold(c, capacity)
    assert ok, reason


def test_hot_key_survives_concurrent_eviction_pressure():
    """A thread spams get(hot) while another thread puts cold keys.

    The hot key is touched constantly so it should never be the LRU and
    should never be evicted.
    """
    capacity = 4
    c = LRUCache(capacity)
    c.put("hot", "HOT")
    # Fill the rest with cold seed keys.
    for i in range(capacity - 1):
        c.put(f"cold-seed-{i}", i)

    stop = threading.Event()
    hot_missing = [0]

    def reader():
        while not stop.is_set():
            v = c.get("hot")
            if v != "HOT":
                hot_missing[0] += 1

    def writer():
        for i in range(60):
            c.put(f"cold-{i}", i)

    r = threading.Thread(target=reader)
    w = threading.Thread(target=writer)
    r.start()
    w.start()
    w.join()
    stop.set()
    r.join()

    assert hot_missing[0] == 0, (
        f"hot key was missing {hot_missing[0]} times despite being constantly accessed"
    )
    assert c.get("hot") == "HOT", "hot key was evicted despite constant access"


def test_no_key_lost_under_interleaved_ops():
    """Mix concurrent puts and gets; verify every key in keys() resolves."""
    capacity = 8
    c = LRUCache(capacity)
    for i in range(capacity):
        c.put(f"init-{i}", i)

    n_threads = 12
    barrier = threading.Barrier(n_threads)

    def putter(i):
        barrier.wait()
        for j in range(5):
            c.put(f"p{i}-{j}", (i, j))

    def getter(i):
        barrier.wait()
        for j in range(5):
            c.get(f"init-{j % capacity}")

    threads = []
    for i in range(n_threads // 2):
        threads.append(threading.Thread(target=putter, args=(i,)))
        threads.append(threading.Thread(target=getter, args=(i,)))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok, reason = _invariants_hold(c, capacity)
    assert ok, reason
