# Issue #65 / PR #63 deliberate-break evidence

This is a fresh replay on current `main`, not reconstructed historical output
from PR #63. The replay ran on 2026-09-29 at exact base
`a8c9f582999690f18e7999647d6fe515144278a8`.

## Baseline

```bash
uv run pytest -q tests/test_gate_commit_status_fork_tolerance.py --no-cov
```

```text
collected 13 items

tests/test_gate_commit_status_fork_tolerance.py .............            [100%]

============================== 13 passed in 0.42s ==============================
```

## Deliberate break

Only the production `readOnlyForkToken` predicate in
`.github/workflows/pr-00-gate.yml` was temporarily replaced with `false`:

```diff
-              const readOnlyForkToken =
-                error?.status === 403 && isForkPullRequest && !hitRateLimit;
+              const readOnlyForkToken = false;
```

The exact named command then exited `1`:

```bash
uv run pytest -q tests/test_gate_commit_status_fork_tolerance.py --no-cov
```

```text
collected 13 items

tests/test_gate_commit_status_fork_tolerance.py FFFFFF.......            [100%]

=================================== FAILURES ===================================
________________ test_fork_read_only_403_does_not_fail_the_gate ________________
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

_______________ test_fork_read_only_403_reports_the_real_verdict _______________
E       AssertionError: assert 'read-only' in ''

______________ test_fork_read_only_403_preserves_failure_verdict _______________
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

_ test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[error-runner errored] _
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

_ test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[pending-checks still pending] _
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

_____________ test_deleted_fork_read_only_403_reports_the_verdict ______________
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

========================= 6 failed, 7 passed in 0.43s ==========================
```

The six failures name the fork and deleted-fork contracts while the seven
same-repository, rate-limit, unrelated-error, and successful-write cases remain
passing. This shows the focused harness observes the production predicate.

## Exact restoration and cleanup

After restoring the two production lines exactly, the same command exited `0`:

```bash
uv run pytest -q tests/test_gate_commit_status_fork_tolerance.py --no-cov
```

```text
collected 13 items

tests/test_gate_commit_status_fork_tolerance.py .............            [100%]

============================== 13 passed in 0.36s ==============================
```

The cleanup command exited `0` with no output:

```bash
git diff --exit-code HEAD -- \
  .github/workflows/pr-00-gate.yml \
  tests/test_gate_commit_status_fork_tolerance.py
```

Only this evidence document remains in the follow-up diff.
