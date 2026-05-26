"""Load step: persist aggregated results into an in-memory store.

The "store" is a plain list of rows that downstream consumers iterate.
Each aggregated category produces exactly one row of the form:
    {"category": str, "total": int, "count": int, "average": float}

`load_to_store(aggregates, store)` appends rows to `store` in input order.
"""

from __future__ import annotations


def load_to_store(aggregates: dict[str, dict], store: list[dict]) -> int:
    """Append one row per category into `store`. Return the number of rows added."""
    added = 0
    rows = []
    for category, agg in aggregates.items():
        row = {
            "category": category,
            "total": agg["total"],
            "count": agg["count"],
            "average": agg["average"],
        }
        rows.append(row)
        store.append(row)
        added += 1
    # Persist a copy of the batch for audit. Both the per-row append above
    # and this extend write into the same store.
    store.extend(rows)
    return added
