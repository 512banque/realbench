"""
Tests for the Order state machine task (022-state-machine).

Design intent: the *representation* of the state machine is not
specified. A dict of transitions, a class per state (Strategy), a
single Machine class with one method per event, a decorator-based
registry — all of these are accepted. The tests check:

    1. Functional behavior: the canonical happy path, every legal
       transition, every illegal one raises `InvalidTransition`,
       documented side-effects (`shipped_at`, `cancellation_reason`).
    2. An invariant on `status` (always a known string).
    3. Structural anti-patterns rejected without imposing a design:
       - A class docstring of at least 30 significant characters.
       - No method named like a hard-coded setter
         (`set_status_to_paid`, `force_*`, etc.) — these would mean
         a state-per-method API bypassing centralized validation.
       - No `__setattr__` business logic on `Order` — keep the object
         scriptable; transitions go through an explicit entry point.
       - `raise InvalidTransition` appears somewhere in order.py.
       - No environment / OS / network imports.

What we deliberately do NOT check:
    - Whether the implementation uses a dict, classes, decorators, ...
    - The internal field names beyond the two documented side-effects.
    - Whether `transition` returns the new status or `None`.
    - Whether an optional `history()` is exposed (positive-only check).
"""

import ast
import inspect
import re
from datetime import datetime

import pytest

import order as order_module
from order import InvalidTransition, Order


ALL_STATES = {
    "pending",
    "paid",
    "shipped",
    "delivered",
    "cancelled",
    "refunded",
    "returned",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _module_source():
    return inspect.getsource(order_module)


def _class_ast():
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Order":
            return node
    raise AssertionError("class Order not found in order.py")


def _method_names():
    names = set()
    for node in _class_ast().body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


# ---------------------------------------------------------------------------
# 1. Functional behavior — positive transitions
# ---------------------------------------------------------------------------

def test_initial_state_is_pending():
    assert Order().status == "pending"


def test_happy_path_pending_to_delivered():
    o = Order()
    o.transition("pay")
    assert o.status == "paid"
    o.transition("ship")
    assert o.status == "shipped"
    o.transition("deliver")
    assert o.status == "delivered"


def test_cancel_from_pending():
    o = Order()
    o.transition("cancel")
    assert o.status == "cancelled"


def test_refund_after_paid():
    o = Order()
    o.transition("pay")
    o.transition("refund")
    assert o.status == "refunded"


def test_return_after_shipped():
    o = Order()
    o.transition("pay")
    o.transition("ship")
    o.transition("return_")
    assert o.status == "returned"


# ---------------------------------------------------------------------------
# 1b. Functional behavior — illegal transitions
# ---------------------------------------------------------------------------

def test_cancel_after_paid_raises():
    o = Order()
    o.transition("pay")
    with pytest.raises(InvalidTransition):
        o.transition("cancel")


def test_refund_after_shipped_raises():
    o = Order()
    o.transition("pay")
    o.transition("ship")
    with pytest.raises(InvalidTransition):
        o.transition("refund")


def test_delivered_is_terminal():
    o = Order()
    o.transition("pay")
    o.transition("ship")
    o.transition("deliver")
    # Every event from delivered must raise.
    for event in ("pay", "ship", "deliver", "cancel", "refund", "return_"):
        with pytest.raises(InvalidTransition):
            o.transition(event)


def test_cancelled_is_terminal():
    o = Order()
    o.transition("cancel")
    for event in ("pay", "ship", "deliver", "cancel", "refund", "return_"):
        with pytest.raises(InvalidTransition):
            o.transition(event)


def test_refunded_is_terminal():
    o = Order()
    o.transition("pay")
    o.transition("refund")
    for event in ("pay", "ship", "deliver", "cancel", "refund", "return_"):
        with pytest.raises(InvalidTransition):
            o.transition(event)


def test_returned_is_terminal():
    o = Order()
    o.transition("pay")
    o.transition("ship")
    o.transition("return_")
    for event in ("pay", "ship", "deliver", "cancel", "refund", "return_"):
        with pytest.raises(InvalidTransition):
            o.transition(event)


def test_same_state_transition_raises():
    """Idempotence is forbidden: re-issuing an event whose source state
    is the current state but which would loop back to the same state
    (here: `pay` from `paid`) must raise rather than silently no-op."""
    o = Order()
    o.transition("pay")
    with pytest.raises(InvalidTransition):
        o.transition("pay")


def test_unknown_event_raises():
    o = Order()
    with pytest.raises(InvalidTransition):
        o.transition("teleport")


# ---------------------------------------------------------------------------
# 1c. Documented side-effects
# ---------------------------------------------------------------------------

def test_shipped_sets_shipped_at():
    o = Order()
    o.transition("pay")
    before = datetime.utcnow()
    o.transition("ship")
    after = datetime.utcnow()
    assert isinstance(o.shipped_at, datetime)
    # Sanity: timestamp lies inside the window of the test, no future, no
    # epoch zero. We allow equality at the bounds to be safe across clocks.
    assert before <= o.shipped_at <= after


def test_cancel_reason_optional():
    # Without a reason: must still work.
    o1 = Order()
    o1.transition("cancel")
    # With a reason: must store it on the Order.
    o2 = Order()
    o2.transition("cancel", reason="duplicate order")
    assert o2.cancellation_reason == "duplicate order"


# ---------------------------------------------------------------------------
# 2. Invariant
# ---------------------------------------------------------------------------

def test_status_always_string():
    o = Order()
    assert o.status in ALL_STATES
    for ev in ("pay", "ship", "deliver"):
        o.transition(ev)
        assert isinstance(o.status, str)
        assert o.status in ALL_STATES


def test_history_tracking_optional_but_consistent():
    """If the class exposes an `history()` method returning a list, the
    last entry must reflect the most recent transition. Implementations
    that don't expose this skip the check entirely — it is optional."""
    o = Order()
    history = getattr(o, "history", None)
    if not callable(history):
        pytest.skip("no history() exposed; optional feature")
    o.transition("pay")
    h = o.history()
    assert isinstance(h, list)
    assert len(h) >= 1
    last = h[-1]
    # Be lenient on the entry shape — accept tuple/dict/str — only check
    # that the new state appears somewhere in the last record.
    last_repr = repr(last)
    assert "paid" in last_repr


# ---------------------------------------------------------------------------
# 3. Structural anti-pattern checks
# ---------------------------------------------------------------------------

def test_class_has_docstring():
    """Order must have a docstring of >= 30 significant characters
    describing the chosen representation. The exact wording is free."""
    doc = ast.get_docstring(_class_ast()) or ""
    sig = re.sub(r"\s+", " ", doc).strip()
    stub = "TODO: implement the state machine."
    assert sig != stub, (
        "Class docstring is the unchanged stub; document your chosen "
        "representation (dict of transitions, class per state, ...)."
    )
    assert len(sig) >= 30, (
        f"Order class docstring must be at least 30 significant chars; got {len(sig)}."
    )


def test_no_hardcoded_status_setters():
    """A method named `set_status_to_<state>` or `force_<anything>` is
    the anti-pattern: it exposes one entry point per target state,
    bypassing centralized validation. Reject these patterns. Methods
    named after the *event* (`pay`, `ship`, `cancel`, ...) are fine —
    that's the standard Machine-class design and is encouraged."""
    bad_re = re.compile(r"^(set_status_to_|force_)")
    bad = sorted(name for name in _method_names() if bad_re.match(name))
    assert not bad, (
        f"order.py defines hard-coded status setters {bad}. Route all "
        "state changes through a centralized transition entry point."
    )


def test_no_setattr_business_logic():
    """Putting transition logic inside `__setattr__` makes the object
    non-scriptable (you can no longer set `self._anything` without
    triggering business code) and hides the state machine from
    callers. Forbid `__setattr__` on the Order class."""
    assert "__setattr__" not in _method_names(), (
        "order.py defines Order.__setattr__. Keep transitions explicit; "
        "do not bury state-machine logic inside a dunder."
    )


def test_invalid_transition_is_raised_somewhere():
    """A static check that the agent uses the exception path rather
    than asserting / printing / returning a sentinel on illegal
    transitions."""
    src = _module_source()
    assert re.search(r"\braise\s+InvalidTransition\b", src), (
        "order.py must `raise InvalidTransition` on illegal transitions, "
        "not assert / print / return a sentinel."
    )


def test_no_external_state():
    """The state machine is pure. No env, no subprocess, no network.
    `datetime` and `time` are explicitly allowed (for `shipped_at`)."""
    tree = ast.parse(_module_source())
    forbidden = {"os", "subprocess", "socket", "urllib", "http", "requests"}
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden:
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in forbidden:
                bad.append(node.module)
    assert not bad, (
        f"order.py imports forbidden modules {bad}. The state machine "
        "must be self-contained: no env, no subprocess, no network."
    )
