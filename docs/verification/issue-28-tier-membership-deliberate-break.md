# Issue #28 tier-membership deliberate-break evidence

This transcript closes the verification-evidence gap recorded in issue #44 for
the implementation merged by PR #34 (`4b8b73d52c76`). The experiment ran on
2026-09-26 at `fd1a9ee9d18bcbf2064a586afc4eff1e73d12694`. That revision was also the
exact `origin/main` baseline used for the unmodified gate, which passed both
named tests (`2 passed`).

## Gate

```bash
python3 -m pytest \
  tests/docx/test_validation_and_cli.py::test_validation_rejects_unknown_tier_before_render \
  tests/docx/test_validation_and_cli.py::test_cli_rejects_unknown_tier_without_writing_output \
  -q --no-cov
```

The unmodified implementation passed:

```text
collected 2 items
tests/docx/test_validation_and_cli.py ..                                 [100%]
2 passed in 0.84s
```

## Deliberate break

The temporary mutation in `ChangeRow.__post_init__` replaced the membership
guard with the type-only validation below:

```diff
-        tier = _string(self.tier, "tier")
-        if tier not in MATERIALITY_TIERS:
-            allowed = ", ".join(sorted(MATERIALITY_TIERS))
-            raise StoreValidationError(f"tier must be one of {allowed}; got {tier!r}")
+        _string(self.tier, "tier")
```

The same command then failed both named gates:

```text
tests/docx/test_validation_and_cli.py FF                                 [100%]

FAILED tests/docx/test_validation_and_cli.py::test_validation_rejects_unknown_tier_before_render
E   Failed: DID NOT RAISE StoreValidationError

FAILED tests/docx/test_validation_and_cli.py::test_cli_rejects_unknown_tier_without_writing_output
E   AssertionError: assert 0 == 2

2 failed in 0.43s
```

## Revert proof

After restoring the membership guard, the same command passed again:

```text
collected 2 items
tests/docx/test_validation_and_cli.py ..                                 [100%]
2 passed in 0.35s
```

`git diff --exit-code HEAD -- src/deliverable_render/store/__init__.py` also passed,
proving that the temporary production mutation was fully reverted.
