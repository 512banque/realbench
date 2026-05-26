Fix a bug in the real Caddy web server codebase.

This task is calibrated against a real upstream pull request
(https://github.com/caddyserver/caddy/pull/6429), pinned at the
parent commit `f8861ca16bd475e8519e7dbf5a2b55e81b329874`.

The workspace ships a `setup.sh` you must run first to fetch the
codebase (shallow clone of caddyserver/caddy at the pinned SHA). It
also installs a regression test that is currently failing because of
the bug.

Steps:

1. From the current directory, run `./setup.sh`. It clones the
   pinned revision into `./caddy/` and copies a regression test in
   place (`caddy/caddytest/integration/intercept_test.go`).
2. Reproduce the failure:
   `cd caddy && go test ./caddytest/integration/ -run TestIntercept -timeout 60s`
3. Diagnose. The test expects the response header `intercepted` to
   equal `ok`, taken from an upstream header `To-Intercept` via the
   placeholder `{resp.header.To-Intercept}`. It's empty instead.
4. Fix the bug. It's a one-line change in
   `caddy/modules/caddyhttp/intercept/intercept.go`. Do **not**
   modify the test file.
5. Re-run the test to confirm it passes.

The bug is in production code, not in the test. The test file is
hash-protected; modifying it will fail the verifier.
