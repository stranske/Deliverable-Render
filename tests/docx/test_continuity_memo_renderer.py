"""Continuity memo renderer tests."""

from pathlib import Path

from docx import Document

from deliverable_render.docx.memo import StructuredStore, render_continuity_memo

FIXTURE = Path("tests/fixtures/stores/consultant_change_minimal.json")


def test_continuity_memo_includes_governance_slice(tmp_path: Path) -> None:
    store = StructuredStore.from_json(FIXTURE)
    output = render_continuity_memo(store, tmp_path / "continuity.docx")
    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Governance" in text
    assert "Policy approved by committee." in text
    assert "Policy renewed without amendment." in text
