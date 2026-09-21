"""End-to-end synthesis profile: one validated store, three public commands."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pptx import Presentation

from deliverable_render.cli.render_docx import main as docx_main
from deliverable_render.cli.render_html import main as html_main
from deliverable_render.cli.render_pptx import main as pptx_main
from deliverable_render.store.communication import (
    CommunicationRenderError,
    adapt_store,
    load_profile,
)
from deliverable_render.store.validate import validate_store
from docx import Document

HERE = Path(__file__).parent.parent
FIXTURES = HERE / "fixtures" / "stores"
STORE = FIXTURES / "communication_render.json"
PATHS = FIXTURES / "communication_paths.json"
MEMO = FIXTURES / "communication_memo.json"
MANIFEST = FIXTURES / "communication_deck.json"
TEMPLATE = HERE / "fixtures" / "deck" / "synthetic_template.pptx"


def test_validated_store_renders_all_three_public_outputs(tmp_path: Path) -> None:
    assert validate_store(STORE).valid
    data, paths = load_profile(STORE, PATHS)
    adapted = adapt_store(data, paths)
    assert adapted.records[0].record_id == "entry-0-mention-0"
    assert adapted.records[0].evidence[0].page == 3

    html = tmp_path / "hub.html"
    pptx = tmp_path / "deck.pptx"
    docx = tmp_path / "memo.docx"
    assert (
        html_main(["--store", str(STORE), "--document-paths", str(PATHS), "--out", str(html)]) == 0
    )
    assert (
        pptx_main(
            [
                "--store",
                str(STORE),
                "--document-paths",
                str(PATHS),
                "--manifest",
                str(MANIFEST),
                "--template",
                str(TEMPLATE),
                "--out",
                str(pptx),
            ]
        )
        == 0
    )
    assert (
        docx_main(
            [
                "--profile",
                "communication-synthesis",
                "--store",
                str(STORE),
                "--document-paths",
                str(PATHS),
                "--memo-overlay",
                str(MEMO),
                "--out",
                str(docx),
            ]
        )
        == 0
    )
    assert all(path.stat().st_size > 100 for path in (html, pptx, docx))
    page = html.read_text(encoding="utf-8")
    assert "file:///synthetic/source%20document.pdf#page=3" in page
    assert "https://" not in page and "http://" not in page
    assert "Capital of $36B" in page
    assert Presentation(pptx).slides[0].shapes.title.text == "Capital"
    assert "Assets of $36B" in " ".join(p.text for p in Document(docx).paragraphs)


def test_missing_document_path_fails_before_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mapping = tmp_path / "paths.json"
    mapping.write_text("{}", encoding="utf-8")
    out = tmp_path / "hub.html"
    assert (
        html_main(["--store", str(STORE), "--document-paths", str(mapping), "--out", str(out)]) == 2
    )
    assert not out.exists()
    assert "document-path mapping missing" in capsys.readouterr().err


def test_missing_page_fails_projection_even_when_store_validates(tmp_path: Path) -> None:
    data = json.loads(STORE.read_text(encoding="utf-8"))
    pointer = data["entries"][0]["mentions"][0]["src"]
    del pointer["page"]
    with_page = tmp_path / "missing-page.json"
    with_page.write_text(json.dumps(data), encoding="utf-8")
    assert validate_store(with_page).valid  # validator allows document-only citations
    out = tmp_path / "hub.html"
    assert (
        html_main(["--store", str(with_page), "--document-paths", str(PATHS), "--out", str(out)])
        == 2
    )
    assert not out.exists()


def test_cross_entry_mention_is_not_silently_reassigned(tmp_path: Path) -> None:
    data = json.loads(STORE.read_text(encoding="utf-8"))
    second = deepcopy(data["entries"][0])
    second["id"] = "other"
    second["mentions"] = []
    data["entries"].append(second)
    data["entries"][0]["mentions"][0]["entry_id"] = "other"
    store_path = tmp_path / "cross-entry.json"
    store_path.write_text(json.dumps(data), encoding="utf-8")
    assert validate_store(store_path).valid
    with pytest.raises(CommunicationRenderError, match="names another entry"):
        adapt_store(data, json.loads(PATHS.read_text(encoding="utf-8")))


def test_memo_requires_reviewed_rows_and_distinct_periods(tmp_path: Path) -> None:
    out = tmp_path / "memo.docx"
    assert (
        docx_main(
            [
                "--profile",
                "communication-synthesis",
                "--store",
                str(STORE),
                "--document-paths",
                str(PATHS),
                "--out",
                str(out),
            ]
        )
        == 2
    )
    assert not out.exists()
    overlay = json.loads(MEMO.read_text(encoding="utf-8"))
    overlay["period_prior"] = overlay["period_current"]
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(overlay), encoding="utf-8")
    assert (
        docx_main(
            [
                "--profile",
                "communication-synthesis",
                "--store",
                str(STORE),
                "--document-paths",
                str(PATHS),
                "--memo-overlay",
                str(path),
                "--out",
                str(out),
            ]
        )
        == 2
    )
    assert not out.exists()


def test_no_material_change_and_existing_output_are_preserved(tmp_path: Path) -> None:
    overlay = json.loads(MEMO.read_text(encoding="utf-8"))
    overlay["changes"][0]["tier"] = "T3"
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(overlay), encoding="utf-8")
    docx = tmp_path / "memo.docx"
    assert (
        docx_main(
            [
                "--profile",
                "communication-synthesis",
                "--store",
                str(STORE),
                "--document-paths",
                str(PATHS),
                "--memo-overlay",
                str(path),
                "--out",
                str(docx),
            ]
        )
        == 2
    )
    assert not docx.exists()

    html = tmp_path / "hub.html"
    html.write_text("existing", encoding="utf-8")
    args = ["--store", str(STORE), "--document-paths", str(PATHS), "--out", str(html)]
    assert html_main(args) == 2
    assert html.read_text(encoding="utf-8") == "existing"
    assert html_main(args + ["--force"]) == 0
    assert "Capital of $36B" in html.read_text(encoding="utf-8")
