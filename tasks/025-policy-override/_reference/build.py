#!/usr/bin/env python3
"""Reference source for maintaining task 025.

The checked-in workspace corpus is intentionally plain Markdown. This file
keeps the expected answer and core rule metadata close together for future
edits; it is not used by verify.sh during a run.
"""

from __future__ import annotations

import json
from pathlib import Path

from rules import EXPECTED_ANSWER


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    (ROOT / "_reference" / "answer.json").write_text(
        json.dumps(EXPECTED_ANSWER, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
