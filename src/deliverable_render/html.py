"""Self-contained HTML output for the shared rendering store."""

from dataclasses import dataclass
from html import escape

from deliverable_render.store import Store


@dataclass(frozen=True)
class RenderSpec:
    """Presentation options for a single HTML deliverable."""

    title: str = "Evidence hub"

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a nonempty string")


_CSS = """
body { font-family: system-ui, sans-serif; margin: 2rem; color: #17202a;
       background: #fff; }
table { border-collapse: collapse; width: 100%; }
caption { text-align: left; margin-bottom: 1rem; }
th, td { border: 1px solid #aab7b8; padding: .75rem; text-align: left;
         vertical-align: top; overflow-wrap: anywhere; }
thead { background: #edf2f7; }
td, li { white-space: pre-wrap; }
ul { margin: 0; padding-left: 1.25rem; }
button { margin-bottom: 1rem; padding: .5rem 1rem; }
.table-container { overflow-x: auto; }
@media print { button { display: none; } body { margin: 0; } }
"""

_JAVASCRIPT = """
"use strict";
const printButton = document.getElementById("print-report");
printButton.addEventListener("click", () => window.print());
printButton.hidden = false;
"""


def render_html(store: Store, spec: RenderSpec) -> str:
    """Return a complete UTF-8-ready HTML document without fetching resources.

    Records retain store order and are present in the static markup, including
    evidence quotes. All input is escaped as text, never interpreted as markup
    or JavaScript. The caller chooses where to write the returned string.
    """
    rows = []
    for record in store.records:
        cells = "".join(
            f"<td>{escape(value)}</td>"
            for value in (record.entity_ref, record.period, record.section, record.text)
        )
        evidence = "".join(
            f"<li>{escape(pointer.stable_id)}, page {pointer.page}: "
            f"{escape(pointer.quote)}</li>"
            for pointer in record.evidence
        )
        evidence_cell = f"<ul>{evidence}</ul>" if evidence else "No evidence"
        rows.append(
            f'<tr><th scope="row">{escape(record.record_id)}</th>'
            f"{cells}<td>{evidence_cell}</td></tr>"
        )
    title = escape(spec.title)
    body = "\n".join(rows)
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
<div class="table-container">
<table>
<caption>{len(store.records)} records</caption>
<thead><tr><th scope="col">Record</th><th scope="col">Entity</th>
<th scope="col">Period</th><th scope="col">Section</th>
<th scope="col">Text</th><th scope="col">Evidence</th></tr></thead>
<tbody>
{body}
</tbody>
</table>
</div>
</main>
<script>{_JAVASCRIPT}</script>
</body>
</html>
"""
