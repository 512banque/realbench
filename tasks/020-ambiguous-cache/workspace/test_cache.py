"""
Tests for the ambiguous Cache task.

Design intent (see task prompt and tasks/020-ambiguous-cache/README in the
bench): the eviction strategy is NOT specified. LRU, LFU, FIFO, random,
2-random, ARC, etc. are all acceptable. The tests only check:

    1. Functional minimum: put/get round-trip, size accounting, bounded
       growth, idempotent update on same key.
    2. Invariants every reasonable strategy must satisfy (eviction
       happens when full, freshly-put key is present right after).
    3. Structural anti-patterns: docstring exists and is non-trivial,
       at least one removal operation lives in cache.py (no purely
       unbounded growth), no environment / OS coupling, and if a Lock
       is instantiated then both `put` and `get` must use it.
    4. Multi-put consistency (overwrite, bound vs unique keys).

What we deliberately DO NOT check:

    - The exact eviction order (LRU vs FIFO vs LFU vs random differ).
    - That "old" keys leave first.
    - The internal data structure (dict, OrderedDict, deque, list, ...).
    - Thread-safety itself — only its consistency if attempted.

`get` on a missing key may return None OR raise: both are accepted via
the `_safe_get` helper, so an agent who picks either convention passes.
"""

import ast
import inspect
import random
import re
import threading

import pytest

import cache as cache_module
from cache import Cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(c, key, default=None):
    """Tolerate both conventions for missing keys: return None or raise."""
    try:
        out = c.get(key)
    except (KeyError, LookupError):
        return default
    return out if out is not None else default


def _present(c, key):
    """True iff `key` is currently retrievable from `c`."""
    sentinel = object()
    try:
        out = c.get(key)
    except (KeyError, LookupError):
        return False
    return out is not None and out is not sentinel


def _class_source():
    return inspect.getsource(Cache)


def _module_source():
    return inspect.getsource(cache_module)


def _class_ast():
    src = inspect.getsource(cache_module)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Cache":
            return node
    raise AssertionError("class Cache not found in cache.py")


def _method_ast(name):
    cls = _class_ast()
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found in class Cache")


# ---------------------------------------------------------------------------
# 1. Functional minimum
# ---------------------------------------------------------------------------

def test_put_then_get():
    c = Cache(max_size=10)
    c.put("a", 1)
    assert c.get("a") == 1


def test_put_existing_updates_value_not_size():
    c = Cache(max_size=10)
    c.put("a", 1)
    s1 = c.size()
    c.put("a", 2)
    assert c.get("a") == 2
    assert c.size() == s1


def test_size_grows_with_unique_puts():
    c = Cache(max_size=10)
    for i in range(5):
        c.put(f"k{i}", i)
    assert c.size() == 5


def test_get_missing_returns_none_or_raises():
    c = Cache(max_size=10)
    # Accept either convention: returns None, OR raises KeyError/LookupError.
    assert _safe_get(c, "nope") is None


def test_size_never_exceeds_max_size():
    c = Cache(max_size=8)
    rng = random.Random(20240524)
    keys = [f"k{i}" for i in range(40)]
    for _ in range(1000):
        c.put(rng.choice(keys), rng.randint(0, 1_000_000))
        # invariant must hold at EVERY step
        assert c.size() <= 8, "size exceeded max_size during sequence"


# ---------------------------------------------------------------------------
# 2. Invariants every reasonable strategy must satisfy
# ---------------------------------------------------------------------------

def test_eviction_happens_when_full():
    c = Cache(max_size=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert c.size() == 3
    c.put("d", 4)  # forces an eviction
    assert c.size() == 3
    # We do NOT assert which of a/b/c got evicted — strategy is free.


def test_recently_added_key_is_present():
    # Whichever strategy is used, the key just inserted must still be
    # retrievable immediately after `put`. Evicting the freshly added
    # entry would be absurd for any reasonable cache.
    c = Cache(max_size=2)
    c.put("x", 100)
    c.put("y", 200)
    c.put("z", 300)
    assert _present(c, "z"), "the key just put was evicted, which is never reasonable"


# ---------------------------------------------------------------------------
# 3. Structural anti-pattern checks
# ---------------------------------------------------------------------------

def test_has_docstring_explaining_strategy():
    """The class OR put() must carry a docstring of at least 30 significant
    characters. We only check the existence and length, not the content —
    the agent is free to describe LRU, LFU, FIFO, random, etc."""
    cls_doc = ast.get_docstring(_class_ast()) or ""
    put_doc = ast.get_docstring(_method_ast("put")) or ""
    # Strip whitespace runs to count significant characters.
    cls_sig = re.sub(r"\s+", " ", cls_doc).strip()
    put_sig = re.sub(r"\s+", " ", put_doc).strip()
    best = max(len(cls_sig), len(put_sig))
    # 30 significant characters is roughly: "LRU: evicts least recent key."
    assert best >= 30, (
        "Cache class (or its put method) must have a docstring of at least 30 "
        f"significant characters explaining the eviction strategy. Got {best}."
    )
    # And it must not be the unchanged stub docstring.
    stub = "A cache with a fixed max size. Behavior when full is up to you."
    assert cls_sig != stub and put_sig != stub, (
        "Docstring is the unchanged stub; describe the chosen eviction strategy."
    )


def test_has_at_least_one_removal_operation():
    """A cache that NEVER removes anything cannot be bounded. We accept any
    of: `del self.x[...]`, `.pop(...)`, `.popitem(...)`, `.clear()`,
    `.remove(...)`, or `del self.x`."""
    cls = _class_ast()
    found = False
    for node in ast.walk(cls):
        if isinstance(node, ast.Delete):
            found = True
            break
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"pop", "popitem", "clear", "remove"}:
                found = True
                break
    assert found, (
        "cache.py contains no removal operation (del, pop, popitem, clear, "
        "remove). A bounded cache must remove entries when full."
    )


def test_no_environment_coupling():
    """The cache must not read process env, spawn subprocesses, or talk to
    the network. (random, time, collections, threading are all fine.)"""
    src = _module_source()
    tree = ast.parse(src)
    forbidden = {"os", "subprocess", "socket", "urllib", "http", "requests", "sys"}
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
        f"cache.py imports forbidden modules {bad}. The cache must be "
        "self-contained: no env, no subprocess, no network."
    )


def test_thread_safety_optional_but_consistent():
    """If the implementation instantiates a Lock/RLock/Semaphore, then BOTH
    `put` and `get` must use it (via `with self._lock:` or `.acquire()`).
    Pure single-threaded implementations skip this check entirely."""
    cls = _class_ast()
    src = _module_source()

    # Heuristic: did the agent actually construct a lock-like primitive?
    lock_constructors = {"Lock", "RLock", "Semaphore", "BoundedSemaphore", "Condition"}
    constructed = False
    for node in ast.walk(cls):
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name in lock_constructors and "threading" in src:
                constructed = True
                break
    if not constructed:
        pytest.skip("no lock constructed; thread safety check not applicable")

    def _uses_sync(method_name):
        m = _method_ast(method_name)
        for node in ast.walk(m):
            if isinstance(node, ast.With):
                return True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"acquire", "__enter__"}:
                    return True
        return False

    missing = [name for name in ("put", "get") if not _uses_sync(name)]
    assert not missing, (
        f"A lock is constructed but methods {missing} do not use any "
        "synchronization (with-block or .acquire()). Half-thread-safe code "
        "is worse than no thread-safety at all."
    )


# ---------------------------------------------------------------------------
# 4. Multi-put consistency
# ---------------------------------------------------------------------------

def test_many_puts_then_size():
    c = Cache(max_size=50)
    rng = random.Random(7)
    keys = [f"k{i}" for i in range(200)]
    for _ in range(1000):
        c.put(rng.choice(keys), rng.randint(0, 1_000_000))
    # Bounded by max_size AND by the number of distinct keys.
    assert c.size() <= 50
    assert c.size() <= 200


def test_put_then_overwrite_consistent():
    c = Cache(max_size=10)
    c.put("k", "v1")
    c.put("k", "v2")
    assert c.get("k") == "v2"
    assert c.size() == 1
