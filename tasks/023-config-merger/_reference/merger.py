import copy


def merge_configs(configs, strategy="default"):
    """Merge a list of config dicts left-to-right with deep recursive
    semantics.

    For each key conflict:
      - If both sides hold a dict, recurse into them so nested keys
        merge rather than wholly replace.
      - Otherwise the later value wins (override). Lists, scalars and
        None values are replaced, never concatenated.

    Inputs are never mutated; the result is a fresh dict and every
    nested container is also a fresh copy. The `strategy` argument is
    accepted for API compatibility but only "default" / "deep" are
    honored here.
    """
    if strategy not in ("default", "deep"):
        raise ValueError(f"unsupported strategy: {strategy!r}")

    result = {}
    for cfg in configs:
        if not isinstance(cfg, dict):
            raise TypeError("each config must be a dict")
        _deep_merge_into(result, cfg)
    return result


def _deep_merge_into(target, source):
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge_into(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
