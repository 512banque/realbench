import threading
import time


class Account:
    """Bank account with its own lock to protect concurrent updates."""

    def __init__(self, account_id, balance):
        self.id = account_id
        self.balance = balance
        self._lock = threading.Lock()


class Bank:
    """In-memory bank with per-account locks and transfer operations.

    Cross transfers are made deadlock-free by always acquiring locks in a
    consistent order, sorted by account id. This breaks the cyclic wait
    condition required for a deadlock.
    """

    def __init__(self):
        self._accounts = {}  # id -> Account

    def add_account(self, account_id, balance):
        self._accounts[account_id] = Account(account_id, balance)

    def balance(self, account_id):
        return self._accounts[account_id].balance

    def total(self):
        return sum(a.balance for a in self._accounts.values())

    def transfer(self, from_id, to_id, amount):
        from_acc = self._accounts[from_id]
        to_acc = self._accounts[to_id]

        # Lock ordering: always acquire locks in a global, consistent order
        # (here, sorted by account id) so that two threads transferring in
        # opposite directions cannot form a cycle.
        if from_id == to_id:
            # Same account: a single lock acquire is enough and avoids
            # re-entering a non-reentrant lock.
            with from_acc._lock:
                if from_acc.balance < amount:
                    return False
                # No-op transfer but keep the semantics consistent.
                return True

        first, second = sorted((from_id, to_id))
        first_lock = self._accounts[first]._lock
        second_lock = self._accounts[second]._lock

        with first_lock:
            time.sleep(0.001)  # latency between the two lock acquires
            with second_lock:
                if from_acc.balance < amount:
                    return False
                from_acc.balance -= amount
                to_acc.balance += amount
                return True
