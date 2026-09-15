"""Change memo renderer tests."""

from pathlib import Path

from docx import Document

from deliverable_render.docx.memo import StructuredStore, render_change_memo

FIXTURE = Path("tests/fixtures/stores/consultant_change_minimal.json")


def _paragraph_text(path: Path) -> str:
    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def test_change_memo_includes_t1_sections(tmp_path: Path) -> None:
    store = StructuredStore.from_json(FIXTURE)
    output = render_change_memo(store, tmp_path / "change.docx")
    text = _paragraph_text(output)
    assert "Fee Schedule" in text
    assert "Rate increase" in text
    assert "T1" in text
    assert "Reporting timeline" in text
    assert "Clarification" in text
    assert "Font styling" not in text


def test_change_memo_smoke_command_shape(tmp_path: Path) -> None:
    store = StructuredStore.from_json(FIXTURE)
    output = tmp_path / "memo.docx"
    render_change_memo(store, output)
    assert output.exists()
    assert output.stat().st_size > 0
