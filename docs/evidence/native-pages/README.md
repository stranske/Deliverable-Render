# Native evidence page conversion — issue #77

Base: `b7fa6bd` (current remote main when the linked worktree was created).

Native `evidence-object/v1` locator pages remain zero-based during validation and
projection. The communication adapter creates one-based renderer pointers exactly
once. Compact legacy input remains one-based. The regression tests exercise native
pages 0/2 in mention and publication locations, with/without document provenance,
invalid negative/boolean/non-integer/missing values, repeated adaptation, input
preservation and the public HTML command. Existing public HTML/PPTX/DOCX legacy
fixtures preserve pages 3/4.

## Acceptance command

`python -m pytest tests/store/test_evidence_object_projection.py tests/store/test_communication_render_profile.py tests/test_render_html_offline.py -q -o addopts= --junitxml=docs/evidence/native-pages/focused-green.xml`

Run with the editable package and console scripts installed in the run's isolated
venv (system site packages provide test dependencies). **87 passed**, zero skips.
Raw stdout and JUnit: `focused-green.log` / `focused-green.xml`.

Full default gate: `python -m pytest --junitxml=docs/evidence/native-pages/full-green.xml`
returns **216 passed**, zero skips, **90.47% coverage**, satisfying the repository
80% coverage floor (`full-green.log` / `.xml`). The focused command without
`-o addopts=` passes its 87 tests but exits nonzero at 79.79% whole-package
coverage (`focused-default-coverage.log`); the issue command was clarified to
distinguish regression selection from the full coverage gate. No acceptance
behavior or full-suite coverage policy was waived.

The new native-page regressions against the unmodified base implementation produced
**6 assertion/validation failures and 2 passes** (`original-red.log` / `.xml`).

## Independent production mutations

`mutations.json` records each exact source replacement, command, exit status and
original/restored source hash. Each source file was restored byte-for-byte in a
finally block before its passing rerun; final source hashes are independently
listed in `sha256.json`.

- Remove the adapter's native `page + 1` conversion: **4 failed**;
  byte-identical restoration: **4 passed**.
- Restore the validator's one-based minimum for native inputs: **2 failed,
  2 passed**; byte-identical restoration: **4 passed**.

Each pair has raw `.log` and JUnit `.xml` receipts. No mutation remains in the diff.

Focused Ruff and Black checks pass. Mypy on the two edited production modules
passes with `--disable-error-code unused-ignore`; the unadjusted local command
reports the existing jsonschema import's now-unused `import-untyped` ignore
because this local environment supplies type information. That import was not
changed. This is bounded local acceptance proof; hosted checks, provider review,
and native PDF viewer navigation are not established by these receipts.
