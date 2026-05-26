import threading
import time

from bank import Bank


# Maximum total wall time we are willing to wait for any single concurrent
# scenario to finish. If it hasn't, we treat it as a deadlock.
DEADLOCK_TIMEOUT_SEC = 5.0


def _join_all(threads, total_timeout):
    """Join `threads` with a shared total budget. Returns the list of threads
    that are still alive after the budget is exhausted."""
    deadline = time.monotonic() + total_timeout
    for t in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        t.join(timeout=remaining)
    return [t for t in threads if t.is_alive()]


def test_create_and_balance():
    bank = Bank()
    bank.add_account("A", balance=100)
    bank.add_account("B", balance=50)

    assert bank.balance("A") == 100
    assert bank.balance("B") == 50
    assert bank.total() == 150


def test_transfer_success():
    bank = Bank()
    bank.add_account("A", balance=100)
    bank.add_account("B", balance=0)

    assert bank.transfer("A", "B", 30) is True
    assert bank.balance("A") == 70
    assert bank.balance("B") == 30
    assert bank.total() == 100


def test_transfer_insufficient_balance():
    bank = Bank()
    bank.add_account("A", balance=10)
    bank.add_account("B", balance=0)

    assert bank.transfer("A", "B", 50) is False
    assert bank.balance("A") == 10
    assert bank.balance("B") == 0
    assert bank.total() == 10


def test_concurrent_same_direction_conserves_total():
    bank = Bank()
    bank.add_account("A", balance=1000)
    bank.add_account("B", balance=0)

    n_threads = 20
    barrier = threading.Barrier(n_threads)

    def worker():
        barrier.wait()
        bank.transfer("A", "B", 1)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(n_threads)]
    for t in threads:
        t.start()

    hung = _join_all(threads, DEADLOCK_TIMEOUT_SEC)
    assert not hung, (
        f"deadlock detected: {len(hung)} thread(s) still alive after "
        f"{DEADLOCK_TIMEOUT_SEC}s during same-direction transfers"
    )

    assert bank.total() == 1000, f"money not conserved: total={bank.total()}"
    assert bank.balance("A") == 1000 - n_threads
    assert bank.balance("B") == n_threads


def test_cross_transfers_deadlock():
    """Two threads transferring in opposite directions must not deadlock."""
    bank = Bank()
    bank.add_account("A", balance=10_000)
    bank.add_account("B", balance=10_000)

    iterations = 200
    barrier = threading.Barrier(2)

    def a_to_b():
        barrier.wait()
        for _ in range(iterations):
            bank.transfer("A", "B", 1)

    def b_to_a():
        barrier.wait()
        for _ in range(iterations):
            bank.transfer("B", "A", 1)

    t1 = threading.Thread(target=a_to_b, daemon=True)
    t2 = threading.Thread(target=b_to_a, daemon=True)
    t1.start()
    t2.start()

    hung = _join_all([t1, t2], DEADLOCK_TIMEOUT_SEC)
    labels = []
    if t1 in hung:
        labels.append("A->B")
    if t2 in hung:
        labels.append("B->A")
    assert not labels, (
        f"deadlock detected: thread(s) {labels} still alive after "
        f"{DEADLOCK_TIMEOUT_SEC}s timeout"
    )

    assert bank.total() == 20_000, (
        f"money not conserved across cross transfers: total={bank.total()}"
    )


def test_concurrent_cross_transfers_conservation_many_accounts():
    """Multiple accounts, multiple cross-transfer pairs concurrently."""
    bank = Bank()
    for name in ("A", "B", "C", "D"):
        bank.add_account(name, balance=5_000)

    iterations = 100
    pairs = [("A", "B"), ("B", "A"), ("C", "D"), ("D", "C"), ("A", "C"), ("C", "A")]
    barrier = threading.Barrier(len(pairs))

    def worker(src, dst):
        barrier.wait()
        for _ in range(iterations):
            bank.transfer(src, dst, 1)

    threads = [threading.Thread(target=worker, args=p, daemon=True) for p in pairs]
    for t in threads:
        t.start()

    hung = _join_all(threads, DEADLOCK_TIMEOUT_SEC)
    assert not hung, (
        f"deadlock detected: {len(hung)} thread(s) still alive after "
        f"{DEADLOCK_TIMEOUT_SEC}s timeout"
    )

    assert bank.total() == 20_000, (
        f"money not conserved: total={bank.total()}"
    )
