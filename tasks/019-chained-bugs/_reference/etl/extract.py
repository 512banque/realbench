"""Extract step: read raw CSV rows from disk into typed records.

Input format (CSV with header):
    category,name,value
    fruit,apple,3
    fruit,banana,5
    veggie,carrot,2

Returns a list of dicts: [{"category": ..., "name": ..., "value": int|None}, ...]
A value of "" (empty cell) is parsed as None — represents a missing measurement.
"""

from __future__ import annotations

from pathlib import Path


def extract_csv(path: str | Path) -> list[dict]:
    text = Path(path).read_text()
    lines = text.split("\n")
    records: list[dict] = []
    # skip header
    for line in lines[1:]:
        # Skip blank lines (trailing newline at EOF produces one).
        if not line.strip():
            continue
        parts = line.split(",")
        category = parts[0].strip()
        name = parts[1].strip()
        raw_value = parts[2].strip()
        value = int(raw_value) if raw_value else None
        records.append({"category": category, "name": name, "value": value})
    return records
