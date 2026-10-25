"""Keep repository-owned CI callers on the owner's tested Python standard."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
RUNTIME_KEYS = {
    "python-version",
    "python-versions",
    "primary-python-version",
    "coverage-python-version",
    "PYTHON_VERSION",
    "COVERAGE_REFERENCE_RUNTIME",
}


def _runtime_pins(node: Any, location: str) -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{location}.{key}"
            if key in RUNTIME_KEYS:
                yield path, value
            yield from _runtime_pins(value, path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _runtime_pins(value, f"{location}[{index}]")


def _contains_old_runtime(value: Any) -> bool:
    if isinstance(value, list):
        return any(_contains_old_runtime(item) for item in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            pass
        else:
            if decoded != value:
                return _contains_old_runtime(decoded)
    return str(value) == "3.12" or str(value).startswith("3.12.")


def _load_workflows() -> dict[str, Any]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOWS.iterdir())
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }


def _assert_workflows_follow_standard(workflows: dict[str, Any]) -> None:
    assert workflows, "No workflow YAML was inspected"
    offenders = [
        location
        for filename, workflow in workflows.items()
        for location, value in _runtime_pins(workflow, filename)
        if _contains_old_runtime(value)
    ]
    assert not offenders, f"Python 3.12 runtime pins remain: {offenders}"
    for filename, job in (("ci.yml", "python"), ("pr-00-gate.yml", "python-ci")):
        config = workflows[filename]["jobs"][job]
        assert json.loads(config["with"]["python-versions"]) == ["3.13", "3.14"]
        assert config["with"]["primary-python-version"] == "3.14"
        assert not config.get("continue-on-error", False)

    references = [
        value
        for location, value in _runtime_pins(workflows["pr-00-gate.yml"], "pr-00-gate.yml")
        if location.endswith(".COVERAGE_REFERENCE_RUNTIME")
    ]
    assert references and all(value == "3.13" for value in references)


def test_workflow_python_pins_follow_standard() -> None:
    _assert_workflows_follow_standard(_load_workflows())


@pytest.mark.parametrize(
    ("filename", "job", "key", "retired_value"),
    [
        ("ci.yml", "python", "python-versions", '["3.12", "3.13"]'),
        ("pr-00-gate.yml", "python-ci", "python-versions", '["3.12", "3.13"]'),
        ("pr-00-gate.yml", "python-ci", "primary-python-version", "3.12"),
    ],
)
def test_rejects_each_original_caller_runtime(
    filename: str, job: str, key: str, retired_value: str
) -> None:
    workflows = _load_workflows()
    inputs = workflows[filename]["jobs"][job]["with"]
    corrected_value = inputs[key]
    inputs[key] = retired_value

    location = f"{filename}.jobs.{job}.with.{key}"
    with pytest.raises(AssertionError, match=re.escape(location)):
        _assert_workflows_follow_standard(workflows)

    inputs[key] = corrected_value
    _assert_workflows_follow_standard(workflows)


def test_rejects_original_coverage_reference_runtime() -> None:
    workflows = _load_workflows()
    references = [
        step["env"]
        for job in workflows["pr-00-gate.yml"]["jobs"].values()
        for step in job.get("steps", [])
        if "COVERAGE_REFERENCE_RUNTIME" in step.get("env", {})
    ]
    assert references, "No coverage reference runtime was inspected"
    for reference in references:
        corrected_value = reference["COVERAGE_REFERENCE_RUNTIME"]
        reference["COVERAGE_REFERENCE_RUNTIME"] = "3.12"
        with pytest.raises(
            AssertionError, match=r"Python 3\.12 runtime pins remain:.*\.COVERAGE_REFERENCE_RUNTIME"
        ):
            _assert_workflows_follow_standard(workflows)

        reference["COVERAGE_REFERENCE_RUNTIME"] = corrected_value
        _assert_workflows_follow_standard(workflows)
