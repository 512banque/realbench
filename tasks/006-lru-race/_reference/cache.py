import threading
import time


class LRUCache:
    """LRU cache with fixed capacity, thread-safe via an RLock."""

    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._values = {}
        self._order = []  # LRU first, MRU last
        self._lock = threading.RLock()

    def __len__(self):
        with self._lock:
            return len(self._values)

    def keys(self):
        with self._lock:
            return list(self._order)

    def get(self, key):
        with self._lock:
            if key not in self._values:
                return None
            value = self._values[key]
            idx = self._order.index(key)
            time.sleep(0.001)  # latency stays inside the critical section
            self._order.pop(idx)
            time.sleep(0.001)
            self._order.append(key)
            return value

    def put(self, key, value):
        with self._lock:
            if key in self._values:
                self._values[key] = value
                idx = self._order.index(key)
                time.sleep(0.001)
                self._order.pop(idx)
                self._order.append(key)
                return

            if len(self._values) >= self._capacity:
                time.sleep(0.001)
                if self._order:
                    victim = self._order.pop(0)
                    self._values.pop(victim, None)

            time.sleep(0.001)
            self._values[key] = value
            self._order.append(key)
