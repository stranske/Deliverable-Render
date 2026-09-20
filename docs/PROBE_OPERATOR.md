# Capability probe operator instructions

Use the probe when you need to learn what a locked-down browser actually supports
before committing to WebAssembly or Pyodide delivery.

## Steps

1. Obtain the single HTML file built by `build_probe.py` (or from the release artifact).
2. Copy only that file to the target machine. Do not rename paths inside the summary.
3. Open the file locally in the browser under test (double-click or **File → Open**).
4. Click **Run probe** and wait for the table to populate.
5. Optionally place a local `pyodide/` directory beside the HTML file and click
   **Run Pyodide stage** if your coordinator asked for runtime initialization proof.
6. Click **Copy summary** and paste the one-line result into your reply.

## Privacy

The summary contains capability pass/fail/blocked markers and the browser-reported
engine version only. It does not include machine names, user names, file paths, or
automatic network calls. Nothing leaves the machine unless you paste the summary.
