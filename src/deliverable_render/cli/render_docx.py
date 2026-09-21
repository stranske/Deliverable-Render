"""CLI entry points for Word memo rendering."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from deliverable_render.cli._output import publish
from deliverable_render.docx.memo import (
    StructuredStore,
    render_change_memo,
    render_continuity_memo,
)
from deliverable_render.store.communication import adapt_memo, adapt_store, load_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render consultant memos to Word documents")
    parser.add_argument("--store", required=True, type=Path, help="Structured store JSON path")
    parser.add_argument("--out", required=True, type=Path, help="Output .docx path")
    parser.add_argument(
        "--profile", choices=("legacy", "communication-synthesis"), default="legacy"
    )
    parser.add_argument("--document-paths", type=Path, help="Explicit source ID to local path JSON")
    parser.add_argument("--memo-overlay", type=Path, help="Reviewed memo rows and period IDs JSON")
    parser.add_argument("--force", action="store_true", help="Replace an existing output")
    parser.add_argument(
        "--kind",
        choices=("change", "continuity"),
        default="change",
        help="Memo type to render (default: change)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.profile == "legacy":
            store = StructuredStore.from_json(args.store)
            if args.kind == "change":
                render_change_memo(store, args.out)
            else:
                render_continuity_memo(store, args.out)
            return 0
        if args.document_paths is None or args.memo_overlay is None:
            raise ValueError("communication-synthesis requires --document-paths and --memo-overlay")
        data, paths = load_profile(args.store, args.document_paths)
        # Require the same complete evidence mapping as the other outputs.
        render_store = adapt_store(data, paths)
        store = adapt_memo(data, args.memo_overlay)
        with tempfile.TemporaryDirectory(prefix="render-docx-") as folder:
            staged = Path(folder) / "memo.docx"
            if args.kind == "change":
                render_change_memo(store, staged)
            else:
                render_continuity_memo(store, staged)
            publish(
                args.out,
                staged.read_bytes(),
                (
                    args.store,
                    args.document_paths,
                    args.memo_overlay,
                    *(Path(document.path) for document in render_store.documents),
                ),
                force=args.force,
            )
    except (OSError, ValueError, KeyError) as exc:
        print(f"render-docx-memo: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
