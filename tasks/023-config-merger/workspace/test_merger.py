"""
Tests for the ambiguous config-merger task (task 023).

Design intent: the merge semantics for *nested* values are NOT specified.
Deep recursive merge, full-replacement, list-concat, strategy-via-param,
etc. are all acceptable. The tests check:

    1. Functional minimum: empty list, single config, top-level
       override, key union, three-way order, idempotency,
       associativity at the top level, no fabricated keys.
    2. Nested-merge polymorphism: when a key holds a dict on both sides,
       either deep-merge OR replace is accepted. The test only pins the
       value that any reasonable implementation must yield.
    3. Strong purity invariant: input configs are never mutated.
    4. Anti-pattern structural checks:
        - real docstring (>= 40 significant chars) mentioning at least
          one merge-related keyword
        - no eval/exec/compile/__import__
        - no IO / network / OS coupling
        - no module-level mutation by merge_configs (no `global`, no
          assignment to a module-level name from inside the function)

Things we deliberately DO NOT check:
    - Which exact value wins for a nested dict (deep vs replace).
    - The internal algorithm (recursive call, stack, reduce, ...).
    - The behavior of `strategy` other than `"default"`.
"""

import ast
import copy
import inspect
import re

import pytest

import merger as merger_module
from merger import merge_configs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _module_source():
    return inspect.getsource(merger_module)


def _module_ast():
    return ast.parse(_module_source())


def _function_ast(name):
    for node in ast.walk(_module_ast()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found in merger.py")


# ---------------------------------------------------------------------------
# 1. Functional minimum
# ---------------------------------------------------------------------------

def test_empty_list_returns_empty_dict():
    assert merge_configs([]) == {}


def test_single_config_returns_equivalent_dict():
    assert merge_configs([{"a": 1}]) == {"a": 1}


def test_later_overrides_earlier_at_top_level():
    assert merge_configs([{"a": 1}, {"a": 2}]) == {"a": 2}


def test_keys_from_different_configs_combined():
    assert merge_configs([{"a": 1}, {"b": 2}]) == {"a": 1, "b": 2}


def test_three_way_merge_order_preserved():
    assert merge_configs([{"k": 1}, {"k": 2}, {"k": 3}]) == {"k": 3}


# ---------------------------------------------------------------------------
# 2. Nested-merge polymorphism (deep merge OR replace both accepted)
# ---------------------------------------------------------------------------

def test_nested_dict_port_always_updated():
    """Whichever strategy is used, the newer value of a leaf key in a
    nested dict must win. We assert ONLY the newer leaf; whether the
    older sibling `host` is preserved (deep merge) or dropped (replace)
    is up to the implementation."""
    result = merge_configs([
        {"db": {"host": "h1", "port": 5432}},
        {"db": {"port": 5433}},
    ])
    assert isinstance(result.get("db"), dict)
    assert result["db"]["port"] == 5433
    # Accept BOTH deep-merge (host preserved) and replace (host dropped).
    assert result["db"].get("host") in (None, "h1")


# ---------------------------------------------------------------------------
# 3. Invariants every reasonable implementation must satisfy
# ---------------------------------------------------------------------------

def test_does_not_mutate_input_configs():
    """STRONG invariant. The caller's dicts must not be mutated at any
    level. We deep-copy a snapshot before the call and compare after."""
    configs = [
        {"a": 1, "nested": {"x": 1, "y": [1, 2]}},
        {"a": 2, "nested": {"y": [3, 4], "z": 9}},
    ]
    snapshot = copy.deepcopy(configs)
    merge_configs(configs)
    assert configs == snapshot, "merge_configs mutated its input list/dicts"


def test_idempotent_on_same_config():
    cfg = {"a": 1, "nested": {"x": 1}}
    assert merge_configs([cfg, cfg]) == merge_configs([cfg])


def test_associative_at_top_level():
    """At the top level, (a,b,c) == ((a,b),c). We only check shared
    top-level keys; nested-merge semantics may differ between calls of
    different shape, which is fine."""
    a = {"k1": 1, "k2": 1}
    b = {"k2": 2, "k3": 2}
    c = {"k3": 3, "k4": 4}
    left = merge_configs([a, b, c])
    right = merge_configs([merge_configs([a, b]), c])
    assert set(left.keys()) == set(right.keys())
    for k in left.keys():
        # Non-dict leaves must match exactly. Dict leaves: skip — left
        # and right may differ if the impl deep-merges, that's fine.
        if not isinstance(left[k], dict):
            assert left[k] == right[k], f"top-level key {k!r} differs"


def test_no_unexpected_keys():
    """The result must not contain a key that was in NONE of the input
    configs."""
    a = {"x": 1}
    b = {"y": 2}
    result = merge_configs([a, b])
    union = set(a.keys()) | set(b.keys())
    extra = set(result.keys()) - union
    assert not extra, f"merge fabricated keys not in any input: {extra}"


# ---------------------------------------------------------------------------
# 4. Structural anti-pattern checks
# ---------------------------------------------------------------------------

_MERGE_KEYWORDS = (
    "merge", "override", "overrides", "overriding",
    "deep", "shallow", "recursive", "recurse",
    "replace", "replaces", "replacement",
    "wins", "win", "priority", "precedence",
    "later", "last",
)


def test_docstring_explains_strategy():
    """`merge_configs` must carry a real docstring of at least 40
    significant characters and must mention at least one merge-related
    keyword. The stub docstring is rejected explicitly."""
    fn = _function_ast("merge_configs")
    doc = ast.get_docstring(fn) or ""
    sig = re.sub(r"\s+", " ", doc).strip()
    stub = "TODO: document your strategy here."
    assert sig != stub, "Docstring is the unchanged stub; document the chosen strategy."
    assert len(sig) >= 40, (
        f"merge_configs docstring must be >= 40 significant characters; got {len(sig)}."
    )
    lowered = sig.lower()
    assert any(kw in lowered for kw in _MERGE_KEYWORDS), (
        "Docstring must mention at least one merge-related keyword "
        f"(any of {list(_MERGE_KEYWORDS)})."
    )


def test_no_eval_or_exec():
    src = _module_source()
    for pattern in ("eval(", "exec(", "compile(", "__import__("):
        assert pattern not in src, f"forbidden construct {pattern!r} in merger.py"


def test_no_external_io():
    """merge_configs receives dicts in memory. No file IO, no network,
    no subprocess, no parsing of JSON/YAML files."""
    tree = _module_ast()
    forbidden = {
        "os", "subprocess", "socket", "urllib", "http", "requests",
        "json", "yaml", "pathlib", "shutil",
    }
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
    assert not bad, f"merger.py imports forbidden modules {bad}"
    # No top-level open() either.
    src = _module_source()
    assert "open(" not in src, "merger.py must not call open()"


def test_no_global_mutation_inside_merge_configs():
    """merge_configs must not declare `global` nor reassign a module-level
    name from inside its body. This kills the 'accumulator-in-module-state'
    anti-pattern."""
    module_level_names = set()
    for node in _module_ast().body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    module_level_names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            module_level_names.add(node.target.id)

    fn = _function_ast("merge_configs")
    param_names = {a.arg for a in fn.args.args}
    local_names = set(param_names)
    for node in ast.walk(fn):
        if isinstance(node, ast.Global):
            raise AssertionError(
                "merge_configs declares `global`; module-level state mutation is forbidden."
            )
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    local_names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            local_names.add(node.target.id)

    # Now check: any plain Name target assignment inside the function whose
    # target collides with a module-level name AND wasn't re-locally bound
    # before any such assignment is suspicious. We use a loose rule: if the
    # function assigns to a name that is ALSO module-level and never used
    # as a local-only variable elsewhere, fail.
    suspicious = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in module_level_names:
                    suspicious.append(tgt.id)
    assert not suspicious, (
        f"merge_configs assigns to module-level name(s) {suspicious}; "
        "use local variables only."
    )
