"""Shared, immutable input contract for deliverable renderers.

JSON contains ``documents`` and ``records`` arrays. Documents have ``stable_id``
and ``path``; records have ``record_id``, ``entity_ref``, ``period``, ``section``,
``text``, and an ``evidence`` array of {stable_id, page, quote} objects. Pages are
one-based. Entity references and period labels are preserved verbatim.

SQLite uses the tables in :data:`SQLITE_SCHEMA`. Records and evidence retain
insertion (rowid) order, just as JSON arrays retain their order. Entity and period
indexes are derived from records rather than persisted, preventing stale indexes.
Missing document references are retained for the renderer's link-integrity check.
This compact rendering contract does not replace the richer fleet evidence schema.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

SQLITE_SCHEMA = """
CREATE TABLE documents (stable_id TEXT PRIMARY KEY, path TEXT NOT NULL);
CREATE TABLE records (
    record_id TEXT PRIMARY KEY,
    entity_ref TEXT NOT NULL,
    period TEXT NOT NULL,
    section TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE evidence (
    record_id TEXT NOT NULL REFERENCES records(record_id),
    stable_id TEXT NOT NULL,
    page INTEGER NOT NULL CHECK (page > 0),
    quote TEXT NOT NULL
);
"""


class StoreValidationError(ValueError):
    """The input does not satisfy the rendering store contract."""


def _string(value: object, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise StoreValidationError(
            f"{field} must be a string" + ("" if allow_empty else " (nonempty)")
        )
    return value


def _object(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise StoreValidationError("Expected an object with string keys")
    return value


def _array(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise StoreValidationError(f"{field} must be an array")
    return value


def _items[T](value: object, field: str, cls: type[T]) -> tuple[T, ...]:
    """Copy model collections, rejecting scalars and mappings even when empty."""
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        raise StoreValidationError(f"{field} must be an iterable of {cls.__name__} objects")
    items = []
    for item in value:
        if not isinstance(item, cls):
            raise StoreValidationError(
                f"{field} contains an invalid object; expected {cls.__name__}"
            )
        items.append(item)
    return tuple(items)


@dataclass(frozen=True)
class EvidencePointer:
    stable_id: str
    page: int
    quote: str

    def __post_init__(self) -> None:
        _string(self.stable_id, "stable_id")
        if type(self.page) is not int or self.page < 1:
            raise StoreValidationError("page must be a positive integer")
        _string(self.quote, "quote", allow_empty=True)


@dataclass(frozen=True)
class Document:
    stable_id: str
    path: str

    def __post_init__(self) -> None:
        _string(self.stable_id, "stable_id")
        _string(self.path, "path")


@dataclass(frozen=True)
class Record:
    record_id: str
    entity_ref: str
    period: str
    section: str
    text: str
    evidence: tuple[EvidencePointer, ...] = ()

    def __post_init__(self) -> None:
        for field in ("record_id", "entity_ref", "period", "section"):
            _string(getattr(self, field), field)
        _string(self.text, "text", allow_empty=True)
        object.__setattr__(self, "evidence", _items(self.evidence, "evidence", EvidencePointer))


@dataclass(frozen=True)
class Store:
    records: tuple[Record, ...]
    documents: tuple[Document, ...]

    def __post_init__(self) -> None:
        for field, cls, key in (
            ("records", Record, "record_id"),
            ("documents", Document, "stable_id"),
        ):
            values = _items(getattr(self, field), field, cls)
            object.__setattr__(self, field, values)
            ids = [getattr(value, key) for value in values]
            if len(ids) != len(set(ids)):
                raise StoreValidationError(f"Duplicate {key} in {field}")

    @property
    def evidence(self) -> tuple[EvidencePointer, ...]:
        """All pointers in record order, including repeated citations."""
        return tuple(pointer for record in self.records for pointer in record.evidence)

    def _index(self, field: str) -> Mapping[str, tuple[Record, ...]]:
        index: dict[str, list[Record]] = {}
        for record in self.records:
            index.setdefault(getattr(record, field), []).append(record)
        return MappingProxyType({key: tuple(records) for key, records in index.items()})

    @property
    def entity_index(self) -> Mapping[str, tuple[Record, ...]]:
        return self._index("entity_ref")

    @property
    def period_index(self) -> Mapping[str, tuple[Record, ...]]:
        return self._index("period")

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Store:
        """Validate decoded JSON; unknown fields are ignored for forward compatibility."""
        data = _object(data)
        documents = []
        for item in _array(data.get("documents"), "documents"):
            obj = _object(item)
            documents.append(
                Document(
                    _string(obj.get("stable_id"), "stable_id"), _string(obj.get("path"), "path")
                )
            )
        records = []
        for item in _array(data.get("records"), "records"):
            obj = _object(item)
            evidence = []
            for raw in _array(obj.get("evidence"), "evidence"):
                pointer = _object(raw)
                page = pointer.get("page")
                if type(page) is not int:
                    raise StoreValidationError("page must be a positive integer")
                evidence.append(
                    EvidencePointer(
                        _string(pointer.get("stable_id"), "stable_id"),
                        page,
                        _string(pointer.get("quote"), "quote", allow_empty=True),
                    )
                )
            records.append(
                Record(
                    record_id=_string(obj.get("record_id"), "record_id"),
                    entity_ref=_string(obj.get("entity_ref"), "entity_ref"),
                    period=_string(obj.get("period"), "period"),
                    section=_string(obj.get("section"), "section"),
                    text=_string(obj.get("text"), "text", allow_empty=True),
                    evidence=tuple(evidence),
                )
            )
        return cls(tuple(records), tuple(documents))

    @classmethod
    def from_json(cls, path: str | Path) -> Store:
        """Load a UTF-8 JSON file."""
        return cls.from_dict(_object(json.loads(Path(path).read_text(encoding="utf-8"))))

    @classmethod
    def from_sqlite(cls, path: str | Path) -> Store:
        """Read an existing database without creating or modifying it."""
        connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            with connection:
                connection.execute("BEGIN")
                documents = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT stable_id, path FROM documents ORDER BY rowid"
                    )
                ]
                records = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT record_id, entity_ref, period, section, text FROM records ORDER BY rowid"
                    )
                ]
                by_id = {record["record_id"]: record for record in records}
                for record in records:
                    record["evidence"] = []
                for row in connection.execute(
                    "SELECT record_id, stable_id, page, quote FROM evidence ORDER BY rowid"
                ):
                    pointer = dict(row)
                    record_id = pointer.pop("record_id")
                    if record_id not in by_id:
                        raise StoreValidationError(f"Evidence names unknown record_id: {record_id}")
                    by_id[record_id]["evidence"].append(pointer)
            return cls.from_dict({"documents": documents, "records": records})
        finally:
            connection.close()


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
        object.__setattr__(self, "changes", _items(self.changes, "changes", ChangeRow))
        object.__setattr__(self, "continuity", _items(self.continuity, "continuity", ContinuityRow))

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
        return cls.from_dict(_object(json.loads(Path(path).read_text(encoding="utf-8"))))
