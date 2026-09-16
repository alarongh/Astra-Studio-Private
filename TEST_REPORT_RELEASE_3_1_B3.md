# TEST REPORT — Astra Studio Release 3.1 B3

Дата: 2026-08-23

## Scope

B3 closes the interactive-editor scope of Release 3.1:

- LSP availability/status page;
- explicit safe install/update entry points for supported language servers;
- completion;
- hover;
- signature help;
- Go to Definition;
- Find References;
- Rename Symbol;
- Document Outline/Symbols;
- stale-response protection for interactive requests;
- guarded WorkspaceEdit application.

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
Tests collected: 72
Passed: 67
Failed: 0
Skipped: 5
Languages/formats: 20
Python registry entries: 41
Bundled assets checked: 11
Installer scripts checked: 13
LSP language configs: 20
```

## B3 tests that run in the sandbox

PASS coverage includes:

- CompletionList/list normalization and deterministic sorting;
- standard completion TextEdit preservation;
- hover MarkupContent/plain-text normalization;
- signature help active-signature/active-parameter normalization;
- Location and LocationLink normalization;
- hierarchical DocumentSymbol normalization;
- WorkspaceEdit `changes` and `documentChanges` normalization;
- Create/Rename/Delete resource-operation detection;
- UTF-16 LSP character offsets for non-BMP characters;
- rejection of overlapping text edits;
- CRLF preservation when the source text retains CRLF;
- safe-install catalog presence for primary StaffedUp language servers;
- explicit external/non-auto-install behavior for GDScript;
- B3 shortcuts/UI hooks;
- interactive request routing with request tokens;
- client capability advertisement with snippet completion deliberately disabled;
- every previous Release 3.0 / B1 / B2 regression test.

## Runtime integration tests collected but deferred

The current Linux sandbox does not have PySide6 installed. These five tests are implemented and collected, but intentionally skipped here:

1. `test_lsp_b1.py::LspProcessLifecycleTests.test_initialize_server_request_and_graceful_shutdown`
2. `test_lsp_b1.py::LspProcessLifecycleTests.test_unexpected_exit_restarts_with_backoff`
3. `test_lsp_b2.py::LspDocumentIntegrationTests.test_manager_syncs_documents_and_collects_diagnostics`
4. `test_lsp_b2.py::LspTcpTransportTests.test_external_tcp_initialize_and_shutdown`
5. `test_lsp_b3.py::LspInteractiveRuntimeTests.test_manager_routes_completion_hover_signature_navigation_rename_and_symbols`

They remain mandatory for the final Windows/PySide6 integration gate after Release 3.3 and are registered in `TEST_REGISTRY_3_X.md`.

## LSP status / install review

The B3 page distinguishes:

- ready language server;
- starting/initializing/restarting/shutting down;
- installed/available local stdio server;
- missing server;
- disabled/no-default configuration;
- external TCP server waiting for its owner application (Godot/GDScript).

Safe install/update plans are intentionally curated instead of accepting arbitrary commands from project content. Current automatic paths cover:

- BasedPyright in the project Python environment;
- TypeScript Language Server + TypeScript through npm, with a current Node.js >=22.22.2 preflight;
- VS Code HTML/CSS/JSON servers through npm;
- YAML Language Server through npm;
- Bash Language Server through npm;
- Intelephense through npm;
- clangd through LLVM/WinGet;
- csharp-ls through `dotnet tool` when a suitable SDK is available.

GDScript is explicitly external because Godot owns that language server. Other ambiguous/no-default server installations remain manual/configurable instead of being guessed by Astra.

The current csharp-ls project requires .NET 10 SDK or later, so B3 performs an explicit active-SDK preflight and refuses automatic csharp-ls installation on an older detected SDK with a clear message.

## Interactive request safety review

- Interactive requests are routed separately from build/install TaskManager jobs.
- Each request is tagged with document path/version state.
- Completion, hover, signature help, definition, references, rename and outline reject stale results where applying/showing them would target an outdated current document.
- Project switches clear queued pre-initialization feature requests.
- An owned language server is stopped before safe install/update starts, avoiding Windows file-lock conflicts during package/tool replacement.
- Server stop/failure/restart drops pending interactive requests rather than applying a response after lifecycle reset.
- Snippet completion support is not advertised in B3; insertion is plain text/TextEdit only.

## Rename safety review

Rename has stronger restrictions than ordinary navigation:

- every edited URI must belong to the active project/attached roots;
- WorkspaceEdit resource operations (Create/Rename/DeleteFile) reject the whole rename;
- overlapping text edits reject the whole file operation;
- closed-file ranges use LSP UTF-16 column semantics;
- CP1251 closed files preserve their encoding;
- closed-file text is decoded directly from bytes so existing CRLF remains CRLF;
- temporary files are unique and staged in the target directory for same-filesystem `os.replace`;
- if replacement of one closed file fails, already replaced closed files are restored from byte backups;
- open files stay modified/unsaved so normal editor Undo remains available.

## Final B3 audit fixes

The final pass after the first B3 implementation also fixed:

- GDScript status no longer falsely says a TCP endpoint is locally "installed" before Godot connects;
- LLVM's standard Windows install directory is added to runtime tool discovery;
- csharp-ls auto-install now warns when detected .NET SDK is below version 10;
- TypeScript Language Server auto-install now warns when detected Node.js is below 22.22.2, matching the current 5.3.0 engine requirement;
- queued interactive requests are cleared on project/workspace switch;
- definition/reference results now use the same stale-document protection as completion/hover;
- closed-file rename no longer normalizes CRLF through universal-newline text I/O;
- rename staging uses unique temporary files instead of a predictable `.astra-rename.tmp` name;
- stale B1/B2 implementation comments/messages were updated to reflect completed Release 3.1 behavior.

## Manual test status

Owner manual Windows testing is intentionally **not performed yet**. Per project policy, the full manual regression run happens only after Release 3.3 and the complete 3.x integration gate.

All required manual test IDs, including expanded B3 edge cases, are maintained in:

`TEST_REGISTRY_3_X.md`

## B3 result

**PASS — B3 implementation gate completed.**

Release 3.1 is now feature-complete and internally gated. It is ready to freeze as the base for Release 3.2, but it is not yet the owner-accepted Windows release.
