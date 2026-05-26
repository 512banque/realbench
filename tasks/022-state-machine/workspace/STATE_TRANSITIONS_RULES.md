# Order state machine — business rules

An `Order` has a `status` and moves between states via business **events**.
The events drive the transitions; clients never assign `status` directly.

## States

- `pending` — initial state. A freshly constructed `Order()` is `pending`.
- `paid` — payment captured.
- `shipped` — physically dispatched.
- `delivered` — terminal. Nothing happens after.
- `cancelled` — terminal.
- `refunded` — terminal.
- `returned` — terminal.

Terminal states reject every further event.

## Events and allowed transitions

| Event       | From      | To         | Notes                                           |
| ----------- | --------- | ---------- | ----------------------------------------------- |
| `pay`       | pending   | paid       |                                                 |
| `ship`      | paid      | shipped    | Sets `shipped_at = datetime.utcnow()`.          |
| `deliver`   | shipped   | delivered  |                                                 |
| `cancel`    | pending   | cancelled  | Optional `reason` kwarg → `cancellation_reason`.|
| `refund`    | paid      | refunded   | Only **before** shipping.                       |
| `return_`   | shipped   | returned   | Only **before** delivery.                       |

Every other (state, event) pair is illegal and must raise
`InvalidTransition`. In particular:

- A redundant event on the current state (e.g. calling `pay` while
  already `paid`) is **not** a no-op — it raises `InvalidTransition`.
  Idempotence is forbidden; if the caller wants to know whether an
  event is currently valid, that's a separate query.
- `cancel` is only legal from `pending`. Once paid, you `refund`.
- `refund` is only legal from `paid`. Once shipped, you `return_`.
- All terminal states (`delivered`, `cancelled`, `refunded`, `returned`)
  reject every event.

## Public API expected by callers

```python
order = Order()
order.status                       # == "pending"
order.transition("pay")            # status -> "paid"
order.transition("ship")           # status -> "shipped", shipped_at set
order.transition("deliver")        # status -> "delivered"

# Side-effects:
order2 = Order()
order2.transition("cancel", reason="duplicate")
# order2.cancellation_reason == "duplicate"

# Illegal:
order3 = Order()
order3.transition("ship")          # raises InvalidTransition
```

The internal representation is **up to you**: a `{(state, event): state}`
table, a `State` class per state with event methods, a `Machine` class
with one method per event, a decorator registry, etc. — all acceptable
as long as the contract above holds.
