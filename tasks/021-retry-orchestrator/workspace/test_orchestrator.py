"""
Tests for the ambiguous RetryOrchestrator task.

Design intent (see task prompt): the retry STRATEGY is intentionally
unspecified. Exponential backoff (with or without jitter), fixed delay,
linear backoff, retry budget, circuit breaker, token bucket... all are
acceptable. The tests only check:

    1. Functional minimum: happy path, permanent error not retried,
       transient retried until success, eventual give-up.
    2. Invariants every reasonable strategy must satisfy (max_total_retries
       respected, total calls bounded, concurrent calls don't crash).
    3. Structural anti-pattern checks (AST-based): docstring exists, no
       module-level mutable state, no `while True` without exit, no
       `time.sleep` inside a `with lock:` block.

What we deliberately DO NOT check:

    - The exact backoff shape (exponential vs linear vs fixed vs jitter).
    - The exact delay between retries.
    - The number of retries used (only the max is enforced).
    - The internal data structure (queue, counters, state machine, ...).
"""

from __future__ import annotations

import ast
import inspect
import threading
import time

import pytest

import orchestrator as orchestrator_module
from orchestrator import RetryOrchestrator
from services import (
    TransientError,
    PermanentError,
    RetryExhausted,
    _AlwaysOk,
    _AlwaysFailPermanent,
    _AlwaysFailTransient,
    _FailNThenOk,
    _FixedRateService,
)


# ---------------------------------------------------------------------------
# AST helpers (used by the structural tests)
# ---------------------------------------------------------------------------

def _module_source():
    return inspect.getsource(orchestrator_module)


def _class_ast():
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "RetryOrchestrator":
            return node
    raise AssertionError("class RetryOrchestrator not found in orchestrator.py")


def _method_ast(name: str):
    cls = _class_ast()
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found in class RetryOrchestrator")


# ---------------------------------------------------------------------------
# 1. Functional minimum
# ---------------------------------------------------------------------------

def test_returns_on_first_success():
    o = RetryOrchestrator(max_total_retries=5)
    svc = _AlwaysOk()
    result = o.call(svc)
    assert result is not None  # value shape is service-dependent
    assert svc.call_count == 1, "happy path must not retry"


def test_permanent_error_no_retry():
    o = RetryOrchestrator(max_total_retries=10)
    svc = _AlwaysFailPermanent()
    with pytest.raises(PermanentError):
        o.call(svc)
    assert svc.call_count == 1, "PermanentError must NOT be retried"


def test_retries_on_transient():
    o = RetryOrchestrator(max_total_retries=5)
    svc = _FailNThenOk(2)  # fails twice, succeeds on the 3rd call
    result = o.call(svc)
    assert result is not None
    assert svc.call_count == 3, (
        f"expected exactly 3 calls (2 fails + 1 success), got {svc.call_count}"
    )


def _call_with_timeout(orch, svc, *, deadline_sec: float = 5.0):
    """Run `orch.call(svc)` in a daemon thread. Returns (status, payload):
    - ("ok", value)       on success
    - ("exc", Exception)  on a raised exception
    - ("timeout", None)   if the orchestrator did not finish in time
    """
    outcome: list = []

    def target():
        try:
            outcome.append(("ok", orch.call(svc)))
        except BaseException as e:  # noqa: BLE001
            outcome.append(("exc", e))

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(deadline_sec)
    if th.is_alive():
        return ("timeout", None)
    return outcome[0]


def test_eventually_gives_up():
    # Wall-clock guard against infinite-retry implementations. Any reasonable
    # strategy with max_total_retries=3 finishes well under a second.
    o = RetryOrchestrator(max_total_retries=3)
    svc = _AlwaysFailTransient()
    status, payload = _call_with_timeout(o, svc, deadline_sec=5.0)
    if status == "timeout":
        pytest.fail(
            "orchestrator did not give up within 5s — the strategy looks "
            "unbounded (no retry budget honored)."
        )
    assert status == "exc", f"expected an exception, got {status!r}: {payload!r}"
    assert isinstance(payload, (RetryExhausted, TransientError)), (
        f"expected RetryExhausted or TransientError, got {payload!r}"
    )


# ---------------------------------------------------------------------------
# 2. Invariants
# ---------------------------------------------------------------------------

def test_respects_max_total_retries():
    """With max_total_retries=3, an always-failing service must be called
    at most 4 times (1 initial + 3 retries) per `call()`."""
    o = RetryOrchestrator(max_total_retries=3)
    svc = _AlwaysFailTransient()
    status, payload = _call_with_timeout(o, svc, deadline_sec=5.0)
    if status == "timeout":
        pytest.fail("orchestrator did not give up within 5s")
    assert status == "exc"
    assert isinstance(payload, (RetryExhausted, TransientError))
    assert svc.call_count <= 4, (
        f"max_total_retries=3 implies <= 4 calls total, got {svc.call_count}"
    )
    assert svc.call_count >= 1, "must call the service at least once"


def test_total_calls_bounded():
    """Over 100 invocations against a 50%-failure service, total internal
    calls must stay well under 10x the number of `call()` invocations.
    This guards against retry-leaks and runaway loops, without enforcing
    a specific strategy."""
    o = RetryOrchestrator(max_total_retries=10)
    svc = _FixedRateService(fail_rate=0.5, seed=2024_05_24)
    successes = 0
    for _ in range(100):
        try:
            o.call(svc)
            successes += 1
        except (RetryExhausted, TransientError):
            pass
    # 50% rate, max 10 retries: in expectation ~2x. The bound 1000 is
    # extremely loose to be strategy-agnostic.
    assert svc.call_count < 1000, (
        f"total internal calls {svc.call_count} exceeded 10x the budget; "
        "the strategy is leaking retries"
    )


def test_concurrent_calls_safe():
    """10 threads invoke `call()` in parallel. No crashes, all expected
    outcomes (success OR RetryExhausted/TransientError on a transient)."""
    o = RetryOrchestrator(max_total_retries=5)
    svc = _FixedRateService(fail_rate=0.3, seed=42)
    errors: list[BaseException] = []
    results: list = []
    lock = threading.Lock()

    def worker():
        try:
            r = o.call(svc)
            with lock:
                results.append(r)
        except (RetryExhausted, TransientError) as e:
            with lock:
                results.append(e)
        except BaseException as e:  # pragma: no cover  - this is the test
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
        assert not t.is_alive(), "worker thread hung; orchestrator deadlocked"

    assert not errors, f"unexpected exception types: {errors}"
    assert len(results) == 10


# ---------------------------------------------------------------------------
# 3. Structural anti-pattern checks
# ---------------------------------------------------------------------------

def test_strategy_documented():
    """The RetryOrchestrator class must have a docstring of at least
    50 significant characters mentioning the chosen strategy. The
    content is free: 'exponential backoff', 'fixed delay', 'circuit
    breaker', etc. are all accepted."""
    import re
    doc = ast.get_docstring(_class_ast()) or ""
    sig = re.sub(r"\s+", " ", doc).strip()
    stub_fragments = [
        "TODO: implement your retry strategy and document it here.",
        "TODO",
    ]
    for stub in stub_fragments:
        if sig == stub:
            pytest.fail(f"docstring is the unchanged stub: {sig!r}")
    assert len(sig) >= 50, (
        f"RetryOrchestrator docstring must be >= 50 significant characters, "
        f"got {len(sig)}: {sig!r}"
    )


def test_no_unbounded_loop():
    """A `while True:` body inside `call()` must contain at least one
    `break` or `return` somewhere. We accept any reachable exit
    statement; we do NOT enforce all branches must return."""
    m = _method_ast("call")
    for node in ast.walk(m):
        if isinstance(node, ast.While):
            # is the condition the literal True (or 1)?
            cond = node.test
            literal_true = (
                (isinstance(cond, ast.Constant) and cond.value is True)
                or (isinstance(cond, ast.Constant) and cond.value == 1)
                or (isinstance(cond, ast.Name) and cond.id == "True")
            )
            if not literal_true:
                continue
            # Any break/return reachable inside the while body?
            has_exit = False
            for inner in ast.walk(node):
                if inner is node:
                    continue
                if isinstance(inner, (ast.Break, ast.Return, ast.Raise)):
                    has_exit = True
                    break
            assert has_exit, (
                "`while True:` in call() has no break/return/raise — "
                "this is an unbounded loop"
            )


def test_no_thread_sleep_inside_lock():
    """`time.sleep(...)` must not appear inside a `with lock:` block.
    Sleeping while holding a lock blocks every other concurrent call —
    a classic anti-pattern.

    We're conservative: we only flag a sleep that lives inside a `with`
    statement whose context manager is identifiable as a lock-like
    primitive (variable name matches lock/mutex/sem heuristics, or is a
    `threading.Lock()`/`RLock()`/`Semaphore()` direct construction).
    Unidentifiable `with` blocks are skipped to avoid false positives.
    """
    LOCK_HINT = ("lock", "mutex", "sem", "_lock", "rlock")
    tree = ast.parse(_module_source())

    def is_lock_context(item: ast.withitem) -> bool:
        node = item.context_expr
        # `with self._lock:` or `with foo_lock:`
        if isinstance(node, ast.Attribute):
            return any(h in node.attr.lower() for h in LOCK_HINT)
        if isinstance(node, ast.Name):
            return any(h in node.id.lower() for h in LOCK_HINT)
        # `with threading.Lock():` or `with Lock():`
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            return name in {"Lock", "RLock", "Semaphore",
                            "BoundedSemaphore", "Condition"}
        return False

    def is_sleep_call(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "sleep":
            # time.sleep(...) typically
            return True
        if isinstance(f, ast.Name) and f.id == "sleep":
            return True
        return False

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any(is_lock_context(i) for i in node.items):
            for inner in ast.walk(node):
                if inner is node:
                    continue
                # Stop at nested With if it explicitly releases the outer lock?
                # Keep it simple: any sleep inside the outer block is a violation.
                if is_sleep_call(inner):
                    violations.append(getattr(inner, "lineno", "?"))
    assert not violations, (
        f"time.sleep(...) found inside a `with lock:` block at lines "
        f"{violations}. Holding a lock across a sleep blocks every other "
        "concurrent call. Sleep OUTSIDE the lock."
    )


def test_no_module_level_mutable_state():
    """The orchestrator must not stash state in module-level mutable
    globals. We only flag the `global` keyword usage and assignment to a
    module-level NAME from inside a method body. Module-level constants
    (UPPER_CASE = 1, _DEFAULTS = {...}) defined at module load time are
    fine; we only inspect what happens INSIDE methods of
    RetryOrchestrator."""
    tree = ast.parse(_module_source())

    # Collect module-level top-level names (excluding imports & class/func defs).
    module_level_names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    module_level_names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            module_level_names.add(node.target.id)

    cls = _class_ast()
    violations = []
    for method in cls.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(method):
            if isinstance(inner, ast.Global):
                violations.append(("global", method.name, inner.names))
            elif isinstance(inner, ast.Assign):
                for tgt in inner.targets:
                    if isinstance(tgt, ast.Name) and tgt.id in module_level_names:
                        violations.append(
                            ("reassign", method.name, tgt.id)
                        )
    assert not violations, (
        "RetryOrchestrator methods mutate module-level state: "
        f"{violations}. Keep state on `self`, not on module globals."
    )
