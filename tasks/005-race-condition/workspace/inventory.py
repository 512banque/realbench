import time


class Inventory:
    """In-memory inventory with per-item stock and reservation log."""

    def __init__(self):
        self._stock = {}
        self._reservations = []

    def add_item(self, item_id, stock):
        self._stock[item_id] = stock

    def reserve(self, user_id, item_id):
        """Reserve one unit of `item_id` for `user_id`.

        Returns True if a unit was reserved, False if out of stock or unknown
        item. Simulates a real-world 'read stock, then write stock' pattern
        (e.g. SELECT followed by UPDATE on a database) with a small latency
        between the read and the write.
        """
        current = self._stock.get(item_id, 0)
        if current <= 0:
            return False
        time.sleep(0.001)  # latency between read and write
        self._stock[item_id] = current - 1
        self._reservations.append((user_id, item_id))
        return True

    def stock(self, item_id):
        return self._stock.get(item_id, 0)

    def reservation_count(self, item_id):
        return sum(1 for _, iid in self._reservations if iid == item_id)
