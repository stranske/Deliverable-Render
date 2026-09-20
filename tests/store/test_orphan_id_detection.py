"""The documented mention q and explicit entry references must resolve."""

from pathlib import Path

from deliverable_render.store.validate import validate_store

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/stores/orphan_entry_id.json"


def test_mistyped_entry_id_fails_validation():
    report = validate_store(FIXTURE)
    assert not report.valid
    assert any(
        issue.code == "orphan-reference"
        and issue.path == "/entries/0/mentions/0/entry_id"
        and "entry-typo" in issue.message
        for issue in report.issues
    )


def test_mistyped_period_id_fails_validation(tmp_path):
    import json

    data = json.loads(FIXTURE.read_text())
    data["entries"][0]["mentions"][0]["entry_id"] = "entry-1"
    data["entries"][0]["mentions"][0]["q"] = "2025QX"
    path = tmp_path / "bad-period.json"
    path.write_text(json.dumps(data))
    report = validate_store(path)
    assert any(
        issue.path == "/entries/0/mentions/0/q" and issue.code == "orphan-reference"
        for issue in report.issues
    )
