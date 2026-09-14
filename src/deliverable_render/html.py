"""Self-contained HTML5 for current Edge, Chrome, Firefox and Safari.

Static tables and source links remain usable with JavaScript disabled. Search
and printing are progressive enhancements using ES2015 browser APIs.
"""

import re
import urllib.parse
from dataclasses import dataclass
from html import escape
from typing import Literal

from deliverable_render.store import Store


@dataclass(frozen=True)
class RenderSpec:
    """Presentation options for a single HTML deliverable."""

    title: str = "Evidence hub"
    document_url_template: str | None = None
    view: Literal["list", "grid"] = "list"

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a nonempty string")
        if self.view not in ("list", "grid"):
            raise ValueError("view must be list or grid")


_CSS = """
body { font-family: system-ui, sans-serif; margin: 2rem; color: #17202a;
       background: #fff; }
table { border-collapse: collapse; width: 100%; margin-bottom: 2rem; }
caption { text-align: left; margin-bottom: 1rem; font-weight: bold; }
th, td { border: 1px solid #aab7b8; padding: .75rem; text-align: left;
         vertical-align: top; overflow-wrap: anywhere; }
thead { background: #edf2f7; }
td, li { white-space: pre-wrap; }
ul { margin: 0; padding-left: 1.25rem; }
button { margin-bottom: 1rem; padding: .5rem 1rem; }
.controls { margin-bottom: 1rem; }
.controls input { padding: .5rem; width: 300px; max-width: 100%; }
.table-container { overflow-x: auto; }
.grid-card { border: 1px solid #ddd; padding: 0.5rem; margin-bottom: 0.5rem; background: #fafafa; }
@media print { button, .controls { display: none; } body { margin: 0; } }
"""

_JAVASCRIPT = """
"use strict";
const printButton = document.getElementById("print-report");
if (printButton) {
    printButton.addEventListener("click", () => window.print());
    printButton.hidden = false;
}
const searchInput = document.getElementById("search-input");
if (searchInput) {
    searchInput.addEventListener("input", (e) => {
        const term = e.target.value.toLowerCase();

        // Filter list rows
        const listRows = document.querySelectorAll("#record-list tbody tr");
        for (const row of listRows) {
            row.hidden = !row.textContent.toLowerCase().includes(term);
        }

        // Filter grid cells/rows
        // We filter individual grid cards
        const gridCards = document.querySelectorAll(".grid-card");
        for (const card of gridCards) {
            card.hidden = !card.textContent.toLowerCase().includes(term);
        }

        // Hide empty grid rows if all cards are hidden
        const gridRows = document.querySelectorAll("#section-grid tbody tr");
        for (const row of gridRows) {
            let hasVisibleCard = false;
            const rowCards = row.querySelectorAll(".grid-card");
            for (const card of rowCards) {
                if (!card.hidden) {
                    hasVisibleCard = true;
                    break;
                }
            }
            // Only hide the row if there were cards but all are hidden
            // Wait, if a row had NO cards to begin with, should we hide it?
            // If we filter, maybe we just leave it or hide it.
            if (rowCards.length > 0 && !hasVisibleCard) {
                row.hidden = true;
            } else {
                row.hidden = false;
            }
        }
    });
}
"""


def _url_path(raw: str) -> str:
    """Turn a stored document path into the path component of a URL.

    `urllib.parse.quote` alone is wrong for Windows paths. It percent-encodes the
    backslashes and the drive colon, so `C:\\My Files\\Doc.pdf` under a `file://{path}`
    template renders as `file://C%3A%5CMy%20Files%5CDoc.pdf` — where `C%3A...` is read as a
    URL *authority*, not a local path, and the link does not open. A usable file URI is
    `file:///C:/My%20Files/Doc.pdf`.

    So: normalise separators, give a drive-letter path the leading slash that makes the
    authority component empty, and keep `/` and `:` unescaped. Relative paths are left
    without a leading slash, because document-system templates interpolate them into a
    base URL where an absolute path would be wrong.
    """
    normalised = raw.replace("\\", "/")
    if re.fullmatch(r"[A-Za-z]:/.*", normalised):
        normalised = "/" + normalised
    return urllib.parse.quote(normalised, safe="/:")


def render_html(store: Store, spec: RenderSpec) -> str:
    """Return a complete UTF-8-ready HTML document without fetching resources."""
    doc_paths = {doc.stable_id: doc.path for doc in store.documents}

    rows = []
    evidence_by_record = {}
    for record in store.records:
        cells = "".join(
            f"<td>{escape(value)}</td>"
            for value in (record.entity_ref, record.period, record.section, record.text)
        )

        evidence_items = []
        for pointer in record.evidence:
            if pointer.stable_id not in doc_paths:
                raise ValueError(f"Dangling document reference: {pointer.stable_id}")
            doc_name_escaped = escape(pointer.stable_id)
            if spec.document_url_template:
                path = _url_path(doc_paths[pointer.stable_id])
                url = spec.document_url_template.format(path=path, page=pointer.page)
                # The prompt asks for configurable escaped local-file/document-system evidence links
                # So we escape the URL before rendering it
                link_html = f'<a href="{escape(url)}">{doc_name_escaped}</a>'
            else:
                link_html = doc_name_escaped
            evidence_items.append(
                f"<li>{link_html}, page {pointer.page}: " f"{escape(pointer.quote)}</li>"
            )

        evidence_cell = f"<ul>{''.join(evidence_items)}</ul>" if evidence_items else "No evidence"
        evidence_by_record[record.record_id] = evidence_cell
        rows.append(
            f'<tr class="record-row"><th scope="row">{escape(record.record_id)}</th>'
            f"{cells}<td>{evidence_cell}</td></tr>"
        )

    # Section-by-period grid
    periods = sorted(store.period_index.keys())
    sections = sorted({r.section for r in store.records})

    grid_headers = "".join(f'<th scope="col">{escape(p)}</th>' for p in periods)
    grid_rows = []
    for section in sections:
        grid_cells = []
        for period in periods:
            matching = [r for r in store.records if r.section == section and r.period == period]
            if matching:
                cell_content = "".join(
                    f'<div class="grid-card" data-record-id="{escape(r.record_id)}">'
                    f"<strong>{escape(r.record_id)}</strong>: {escape(r.text)}"
                    f"{evidence_by_record[r.record_id]}</div>"
                    for r in matching
                )
            else:
                cell_content = ""
            grid_cells.append(f"<td>{cell_content}</td>")
        grid_rows.append(f'<tr><th scope="row">{escape(section)}</th>{"".join(grid_cells)}</tr>')

    grid_table = ""
    if periods and sections:
        grid_table = f"""
<table id="section-grid">
<caption>Section-by-period grid</caption>
<thead><tr><th scope="col">Section</th>{grid_headers}</tr></thead>
<tbody>
{"\n".join(grid_rows)}
</tbody>
</table>
"""

    title = escape(spec.title)
    body = "\n".join(rows)
    record_table = f"""
<table id="record-list">
<caption>{len(store.records)} records</caption>
<thead><tr><th scope="col">Record</th><th scope="col">Entity</th>
<th scope="col">Period</th><th scope="col">Section</th>
<th scope="col">Text</th><th scope="col">Evidence</th></tr></thead>
<tbody>
{body}
</tbody>
</table>
"""
    table = grid_table if spec.view == "grid" and grid_table else record_table
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{_CSS}</style>
</head>
<body>
<main>
<h1>{title}</h1>
<button id="print-report" type="button" hidden>Print report</button>

<div class="controls">
<label for="search-input">Search:</label>
<input type="search" id="search-input" placeholder="Search records...">
</div>

<div class="table-container">
{table}
</div>
</main>
<script>{_JAVASCRIPT}</script>
</body>
</html>
"""
