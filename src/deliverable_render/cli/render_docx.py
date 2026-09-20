"""CLI entry points for Word memo rendering."""

from __future__ import annotations

import argparse
from pathlib import Path

from deliverable_render.docx.memo import (
    StructuredStore,
    render_change_memo,
    render_continuity_memo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render consultant memos to Word documents")
    parser.add_argument("--store", required=True, type=Path, help="Structured store JSON path")
    parser.add_argument("--out", required=True, type=Path, help="Output .docx path")
    parser.add_argument(
        "--kind",
        choices=("change", "continuity"),
        default="change",
        help="Memo type to render (default: change)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = StructuredStore.from_json(args.store)
    if args.kind == "change":
        render_change_memo(store, args.out)
    else:
        render_continuity_memo(store, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
