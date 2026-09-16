# TEST REPORT — Astra Studio Release 3.1 B2

Дата: 2026-08-23

## Scope

B2 covers:

- Godot/GDScript external TCP LSP adapter;
- `didOpen` / `didChange` / `didSave` / `didClose`;
- LSP document version tracking;
- diagnostics collection and stale-version protection;
- Problems panel and filters;
- diagnostic navigation to file/line/column;
- document re-sync after language-server restart;
- retry cooldown for unavailable servers.

## Automated gate

Executed in the current sandbox:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m unittest discover -s tests -v
```

Result:

```text
Static smoke: PASS
Tests collected: 55
Passed: 51
Failed: 0
Skipped: 4
Languages/formats: 20
Python registry entries: 41
Bundled assets checked: 11
Installer scripts checked: 13
LSP language configs: 20
```

## B2 tests that run in the sandbox

PASS:

- document version increases on change;
- close removes document state;
- `publishDiagnostics` normalization;
- stale versioned diagnostics are ignored;
- file URI roundtrip including Unicode/spaces;
- non-file URI rejection;
- GDScript resolves to `external_tcp` on `127.0.0.1:6005`;
- main contains Problems/document-sync integration hooks;
- transport contains `didOpen`, `didChange`, `didSave`, `didClose` and `publishDiagnostics` routing;
- all previous Release 3.0 / B1 regression tests continue to pass.

## Runtime integration tests collected but deferred

The current Linux sandbox does not have PySide6 installed. These tests are implemented and collected, but intentionally skipped here:

1. `test_lsp_b1.py::LspProcessLifecycleTests.test_initialize_server_request_and_graceful_shutdown`
2. `test_lsp_b1.py::LspProcessLifecycleTests.test_unexpected_exit_restarts_with_backoff`
3. `test_lsp_b2.py::LspDocumentIntegrationTests.test_manager_syncs_documents_and_collects_diagnostics`
4. `test_lsp_b2.py::LspTcpTransportTests.test_external_tcp_initialize_and_shutdown`

They remain mandatory for the final Windows/PySide6 integration gate after Release 3.3 and are also listed in `TEST_REGISTRY_3_X.md`.

## Important implementation checks

- `main.py` has no duplicate `AstraStudio` method definitions after B2 integration.
- document changes are debounced before `didChange`;
- a pending text change is flushed into LSP state before `didSave`;
- Save As closes the old document URI after the new file is successfully saved;
- project switch clears LSP document/diagnostic state;
- only files inside the active project/attached roots are automatically synced;
- server restart resets opened-URI state so current documents get a fresh `didOpen`;
- missing/failed server attempts use a 5-second retry cooldown to avoid per-keystroke reconnect storms;
- diagnostics are replaced per URI and versioned stale notifications cannot roll back newer state;
- Problems navigation uses `file://` URI conversion and existing `open_file_at_line` logic.

## Manual test status

Owner manual Windows testing is intentionally **not performed yet**. Per project policy, the full manual regression run happens only after Release 3.3 and the final 3.x integration gate.

All required manual test names/IDs are maintained in:

`TEST_REGISTRY_3_X.md`

## B2 result

**PASS — B2 implementation gate completed.**

B2 is ready to freeze as the base for Release 3.1 B3. This is not yet the final user-tested Release 3.1 build.
