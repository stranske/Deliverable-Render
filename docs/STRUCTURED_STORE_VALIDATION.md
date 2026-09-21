# Structured-store validation

Run `validate-structured-store path/to/store.json` (or
`python scripts/validate_structured_store.py path/to/store.json` in a checkout).
It reads the file without changing it and exits nonzero for malformed input,
unresolved references, suspected currency-substitution remnants, or evidence
that cannot satisfy the fleet's `evidence-object/v1` contract. It does not
render output or upload data.

This is the communication-synthesis format: `fund` is an object and
`periods`, `entries`, `themes`, `documents`, and `gaps` are arrays.
Periods and entries need unique nonempty `id` fields. Each entry's nested
`mentions[].q` refers to a period ID; optional `mentions[].entry_id` refers
to an entry ID. `entries[].first/last` and `themes[].periods` also refer to
period IDs when supplied. This follows the source's nested shape: the source
does **not** describe a `mentions` field on the top-level entries list
referencing entry IDs. An explicit entry reference is supported where producers
provide one, while the documented `q` join is always checked.

An evidence pointer in `mentions[].src` or `entries[].pub.src` must contain
`stable_id` (or `source_id`), `method`, and `quote` (or `excerpt`, which
may explicitly be null). The validator deterministically derives an
`evidence_id` and enclosing `fact_ref`, retains one-based page numbers in
`locator.page`, and validates the result against a packaged copy of the shared
schema. A native `evidence-object/v1` can be supplied directly. A bare source
name cannot provide extraction method or excerpt, so it fails with an explicit
projection diagnostic; no provenance is invented.

The dollar heuristic flags `B` or `$B` in monetary fields such as `size`,
`peak`, or `amount`, and in monetary phrases such as “capital of B”.
It is a suspicion, not an attempt to reconstruct the missing number. A ticker
`B`, a class B rating, and a valid `$36B` are accepted. Unknown monetary
contexts cannot be conclusively inferred from a single damaged file; review
such data against its source before relying on it.

Existing `Store` and `StructuredStore` loaders for renderer input remain
unchanged. This semantic validator is an explicit gate for the separate
communication-synthesis format. The `communication-synthesis` rendering profile
validates that format before projecting it into the existing HTML/PPTX `Store`.
The renderer also requires an explicit JSON document-path map, keyed by each
`documents[].stable_id` (or `name` when no stable ID exists). A missing map or
a citation without a positive one-based page fails before publishing output.
Paths are operator supplied and must be absolute local paths. The adapter does
not infer a path from a document name or require that a path exists on the
machine that builds the deliverable.

Each mention becomes `record:entry-<entry-array-index>-mention-<mention-index>`
for a deck manifest. An entry with a thesis also becomes
`record:entry-<entry-array-index>-thesis`. Publication evidence becomes a
separate `record:entry-<entry-array-index>-publication`. Those IDs are stable
for identical input order, but change when entries or mentions are reordered.
The compact rendering model retains source ID, page, and excerpt for HTML
links; it does not include every provenance field from evidence-object/v1.

DOCX change/continuity memo rows require a reviewed JSON overlay with
`period_prior`, `period_current` (distinct IDs from the source's `periods`),
`changes` and optional `continuity`. The rows use the existing
`StructuredStore` fields. The adapter never infers a change tier, previous
text, or continuity from mentions. A change memo with no T1/T2 rows fails
without publishing a file. Existing legacy memo input remains supported.
