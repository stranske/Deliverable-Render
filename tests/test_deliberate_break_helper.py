"""Regression coverage for the reviewed assertion replacement exception."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import check_deliberate_break
from scripts.check_deliberate_break import _assertion_diff_lines

OLD = "assert validate_store(without_page).valid  # validator allows document-only citations"
NEW = "assert not validate_store(without_page).valid"


def test_approved_assertion_replacement_requires_same_hunk() -> None:
    diff = f"@@ -1 +1 @@\n-{OLD}\n+{NEW}\n"
    assert list(_assertion_diff_lines(diff, (OLD, NEW))) == []

    split = f"@@ -1 +1 @@\n-{OLD}\n@@ -8 +8 @@\n+{NEW}\n"
    assert list(_assertion_diff_lines(split, (OLD, NEW))) == [f"-{OLD}"]


def test_approved_assertion_replacement_cannot_cover_second_removal() -> None:
    diff = f"@@ -1,2 +1 @@\n-{OLD}\n-{OLD}\n+{NEW}\n"
    assert list(_assertion_diff_lines(diff, (OLD, NEW))) == [f"-{OLD}"]


def test_unmatched_pr_metadata_has_no_assertion_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    diff = f"@@ -1 +1 @@\n-{OLD}\n+{NEW}\n"
    monkeypatch.setenv("GITHUB_REPOSITORY", "stranske/Deliverable-Render")
    monkeypatch.setattr(
        check_deliberate_break,
        "_git",
        lambda args, cwd: (
            SimpleNamespace(stdout="M\ttests/store/test_communication_render_profile.py\n")
            if "--name-status" in args
            else SimpleNamespace(stdout=diff)
        ),
    )
    removed = check_deliberate_break._changed_assertions(
        "base",
        "head",
        "tests/store/test_communication_render_profile.py",
        tmp_path,
        "<!-- meta:issue:999 -->",
    )
    assert removed == [f"-{OLD}"]
