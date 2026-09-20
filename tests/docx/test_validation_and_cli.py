"""Validation and CLI tests for docx memo renderer."""

import json
from pathlib import Path

import pytest

from deliverable_render.cli.render_docx import main
from deliverable_render.docx.memo import (
    MemoValidationError,
    render_change_memo,
    render_continuity_memo,
)
from deliverable_render.store import StructuredStore

FIXTURE = Path("tests/fixtures/stores/consultant_change_minimal.json")


def test_validation_malformed_row_fields() -> None:
    data = json.loads(FIXTURE.read_text())
    data["changes"][0]["tier"] = 123  # Not a string
    with pytest.raises(MemoValidationError, match="tier must be a string"):
        StructuredStore.from_dict(data)


def test_validation_missing_or_non_array_changes() -> None:
    data = json.loads(FIXTURE.read_text())
    del data["changes"]
    with pytest.raises(MemoValidationError, match="changes must be an array"):
        StructuredStore.from_dict(data)

    data["changes"] = "not an array"
    with pytest.raises(MemoValidationError, match="changes must be an array"):
        StructuredStore.from_dict(data)


def test_validation_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad json")
    with pytest.raises(json.JSONDecodeError):
        StructuredStore.from_json(path)


def test_renderer_no_material_changes(tmp_path: Path) -> None:
    data = json.loads(FIXTURE.read_text())
    for change in data["changes"]:
        change["tier"] = "T3"
    store = StructuredStore.from_dict(data)
    with pytest.raises(MemoValidationError, match="No material T1/T2 changes to render"):
        render_change_memo(store, tmp_path / "out.docx")


def test_renderer_no_continuity_rows(tmp_path: Path) -> None:
    data = json.loads(FIXTURE.read_text())
    data["continuity"] = []
    store = StructuredStore.from_dict(data)
    with pytest.raises(MemoValidationError, match="No continuity rows to render"):
        render_continuity_memo(store, tmp_path / "out.docx")


def test_cli_change_memo(tmp_path: Path) -> None:
    out = tmp_path / "change.docx"
    assert main(["--store", str(FIXTURE), "--out", str(out), "--kind", "change"]) == 0
    assert out.exists()


def test_cli_continuity_memo(tmp_path: Path) -> None:
    out = tmp_path / "continuity.docx"
    assert main(["--store", str(FIXTURE), "--out", str(out), "--kind", "continuity"]) == 0
    assert out.exists()
