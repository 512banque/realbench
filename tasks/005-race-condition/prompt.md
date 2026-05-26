The tests in `test_inventory.py` are failing: the
`Inventory.reserve(user_id, item_id)` function allows more reservations than
the available stock when multiple threads call it concurrently (oversell).

Identify the cause and fix `inventory.py` so that all invariants respect the
stock even under contention. Do not modify the tests.
