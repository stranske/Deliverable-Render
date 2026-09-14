"""The scaffold rename is load-bearing: CI installs the distribution by name and imports the package.

A leftover template name is not a cosmetic defect. It means the installed distribution and the
imported module disagree, which surfaces later as an import error in a workflow rather than here.
"""

from __future__ import annotations

import importlib
import pathlib
import tomllib


def test_distribution_and_package_names_are_not_the_template_placeholder() -> None:
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "deliverable-render"
    assert not pathlib.Path("src/my_project").exists()


def test_package_imports_and_exposes_a_version() -> None:
    mod = importlib.import_module("deliverable_render")
    assert mod.__version__


def test_authors_are_not_template_placeholders() -> None:
    """The template ships `Your Name`; these values land in the built sdist and wheel.

    Same failure mode as the distribution name above, one layer out: an installer reads the
    placeholder as this package's author of record.
    """
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    for author in data["project"]["authors"]:
        assert "Your Name" not in author.get("name", "")
        assert "your.email@example.com" not in author.get("email", "")


def test_project_urls_point_at_this_repository() -> None:
    """The template's URLs send a reader to stranske/Template, a different repository."""
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    urls = data["project"]["urls"]
    for label in ("Homepage", "Repository"):
        assert urls[label].endswith("/Deliverable-Render"), f"{label} -> {urls[label]}"
