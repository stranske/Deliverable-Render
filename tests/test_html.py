"""Validate the static document without executing JavaScript or loading resources."""

import urllib.parse
from html.parser import HTMLParser

import pytest

from deliverable_render import RenderSpec, render_html
from deliverable_render.store import Document, EvidencePointer, Record, Store
from deliverable_render.store.communication import adapt_store


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

    backslash_path = "/synthetic/a\\b.pdf"
    store_bs = Store(
        (Record("r2", "E", "P", "S", "T", (EvidencePointer("doc2", 3, ""),)),),
        (Document("doc2", backslash_path),),
    )
    output_bs = render_html(store_bs, spec)
    expected_href = "file:///synthetic/a%5Cb.pdf#page=3"
    assert f'<a href="{expected_href}">doc2</a>' in output_bs
    path_only = expected_href.split("#", 1)[0].removeprefix("file://")
    assert urllib.parse.unquote(path_only) == backslash_path


def test_windows_unc_file_links_preserve_share_and_page():
    """Both UNC spellings must yield `file://<server>/<share>/...`, not `file:////...`.

    Previously `\\\\fileserver\\share\\x.pdf` and `//fileserver/share/x.pdf` both rendered as
    `file:////fileserver/share/x.pdf`: an empty authority followed by a bogus extra slash, so the
    server was lost from the authority and the link did not open.
    """
    spec = RenderSpec(title="Hub", document_url_template="file://{path}#page={page}")
    backslash_unc = r"\\fileserver\Board Share\Q3 & Q4\Report.pdf"
    slash_unc = "//fileserver/Board Share/Q3 & Q4/Report.pdf"
    expected_href = "file://fileserver/Board%20Share/Q3%20%26%20Q4/Report.pdf#page=4"

    rendered_hrefs: dict[str, str] = {}
    for label, unc_path in (("backslash", backslash_unc), ("slash", slash_unc)):
        store = Store(
            (Record("r1", "E", "P", "S", "T", (EvidencePointer("unc", 4, ""),)),),
            (Document("unc", unc_path),),
        )
        output = render_html(store, spec)
        links = [attrs["href"] for tag, attrs in ParsedHTML(output).tags if tag == "a"]
        assert links == [expected_href]
        assert f'<a href="{expected_href}">unc</a>' in output
        assert "file:////" not in output
        assert "%5C" not in output
        parts = urllib.parse.urlsplit(links[0])
        assert (parts.scheme, parts.netloc, parts.fragment) == ("file", "fileserver", "page=4")
        assert parts.path == "/Board%20Share/Q3%20%26%20Q4/Report.pdf"
        assert urllib.parse.unquote(parts.path) == "/Board Share/Q3 & Q4/Report.pdf"
        rendered_hrefs[label] = links[0]

    assert rendered_hrefs["backslash"] == rendered_hrefs["slash"]

    # Compatibility controls: #90 POSIX literal-backslash path, #77 native zero-based
    # evidence-object/v1 page normalization through `adapt_store`, and local Windows drive path.
    posix_path = "/synthetic/a\\b.pdf"
    drive_path = r"C:\My Files\Doc.pdf"
    native_store = adapt_store(
        {
            "documents": [
                {"stable_id": "unc-bs", "name": "UNC Backslash"},
                {"stable_id": "unc-sl", "name": "UNC Slash"},
                {"stable_id": "posix", "name": "POSIX Control"},
                {"stable_id": "drive", "name": "Drive Control"},
            ],
            "entries": [
                {
                    "id": "entry-1",
                    "name": "Governance",
                    "mentions": [
                        {
                            "q": "2026-Q3",
                            "text": "UNC backslash native page.",
                            "src": {
                                "schema_version": "evidence-object/v1",
                                "fact_ref": "entries/entry-1/mentions/0",
                                "source_id": "unc-bs",
                                "locator": {"page": 3},
                                "excerpt": "Board approved.",
                            },
                        },
                        {
                            "q": "2026-Q3",
                            "text": "UNC slash native page.",
                            "src": {
                                "schema_version": "evidence-object/v1",
                                "fact_ref": "entries/entry-1/mentions/1",
                                "source_id": "unc-sl",
                                "locator": {"page": 3},
                                "excerpt": "Board approved.",
                            },
                        },
                        {
                            "q": "2026-Q3",
                            "text": "POSIX literal backslash control.",
                            "src": {
                                "schema_version": "evidence-object/v1",
                                "fact_ref": "entries/entry-1/mentions/2",
                                "source_id": "posix",
                                "locator": {"page": 6},
                                "excerpt": "Literal backslash.",
                            },
                        },
                        {
                            "q": "2026-Q3",
                            "text": "Native zero-based page zero control.",
                            "src": {
                                "schema_version": "evidence-object/v1",
                                "fact_ref": "entries/entry-1/mentions/3",
                                "source_id": "drive",
                                "locator": {"page": 0},
                                "excerpt": "Cover page.",
                            },
                        },
                    ],
                }
            ],
        },
        {
            "unc-bs": backslash_unc,
            "unc-sl": slash_unc,
            "posix": posix_path,
            "drive": drive_path,
        },
    )
    native_output = render_html(native_store, spec)
    native_links = [attrs["href"] for tag, attrs in ParsedHTML(native_output).tags if tag == "a"]
    assert native_links == [
        "file://fileserver/Board%20Share/Q3%20%26%20Q4/Report.pdf#page=4",
        "file://fileserver/Board%20Share/Q3%20%26%20Q4/Report.pdf#page=4",
        "file:///synthetic/a%5Cb.pdf#page=7",
        "file:///C:/My%20Files/Doc.pdf#page=1",
    ]
    assert "page 4: Board approved." in native_output
    assert "page 7: Literal backslash." in native_output
    assert "page 1: Cover page." in native_output
    assert "#page=0" not in native_output
    posix_parts = urllib.parse.urlsplit(native_links[2])
    assert (posix_parts.scheme, posix_parts.netloc, posix_parts.fragment) == ("file", "", "page=7")
    assert urllib.parse.unquote(posix_parts.path) == posix_path
    drive_parts = urllib.parse.urlsplit(native_links[3])
    assert (drive_parts.scheme, drive_parts.netloc, drive_parts.fragment) == ("file", "", "page=1")
    assert urllib.parse.unquote(drive_parts.path) == "/C:/My Files/Doc.pdf"


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
