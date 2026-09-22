"""Read-only semantic validation of the communication-synthesis store."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from .schema import ARRAY_FIELDS, MONETARY_FIELDS, REQUIRED_TOP_LEVEL, evidence_schema

_MONEY_REMNANT = re.compile(r"^\$?B$", re.IGNORECASE)
_EXPLICIT_MONEY_REMNANT = re.compile(r"\$B\b", re.IGNORECASE)
_MONEY_CONTEXT = re.compile(
    r"\b(?:assets?|aum|valuation|capital|size|amount|market value|worth)"
    r"\s*(?:of|at|:|=)?\s*\$?B\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    def fail(self, code: str, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(code, path, message))


def _path(base: str, part: str | int) -> str:
    return base + "/" + str(part).replace("~", "~0").replace("/", "~1")


def _objects(value: Any, path: str, report: ValidationReport) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        report.fail("type", path, "expected an array")
        return []
    objects = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            objects.append(item)
        else:
            report.fail("type", _path(path, index), "expected an object")
            objects.append({})  # retain the original index for subsequent diagnostics
    return objects


def _ids(items: list[dict[str, Any]], path: str, report: ValidationReport) -> set[str]:
    found: set[str] = set()
    for index, item in enumerate(items):
        ident = item.get("id")
        item_path = _path(_path(path, index), "id")
        if not isinstance(ident, str) or not ident.strip():
            report.fail("id", item_path, "expected a nonempty string ID")
        elif ident in found:
            report.fail("duplicate-id", item_path, f"duplicate ID {ident!r}")
        else:
            found.add(ident)
    return found


def _document_identities(
    items: list[dict[str, Any]], path: str, report: ValidationReport
) -> set[str]:
    """Return unique render-facing document identities without inventing fallbacks."""
    identities: set[str] = set()
    for index, item in enumerate(items):
        identity_field = "stable_id" if "stable_id" in item else "name"
        identity = item.get(identity_field)
        if isinstance(identity, str) and identity.strip():
            identity_path = _path(_path(path, index), identity_field)
            if identity in identities:
                report.fail(
                    "duplicate-document-identity",
                    identity_path,
                    f"duplicate document identity {identity!r}",
                )
            else:
                identities.add(identity)
    return identities


def _reference(
    value: Any, targets: set[str], path: str, collection: str, report: ValidationReport
) -> None:
    if not isinstance(value, str) or value not in targets:
        report.fail("orphan-reference", path, f"{value!r} does not resolve in {collection}")


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def project_evidence(pointer: dict[str, Any], *, fact_ref: str) -> dict[str, Any]:
    """Project an explicit pointer without inventing extraction method or excerpt."""
    if pointer.get("schema_version") == "evidence-object/v1":
        native = dict(pointer)
        if native.get("fact_ref") != fact_ref:
            raise ValueError("fact_ref does not match the enclosing store location")
        return native
    source_id = pointer.get("source_id", pointer.get("stable_id"))
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id/stable_id is required")
    if "method" not in pointer:
        raise ValueError("method is required; extraction provenance cannot be inferred")
    if "excerpt" not in pointer and "quote" not in pointer:
        raise ValueError("excerpt/quote is required (explicit null is allowed)")
    excerpt = pointer.get("excerpt", pointer.get("quote"))
    identity = json.dumps([source_id, fact_ref, excerpt], ensure_ascii=False, sort_keys=True)
    projected: dict[str, Any] = {
        "schema_version": "evidence-object/v1",
        "evidence_id": pointer.get(
            "evidence_id", "sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        ),
        "fact_ref": fact_ref,
        "source_id": source_id,
        "method": pointer["method"],
        "excerpt": excerpt,
    }
    if "confidence" in pointer:
        projected["confidence"] = pointer["confidence"]
    if "entity_ref" in pointer:
        projected["entity_ref"] = pointer["entity_ref"]
    if "locator" in pointer:
        locator = dict(pointer["locator"])
        if "page" in pointer:
            locator.setdefault("page", pointer["page"])
        projected["locator"] = locator
    elif "page" in pointer:
        projected["locator"] = {"page": pointer["page"]}
    return projected


def _validate_pointer(
    pointer: Any,
    path: str,
    fact_ref: str,
    validator: Draft202012Validator,
    document_ids: set[str],
    report: ValidationReport,
) -> None:
    if not isinstance(pointer, dict):
        report.fail(
            "evidence-projection",
            path,
            "source pointer must include method and excerpt; a bare document ID cannot project",
        )
        return
    try:
        projected = project_evidence(pointer, fact_ref=fact_ref)
    except (TypeError, ValueError) as exc:
        report.fail("evidence-projection", path, str(exc))
        return
    for error in sorted(validator.iter_errors(projected), key=lambda e: str(e.absolute_path)):
        location = path
        for part in error.absolute_path:
            location = _path(location, part)
        report.fail("evidence-schema", location, error.message)
    locator = projected.get("locator") or {}
    page = locator.get("page")
    if type(page) is not int or page < 1:
        page_path = (
            _path(_path(path, "locator"), "page")
            if isinstance(pointer.get("locator"), dict)
            else _path(path, "page")
        )
        report.fail(
            "invalid-evidence-page",
            page_path,
            "positive one-based evidence page required",
        )
    _reference(
        projected.get("source_id"),
        document_ids,
        _path(path, "source_id"),
        "documents",
        report,
    )


def _check_money(value: Any, path: str, report: ValidationReport, key: str = "") -> None:
    if isinstance(value, dict):
        for name, child in value.items():
            _check_money(child, _path(path, name), report, name)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_money(child, _path(path, index), report, key)
    elif isinstance(value, str) and (
        _EXPLICIT_MONEY_REMNANT.search(value)
        or (key.lower() in MONETARY_FIELDS and _MONEY_REMNANT.fullmatch(value.strip()))
        or (
            key.lower() in {"text", "note", "thesis", "desc", "detail"}
            and _MONEY_CONTEXT.search(value)
        )
    ):
        report.fail(
            "currency-remnant",
            path,
            "suspected dollar-substitution corruption: bare magnitude without a number",
        )


def validate_store(path: Path) -> ValidationReport:
    """Validate without mutating the store or accepting syntax-only success."""
    report = ValidationReport()
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        report.fail("input", "", f"cannot read JSON store: {exc}")
        return report
    if not isinstance(data, dict):
        report.fail("type", "", "expected a top-level object")
        return report
    for name in REQUIRED_TOP_LEVEL:
        if name not in data:
            report.fail("missing", _path("", name), "required store field is absent")
    if not isinstance(data.get("fund"), dict):
        report.fail("type", "/fund", "expected an object")
    sections = {
        name: _objects(data[name], _path("", name), report) for name in ARRAY_FIELDS if name in data
    }
    entry_ids = _ids(sections.get("entries", []), "/entries", report)
    period_ids = _ids(sections.get("periods", []), "/periods", report)
    document_ids = _document_identities(sections.get("documents", []), "/documents", report)
    validator = Draft202012Validator(evidence_schema())

    for entry_index, entry in enumerate(sections.get("entries", [])):
        entry_path = _path("/entries", entry_index)
        entry_id = entry.get("id")
        mentions = entry.get("mentions", [])
        for mention_index, mention in enumerate(
            _objects(mentions, _path(entry_path, "mentions"), report)
        ):
            mention_path = _path(_path(entry_path, "mentions"), mention_index)
            # The documented producer nests mentions in entries. Its q names a period;
            # explicit entry_id, if supplied, names an entry.
            _reference(mention.get("q"), period_ids, _path(mention_path, "q"), "periods", report)
            if "entry_id" in mention:
                _reference(
                    mention["entry_id"],
                    entry_ids,
                    _path(mention_path, "entry_id"),
                    "entries",
                    report,
                )
            if "src" in mention:
                _validate_pointer(
                    mention["src"],
                    _path(mention_path, "src"),
                    f"entries/{entry_id}/mentions/{mention_index}",
                    validator,
                    document_ids,
                    report,
                )
        publication = entry.get("pub")
        if isinstance(publication, dict) and "src" in publication:
            _validate_pointer(
                publication["src"],
                _path(_path(entry_path, "pub"), "src"),
                f"entries/{entry_id}/pub",
                validator,
                document_ids,
                report,
            )
        for field_name in ("first", "last"):
            if entry.get(field_name) not in (None, ""):
                _reference(
                    entry[field_name],
                    period_ids,
                    _path(entry_path, field_name),
                    "periods",
                    report,
                )

    for index, theme in enumerate(sections.get("themes", [])):
        theme_path = _path("/themes", index)
        periods = theme.get("periods", [])
        if not isinstance(periods, list):
            report.fail("type", _path(theme_path, "periods"), "expected an array")
            continue
        for period_index, period in enumerate(periods):
            _reference(
                period,
                period_ids,
                _path(_path(theme_path, "periods"), period_index),
                "periods",
                report,
            )
    _check_money(data, "", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a structured store without modifying it")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    report = validate_store(args.path)
    for issue in report.issues:
        print(f"{issue.code} {issue.path or '/'}: {issue.message}")
    if report.valid:
        print("structured store valid")
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
