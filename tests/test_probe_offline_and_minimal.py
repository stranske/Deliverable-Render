"""Tests for the offline capability probe (issue #4 acceptance gate)."""

import json
import re
import subprocess
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
INLINE_SCRIPT_RE = re.compile(r"<script>\s*(.*?)\s*</script>", re.DOTALL)
ES5_FORBIDDEN_RE = re.compile(r"\b(const|let)\s+|async\s+function\b")


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


def _extract_inline_script(html: str) -> str:
    match = INLINE_SCRIPT_RE.search(html)
    assert match is not None, "inline probe script missing"
    return match.group(1)


def _probe_dom_mock() -> str:
    return """
var captured = {};
var cells = {};
function makeCell(initial) {
  return { textContent: initial };
}
["wasm","worker","sab","idb","ls","fetch","link","js","pyodide"].forEach(function(key) {
  cells[key] = makeCell("pending");
});
function noopButton() {
  return { disabled: false, addEventListener: function() {} };
}
var summaryArea = { value: "", select: function() {} };
var copyButton = noopButton();
var document = {
  getElementById: function(id) {
    if (id === "summary") return summaryArea;
    if (id === "copy-summary") return copyButton;
    if (id === "run-probe") return noopButton();
    if (id === "run-pyodide") return noopButton();
    if (id === "pyodide-status") return { textContent: "" };
    if (id.indexOf("row-") === 0) {
      var key = id.slice(4);
      return {
        querySelector: function() { return cells[key]; }
      };
    }
    return null;
  },
  querySelector: function(selector) {
    if (selector === "#row-pyodide .result") return cells.pyodide;
    return null;
  },
  querySelectorAll: function(selector) {
    if (selector === "#results .result") {
      return Object.keys(cells).map(function(key) { return cells[key]; });
    }
    return [];
  },
  createElement: function() { return {}; },
  head: { appendChild: function() {} },
  body: { appendChild: function() {} },
  execCommand: function() { return true; }
};
Object.defineProperty(globalThis, "navigator", {
  value: { userAgent: "Mozilla/5.0 Chrome/120.0.0.0", clipboard: null },
  configurable: true
});
var openedWindow = { closed: false, close: function() { this.closed = true; } };
var window = {
  open: function() { return openedWindow; },
  indexedDB: undefined
};
"""


def _node_probe_runtime(script: str, prelude: str = "") -> dict[str, object]:
    runner = f"""{_probe_dom_mock()}
{script}
{prelude}
captured.summary = buildSummary();
captured.results = results;
captured.summaryArea = summaryArea.value;
captured.copyDisabled = copyButton.disabled;
console.log(JSON.stringify(captured));
"""
    proc = subprocess.run(
        ["node", "-e", runner],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"node probe runtime failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return json.loads(proc.stdout.strip())


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


def test_generated_summary_privacy_and_shape() -> None:
    html = build_probe()
    script = _extract_inline_script(html)
    controlled = _node_probe_runtime(
        script,
        prelude="""
setResult("wasm", "pass");
setResult("worker", "pass");
setResult("sab", "blocked");
setResult("idb", "pass");
setResult("ls", "pass");
setResult("fetch", "blocked");
setResult("link", "blocked");
setResult("js", "pass");
""",
    )
    summary = controlled["summary"]
    assert isinstance(summary, str)
    assert FORBIDDEN_SUMMARY_RE.search(summary) is None
    assert summary.startswith("cap-probe|")
    assert "wasm=pass" in summary
    assert "worker=pass" in summary
    assert "engine=Chrome/120.0.0.0" in summary
    assert "pyodide=" not in summary


def test_generated_bootstrap_is_es5_parse_safe() -> None:
    html = build_probe()
    script = _extract_inline_script(html)
    assert ES5_FORBIDDEN_RE.search(script) is None
    assert "new Function(" in script


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
    script = _extract_inline_script(html)
    runtime = _node_probe_runtime(
        script,
        prelude="""
WebAssembly = undefined;
testWasm();
""",
    )
    assert runtime["results"]["wasm"] == "fail"


def test_generated_run_probe_updates_summary_with_worker_result() -> None:
    html = build_probe()
    script = _extract_inline_script(html)
    proc = subprocess.run(
        [
            "node",
            "-e",
            f"""{_probe_dom_mock()}
var WebAssembly = {{ instantiate: function() {{ return Promise.resolve(); }} }};
var Worker = function(url) {{
  this.onmessage = null;
  setImmediate(function() {{ if (this.onmessage) this.onmessage({{ data: "ok" }}); }}.bind(this));
}};
var URL = {{ createObjectURL: function() {{ return "blob:probe"; }}, revokeObjectURL: function() {{}} }};
var Blob = function() {{}};
var localStorage = {{
  _data: {{}},
  setItem: function(k, v) {{ this._data[k] = String(v); }},
  getItem: function(k) {{ return this._data[k] || null; }},
  removeItem: function(k) {{ delete this._data[k]; }}
}};
var fetch = function() {{ return Promise.reject(new Error("blocked")); }};
{script}
runProbe().then(function() {{
  console.log(JSON.stringify({{ summary: summaryArea.value, worker: results.worker, wasm: results.wasm }}));
}});
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.strip())
    payload = json.loads(proc.stdout.strip())
    assert payload["wasm"] == "pass"
    assert payload["worker"] == "pass"
    assert "worker=pass" in payload["summary"]
    assert "wasm=pass" in payload["summary"]


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
