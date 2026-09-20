"""A syntactically valid shell-substitution remnant must not be accepted."""

import json
from pathlib import Path

from deliverable_render.store.validate import validate_store

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/stores"


def test_shell_substitution_corruption_fails_validation():
    report = validate_store(FIXTURES / "corrupted_dollar_amount.json")
    assert not report.valid
    assert {issue.path for issue in report.issues if issue.code == "currency-remnant"} == {
        "/entries/0/mentions/0/size",
        "/entries/0/mentions/0/text",
    }


def test_valid_amount_and_legitimate_ticker_b_are_not_rejected():
    report = validate_store(FIXTURES / "valid_evidence_store.json")
    assert report.valid, report.issues


def test_bare_b_in_nonmonetary_prose_is_not_a_false_positive(tmp_path):
    data = json.loads((FIXTURES / "valid_evidence_store.json").read_text())
    data["entries"][0]["thesis"] = "Class B rating"
    path = tmp_path / "legitimate.json"
    path.write_text(json.dumps(data))
    assert validate_store(path).valid
