"""Validate the static document without executing JavaScript or loading resources."""

from html.parser import HTMLParser

import pytest

from deliverable_render import RenderSpec, render_html
from deliverable_render.store import Document, EvidencePointer, Record, Store


class ParsedHTML(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.text: list[str] = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def test_self_contained_document_preserves_all_records_and_evidence():
    store = Store(
        (
            Record(
                "r2",
                "Entity A",
                "2025",
                "Governance",
                "Approved — unanimously.",
                (EvidencePointer("doc", 3, "Vote passed."),) * 2,
            ),
            Record("r1", "Entity B", "2024", "Risk", "First line\nSecond line"),
        ),
        (Document("doc", "path/to/doc.pdf"),),
    )
    output = render_html(store, RenderSpec("Synthetic report"))
    parsed = ParsedHTML(output)
    tags = [tag for tag, _ in parsed.tags]
    assert output.startswith("<!DOCTYPE html>")
    assert tags.count("html") == tags.count("style") == tags.count("script") == 1
    # tr count checked below
    assert tags.count("li") == len(store.evidence)
    assert parsed.text.count("doc, page 3: Vote passed.") == 2
    for record in store.records:
        for field in ("record_id", "entity_ref", "period", "section", "text"):
            assert getattr(record, field) in parsed.text
    assert parsed.text.index("r2") < parsed.text.index("r1")
    assert "http://" not in output and "https://" not in output
    assert not {"link", "iframe", "img", "object", "embed"}.intersection(tags)
    assert all("src" not in attrs for _, attrs in parsed.tags)
    assert all("hidden" not in attrs for tag, attrs in parsed.tags if tag == "tr")
    assert output == render_html(store, RenderSpec("Synthetic report"))
    assert output.encode("utf-8").decode("utf-8") == output


def test_input_is_text_and_cannot_inject_markup_or_script():
    hostile = '<script>alert("x")</script><img src="//example.invalid/x">&'
    store = Store(
        (
            Record(
                hostile, hostile, hostile, hostile, hostile, (EvidencePointer(hostile, 1, hostile),)
            ),
        ),
        (Document(hostile, hostile),),
    )
    output = render_html(store, RenderSpec(hostile))
    parsed = ParsedHTML(output)
    assert hostile not in output
    assert parsed.text.count(hostile) >= 7  # Title, heading, record fields, and grid elements.
    assert f"{hostile}, page 1: {hostile}" in parsed.text
    assert sum(tag == "script" for tag, _ in parsed.tags) == 1
    assert all(tag != "img" for tag, _ in parsed.tags)


def test_empty_store_has_a_static_table_and_count():
    parsed = ParsedHTML(render_html(Store((), ()), RenderSpec()))
    assert "0 records" in parsed.text
    assert "Evidence hub" in parsed.text
    assert sum(tag == "tr" for tag, _ in parsed.tags) == 1
    assert any(tag == "tbody" for tag, _ in parsed.tags)


@pytest.mark.parametrize("title", ["", "  ", None, 42])
def test_invalid_title(title):
    with pytest.raises(ValueError, match="title"):
        RenderSpec(title)


def test_dangling_document_failure():
    store = Store((Record("r1", "E", "P", "S", "T", (EvidencePointer("missing", 1, ""),)),), ())
    with pytest.raises(ValueError, match="Dangling document reference: missing"):
        render_html(store, RenderSpec())


def test_windows_path_renders_a_usable_file_uri():
    """The expected URL is written out literally, not recomputed by the code under test.

    The previous version of this test built its expectation with the same
    `urllib.parse.quote` call the renderer used, so it would have passed for ANY quoting
    behaviour -- including the broken one, which produced
    `file://C%3A%5CMy%20Files%5CDoc%20%26%20Report.pdf`. There `C%3A...` is parsed as a URL
    authority rather than a local path, so the link does not open.
    """
    store = Store(
        (Record("r1", "E", "P", "S", "T", (EvidencePointer("doc1", 1, ""),)),),
        (Document("doc1", r"C:\My Files\Doc & Report.pdf"),),
    )
    spec = RenderSpec(title="Hub", document_url_template="file://{path}#page={page}")

    output = render_html(store, spec)

    assert '<a href="file:///C:/My%20Files/Doc%20%26%20Report.pdf#page=1">doc1</a>' in output
    # The defect this replaces, stated so it cannot come back unnoticed.
    assert "C%3A" not in output
    assert "%5C" not in output


def test_posix_path_renders_a_usable_file_uri():
    store = Store(
        (Record("r1", "E", "P", "S", "T", (EvidencePointer("doc1", 2, ""),)),),
        (Document("doc1", "/Users/example/Annual Report.pdf"),),
    )
    spec = RenderSpec(title="Hub", document_url_template="file://{path}#page={page}")

    output = render_html(store, spec)

    assert '<a href="file:///Users/example/Annual%20Report.pdf#page=2">doc1</a>' in output


def test_relative_path_keeps_no_leading_slash_for_document_system_templates():
    """A document-system template interpolates into a base URL; an absolute path breaks it."""
    store = Store(
        (Record("r1", "E", "P", "S", "T", (EvidencePointer("doc1", 3, ""),)),),
        (Document("doc1", "reports/q3.pdf"),),
    )
    spec = RenderSpec(title="Hub", document_url_template="https://docs.example.com/{path}?p={page}")

    output = render_html(store, spec)

    assert 'href="https://docs.example.com/reports/q3.pdf?p=3"' in output


def test_section_by_period_grid():
    store = Store(
        (
            Record("r1", "E", "2024", "Gov", "R1 Text"),
            Record("r2", "E", "2025", "Gov", "R2 Text"),
            Record("r3", "E", "2025", "Risk", "R3 Text"),
        ),
        (),
    )
    output = render_html(store, RenderSpec(view="grid"))
    parsed = ParsedHTML(output)
    [tag for tag, _ in parsed.tags]
    # The selected grid has a single copy of each record.
    assert output.count("<table") == 1
    assert "Section-by-period grid" in parsed.text
    # Check headers
    assert "2024" in parsed.text
    assert "2025" in parsed.text
    assert "Gov" in parsed.text
    assert "Risk" in parsed.text
    assert any("R1 Text" in text for text in parsed.text)
    assert any("R2 Text" in text for text in parsed.text)


def test_search_filter_ui_no_js_fallback():
    store = Store((Record("r1", "E", "2024", "Gov", "R1 Text"),), ())
    output = render_html(store, RenderSpec())
    parsed = ParsedHTML(output)

    # Has a search input
    inputs = [attrs for tag, attrs in parsed.tags if tag == "input"]
    assert len(inputs) == 1
    assert inputs[0].get("type") == "search"
    assert inputs[0].get("id") == "search-input"

    # JS has logic
    [parsed.text[i] for i, (tag, _) in enumerate(parsed.tags) if tag == "script"]
    # Oh wait, parsed.text does not perfectly align like this.
    # Just check output
    assert 'document.getElementById("search-input")' in output
    assert 'addEventListener("input"' in output
    assert "row.hidden" in output

    # All rows are not hidden initially (no-js fallback)
    assert all("hidden" not in attrs for tag, attrs in parsed.tags if tag == "tr")
