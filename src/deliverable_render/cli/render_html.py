"""Render a validated communication-synthesis store as an offline HTML hub."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from deliverable_render.cli._output import publish
from deliverable_render.html import RenderSpec, render_html
from deliverable_render.store.communication import adapt_store, load_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an offline evidence hub")
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--document-paths", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--title", default="Evidence hub")
    parser.add_argument("--view", choices=("list", "grid"), default="list")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        data, paths = load_profile(args.store, args.document_paths)
        store = adapt_store(data, paths)
        html = render_html(
            store,
            RenderSpec(
                title=args.title, document_url_template="file://{path}#page={page}", view=args.view
            ),
        )
        publish(args.out, html.encode("utf-8"), (args.store, args.document_paths), force=args.force)
    except (OSError, ValueError, KeyError) as exc:
        print(f"render-html-hub: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
