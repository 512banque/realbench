"""Order state machine — reference implementation.

Representation chosen: a flat dict of `(state, event) -> next_state`.
This is the most compact representation that lets the transition logic
live in a single place (`transition`) without one method per event.

Side effects are kept out of the table and handled explicitly after a
successful state change, keyed off the destination state, so the table
stays declarative.
"""

from datetime import datetime


class InvalidTransition(Exception):
    """Raised when an event is not allowed from the current state."""


# (from_state, event) -> to_state
_TRANSITIONS = {
    ("pending", "pay"): "paid",
    ("pending", "cancel"): "cancelled",
    ("paid", "ship"): "shipped",
    ("paid", "refund"): "refunded",
    ("shipped", "deliver"): "delivered",
    ("shipped", "return_"): "returned",
}


class Order:
    """Order modelled as a dict-driven state machine.

    The full transition table is the module-level `_TRANSITIONS` mapping
    `(state, event) -> next_state`. Any pair absent from the table is
    illegal and raises `InvalidTransition` — including terminal states,
    unknown events, and self-loops (which are simply not in the table).
    """

    def __init__(self):
        self.status = "pending"
        self.shipped_at = None
        self.cancellation_reason = None

    def transition(self, event, **kwargs):
        key = (self.status, event)
        if key not in _TRANSITIONS:
            raise InvalidTransition(
                f"event {event!r} not allowed from state {self.status!r}"
            )
        new_state = _TRANSITIONS[key]
        # Apply side effects keyed by the destination state.
        if new_state == "shipped":
            self.shipped_at = datetime.utcnow()
        elif new_state == "cancelled":
            reason = kwargs.get("reason")
            if reason is not None:
                self.cancellation_reason = reason
        self.status = new_state
