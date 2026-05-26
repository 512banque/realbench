"""Transform step: aggregate extracted records per category.

Input: list of dicts {"category", "name", "value"} (value may be None).
Output: dict {category: {"total": int, "count": int, "average": float}}
- total: sum of non-None values
- count: number of non-None values
- average: total / count (rounded to 4 decimals); 0.0 if count == 0
"""

from __future__ import annotations

from collections import defaultdict


def aggregate(records: list[dict]) -> dict[str, dict]:
    groups: dict[str, list[int]] = defaultdict(list)
    for r in records:
        v = r["value"]
        if v is not None:
            groups[r["category"]].append(v)

    out: dict[str, dict] = {}
    for category, values in groups.items():
        n = len(values)
        total = sum(values)
        average = total / n if n > 0 else 0.0
        out[category] = {
            "total": total,
            "count": n,
            "average": round(average, 4),
        }
    return out
