"""Order state machine — stub.

Implement the state machine described in `STATE_TRANSITIONS_RULES.md`.
The internal representation is up to you. Document your choice in a
docstring on `Order` (or on `transition`).
"""


class InvalidTransition(Exception):
    """Raised when an event is not allowed from the current state."""


class Order:
    """TODO: implement the state machine."""

    def __init__(self):
        self.status = "pending"
        # add fields as needed (shipped_at, cancellation_reason, ...)

    def transition(self, event, **kwargs):
        """TODO: dispatch `event` from the current `status`."""
        raise NotImplementedError
