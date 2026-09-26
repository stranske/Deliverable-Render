# Issue #32 duplicate-scan deliberate-break verification

This transcript records a deliberate-break check against merged PR #35 and its
duplicate document identity regression test. The clean baseline was
`fd1a9eeea776b7fd3e710115254316a007f755ca` on `main`.

## Verification command

```bash
python3 -m pytest tests/store/test_communication_render_profile.py::test_validator_rejects_duplicate_document_identity -q --no-cov
```

The baseline and restored implementation both produced:

```text
collected 1 item
tests/store/test_communication_render_profile.py .                       [100%]
============================== 1 passed in 0.88s ===============================
```

## Deliberate break

I temporarily removed the duplicate branch in
`_document_identities`, replacing the guarded `report.fail(...)` / `else`
block with an unconditional `identities.add(identity)`. No production change
from this break was committed.

The same command then failed as required:

```text
collected 1 item
tests/store/test_communication_render_profile.py F                       [100%]

E       assert not True
E        +  where True = ValidationReport(issues=[]).valid

FAILED tests/store/test_communication_render_profile.py::test_validator_rejects_duplicate_document_identity
============================== 1 failed in 0.53s ===============================
```

This proves the named test observes the production duplicate scan rather than
passing through an unrelated fixture or assertion.

## Revert and cleanup proof

After restoring the implementation, the verification command passed again.
The following check then confirmed that the deliberate break left no source
change behind:

```bash
git diff --exit-code HEAD -- src/deliverable_render/store/validate.py
```

The cleanup check exited `0` with no output. Only this verification transcript
is intended to remain in the follow-up PR.
