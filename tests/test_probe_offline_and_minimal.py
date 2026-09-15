"""Tests for the offline capability probe (issue #4 acceptance gate)."""

import re
from html.parser import HTMLParser
from pathlib import Path

from deliverable_render.probe.build_probe import build_probe

EXTERNAL_URL_RE = re.compile(
    r"""(?:src|href)\s*=\s*["'](?:https?:|//)[^"']+["']""",
    re.IGNORECASE,
)
FETCH_CALL_RE = re.compile(r"\bfetch\s*\(\s*['\"]https?://", re.IGNORECASE)
FORBIDDEN_SUMMARY_RE = re.compile(
    r"(?:/Users/|/home/|C:\\\\|localhost|file://|\\\\)",
    re.IGNORECASE,
)


class _TagScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, {k: v or "" for k, v in attrs}))


def _scan(html: str) -> _TagScanner:
    parser = _TagScanner()
    parser.feed(html)
    return parser


def test_built_probe_is_single_file_without_external_resources() -> None:
    html = build_probe()
    assert html.startswith("<!DOCTYPE html>")
    assert EXTERNAL_URL_RE.search(html) is None
    assert FETCH_CALL_RE.search(html) is None
    parsed = _scan(html)
    for tag, attrs in parsed.tags:
        for key in ("src", "href"):
            value = attrs.get(key, "")
            if value.startswith(("http://", "https://", "//")):
                raise AssertionError(f"external {key}={value} in <{tag}>")


def test_summary_sample_contains_no_identifying_paths() -> None:
    sample = (
        "cap-probe|wasm=pass|worker=pass|sab=blocked|idb=pass|ls=pass|"
        "fetch=blocked|link=pass|js=pass|engine=Chrome/120.0.0.0"
    )
    assert FORBIDDEN_SUMMARY_RE.search(sample) is None
    assert "cap-probe|" in sample
    assert "engine=" in sample


def test_deliberate_remote_script_tag_fails_external_scan() -> None:
    html = build_probe()
    broken = html.replace(
        "</head>",
        '<script src="https://evil.example.invalid/track.js"></script></head>',
    )
    assert EXTERNAL_URL_RE.search(broken) is not None
    assert EXTERNAL_URL_RE.search(html) is None


def test_disabling_wasm_reports_fail_not_blank() -> None:
    html = build_probe()
    disabled = html.replace(
        "<script>",
        "<script>WebAssembly = undefined;",
        1,
    )
    assert "WebAssembly = undefined" in disabled
    assert 'setResult("wasm", "fail")' in disabled
    assert disabled.count("pending") >= 1


def test_probe_includes_all_required_capability_rows() -> None:
    html = build_probe()
    for label in (
        "WebAssembly",
        "Web Worker",
        "SharedArrayBuffer",
        "IndexedDB",
        "localStorage",
        "fetch same-directory",
        "local-file link",
        "ES2015 JavaScript",
    ):
        assert label in html


def test_pyodide_stage_is_optional() -> None:
    with_stage = build_probe(include_pyodide_stage=True)
    without_stage = build_probe(include_pyodide_stage=False)
    assert "run-pyodide" in with_stage
    assert "run-pyodide" not in without_stage


def test_operator_instructions_present() -> None:
    html = build_probe()
    assert "Operator instructions" in html
    assert "Nothing is transmitted" in html or "nothing is transmitted" in html.lower()


def test_build_probe_writes_to_dist(tmp_path: Path) -> None:
    out = tmp_path / "probe.html"
    out.write_text(build_probe(), encoding="utf-8")
    assert out.stat().st_size > 1000
    assert "Run probe" in out.read_text(encoding="utf-8")
