# Template slide guard proof

The manifest is the sole authority for output slides. Populated templates are rejected before store queries or slide assembly, and the final count is checked before serialization. The public CLI already maps DeckBuildError (ValueError) to exit 2 before calling publish, so no CLI implementation change is needed.

Original production source with the new tests: 9 assertion failures, including bytes/path templates with one/two stale slides, injected extra slides, and all combinations of existing/new CLI output and force/no-force. The subsequent early-query regression explicitly proves rejection happens before store queries.

Corrected full repository gate: 230 passed, zero skipped, 90.67% coverage (80% required). The focused suite has 81 cases after the early-query regression was added. Reopened successful PPTX files match active manifest titles in order and reported slide counts, including dropped/allow-empty/empty cases. Existing output and input-template bytes are preserved on failure.

## Replay

From this checkout with development dependencies installed:

- `PYTHONPATH=src python -m pytest -o addopts= tests/test_deck_completeness_gate.py tests/store/test_communication_render_profile.py -q`
- `PYTHONPATH=src python -m pytest`

For independent mutation proof, save the exact manifest.py bytes and temporarily replace only `if len(presentation.slides) > 0:` with `if False:`. Run the focused command above with `-k populated_template`: it must fail, including the early-query assertion. Restore the saved bytes, verify their SHA256 and rerun: 9 passed. Separately replace only `if len(presentation.slides) != slides_built:` with `if False:` and run with `-k unmanifested_slide`: it must fail because the unauthorized slide is accepted. Restore bytes and rerun: 1 passed. Never commit either mutation.

Sanitized logs and JUnit preserve the original failure, both independent mutations, restored runs, focused success and full coverage gate. `mutations.json` records original/mutated/restored SHA256 values; `SHA256SUMS` binds the published evidence. Private hostnames and local user/worktree/temp paths are replaced with stable placeholders; test outcomes, assertions, timestamps, and source restoration hashes are preserved. Unredacted originals remain local. The build uses real python-pptx serialization/reopening. Native Office visual rendering and hosted CI/provider acceptance are outside this local proof.
