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
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: /private/tmp/imi-closer-deliverable-render-66.UCXVYW
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 13 items

tests/test_gate_commit_status_fork_tolerance.py FFFFFF.......            [100%]

=================================== FAILURES ===================================
________________ test_fork_read_only_403_does_not_fail_the_gate ________________

outcomes = {'fork_read_only': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, 'fork_read_only_failur...: [], ...}, 'fork_read_only_pending': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, ...}

    def test_fork_read_only_403_does_not_fail_the_gate(outcomes: dict[str, Any]) -> None:
>       assert outcomes["fork_read_only"]["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:251: AssertionError

_______________ test_fork_read_only_403_reports_the_real_verdict _______________

outcomes = {'fork_read_only': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, 'fork_read_only_failur...: [], ...}, 'fork_read_only_pending': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, ...}

    def test_fork_read_only_403_reports_the_real_verdict(outcomes: dict[str, Any]) -> None:
        case = outcomes["fork_read_only"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert "read-only" in warning
E       AssertionError: assert 'read-only' in ''

tests/test_gate_commit_status_fork_tolerance.py:259: AssertionError

______________ test_fork_read_only_403_preserves_failure_verdict _______________

outcomes = {'fork_read_only': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, 'fork_read_only_failur...: [], ...}, 'fork_read_only_pending': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, ...}

    def test_fork_read_only_403_preserves_failure_verdict(
        outcomes: dict[str, Any],
    ) -> None:
        case = outcomes["fork_read_only_failure"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:273: AssertionError

_ test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[error-runner errored] _

outcomes = {'fork_read_only': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, 'fork_read_only_failur...: [], ...}, 'fork_read_only_pending': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, ...}
state = 'error', description = 'runner errored'

    @pytest.mark.parametrize(
        ("state", "description"),
        [("error", "runner errored"), ("pending", "checks still pending")],
    )
    def test_fork_read_only_403_fails_closed_for_other_non_success_verdicts(
        outcomes: dict[str, Any], state: str, description: str
    ) -> None:
        case = outcomes[f"fork_read_only_{state}"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:292: AssertionError

_ test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[pending-checks still pending] _

outcomes = {'fork_read_only': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, 'fork_read_only_failur...: [], ...}, 'fork_read_only_pending': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, ...}
state = 'pending', description = 'checks still pending'

    @pytest.mark.parametrize(
        ("state", "description"),
        [("error", "runner errored"), ("pending", "checks still pending")],
    )
    def test_fork_read_only_403_fails_closed_for_other_non_success_verdicts(
        outcomes: dict[str, Any], state: str, description: str
    ) -> None:
        case = outcomes[f"fork_read_only_{state}"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:292: AssertionError

_____________ test_deleted_fork_read_only_403_reports_the_verdict ______________

outcomes = {'fork_read_only': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, 'fork_read_only_failur...: [], ...}, 'fork_read_only_pending': {'failures': [], 'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], ...}, ...}

    def test_deleted_fork_read_only_403_reports_the_verdict(
        outcomes: dict[str, Any],
    ) -> None:
        case = outcomes["deleted_fork_read_only"]
        warning = " ".join(case["warnings"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:304: AssertionError

=========================== short test summary info ============================
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_does_not_fail_the_gate
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_reports_the_real_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_preserves_failure_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[error-runner errored]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[pending-checks still pending]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_deleted_fork_read_only_403_reports_the_verdict
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

The required PR-base whitespace check also exited `0` with no output:

```bash
git diff --check origin/main...HEAD
```

Only this evidence document remains in the follow-up diff.
