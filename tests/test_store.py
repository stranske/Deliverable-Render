import typing

"""The same synthetic input must survive both storage backends unchanged."""

import json
import sqlite3
from contextlib import closing
from dataclasses import FrozenInstanceError

import pytest

from deliverable_render.store import (
    SQLITE_SCHEMA,
    Document,
    EvidencePointer,
    Record,
    Store,
    StoreValidationError,
)


@pytest.fixture
def payload():
    return {
        "documents": [{"stable_id": "document:synthetic", "path": "reports/Annual report.pdf"}],
        "records": [
            {
                "record_id": "r2",
                "entity_ref": "fund:example",
                "period": "2025",
                "section": "Governance",
                "text": "Committee reviewed the policy — approved.",
                "evidence": [
                    {"stable_id": "document:synthetic", "page": 3, "quote": "Approved."},
                    {"stable_id": "document:synthetic", "page": 3, "quote": "Approved."},
                ],
            },
            {
                "record_id": "r1",
                "entity_ref": "fund:example",
                "period": "2024",
                "section": "Governance",
                "text": "",
                "evidence": [],
            },
        ],
    }


def write_database(path: typing.Any, payload: typing.Any) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SQLITE_SCHEMA)
        for document in payload["documents"]:
            db.execute(
                "INSERT INTO documents VALUES (?, ?)", (document["stable_id"], document["path"])
            )
        for record in payload["records"]:
            db.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                tuple(
                    record[key] for key in ("record_id", "entity_ref", "period", "section", "text")
                ),
            )
            for pointer in record["evidence"]:
                db.execute(
                    "INSERT INTO evidence VALUES (?, ?, ?, ?)",
                    (record["record_id"], pointer["stable_id"], pointer["page"], pointer["quote"]),
                )


def test_json_and_sqlite_preserve_records_and_indexes(tmp_path, payload):
    json_path = tmp_path / "store.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "store #1.sqlite"
    write_database(db_path, payload)
    before = db_path.read_bytes()
    store = Store.from_json(json_path)
    assert Store.from_sqlite(db_path) == store == Store.from_dict(payload)
    assert db_path.read_bytes() == before
    assert [record.record_id for record in store.records] == ["r2", "r1"]
    assert store.documents == (Document("document:synthetic", "reports/Annual report.pdf"),)
    assert store.entity_index == {"fund:example": store.records}
    assert list(store.period_index) == ["2025", "2024"]
    assert store.period_index["2024"] == (store.records[1],)
    assert store.evidence == (EvidencePointer("document:synthetic", 3, "Approved."),) * 2


def test_empty_store_loads_from_both_formats(tmp_path):
    payload: typing.Any = {"documents": [], "records": []}
    path = tmp_path / "empty.sqlite"
    write_database(path, payload)
    store = Store.from_dict(payload)
    assert Store.from_sqlite(path) == store
    assert store.records == () and store.evidence == ()
    assert store.entity_index == store.period_index == {}


def test_model_is_immutable_and_copies_input(payload):
    store = Store.from_dict(payload)
    payload["records"][0]["evidence"].clear()
    assert len(store.evidence) == 2
    with pytest.raises(FrozenInstanceError):
        store.records[0].text = "changed"  # type: ignore
    with pytest.raises(TypeError):
        store.entity_index["new"] = ()  # type: ignore
    pointers = [EvidencePointer("doc", 1, "")]
    record = Record("r", "fund:example", "2025", "Section", "", tuple(pointers))
    records = [record]
    direct = Store(tuple(records), ())
    pointers.clear()
    records.clear()
    assert direct.records == (record,)
    assert record.evidence == (EvidencePointer("doc", 1, ""),)


@pytest.mark.parametrize("page", [0, -1, True, 1.5, "3", None])
def test_invalid_pages_are_rejected(payload, page):
    payload["records"][0]["evidence"][0]["page"] = page
    with pytest.raises(StoreValidationError, match="page"):
        Store.from_dict(payload)


@pytest.mark.parametrize(
    "field", ["record_id", "entity_ref", "period", "section", "text", "evidence"]
)
def test_required_record_fields(payload, field):
    del payload["records"][0][field]
    with pytest.raises(StoreValidationError, match=field):
        Store.from_dict(payload)


@pytest.mark.parametrize("field", ["records", "documents"])
def test_duplicate_ids_rejected(payload, field):
    payload[field].append(payload[field][0])
    with pytest.raises(StoreValidationError, match="Duplicate"):
        Store.from_dict(payload)


@pytest.mark.parametrize("item", [None, [], "record", {1: "value"}])
def test_invalid_objects_rejected(payload, item):
    payload["records"] = [item]
    with pytest.raises(StoreValidationError, match="object"):
        Store.from_dict(payload)


def test_missing_document_is_retained_for_render_validation(payload):
    payload["documents"] = []
    assert Store.from_dict(payload).evidence[0].stable_id == "document:synthetic"


def test_orphan_sqlite_evidence_rejected(tmp_path):
    path = tmp_path / "orphan.sqlite"
    write_database(path, {"documents": [], "records": []})
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("INSERT INTO evidence VALUES (?, ?, ?, ?)", ("missing", "doc", 1, "quote"))
    with pytest.raises(StoreValidationError, match="unknown record_id: missing"):
        Store.from_sqlite(path)


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        Store.from_sqlite(path)
    assert not path.exists()


def test_invalid_direct_models():
    with pytest.raises(StoreValidationError, match="evidence"):
        Record("r", "entity", "period", "section", "", ("invalid",))  # type: ignore
    with pytest.raises(StoreValidationError, match="invalid object"):
        Store(("invalid",), ())  # type: ignore
    with pytest.raises(StoreValidationError, match="nonempty"):
        Document(" ", "path")


def test_invalid_json_root(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(StoreValidationError, match="object"):
        Store.from_json(path)


def test_unknown_fields_are_ignored(payload):
    payload["unknown_root_field"] = "ignored"
    payload["documents"][0]["unknown_doc_field"] = "ignored"
    payload["records"][0]["unknown_record_field"] = "ignored"
    payload["records"][0]["evidence"][0]["unknown_ev_field"] = "ignored"
    store = Store.from_dict(payload)
    assert len(store.documents) == 1
    assert len(store.records) == 2
