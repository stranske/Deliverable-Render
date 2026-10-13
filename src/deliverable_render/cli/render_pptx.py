"""Render a manifest-gated deck from a communication-synthesis store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pptx.exc import PythonPptxError

from deliverable_render.cli._output import publish
from deliverable_render.pptx.manifest import (
    DeckBuildError,
    DeckManifest,
    build_deck,
    uncovered_record_ids,
)
from deliverable_render.store.communication import adapt_profile


def _load_manifest_mapping(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manifest must be a JSON object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a manifest-gated PowerPoint deck")
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--document-paths", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--prior-manifest", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require every store record to be covered by an active record-source slide",
    )
    args = parser.parse_args(argv)
    try:
        store = adapt_profile(args.store, args.document_paths)
        manifest = DeckManifest.from_mapping(_load_manifest_mapping(args.manifest))
        prior = None
        if args.prior_manifest:
            prior = DeckManifest.from_mapping(_load_manifest_mapping(args.prior_manifest))
        content, summary = build_deck(args.template, manifest, store, prior=prior)
        uncovered = uncovered_record_ids(manifest, store)
        if uncovered or summary.slides_missing_source:
            print(
                f"render-pptx-deck: warning: uncovered_record_ids ({len(uncovered)}): "
                f"{json.dumps(uncovered)}; allow_empty blank slides: {summary.slides_missing_source}",
                file=sys.stderr,
            )
        if args.strict and uncovered:
            raise DeckBuildError("strict mode requires every store record to have an active slide")
        inputs = [args.store, args.document_paths, args.manifest, args.template]
        if args.prior_manifest:
            inputs.append(args.prior_manifest)
        inputs.extend(Path(document.path) for document in store.documents)
        inputs.extend(
            args.template.parent / slide.source.removeprefix("static:")
            for slide in manifest.slides
            if slide.dropped_reason is None and slide.source.startswith("static:")
        )
        publish(args.out, content, tuple(inputs), force=args.force)
        print(json.dumps(summary.as_dict(), sort_keys=True))
    except (OSError, ValueError, KeyError, PythonPptxError) as exc:
        print(f"render-pptx-deck: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
