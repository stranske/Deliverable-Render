# Issue #61 no-renderable-content deliberate-break evidence

This transcript closes the D4 verification-evidence gap recorded in issue #61
for the implementation merged by PR #60 (`dbf75a7d5b1b`). The experiment ran on
2026-09-28 at `10a883918f0795d4c5196fda6328c099c5d52982`, the exact fresh
`origin/main` baseline used for the unmodified gate.

## Gate

```bash
python3 -m pytest \
  tests/store/test_communication_render_profile.py::test_blank_unsourced_mention_is_skipped \
  -q --no-cov
```

Before the deliberate break, the full focused test file also passed:

```text
collected 50 items
tests/store/test_communication_render_profile.py ....................... [ 46%]
...........................                                              [100%]
50 passed in 1.72s
```

## Deliberate break

I temporarily removed only the final `if not has_renderable_content` block in
`src/deliverable_render/store/validate.py`. That block emits the
`no-renderable-content` issue at `/entries`. No production change from this
break was committed.

The named gate then failed as required:

```text
tests/store/test_communication_render_profile.py F                       [100%]

>       assert any(
            issue.code == "no-renderable-content" and issue.path == "/entries"
            for issue in report.issues
        )
E       assert False

FAILED tests/store/test_communication_render_profile.py::test_blank_unsourced_mention_is_skipped
1 failed in 0.62s
```

This failure proves that the named regression test observes the production
guard and its exact issue-code/path contract.

## Revert and cleanup proof

After restoring the guard exactly, the same named command passed:

```text
tests/store/test_communication_render_profile.py .                       [100%]
1 passed in 0.51s
```

The cleanup check below exited `0` with no output, proving that the temporary
production mutation was fully reverted:

```bash
git diff --exit-code HEAD -- src/deliverable_render/store/validate.py
```

Only this durable verification transcript remains in the follow-up change.
