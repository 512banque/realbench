The tests in `test_cache.py` are failing: the `LRUCache` class in `cache.py`
suffers from a race condition under concurrency. The `get` operation (which
promotes a key to MRU) and `put` (which may evict the LRU) manipulate two
internal structures (`_values` and `_order`) in multiple non-atomic steps,
which can break the capacity invariant or cause a frequently accessed key to
disappear.

Identify the cause and fix `cache.py` so that all tests pass. Do not modify
the tests.
