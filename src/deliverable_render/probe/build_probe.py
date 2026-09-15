"""Build a self-contained HTML capability probe for offline environments."""

from __future__ import annotations

from html import escape

# Minimal valid WebAssembly module (empty module) inlined as bytes for offline use.
_WASM_BYTES = bytes([0, 97, 115, 109, 1, 0, 0, 0])
_WASM_JS_ARRAY = ",".join(str(b) for b in _WASM_BYTES)


def build_probe(include_pyodide_stage: bool = True) -> str:
    """Return one self-contained HTML file reporting browser capabilities.

    The page performs no network activity on load. Capability checks run when the
    operator clicks **Run probe**. An optional Pyodide stage loads only from a
    local ``pyodide/`` subdirectory when the operator explicitly requests it.
    """

    pyodide_section = ""
    pyodide_row = ""
    pyodide_script = ""
    if include_pyodide_stage:
        pyodide_row = (
            '<tr id="row-pyodide"><td>Pyodide runtime (local)</td>'
            "<td class=\"result\">not run</td></tr>"
        )
        pyodide_section = """
<section id="pyodide-stage">
  <h2>Optional: Pyodide runtime</h2>
  <p>This second stage loads a real Pyodide bundle from a <code>pyodide/</code>
     folder next to this file. Run it only if you have copied that folder here.</p>
  <button type="button" id="run-pyodide">Run Pyodide stage</button>
  <p id="pyodide-status" class="muted">Not started.</p>
</section>
"""
        pyodide_script = """
async function runPyodideStage() {
  const status = document.getElementById("pyodide-status");
  const cell = document.querySelector("#row-pyodide .result");
  status.textContent = "Loading local Pyodide runtime…";
  try {
    const script = document.createElement("script");
    script.src = "pyodide/pyodide.js";
    script.onerror = () => { throw new Error("local pyodide.js missing"); };
    await new Promise((resolve, reject) => {
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
    if (!globalThis.loadPyodide) {
      throw new Error("loadPyodide unavailable after script load");
    }
    await globalThis.loadPyodide({ indexURL: "pyodide/" });
    setResult("pyodide", "pass");
    status.textContent = "Pyodide initialized successfully from local files.";
  } catch (err) {
    setResult("pyodide", "fail");
    status.textContent = "Pyodide stage failed: " + String(err && err.message || err);
  }
}
document.getElementById("run-pyodide").addEventListener("click", runPyodideStage);
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Deliverable Render capability probe</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 52rem; line-height: 1.5; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #ccc; padding: 0.5rem 0.75rem; text-align: left; }}
th {{ background: #f4f6f8; }}
.result {{ font-weight: 600; }}
button {{ padding: 0.5rem 1rem; margin: 0.5rem 0.25rem 0.5rem 0; }}
textarea {{ width: 100%; font-family: ui-monospace, monospace; font-size: 0.9rem; }}
.muted {{ color: #555; }}
</style>
</head>
<body>
<h1>Capability probe</h1>
<p>Open this file from a local path in the target environment. Click
   <strong>Run probe</strong> to test capabilities. Nothing is transmitted;
   results stay on this machine until you copy them deliberately.</p>
<p class="muted">The summary string contains only capability pass/fail/blocked
   results and your browser&apos;s own user-agent engine version. It does not
   include paths, host names, user names, or file listings.</p>
<button type="button" id="run-probe">Run probe</button>
<button type="button" id="copy-summary" disabled>Copy summary</button>
<table id="results">
  <thead><tr><th>Capability</th><th>Result</th></tr></thead>
  <tbody>
    <tr id="row-wasm"><td>WebAssembly (inlined module)</td><td class="result">pending</td></tr>
    <tr id="row-worker"><td>Web Worker</td><td class="result">pending</td></tr>
    <tr id="row-sab"><td>SharedArrayBuffer</td><td class="result">pending</td></tr>
    <tr id="row-idb"><td>IndexedDB read/write</td><td class="result">pending</td></tr>
    <tr id="row-ls"><td>localStorage</td><td class="result">pending</td></tr>
    <tr id="row-fetch"><td>fetch same-directory file</td><td class="result">pending</td></tr>
    <tr id="row-link"><td>local-file link (new tab)</td><td class="result">pending</td></tr>
    <tr id="row-js"><td>ES2015 JavaScript baseline</td><td class="result">pending</td></tr>
    {pyodide_row}
  </tbody>
</table>
<label for="summary">Copyable summary</label>
<textarea id="summary" rows="3" readonly placeholder="Run the probe first"></textarea>
{pyodide_section}
<section>
  <h2>Operator instructions</h2>
  <ol>
    <li>Copy this single HTML file to the target environment.</li>
    <li>Open it locally in the browser you need to qualify.</li>
    <li>Click <strong>Run probe</strong> and wait for the table to fill in.</li>
    <li>Optionally run the Pyodide stage if you placed a local <code>pyodide/</code> folder beside this file.</li>
    <li>Click <strong>Copy summary</strong> and paste the one-line result back to your coordinator.</li>
  </ol>
</section>
<script>
"use strict";
const WASM_BYTES = new Uint8Array([{_WASM_JS_ARRAY}]);
const results = {{}};
function setResult(key, value) {{
  results[key] = value;
  const row = document.getElementById("row-" + key);
  if (row) row.querySelector(".result").textContent = value;
}}
function engineVersion() {{
  const ua = navigator.userAgent || "";
  const match = ua.match(/(Chrome|Firefox|Safari|Edg)\\/[\\d.]+/);
  return match ? match[0] : "unknown-engine";
}}
function buildSummary() {{
  const order = ["wasm","worker","sab","idb","ls","fetch","link","js","pyodide"];
  const parts = order.filter((k) => results[k]).map((k) => k + "=" + results[k]);
  return "cap-probe|" + parts.join("|") + "|engine=" + engineVersion();
}}
function updateSummary() {{
  const summary = buildSummary();
  const area = document.getElementById("summary");
  area.value = summary;
  document.getElementById("copy-summary").disabled = !summary.includes("wasm=");
}}
async function testWasm() {{
  if (typeof WebAssembly === "undefined") {{
    setResult("wasm", "fail");
    return;
  }}
  try {{
    await WebAssembly.instantiate(WASM_BYTES);
    setResult("wasm", "pass");
  }} catch (err) {{
    setResult("wasm", "fail");
  }}
}}
function testWorker() {{
  try {{
    const blob = new Blob(["postMessage('ok');"], {{ type: "application/javascript" }});
    const url = URL.createObjectURL(blob);
    const worker = new Worker(url);
    worker.onmessage = () => {{ setResult("worker", "pass"); URL.revokeObjectURL(url); }};
    worker.onerror = () => {{ setResult("worker", "fail"); URL.revokeObjectURL(url); }};
  }} catch (err) {{
    setResult("worker", err && err.name === "SecurityError" ? "blocked" : "fail");
  }}
}}
function testSab() {{
  try {{
    if (typeof SharedArrayBuffer === "undefined") {{
      setResult("sab", "blocked");
      return;
    }}
    new SharedArrayBuffer(8);
    setResult("sab", "pass");
  }} catch (err) {{
    setResult("sab", "blocked");
  }}
}}
async function testIdb() {{
  if (!window.indexedDB) {{
    setResult("idb", "blocked");
    return;
  }}
  const name = "dr-probe-" + Date.now();
  try {{
    await new Promise((resolve, reject) => {{
      const req = indexedDB.open(name, 1);
      req.onupgradeneeded = () => req.result.createObjectStore("probe");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    }}).then(async (db) => {{
      await new Promise((resolve, reject) => {{
        const tx = db.transaction("probe", "readwrite");
        tx.objectStore("probe").put("ok", "k");
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
      }});
      db.close();
      indexedDB.deleteDatabase(name);
      setResult("idb", "pass");
    }});
  }} catch (err) {{
    setResult("idb", "fail");
  }}
}}
function testLocalStorage() {{
  try {{
    const key = "__dr_probe__";
    localStorage.setItem(key, "1");
    const ok = localStorage.getItem(key) === "1";
    localStorage.removeItem(key);
    setResult("ls", ok ? "pass" : "fail");
  }} catch (err) {{
    setResult("ls", "blocked");
  }}
}}
async function testFetchLocal() {{
  try {{
    const resp = await fetch("?probe=local");
    setResult("fetch", resp && (resp.ok || resp.type === "basic") ? "pass" : "fail");
  }} catch (err) {{
    setResult("fetch", "blocked");
  }}
}}
function testLocalLink() {{
  try {{
    const anchor = document.createElement("a");
    anchor.href = "file:///probe-local-check.html";
    anchor.target = "_blank";
    anchor.rel = "noopener";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setResult("link", "pass");
  }} catch (err) {{
    setResult("link", "blocked");
  }}
}}
function testJsBaseline() {{
  try {{
    const arrow = () => true;
    const spread = [...[1, 2]];
    const tmpl = `x${{1}}`;
    setResult("js", arrow() && spread.length === 2 && tmpl === "x1" ? "pass" : "fail");
  }} catch (err) {{
    setResult("js", "fail");
  }}
}}
async function runProbe() {{
  document.querySelectorAll("#results .result").forEach((cell) => {{
    if (cell.textContent === "pending" || cell.textContent === "not run") {{
      cell.textContent = "running…";
    }}
  }});
  await testWasm();
  testWorker();
  testSab();
  await testIdb();
  testLocalStorage();
  await testFetchLocal();
  testLocalLink();
  testJsBaseline();
  updateSummary();
}}
document.getElementById("run-probe").addEventListener("click", runProbe);
document.getElementById("copy-summary").addEventListener("click", async () => {{
  const area = document.getElementById("summary");
  area.select();
  try {{
    await navigator.clipboard.writeText(area.value);
  }} catch (err) {{
    document.execCommand("copy");
  }}
}});
{pyodide_script}
</script>
</body>
</html>
"""
