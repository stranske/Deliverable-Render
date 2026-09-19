"""Build a self-contained HTML capability probe for offline environments."""

from __future__ import annotations

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
            '<td class="result">not run</td></tr>'
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
function runPyodideStage() {
  var status = document.getElementById("pyodide-status");
  var cell = document.querySelector("#row-pyodide .result");
  status.textContent = "Loading local Pyodide runtime…";
  cell.textContent = "running…";
  var script = document.createElement("script");
  script.src = "pyodide/pyodide.js";
  script.onerror = function() { throw new Error("local pyodide.js missing"); };
  new Promise(function(resolve, reject) {
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  }).then(function() {
    if (!globalThis.loadPyodide) {
      throw new Error("loadPyodide unavailable after script load");
    }
    return globalThis.loadPyodide({ indexURL: "pyodide/" });
  }).then(function() {
    setResult("pyodide", "pass");
    status.textContent = "Pyodide initialized successfully from local files.";
    updateSummary();
  }).catch(function(err) {
    setResult("pyodide", "fail");
    status.textContent = "Pyodide stage failed: " + String(err && err.message || err);
    updateSummary();
  });
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
var WASM_BYTES = new Uint8Array([{_WASM_JS_ARRAY}]);
var results = {{}};
function setResult(key, value) {{
  results[key] = value;
  var row = document.getElementById("row-" + key);
  if (row) row.querySelector(".result").textContent = value;
}}
function engineVersion() {{
  var ua = navigator.userAgent || "";
  var match = ua.match(/(Chrome|Firefox|Safari|Edg)\\/[\\d.]+/);
  return match ? match[0] : "unknown-engine";
}}
function buildSummary() {{
  var order = ["wasm","worker","sab","idb","ls","fetch","link","js","pyodide"];
  var parts = [];
  for (var i = 0; i < order.length; i++) {{
    var key = order[i];
    if (results[key]) parts.push(key + "=" + results[key]);
  }}
  return "cap-probe|" + parts.join("|") + "|engine=" + engineVersion();
}}
function updateSummary() {{
  var summary = buildSummary();
  var area = document.getElementById("summary");
  area.value = summary;
  document.getElementById("copy-summary").disabled = summary.indexOf("wasm=") === -1;
}}
function testWasm() {{
  if (typeof WebAssembly === "undefined") {{
    setResult("wasm", "fail");
    return Promise.resolve();
  }}
  return WebAssembly.instantiate(WASM_BYTES).then(function() {{
    setResult("wasm", "pass");
  }}, function() {{
    setResult("wasm", "fail");
  }});
}}
function testWorker() {{
  return new Promise(function(resolve) {{
    try {{
      var blob = new Blob(["postMessage('ok');"], {{ type: "application/javascript" }});
      var url = URL.createObjectURL(blob);
      var worker = new Worker(url);
      worker.onmessage = function() {{
        setResult("worker", "pass");
        URL.revokeObjectURL(url);
        resolve();
      }};
      worker.onerror = function() {{
        setResult("worker", "fail");
        URL.revokeObjectURL(url);
        resolve();
      }};
    }} catch (err) {{
      setResult("worker", err && err.name === "SecurityError" ? "blocked" : "fail");
      resolve();
    }}
  }});
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
function testIdb() {{
  if (!window.indexedDB) {{
    setResult("idb", "blocked");
    return Promise.resolve();
  }}
  var name = "dr-probe-" + Date.now();
  return new Promise(function(resolve, reject) {{
    var req = indexedDB.open(name, 1);
    req.onupgradeneeded = function() {{ req.result.createObjectStore("probe"); }};
    req.onsuccess = function() {{ resolve(req.result); }};
    req.onerror = function() {{ reject(req.error); }};
  }}).then(function(db) {{
    return new Promise(function(resolve, reject) {{
      var tx = db.transaction("probe", "readwrite");
      tx.objectStore("probe").put("ok", "k");
      tx.oncomplete = resolve;
      tx.onerror = function() {{ reject(tx.error); }};
    }}).then(function() {{
      return new Promise(function(resolve, reject) {{
        var tx = db.transaction("probe", "readonly");
        var req = tx.objectStore("probe").get("k");
        req.onsuccess = function() {{ resolve(req.result); }};
        req.onerror = function() {{ reject(req.error); }};
      }});
    }}).then(function(value) {{
      if (value !== "ok") throw new Error("IndexedDB read verification failed");
      db.close();
      indexedDB.deleteDatabase(name);
      setResult("idb", "pass");
    }});
  }}).catch(function() {{
    setResult("idb", "fail");
  }});
}}
function testLocalStorage() {{
  try {{
    var key = "__dr_probe__";
    localStorage.setItem(key, "1");
    var ok = localStorage.getItem(key) === "1";
    localStorage.removeItem(key);
    setResult("ls", ok ? "pass" : "fail");
  }} catch (err) {{
    setResult("ls", "blocked");
  }}
}}
function testFetchLocal() {{
  return fetch("?probe=local").then(function(resp) {{
    setResult("fetch", resp && (resp.ok || resp.type === "basic") ? "pass" : "fail");
  }}, function() {{
    setResult("fetch", "blocked");
  }});
}}
function testLocalLink() {{
  try {{
    var opened = window.open("file:///probe-local-check.html", "_blank", "noopener");
    if (!opened) {{
      setResult("link", "blocked");
      return;
    }}
    try {{ opened.close(); }} catch (ignore) {{}}
    setResult("link", "pass");
  }} catch (err) {{
    setResult("link", "blocked");
  }}
}}
function testJsBaseline() {{
  try {{
    var ok = new Function("var arrow = () => true; var spread = [...[1,2]]; var tmpl = `x${{1}}`; return arrow() && spread.length === 2 && tmpl === 'x1';")();
    setResult("js", ok ? "pass" : "fail");
  }} catch (err) {{
    setResult("js", "fail");
  }}
}}
function runProbe() {{
  var cells = document.querySelectorAll("#results .result");
  for (var i = 0; i < cells.length; i++) {{
    if (cells[i].textContent === "pending") {{
      cells[i].textContent = "running…";
    }}
  }}
  return testWasm().then(function() {{
    return testWorker();
  }}).then(function() {{
    testSab();
    return testIdb();
  }}).then(function() {{
    testLocalStorage();
    return testFetchLocal();
  }}).then(function() {{
    testLocalLink();
    testJsBaseline();
    updateSummary();
  }});
}}
document.getElementById("run-probe").addEventListener("click", function() {{
  runProbe();
}});
document.getElementById("copy-summary").addEventListener("click", function() {{
  var area = document.getElementById("summary");
  area.select();
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(area.value).catch(function() {{
      document.execCommand("copy");
    }});
  }} else {{
    document.execCommand("copy");
  }}
}});
{pyodide_script}
</script>
</body>
</html>
"""
