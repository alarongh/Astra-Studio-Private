# TEST REPORT — Astra Studio Release 3.1 / B1 LSP Transport

Дата: 2026-08-23

## Scope

Проверяется только B1:

- JSON-RPC/LSP framing;
- initialize/shutdown lifecycle implementation;
- per-language server registry/configuration;
- crash/restart handling;
- main application lifecycle integration;
- regressions Release 3.0.

B2/B3 не считаются реализованными и не проверяются как готовые функции.

## Automated results

- Static smoke suite: **PASS**.
- Current unit/static suite: **44 tests collected**.
- Passed: **42**.
- Skipped: **2**.
- Failed: **0**.

Два skipped-теста — реальные QProcess lifecycle checks против `tests/fake_lsp_server.py`:

1. initialize → server request → graceful shutdown;
2. unexpected exit → bounded restart → successful initialize.

Они пропущены только потому, что sandbox не содержит PySide6. Сам production transport остаётся PySide6/QProcess-кодом, как и Astra Studio. Тесты не удалены и будут выполнены в Windows/PySide6-capable gate перед ручным тестом владельца.

## Verified automatically

- fragmented JSON-RPC messages parse correctly;
- multiple back-to-back messages parse correctly;
- UTF-8 payload byte length is correct;
- invalid Content-Length rejected;
- oversized payload rejected before buffering its body;
- all 20 Astra languages have explicit LSP config records;
- Python, TypeScript, C++, Luau and Godot mappings match intended transports;
- project-local `node_modules/.bin` server discovery precedes PATH;
- malformed user config cannot replace integer/bool runtime fields with unsafe string values;
- `main.py` owns `LspManager`, updates project root and performs blocking LSP shutdown on application close;
- transport contains initialize/initialized/shutdown/exit sequence;
- transport uses separate QProcess channels and bounded restart config;
- Release 3.0 project/environment/installer regression tests still pass.

## Known B1 limitations by design

- no `didOpen/didChange/didSave/didClose` yet;
- no Problems panel or diagnostics routing yet;
- no completion/hover/navigation yet;
- no automatic language-server installation yet;
- GDScript uses Godot's external TCP LSP and therefore needs a TCP adapter beyond B1's process/stdin transport;
- PowerShell Editor Services bootstrap and XML default server are deliberately not guessed.

## Gate result

**B1 IMPLEMENTATION GATE: PASS WITH 2 ENVIRONMENT-SKIPPED QPROCESS TESTS.**

This is sufficient to continue to B2 under the project's rule that full manual Windows testing is deferred until after Release 3.3. The two skipped tests remain mandatory in the final integration gate.
