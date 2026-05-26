Implement the `Cache` class in `cache.py` so that all tests in
`test_cache.py` pass.

The cache has a maximum size fixed at construction (`max_size`). When
the cache is full and a new `put` arrives with an unknown key,
**you choose the eviction strategy**: LRU, LFU, FIFO,
random, 2-random, ARC, etc. All are valid. Pick one that seems
reasonable and document it in a docstring (on the class or
on `put`).

Minimum API:

- `Cache(max_size: int)` — builds a cache bounded to `max_size` entries.
- `put(key, value)` — inserts or updates the key. When the cache is
  full and an unknown key is inserted, an existing entry is evicted.
- `get(key)` — returns the value, or `None` if the key is absent.
  (Raising a `KeyError` is also accepted if you prefer.)
- `size() -> int` — number of entries present. Must always remain
  `<= max_size`.

Do not modify the tests.
