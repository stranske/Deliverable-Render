"""Source #2 acceptance through persisted inputs and the production renderer."""

from collections import Counter
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from deliverable_render import RenderSpec, render_html
from deliverable_render.store import Store

FIXTURES = Path(__file__).parent / "fixtures"
LOCAL = "file://{path}#page={page}"
REMOTE = "https://documents.example.invalid{path}#page={page}"
EXPECTED_LINKS = [
    "file:///C:/Synthetic/Annual%20Report.pdf#page=3",
    "file:///C:/Synthetic/Annual%20Report.pdf#page=8",
    "file:///C:/Synthetic/Risk%20%26%20Controls.pdf#page=2",
]


class Markup(HTMLParser):
    """Compare parsed structure, attribute sets and meaningful text, not bytes."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.events = []
        self.tags = []
        self.text = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self.events.append(("start", tag, tuple(sorted(attrs))))

    def handle_endtag(self, tag):
        self.events.append(("end", tag))

    def handle_data(self, data):
        if data.strip():
            self.events.append(("text", data.strip()))
            self.text.append(data.strip())

    @property
    def links(self):
        return [attrs["href"] for tag, attrs in self.tags if tag == "a"]


@pytest.fixture
def store():
    return Store.from_json(FIXTURES / "synthetic_store.json")


def spec(view, template=LOCAL):
    return RenderSpec("Synthetic evidence hub", template, view=view)


@pytest.mark.parametrize("view", ["list", "grid"])
def test_persisted_golden_matches_renderer_structure(store, view):
    golden = (FIXTURES / f"expected_{view}.html").read_text(encoding="utf-8")
    rendered = render_html(store, spec(view))
    assert Markup(rendered).events == Markup(golden).events
    # Whitespace between elements and attribute ordering are not byte contracts.
    reformatted = golden.replace(
        '<input type="search" id="search-input"', '<input id="search-input" type="search"'
    ).replace("</head>", "</head>\n\n")
    assert golden != reformatted
    assert Markup(golden).events == Markup(reformatted).events


@pytest.mark.parametrize("view", ["list", "grid"])
@pytest.mark.parametrize("persisted", [False, True])
def test_no_external_resource_references(store, view, persisted):
    output = (
        (FIXTURES / f"expected_{view}.html").read_text(encoding="utf-8")
        if persisted
        else render_html(store, spec(view))
    )
    assert "http://" not in output and "https://" not in output
    parsed = Markup(output)
    assert not {"link", "iframe", "img", "object", "embed"}.intersection(
        tag for tag, _ in parsed.tags
    )
    assert all("src" not in attrs and "srcset" not in attrs for _, attrs in parsed.tags)


@pytest.mark.parametrize("view", ["list", "grid"])
def test_each_pointer_has_exactly_one_source_link(store, view):
    parsed = Markup(render_html(store, spec(view)))
    assert Counter(parsed.links) == Counter(EXPECTED_LINKS)
    assert len(parsed.links) == len(store.evidence)
    assert len([tag for tag, _ in parsed.tags if tag == "table"]) == 1
    if view == "grid":
        cards = [a["data-record-id"] for t, a in parsed.tags if a.get("class") == "grid-card"]
        assert Counter(cards) == Counter(r.record_id for r in store.records)
        assert "section-grid" in [a.get("id") for t, a in parsed.tags if t == "table"]


@pytest.mark.parametrize("view", ["list", "grid"])
def test_missing_document_fails_before_rendering(store, view):
    missing = replace(store, documents=store.documents[:1])
    with pytest.raises(ValueError, match="Dangling document reference: risk"):
        render_html(missing, spec(view))


@pytest.mark.parametrize("view", ["list", "grid"])
def test_persisted_golden_preserves_rows_without_javascript(store, view):
    parsed = Markup((FIXTURES / f"expected_{view}.html").read_text(encoding="utf-8"))
    # HTMLParser never executes the inline script. These records exist in static markup.
    for record in store.records:
        assert record.record_id in parsed.text
        assert any(record.text in text for text in parsed.text)
    for tag, attrs in parsed.tags:
        if tag == "tr" or attrs.get("class") == "grid-card":
            assert "hidden" not in attrs
            assert "display:none" not in attrs.get("style", "").replace(" ", "")


@pytest.mark.parametrize("view", ["list", "grid"])
def test_link_modes_change_only_source_prefix(store, view):
    local = render_html(store, spec(view))
    remote = render_html(store, spec(view, REMOTE))
    parsed = Markup(remote)
    assert len(parsed.links) == len(EXPECTED_LINKS)
    assert all(urlsplit(link).hostname == "documents.example.invalid" for link in parsed.links)
    assert Markup(remote.replace("https://documents.example.invalid", "file://")).events == (
        Markup(local).events
    )
    # Document-system URLs are navigational anchors, never fetched page resources.
    assert all("src" not in attrs for _, attrs in parsed.tags)


def test_unknown_view_is_rejected():
    with pytest.raises(ValueError, match="view must be list or grid"):
        spec("unknown")


def test_empty_grid_keeps_visible_empty_table():
    parsed = Markup(render_html(Store((), ()), spec("grid")))
    assert "0 records" in parsed.text
    assert sum(tag == "table" for tag, _ in parsed.tags) == 1
