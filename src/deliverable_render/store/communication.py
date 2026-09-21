"""Explicit rendering profile for validated communication-synthesis stores.

The semantic validator checks references and evidence provenance. Rendering also
needs document paths and page-level citations, supplied here without inference.
"""

from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any

from deliverable_render.store import (
    Document,
    EvidencePointer,
    Record,
    Store,
    StoreValidationError,
    StructuredStore,
)
from deliverable_render.store.validate import project_evidence, validate_store


class CommunicationRenderError(StoreValidationError):
    """A valid synthesis store lacks explicit data required for rendering."""


def _text(value: Any, location: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise CommunicationRenderError(f"{location} must be a nonempty string")
    return value


def _validate_document_paths(paths: object) -> dict[str, str]:
    """Copy and validate the explicit source-ID-to-absolute-path mapping."""
    if not isinstance(paths, dict):
        raise CommunicationRenderError("document-path mapping must be a JSON object")
    validated: dict[str, str] = {}
    for raw_key, raw_value in paths.items():
        key = _text(raw_key, "document-path mapping key")
        value = _text(raw_value, f"document-path mapping for {key!r}")
        if not (Path(value).is_absolute() or PureWindowsPath(value).is_absolute()):
            raise CommunicationRenderError(
                f"document-path mapping for {key!r} must be an absolute local path"
            )
        validated[key] = value
    return validated


def load_profile(store_path: Path, paths_path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate the source and load its separate, explicit document-path map."""
    report = validate_store(store_path)
    if not report.valid:
        first = report.issues[0]
        raise CommunicationRenderError(f"store validation: {first.path}: {first.message}")
    data = json.loads(store_path.read_text(encoding="utf-8"))
    try:
        paths = json.loads(paths_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommunicationRenderError(f"document-path mapping: {exc}") from exc
    return data, _validate_document_paths(paths)


def _evidence(pointer: dict[str, Any], fact_ref: str, known: set[str]) -> EvidencePointer:
    projected = project_evidence(pointer, fact_ref=fact_ref)
    source = _text(projected["source_id"], f"{fact_ref} source_id")
    if source not in known:
        raise CommunicationRenderError(f"{fact_ref}: source {source!r} is not a declared document")
    locator = projected.get("locator") or {}
    page = locator.get("page")
    if type(page) is not int or page < 1:
        raise CommunicationRenderError(f"{fact_ref}: positive one-based evidence page required")
    excerpt = projected.get("excerpt")
    if excerpt is not None and not isinstance(excerpt, str):
        raise CommunicationRenderError(f"{fact_ref}: evidence excerpt must be text or null")
    return EvidencePointer(source, page, excerpt or "")


def adapt_store(data: dict[str, Any], paths: dict[str, str]) -> Store:
    """Project validated synthesis entries into existing HTML/PPTX input types."""
    paths = _validate_document_paths(paths)
    documents: list[Document] = []
    known: set[str] = set()
    for index, raw in enumerate(data["documents"]):
        source = _text(raw.get("stable_id") or raw.get("name"), f"documents[{index}] identity")
        if source in known:
            raise CommunicationRenderError(f"duplicate document identity {source!r}")
        known.add(source)
        if source not in paths:
            raise CommunicationRenderError(f"document-path mapping missing for {source!r}")
        documents.append(Document(source, paths[source]))

    records: list[Record] = []
    for entry_index, entry in enumerate(data["entries"]):
        entry_id = _text(entry.get("id"), f"entries[{entry_index}].id")
        section = _text(entry.get("name") or entry_id, f"entries[{entry_index}].name")
        mentions = entry.get("mentions", [])
        if not isinstance(mentions, list):
            raise CommunicationRenderError(f"entries[{entry_index}].mentions must be an array")
        for mention_index, mention in enumerate(mentions):
            if not isinstance(mention, dict):
                raise CommunicationRenderError("mention must be an object")
            if "entry_id" in mention and mention["entry_id"] != entry_id:
                raise CommunicationRenderError(
                    f"entries[{entry_index}].mentions[{mention_index}] names another entry"
                )
            fact_ref = f"entries/{entry_id}/mentions/{mention_index}"
            pointer = mention.get("src")
            evidence = (_evidence(pointer, fact_ref, known),) if isinstance(pointer, dict) else ()
            records.append(
                Record(
                    record_id=f"entry-{entry_index}-mention-{mention_index}",
                    entity_ref=entry_id,
                    period=_text(mention.get("q"), f"{fact_ref}.q"),
                    section=section,
                    text=_text(mention.get("text", ""), f"{fact_ref}.text", allow_empty=True),
                    evidence=evidence,
                )
            )
        thesis = entry.get("thesis")
        if isinstance(thesis, str) and thesis.strip():
            period = entry.get("last") or entry.get("first")
            records.append(
                Record(
                    f"entry-{entry_index}-thesis",
                    entry_id,
                    _text(period, f"entries[{entry_index}] thesis period"),
                    section,
                    thesis,
                )
            )
        publication = entry.get("pub")
        if isinstance(publication, dict) and "src" in publication:
            detail = publication.get("detail") or publication.get("state")
            fact_ref = f"entries/{entry_id}/pub"
            records.append(
                Record(
                    f"entry-{entry_index}-publication",
                    entry_id,
                    _text(entry.get("last") or entry.get("first"), f"{fact_ref} period"),
                    section,
                    _text(detail, f"{fact_ref} detail"),
                    (_evidence(publication["src"], fact_ref, known),),
                )
            )
    if not records:
        raise CommunicationRenderError("communication store has no renderable entry text")
    return Store(tuple(records), tuple(documents))


def adapt_profile(store_path: Path, paths_path: Path) -> Store:
    """Validate and adapt a communication-synthesis file for HTML/PPTX renderers."""
    data, paths = load_profile(store_path, paths_path)
    return adapt_store(data, paths)


def adapt_memo(data: dict[str, Any], overlay_path: Path) -> StructuredStore:
    """Use reviewed memo rows and period IDs; never infer change materiality."""
    try:
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommunicationRenderError(f"memo overlay: {exc}") from exc
    if not isinstance(overlay, dict):
        raise CommunicationRenderError("memo overlay must be a JSON object")
    period_ids = {period.get("id") for period in data["periods"]}
    current = _text(overlay.get("period_current"), "memo period_current")
    prior = _text(overlay.get("period_prior"), "memo period_prior")
    if current == prior or current not in period_ids or prior not in period_ids:
        raise CommunicationRenderError(
            "memo period_current and period_prior must be distinct store period IDs"
        )
    entity = _text(data["fund"].get("name"), "fund.name")
    memo = StructuredStore.from_dict(
        {
            "entity_ref": entity,
            "period_current": current,
            "period_prior": prior,
            "changes": overlay.get("changes"),
            "continuity": overlay.get("continuity", []),
        }
    )
    for row in memo.changes:
        if row.tier not in {"T1", "T2", "T3"}:
            raise CommunicationRenderError(f"memo change tier {row.tier!r} is unsupported")
    return memo
