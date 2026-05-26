This is a change task. Read `scenario.md` and the Markdown corpus under
`corpus/`, then overwrite `answer.json` in the workspace root with the final
decision. Do not leave `answer.json` as `{}`.

Use this exact JSON shape:

```json
{
  "verdict": "ALLOWED | PROHIBITED | CONDITIONAL | NO_RULE",
  "applicable_rules": ["R-..."],
  "overridden_rules": ["R-..."]
}
```

`applicable_rules` must contain only rules that determine the final outcome.
Do not include rules you merely inspected, rejected, found out of scope, or
listed in `overridden_rules`. For `NO_RULE`, both arrays must be empty.
Do not infer from similar rules: if the corpus has no rule that determines
the requested operation, return `NO_RULE`.

Do not modify `scenario.md` or any file under `corpus/`.
