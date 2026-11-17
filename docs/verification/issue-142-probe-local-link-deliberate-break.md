# Issue #142 probe local-link deliberate-break evidence

This transcript closes the deliberate-break acceptance criterion for issue #142 /
PR #143. The experiment ran on 2026-11-17 against branch `cursor/issue-142` with
restored `openLocalLinkCheck` behavior at `HEAD` after the check below.

## Gate

```bash
python3 -m pytest tests/test_probe_offline_and_minimal.py::test_local_link_handle_alone_is_not_pass --no-cov -q
```

## Deliberate break

Temporarily changed `openLocalLinkCheck` in `src/deliverable_render/probe/build_probe.py`
so that a truthy `window.open` handle sets `link=pass` immediately (reverting the
operator-confirmation requirement). This break was applied only in the local
working tree and was **not** committed.

The named gate then failed as required:

```text
tests/test_probe_offline_and_minimal.py F                                [100%]

>       assert with_handle["results"]["link"] == "unverified"
E       AssertionError: assert 'pass' == 'unverified'

FAILED tests/test_probe_offline_and_minimal.py::test_local_link_handle_alone_is_not_pass
1 failed in 0.06s
```

That failure proves the regression would again treat a popup handle alone as pass.

## Revert and cleanup proof

After restoring `setResult("link", "unverified")` for the handle-only path, the
same named command passed:

```text
tests/test_probe_offline_and_minimal.py .                                [100%]
1 passed in 0.07s
```

The cleanup check exited `0` with no output:

```bash
git diff --exit-code HEAD -- src/deliverable_render/probe/build_probe.py
```

## Re-verification (keepalive 2/12)

Re-ran the uncommitted handle-only `link=pass` break on 2026-11-17 (local worktree,
branch `cursor/issue-142`). `test_local_link_handle_alone_is_not_pass` failed with
`assert 'pass' == 'unverified'`; after revert, the same test passed with `--no-cov`
and `build_probe.py` matched `HEAD` (`git diff --exit-code` exit 0).

Note: the acceptance-criteria `python3 -m pytest … -q` commands (without `--no-cov`)
report a coverage fail-under exit code when only the probe test module runs locally;
CI runs the full suite and exits 0.