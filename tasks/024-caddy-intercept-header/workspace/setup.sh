#!/usr/bin/env bash
# Fetch the Caddy codebase at the pinned commit and install the
# regression test that exposes the bug. Run from the workspace dir.
#
# Pinned at parent SHA of https://github.com/caddyserver/caddy/pull/6429.
# We use a shallow `git fetch <sha>` instead of a full clone — GitHub
# allows fetching reachable SHAs from depth 1, so this pulls ~5 MB.
set -euo pipefail

SHA="f8861ca16bd475e8519e7dbf5a2b55e81b329874"
HERE="$(cd "$(dirname "$0")" && pwd)"

cd "$HERE"

if [ -d caddy/.git ]; then
  echo "caddy/ already initialised, skipping clone."
else
  mkdir -p caddy
  cd caddy
  git init --quiet
  git remote add origin https://github.com/caddyserver/caddy.git
  echo "Fetching caddyserver/caddy@${SHA} (shallow)..."
  git fetch --depth 1 --quiet origin "${SHA}"
  git checkout --quiet FETCH_HEAD
  cd "$HERE"
fi

# Install the regression test on top of the codebase. The test ships in
# this workspace and is hash-protected by the realbench runner.
cp intercept_test.go caddy/caddytest/integration/intercept_test.go

echo "Setup complete. Reproduce the failure with:"
echo "  cd caddy && go test ./caddytest/integration/ -run TestIntercept -timeout 60s"
