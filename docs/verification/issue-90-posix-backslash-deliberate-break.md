# Issue #90 POSIX backslash deliberate-break evidence

This transcript closes the deliberate-break acceptance criterion for issue #90 /
PR #96. The experiment ran on 2026-10-17 against
`1529dc742a0d4b7de8628fd9de9aa2c170632c9e` on branch
`cursor/issue-90-preserve-posix-backslashes`.

## Gate

```bash
pytest tests/test_html.py::test_posix_path_renders_a_usable_file_uri --no-cov -q
```

## Deliberate break

Temporarily replaced the fixed `_url_path` in `src/deliverable_render/html.py`
with the pre-fix body from `b7a0cb591bd3c7240d7a7db966476a47cfe4fa4e`, which
always runs `raw.replace("\\", "/")` before Windows-drive detection. No
production change from this break was committed.

The named gate then failed as required on the literal POSIX backslash href:

```text
tests/test_html.py F                                                     [100%]

>       assert f'<a href="{expected_href}">doc2</a>' in output_bs
E       assert '<a href="file:///synthetic/a%5Cb.pdf#page=3">doc2</a>' in '...'

FAILED tests/test_html.py::test_posix_path_renders_a_usable_file_uri
1 failed in 0.07s
```

That failure proves the regression observes the described defect: the broken
normaliser turns `/synthetic/a\b.pdf` into a directory separator path instead of
`file:///synthetic/a%5Cb.pdf#page=3`.

## Revert and cleanup proof

After restoring `_url_path` exactly, the same named command passed:

```text
tests/test_html.py .                                                     [100%]
1 passed in 0.03s
```

The cleanup check exited `0` with no output:

```bash
git diff --exit-code HEAD -- src/deliverable_render/html.py
```
