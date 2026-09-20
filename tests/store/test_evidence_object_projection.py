"""The packaged contract and projected pointers agree with the fleet schema."""

import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from deliverable_render.store.schema import evidence_schema
from deliverable_render.store.validate import project_evidence, validate_store

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/stores"


def test_store_evidence_projects_to_schema():
    shared = json.loads(
        (ROOT / "docs/contracts/schemas/evidence-object-v1.schema.json").read_text()
    )
    assert evidence_schema() == shared
    pointer = json.loads((FIXTURES / "valid_evidence_store.json").read_text())["entries"][0][
        "mentions"
    ][0]["src"]
    first = project_evidence(pointer, fact_ref="entries/entry-1/mentions/0")
    assert first == project_evidence(pointer, fact_ref="entries/entry-1/mentions/0")
    assert first["source_id"] == "doc-1"
    assert first["excerpt"] == "Assets of $36B"
    assert first["fact_ref"] == "entries/entry-1/mentions/0"
    assert first["locator"]["page"] == 3
    assert list(Draft202012Validator(shared).iter_errors(first)) == []
    assert validate_store(FIXTURES / "valid_evidence_store.json").valid


def test_publication_src_projects_with_pub_fact_ref():
    pointer = {
        "stable_id": "doc-1",
        "method": "parser",
        "quote": "Published excerpt",
        "page": 2,
        "confidence": 0.9,
    }
    projected = project_evidence(pointer, fact_ref="entries/entry-1/pub")
    assert projected["fact_ref"] == "entries/entry-1/pub"
    assert projected["confidence"] == 0.9
    assert projected["locator"]["page"] == 2
    assert list(Draft202012Validator(evidence_schema()).iter_errors(projected)) == []


def test_publication_src_rejects_conflicting_native_fact_ref(tmp_path):
    data = json.loads((FIXTURES / "valid_evidence_store.json").read_text())
    data["entries"][0]["pub"]["src"] = {
        "schema_version": "evidence-object/v1",
        "evidence_id": "sha256:deadbeef",
        "fact_ref": "entries/wrong/pub",
        "source_id": "doc-1",
        "method": "parser",
        "excerpt": "Published excerpt",
    }
    path = tmp_path / "bad-pub.json"
    path.write_text(json.dumps(data))
    issues = validate_store(path).issues
    assert any(
        issue.code == "evidence-projection" and "/pub/src" in issue.path for issue in issues
    )


def test_nonfinite_json_constant_rejected(tmp_path):
    path = tmp_path / "nan.json"
    path.write_text('{"fund": {}, "periods": [], "entries": [], "themes": [], "documents": [], "gaps": [], "bps": NaN}')
    report = validate_store(path)
    assert any(issue.code == "input" for issue in report.issues)


def test_missing_method_cannot_be_fabricated(tmp_path):
    data = json.loads((FIXTURES / "valid_evidence_store.json").read_text())
    del data["entries"][0]["mentions"][0]["src"]["method"]
    path = tmp_path / "missing-method.json"
    path.write_text(json.dumps(data))
    assert any(issue.code == "evidence-projection" for issue in validate_store(path).issues)


def test_both_cli_entry_paths_return_failure_for_orphan():
    bad = FIXTURES / "orphan_entry_id.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    commands = [
        [sys.executable, str(ROOT / "scripts/validate_structured_store.py"), str(bad)],
        [sys.executable, "-m", "deliverable_render.store.validate", str(bad)],
    ]
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
        assert result.returncode == 1
        assert "entry-typo" in result.stdout


def test_cli_success_for_valid_store():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_structured_store.py"),
            str(FIXTURES / "valid_evidence_store.json"),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_packaged_console_entry_rejects_orphan(tmp_path):
    wheel_dir = tmp_path / "wheels"
    install_dir = tmp_path / "site"
    wheel_dir.mkdir()
    install_dir.mkdir()
    build = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "-w", str(wheel_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheel = next(wheel_dir.glob("deliverable_render-*.whl"))
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--target", str(install_dir), str(wheel)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    env = {**os.environ, "PYTHONPATH": str(install_dir)}
    result = subprocess.run(
        [sys.executable, "-m", "deliverable_render.store.validate", str(FIXTURES / "orphan_entry_id.json")],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 1
    assert "entry-typo" in result.stdout
