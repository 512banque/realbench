#!/usr/bin/env bash
# Toolchain: Python >= 3.10
# Exit codes:
#   0   = success
#   1   = answer missing/malformed/incorrect
#   2   = protected input file was tampered with
#   127 = python3 not found
set -u
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "verify: python3 not found on PATH" >&2
  exit 127
fi

python3 - <<'PY'
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
PROTECTED = [
    "workspace/scenario.md",
    "workspace/corpus/INDEX.md",
    "workspace/corpus/R-025-001.md",
    "workspace/corpus/R-025-004.md",
    "workspace/corpus/R-025-006.md",
    "workspace/corpus/R-025-009.md",
    "workspace/corpus/R-025-012.md",
    "workspace/corpus/R-025-018.md",
    "workspace/corpus/R-025-021.md",
]
EXPECTED_HASH = (ROOT / ".test_hash").read_text(encoding="utf-8").strip()


def digest(paths):
    h = hashlib.sha256()
    for rel in paths:
        p = ROOT / rel
        h.update(rel.encode("utf-8") + b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


if digest(PROTECTED) != EXPECTED_HASH:
    print("verify: protected input modified (hash mismatch)", file=sys.stderr)
    sys.exit(2)

expected = {
    "verdict": "ALLOWED",
    "applicable_rules": ["R-025-004", "R-025-009"],
    "overridden_rules": ["R-025-006"],
}

answer_path = ROOT / "workspace" / "answer.json"
try:
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    print("verify: workspace/answer.json missing", file=sys.stderr)
    sys.exit(1)
except json.JSONDecodeError as exc:
    print(f"verify: workspace/answer.json is not valid JSON: {exc}", file=sys.stderr)
    sys.exit(1)

if set(answer) != set(expected):
    print(f"verify: answer keys mismatch: got {sorted(answer)}, expected {sorted(expected)}", file=sys.stderr)
    sys.exit(1)

for key in ("applicable_rules", "overridden_rules"):
    if sorted(answer.get(key, [])) != sorted(expected[key]):
        print(f"verify: {key} mismatch: got {answer.get(key)!r}, expected {expected[key]!r}", file=sys.stderr)
        sys.exit(1)

if answer.get("verdict") != expected["verdict"]:
    print(f"verify: verdict mismatch: got {answer.get('verdict')!r}, expected {expected['verdict']!r}", file=sys.stderr)
    sys.exit(1)

sys.exit(0)
PY
