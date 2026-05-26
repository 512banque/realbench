import threading
import time


class Inventory:
    """In-memory inventory with per-item stock and reservation log."""

    def __init__(self):
        self._stock = {}
        self._reservations = []
        self._lock = threading.Lock()

    def add_item(self, item_id, stock):
        with self._lock:
            self._stock[item_id] = stock

    def reserve(self, user_id, item_id):
        with self._lock:
            current = self._stock.get(item_id, 0)
            if current <= 0:
                return False
            time.sleep(0.001)  # latency stays inside the critical section
            self._stock[item_id] = current - 1
            self._reservations.append((user_id, item_id))
            return True

    def stock(self, item_id):
        with self._lock:
            return self._stock.get(item_id, 0)

    def reservation_count(self, item_id):
        with self._lock:
            return sum(1 for _, iid in self._reservations if iid == item_id)
