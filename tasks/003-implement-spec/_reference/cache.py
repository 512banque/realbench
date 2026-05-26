import threading
import time


class TTLCache:
    def __init__(self, ttl, clock=None):
        self._ttl = ttl
        self._clock = clock if clock is not None else time.monotonic
        self._lock = threading.RLock()
        self._data = {}

    def _expired(self, expires_at):
        return self._clock() >= expires_at

    def set(self, key, value):
        with self._lock:
            self._data[key] = (value, self._clock() + self._ttl)

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._expired(expires_at):
                del self._data[key]
                return None
            return value

    def delete(self, key):
        with self._lock:
            self._data.pop(key, None)

    def size(self):
        with self._lock:
            expired_keys = [k for k, (_, exp) in self._data.items() if self._expired(exp)]
            for k in expired_keys:
                del self._data[k]
            return len(self._data)
