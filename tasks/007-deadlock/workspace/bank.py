import threading
import time


class Account:
    """Bank account with its own lock to protect concurrent updates."""

    def __init__(self, account_id, balance):
        self.id = account_id
        self.balance = balance
        self._lock = threading.Lock()


class Bank:
    """In-memory bank with per-account locks and transfer operations."""

    def __init__(self):
        self._accounts = {}  # id -> Account

    def add_account(self, account_id, balance):
        self._accounts[account_id] = Account(account_id, balance)

    def balance(self, account_id):
        return self._accounts[account_id].balance

    def total(self):
        return sum(a.balance for a in self._accounts.values())

    def transfer(self, from_id, to_id, amount):
        """Transfer `amount` from `from_id` to `to_id`.

        Returns True on success, False if the source has insufficient funds.
        Acquires the source lock then the destination lock, simulating a
        real-world 'debit then credit' pattern with a small latency between
        the two acquires.
        """
        from_acc = self._accounts[from_id]
        to_acc = self._accounts[to_id]
        with from_acc._lock:
            time.sleep(0.001)  # latency between the two lock acquires
            with to_acc._lock:
                if from_acc.balance < amount:
                    return False
                from_acc.balance -= amount
                to_acc.balance += amount
                return True
