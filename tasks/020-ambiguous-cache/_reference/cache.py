from collections import OrderedDict


class Cache:
    """Bounded cache with LRU eviction.

    The least-recently-used entry is evicted when the cache is full and a
    new key is inserted. Reads count as a use: a `get` on key `k` moves
    `k` to the most-recent end of the order. Updates on an existing key
    also refresh recency. This gives the standard LRU contract.
    """

    def __init__(self, max_size: int):
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._max_size = max_size
        self._data: "OrderedDict[object, object]" = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key, value):
        if key in self._data:
            self._data[key] = value
            self._data.move_to_end(key)
            return
        self._data[key] = value
        if len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def size(self) -> int:
        return len(self._data)
