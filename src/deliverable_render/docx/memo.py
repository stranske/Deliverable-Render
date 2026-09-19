"""Render consultant change and continuity memos from a structured store."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from docx import Document as DocumentFactory

from deliverable_render.store import ChangeRow, StructuredStore, StoreValidationError as MemoValidationError

if TYPE_CHECKING:
    from docx.document import Document

MATERIAL_TIERS = frozenset({"T1", "T2"})


def _material_changes(store: StructuredStore) -> tuple[ChangeRow, ...]:
    return tuple(row for row in store.changes if row.tier in MATERIAL_TIERS)


def _write_change_sections(document: Document, rows: tuple[ChangeRow, ...]) -> None:
    for row in rows:
        document.add_heading(row.canonical_section, level=2)
        document.add_paragraph(f"Change type: {row.change_type}")
        document.add_paragraph(f"Tier: {row.tier}")
        document.add_paragraph(f"Prior ({row.prior_text})")
        document.add_paragraph(f"Current ({row.current_text})")


def render_change_memo(store: StructuredStore, output_path: Path) -> Path:
    """Write a change memo covering material T1/T2 ledger rows."""
    output_path = Path(output_path)
    document = DocumentFactory()
    document.add_heading("Consultant Change Memo", level=0)
    document.add_paragraph(f"{store.entity_ref}: {store.period_prior} to {store.period_current}")
    material = _material_changes(store)
    if not material:
        raise MemoValidationError("No material T1/T2 changes to render")
    _write_change_sections(document, material)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return output_path


def render_continuity_memo(store: StructuredStore, output_path: Path) -> Path:
    """Write a continuity memo for unchanged ledger slices."""
    output_path = Path(output_path)
    document = DocumentFactory()
    document.add_heading("Consultant Continuity Memo", level=0)
    document.add_paragraph(
        f"{store.entity_ref}: continuity from {store.period_prior} to {store.period_current}"
    )
    if not store.continuity:
        raise MemoValidationError("No continuity rows to render")
    for row in store.continuity:
        document.add_heading(row.canonical_section, level=2)
        document.add_paragraph(f"Prior: {row.prior_text}")
        document.add_paragraph(f"Current: {row.current_text}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return output_path
