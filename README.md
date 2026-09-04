# Deliverable-Render

Turn a structured store into the deliverables people actually read: a deep-linked static HTML hub, a manifest-gated PowerPoint deck, and a Word memo. One renderer set, three output shapes, no server and no database.

**Why this repo exists.** An inventory of the owner's work environment (2026-09-04) found the same renderer written three times in two languages, with a fourth about to be started, and found recurring slide decks assembled by hand for nearly every manager with only two exceptions. Both are duplicated work with a proven pattern sitting next to them. This repo generalizes the pattern once.

**Hard constraints, taken from that environment rather than assumed.**

- No server and no database. Every output is a file: an HTML page opened directly from a shared folder, a `.pptx`, a `.docx`, or a spreadsheet. Nothing here may require a hosted service to render or to view.
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

The structured-store contract is aligned with the fleet's shared formats in `docs/contracts/` (run records, artifact manifests, evidence objects, identity conventions) and with the field names already in use in the owner's work tools, so a store produced there renders here without a translation step.
