#!/usr/bin/env bash
# Verify task 024-caddy-intercept-header.
# Exits 0 if the fix is in place and `go test` passes; non-zero otherwise.
#   2   = test fixture (workspace/intercept_test.go) modified — tampering.
#   3   = setup not run, no caddy/ checkout to test.
#   4   = caddy/ checked out at the wrong commit.
#   5   = installed test file modified inside caddy/ — tampering.
#   127 = `go` toolchain missing.
set -u
cd "$(dirname "$0")"

# 1. Anti-tamper on the test fixture stored in workspace/.
if [ -f .test_hash ]; then
  current=$(shasum -a 256 workspace/intercept_test.go | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: workspace/intercept_test.go modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace

# 2. The agent must have run ./setup.sh to materialise the codebase.
if [ ! -d caddy/.git ]; then
  echo "verify: caddy/ checkout missing — did the agent run ./setup.sh?" >&2
  exit 3
fi

# 3. The checkout must be at the pinned SHA (no funny `git checkout main`).
expected_sha="f8861ca16bd475e8519e7dbf5a2b55e81b329874"
actual_sha=$(cd caddy && git rev-parse HEAD)
if [ "$actual_sha" != "$expected_sha" ]; then
  echo "verify: caddy at $actual_sha, expected $expected_sha" >&2
  exit 4
fi

# 4. The installed test file inside caddy/ must match the fixture too —
#    extra layer in case the agent edited the in-tree copy.
fixture_hash=$(shasum -a 256 intercept_test.go | awk '{print $1}')
installed_hash=$(shasum -a 256 caddy/caddytest/integration/intercept_test.go | awk '{print $1}')
if [ "$fixture_hash" != "$installed_hash" ]; then
  echo "verify: caddy/caddytest/integration/intercept_test.go diverges from fixture" >&2
  exit 5
fi

# 5. Toolchain check.
command -v go >/dev/null 2>&1 || { echo "verify: 'go' not on PATH" >&2; exit 127; }

# 6. Run the integration test. -count=1 disables go test caching.
cd caddy
exec go test ./caddytest/integration/ -run TestIntercept -timeout 60s -count=1
