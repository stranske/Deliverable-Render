"""Validate the static document without executing JavaScript or loading resources."""

from html.parser import HTMLParser

import pytest

from deliverable_render import RenderSpec, render_html
from deliverable_render.store import EvidencePointer, Record, Store


class ParsedHTML(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.text = []
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
        (),
    )
    output = render_html(store, RenderSpec("Synthetic report"))
    parsed = ParsedHTML(output)
    tags = [tag for tag, _ in parsed.tags]
    assert output.startswith("<!DOCTYPE html>")
    assert tags.count("html") == tags.count("style") == tags.count("script") == 1
    assert tags.count("tr") == len(store.records) + 1
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
        (),
    )
    output = render_html(store, RenderSpec(hostile))
    parsed = ParsedHTML(output)
    assert hostile not in output
    assert parsed.text.count(hostile) == 7  # Title, heading and five record fields.
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
