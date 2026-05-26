import time


class LRUCache:
    """LRU cache with fixed capacity.

    Stores key -> value in `_values` and the LRU order in `_order`
    (front = least recently used, back = most recently used).

    `get(key)` returns the value (or None) AND promotes the key to MRU.
    `put(key, value)` inserts/updates; if capacity is exceeded, the LRU
    entry is evicted.

    The two structures (`_values`, `_order`) must stay consistent: every
    key in `_values` must appear exactly once in `_order` and vice versa,
    and `len(self) <= capacity` must always hold.
    """

    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._values = {}
        self._order = []  # LRU first, MRU last

    def __len__(self):
        return len(self._values)

    def keys(self):
        # LRU first -> MRU last
        return list(self._order)

    def get(self, key):
        if key not in self._values:
            return None
        value = self._values[key]
        # Promote the key to MRU: remove from current position, append at end.
        # This is a multi-step operation that simulates the "read index, then
        # mutate" pattern you see when a separate order structure is kept in
        # sync with the value store.
        try:
            idx = self._order.index(key)
        except ValueError:
            # Key disappeared from the order list between the dict check and
            # now; nothing to promote.
            return value
        time.sleep(0.001)  # window where another thread may mutate _order
        try:
            # Re-find the key in case its position moved; if it's gone, abort
            # the promotion silently (the caller already has the value).
            self._order.pop(idx)
        except IndexError:
            return value
        time.sleep(0.001)
        self._order.append(key)
        return value

    def put(self, key, value):
        if key in self._values:
            # Update in place and promote.
            self._values[key] = value
            try:
                idx = self._order.index(key)
            except ValueError:
                # Order list lost the key; just re-append.
                self._order.append(key)
                return
            time.sleep(0.001)
            try:
                self._order.pop(idx)
            except IndexError:
                pass
            self._order.append(key)
            return

        # New key. Check capacity first.
        if len(self._values) >= self._capacity:
            # Evict LRU (front of _order).
            time.sleep(0.001)  # window where another thread may also evict / insert
            if self._order:
                victim = self._order.pop(0)
                # Drop the victim from _values too.
                self._values.pop(victim, None)

        # Insert.
        time.sleep(0.001)
        self._values[key] = value
        self._order.append(key)
