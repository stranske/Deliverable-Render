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
communication-synthesis format, not a new implicit validation step on every
legacy renderer load.
