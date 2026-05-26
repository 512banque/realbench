Implement the state machine of an order in `order.py`. An order
has a status and can transition on business events (`pay`,
`ship`, `deliver`, `cancel`, `refund`, `return_`). The full rules
are in `STATE_TRANSITIONS_RULES.md`, shipped in the workspace — read it
before coding.

Pick your representation: transitions dict, one `State` class per state,
a `Machine` class with one method per event, lookup table with
decorators, whatever you want. Document your choice in a docstring on
`Order` (or on `transition`).

Public API seen by the tests:

- `Order()` — initial state `pending`.
- `order.status` — string in `{pending, paid, shipped, delivered,
  cancelled, refunded, returned}`.
- `order.transition(event, **kwargs)` — applies the event. Illegal
  transitions (wrong source state, unknown event,
  re-emitting an event toward the same state) must raise
  `InvalidTransition`.
- Required side effects:
  - `transition("ship")` sets `order.shipped_at = datetime.utcnow()`.
  - `transition("cancel", reason=...)` sets `order.cancellation_reason`.

Do not modify `test_order.py` or `STATE_TRANSITIONS_RULES.md`.
