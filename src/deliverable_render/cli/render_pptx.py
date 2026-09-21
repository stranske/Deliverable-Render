"""Render a manifest-gated deck from a communication-synthesis store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deliverable_render.cli._output import publish
from deliverable_render.pptx.manifest import DeckManifest, build_deck
from deliverable_render.store.communication import adapt_store, load_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a manifest-gated PowerPoint deck")
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--document-paths", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--prior-manifest", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        data, paths = load_profile(args.store, args.document_paths)
        store = adapt_store(data, paths)
        manifest = DeckManifest.from_mapping(json.loads(args.manifest.read_text(encoding="utf-8")))
        prior = None
        if args.prior_manifest:
            prior = DeckManifest.from_mapping(
                json.loads(args.prior_manifest.read_text(encoding="utf-8"))
            )
        content, _ = build_deck(args.template, manifest, store, prior=prior)
        inputs = [args.store, args.document_paths, args.manifest, args.template]
        if args.prior_manifest:
            inputs.append(args.prior_manifest)
        publish(args.out, content, tuple(inputs), force=args.force)
    except (OSError, ValueError, KeyError) as exc:
        print(f"render-pptx-deck: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
