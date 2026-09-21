# Deliverable-Render

Turn a structured store into the deliverables people actually read: a deep-linked static HTML hub, a manifest-gated PowerPoint deck, and a Word memo. One renderer set, three output shapes, no server and no database.

**Why this repo exists.** An inventory of the owner's work environment (2026-09-04) found the same renderer written three times in two languages, with a fourth about to be started, and found recurring slide decks assembled by hand for nearly every manager with only two exceptions. Both are duplicated work with a proven pattern sitting next to them. This repo generalizes the pattern once.

**Hard constraints, taken from that environment rather than assumed.**

- **Viewing** an output must never require a hosted service. Every deliverable is a file: an HTML page opened directly from a shared folder, a `.pptx`, a `.docx`, or a spreadsheet. That is a property of the output, and it holds regardless of where the renderer runs.
- **Rendering** may eventually run wherever it runs best. Nothing server-hosted or database-backed exists in the target environment today, so the renderers are built to run as a local command; but this is a current constraint, not a permanent one, and the owner intends to seek an accommodation from the work IT team where a hosted component would genuinely serve a goal a local command cannot. Where that case arises, record the goal, why local-first cannot reach it, and the specific accommodation required, rather than dropping the capability.
- Local-file deep links must work. A rendered hub links to a specific page of a specific local source document, and that is the one-click verification path the whole approach depends on.
- WebAssembly is unverified in that environment. Nothing here may depend on Pyodide or stlite until a probe proves it loads there.
- Synthetic and public inputs only in this repository. No proprietary material is ever committed or used in tests.

## Shape

```
render/store        the structured-store contract this repo consumes (records, evidence pointers, identity)
render/html         deep-linked single-page hub renderer
render/pptx         manifest-gated deck builder: a prior slide with no successor and no recorded reason fails the build
render/docx         memo renderer
render/probe        capability probes an operator can run in a locked-down environment and send back
```

## Interoperability

The renderer's compact store contract is aligned with the fleet's shared formats
in `docs/contracts/` (run records, artifact manifests, evidence objects, identity
conventions). The communication-synthesis format has a documented adapter below.

### Communication-synthesis rendering profile

The communication-synthesis format uses `fund`, `periods`, `entries`,
`themes`, `documents`, and `gaps`. The local commands below validate it, then
adapt it to the existing renderer inputs. Supply the local document paths
explicitly in JSON, keyed by source ID. For a DOCX memo, also supply reviewed
period IDs and change/continuity rows; the source format does not contain
change tiers or prior memo text.

```bash
render-html-hub --store tests/fixtures/stores/communication_render.json \
  --document-paths tests/fixtures/stores/communication_paths.json --out hub.html
render-pptx-deck --store tests/fixtures/stores/communication_render.json \
  --document-paths tests/fixtures/stores/communication_paths.json \
  --manifest tests/fixtures/stores/communication_deck.json \
  --template tests/fixtures/deck/synthetic_template.pptx --out deck.pptx
render-docx-memo --profile communication-synthesis \
  --store tests/fixtures/stores/communication_render.json \
  --document-paths tests/fixtures/stores/communication_paths.json \
  --memo-overlay tests/fixtures/stores/communication_memo.json --out memo.docx
```

The HTML page contains local-file evidence links and no network resources.
The deck requires an explicit manifest and template. The synthesis-profile
commands leave an existing output alone unless `--force` is supplied. See
`docs/STRUCTURED_STORE_VALIDATION.md` for mapping diagnostics and record IDs.

## Offline HTML hub

```python
from pathlib import Path
from deliverable_render import RenderSpec, render_html
from deliverable_render.store import Store

store = Store.from_json("tests/fixtures/synthetic_store.json")
spec = RenderSpec(
    title="Synthetic evidence hub",
    document_url_template="file://{path}#page={page}",
    view="grid",
)
Path("hub.html").write_text(render_html(store, spec), encoding="utf-8")
```

`view="list"` is the default; `view="grid"` groups records by section and period.
Each page renders one view. When `document_url_template` is set, it renders one
source link per evidence pointer, including multiple pointers on a record. Unlike
the initial renderer, it does not append a
second view automatically. Records without evidence remain visible. An empty grid
falls back to the empty records table.

Set `document_url_template` to a local-file template as above, or to a document
system template such as `https://documents.example.invalid{path}#page={page}`.
The template changes only navigational links, never page resource loading. Leaving
it unset retains plain-text evidence. All referenced document IDs are validated in
either mode. The synthetic paths are illustrative and do not identify real files.

The saved `tests/fixtures/expected_list.html` and `expected_grid.html` are golden
reference artifacts for the synthetic JSON store. `tests/test_render_html_offline.py`
compares parsed structure and content, validates the saved pages without executing
JavaScript, and checks both link modes. These goldens are committed references;
tests never regenerate them. Review intentional renderer changes before updating
both files. Current Edge, Chrome, Firefox and Safari support the HTML5/ES2015
baseline; the tables and links remain available with JavaScript disabled.
