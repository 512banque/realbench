import threading

from inventory import Inventory


def test_single_thread_basic():
    inv = Inventory()
    inv.add_item(1, stock=3)

    assert inv.reserve("alice", 1) is True
    assert inv.reserve("bob", 1) is True
    assert inv.reserve("carol", 1) is True
    assert inv.reserve("dave", 1) is False

    assert inv.stock(1) == 0
    assert inv.reservation_count(1) == 3


def test_unknown_item():
    inv = Inventory()
    assert inv.reserve("alice", 999) is False


def test_single_unit_then_empty():
    inv = Inventory()
    inv.add_item(7, stock=1)

    assert inv.reserve("alice", 7) is True
    assert inv.reserve("bob", 7) is False
    assert inv.stock(7) == 0
    assert inv.reservation_count(7) == 1


def _run_concurrent_reserve(inv, item_id, n_threads):
    """Fire `n_threads` threads simultaneously calling reserve(uid, item_id).

    Returns the count of reservations that returned True.
    """
    barrier = threading.Barrier(n_threads)
    counter_lock = threading.Lock()
    successes = [0]

    def worker(uid):
        barrier.wait()  # release all threads at the same instant
        if inv.reserve(uid, item_id):
            with counter_lock:
                successes[0] += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return successes[0]


def test_concurrent_reserve_does_not_oversell_single_unit():
    inv = Inventory()
    inv.add_item(42, stock=1)

    successes = _run_concurrent_reserve(inv, 42, n_threads=20)

    assert successes == 1, (
        f"oversold: got {successes} successful reservations for stock=1"
    )
    assert inv.stock(42) == 0
    assert inv.reservation_count(42) == 1


def test_concurrent_reserve_respects_stock_limit():
    inv = Inventory()
    inv.add_item(100, stock=10)

    successes = _run_concurrent_reserve(inv, 100, n_threads=50)

    assert successes == 10, f"oversold: got {successes} successes for stock=10"
    assert inv.stock(100) == 0
    assert inv.reservation_count(100) == 10
