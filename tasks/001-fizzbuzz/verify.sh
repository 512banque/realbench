#!/usr/bin/env bash
# Exits 0 if the task is solved, non-zero otherwise.
# 2 = test file was modified (tampering).
set -e
cd "$(dirname "$0")"

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/test_solution.py | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test file modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace
exec python3 -m pytest test_solution.py -q
