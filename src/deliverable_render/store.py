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
from collections.abc import Mapping
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
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise StoreValidationError("Expected an object with string keys")
    return value


def _array(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise StoreValidationError(f"{field} must be an array")
    return value


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
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if any(not isinstance(pointer, EvidencePointer) for pointer in self.evidence):
            raise StoreValidationError("evidence must contain EvidencePointer objects")


@dataclass(frozen=True)
class Store:
    records: tuple[Record, ...]
    documents: tuple[Document, ...]

    def __post_init__(self) -> None:
        for field, cls, key in (
            ("records", Record, "record_id"),
            ("documents", Document, "stable_id"),
        ):
            values = tuple(getattr(self, field))
            object.__setattr__(self, field, values)
            if any(not isinstance(value, cls) for value in values):
                raise StoreValidationError(f"{field} contains an invalid object")
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
