Implement `merge_configs(configs, strategy)` in `merger.py`.

You get a list of dicts (`configs`). Configs later in the
list take priority over earlier ones. Handling of nested dicts is
your call: recursive merge? full replacement? specific rule for
lists? **Pick a reasonable strategy** and document it in the
docstring of `merge_configs`.

API:

- `merge_configs(configs: list[dict], strategy: str = "default") -> dict`
  returns a new dict, the result of the merge. `configs == []` returns
  `{}`. The `strategy` parameter is a hint — you can support
  just one (`"default"`) or expose several named ones.

Expected invariants:

- Configs passed as arguments are never mutated (neither at top-level,
  nor inside sub-dicts).
- The merge does not invent keys that didn't exist in any config.
- When the same key appears multiple times at top-level, the last
  value wins, at least for that level.

Constraints:

- Python stdlib only. No `deepmerge`, `mergedeep`, etc.
- No files to read: the function already receives dicts in memory.
  No `open()`, no network, no subprocess.
- No global side effects (no module-level variable modified by
  the function, no `print` outside an `if __name__ == "__main__"`).
- No `eval` / `exec` / `compile` / `__import__`.

The `samples/` folder contains a few example configs for
reference — you don't need to parse them, they're just to illustrate
the kind of structures we merge in practice.

Do not modify `test_merger.py`.
