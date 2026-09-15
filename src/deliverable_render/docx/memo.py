"""Render consultant change and continuity memos from a structured store."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from docx import Document

MATERIAL_TIERS = frozenset({"T1", "T2"})


class MemoValidationError(ValueError):
    """The structured store does not satisfy the memo rendering contract."""


def _string(value: object, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise MemoValidationError(
            f"{field} must be a string" + ("" if allow_empty else " (nonempty)")
        )
    return value


def _object(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MemoValidationError("Expected an object")
    return value


def _array(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise MemoValidationError(f"{field} must be an array")
    return value


@dataclass(frozen=True)
class ChangeRow:
    canonical_section: str
    change_type: str
    tier: str
    prior_text: str
    current_text: str

    def __post_init__(self) -> None:
        _string(self.canonical_section, "canonical_section")
        _string(self.change_type, "change_type")
        _string(self.tier, "tier")
        _string(self.prior_text, "prior_text", allow_empty=True)
        _string(self.current_text, "current_text", allow_empty=True)


@dataclass(frozen=True)
class ContinuityRow:
    canonical_section: str
    prior_text: str
    current_text: str

    def __post_init__(self) -> None:
        _string(self.canonical_section, "canonical_section")
        _string(self.prior_text, "prior_text", allow_empty=True)
        _string(self.current_text, "current_text", allow_empty=True)


@dataclass(frozen=True)
class StructuredStore:
    """Ledger-oriented store consumed by memo renderers."""

    entity_ref: str
    period_current: str
    period_prior: str
    changes: tuple[ChangeRow, ...]
    continuity: tuple[ContinuityRow, ...] = ()

    def __post_init__(self) -> None:
        _string(self.entity_ref, "entity_ref")
        _string(self.period_current, "period_current")
        _string(self.period_prior, "period_prior")

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> StructuredStore:
        data = _object(data)
        changes = []
        for item in _array(data.get("changes"), "changes"):
            obj = _object(item)
            changes.append(
                ChangeRow(
                    canonical_section=_string(obj.get("canonical_section"), "canonical_section"),
                    change_type=_string(obj.get("change_type"), "change_type"),
                    tier=_string(obj.get("tier"), "tier"),
                    prior_text=_string(obj.get("prior_text"), "prior_text", allow_empty=True),
                    current_text=_string(obj.get("current_text"), "current_text", allow_empty=True),
                )
            )
        continuity = []
        for item in _array(data.get("continuity", []), "continuity"):
            obj = _object(item)
            continuity.append(
                ContinuityRow(
                    canonical_section=_string(obj.get("canonical_section"), "canonical_section"),
                    prior_text=_string(obj.get("prior_text"), "prior_text", allow_empty=True),
                    current_text=_string(obj.get("current_text"), "current_text", allow_empty=True),
                )
            )
        return cls(
            entity_ref=_string(data.get("entity_ref"), "entity_ref"),
            period_current=_string(data.get("period_current"), "period_current"),
            period_prior=_string(data.get("period_prior"), "period_prior"),
            changes=tuple(changes),
            continuity=tuple(continuity),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> StructuredStore:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


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
    document = Document()
    document.add_heading("Consultant Change Memo", level=0)
    document.add_paragraph(
        f"{store.entity_ref}: {store.period_prior} to {store.period_current}"
    )
    material = _material_changes(store)
    if not material:
        raise MemoValidationError("No material T1/T2 changes to render")
    _write_change_sections(document, material)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    return output_path


def render_continuity_memo(store: StructuredStore, output_path: Path) -> Path:
    """Write a continuity memo for unchanged ledger slices."""
    output_path = Path(output_path)
    document = Document()
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
    document.save(output_path)
    return output_path
