# CHANGELOG — Astra Studio Release 3.1

## B1 — LSP Transport

Дата блока: 2026-08-23

Release 3.1 начинается с отдельного транспортного слоя Language Server Protocol. B1 сознательно не включает document synchronization, Problems UI, completion, hover или navigation — они остаются B2/B3.

### Добавлено

- `core/lsp_protocol.py`:
  - JSON-RPC/LSP `Content-Length` framing;
  - incremental parsing фрагментированного stdout;
  - корректный UTF-8 byte length;
  - safety limits для header/payload;
  - URI conversion для workspace path.
- `core/lsp_servers.py`:
  - типизированный каталог server configs;
  - явная конфигурация для всех 20 языков/форматов Astra;
  - project-local executable discovery через `node_modules/.bin` и `.venv`/`venv`;
  - PATH fallback;
  - `%LOCALAPPDATA%\AstralStudio\lsp_servers.json` user overrides;
  - строгая валидация override типов.
- `core/lsp_transport.py`:
  - отдельный persistent `QProcess` на language server;
  - `initialize` / `initialized` lifecycle;
  - graceful `shutdown` / `exit`;
  - stderr logging отдельно от JSON-RPC stdout;
  - request/response/notification routing;
  - безопасные ответы на базовые server→client requests;
  - bounded auto-restart с exponential backoff;
  - restart budget и explicit manual restart;
  - manager для нескольких независимых language servers.

### Интеграция с Astra

- `AstraStudio` создаёт отдельный `LspManager`.
- LSP не использует `TaskManager`: build/install tasks и постоянные language servers больше не конкурируют за один process slot.
- При смене проекта LSP manager получает новый project root и завершает старые connections.
- При закрытии Astra все LSP children закрываются до terminal/installer shutdown.
- `APP_VERSION` обновлён до `Release 3.1`.

### Базовые server mappings

- Python → `basedpyright-langserver --stdio` / `pyright-langserver --stdio`.
- C++ → `clangd`.
- JavaScript / TypeScript → `typescript-language-server --stdio`.
- Luau → `luau-lsp lsp`.
- HTML/CSS/JSON → VS Code language server binaries over stdio.
- YAML → `yaml-language-server --stdio`.
- PHP → `intelephense --stdio`.
- C# → `csharp-ls`.
- Java → `jdtls` wrapper when installed.
- SQL → `sqls`.
- TOML → `taplo lsp stdio`.
- Dockerfile → official `docker-language-server start --stdio` with legacy fallback.
- GDScript → external Godot TCP LSP config on port `6005`; stdio process transport intentionally not fabricated.
- PowerShell/XML → explicit no-default/disabled configuration until a reliable bootstrap is implemented.

### Crash / restart rules

- unexpected normal exit and crash exit are both treated as server failure;
- restart is bounded by `max_restarts` (default 3);
- delay grows exponentially from `restart_base_delay_ms`;
- user/project shutdown cancels pending restart timers;
- failed initialization does not enter an infinite restart loop;
- project switch retires old connections instead of orphaning child processes.

### Tests

- Release 3.0 regression suite carried forward and updated to 3.1.
- Added LSP framing tests.
- Added registry/override tests.
- Added explicit 20-language catalog coverage.
- Added static lifecycle/integration tests for main ↔ LspManager.
- Added fake LSP server and two QProcess lifecycle tests.

Current sandbox does not have PySide6 installed, so the two executable QProcess lifecycle tests are collected but skipped here. They are retained for a Windows/PySide6-capable environment and the final 3.x integration test.

## B2 — Documents + Diagnostics

Дата блока: 2026-08-23

B2 подключает редактор к уже готовому LSP transport из B1. После этого Astra умеет синхронизировать открытые файлы с language server, принимать diagnostics и показывать их в интерфейсе.

### Добавлено

- `core/lsp_documents.py`:
  - состояние открытых LSP-документов;
  - версия документа с увеличением на каждое изменение;
  - нормализация `textDocument/publishDiagnostics`;
  - store diagnostics по URI;
  - защита от отката на устаревшие versioned diagnostics.
- `core/lsp_tcp_transport.py`:
  - внешний TCP transport для language servers, которыми Astra не владеет как процессом;
  - Godot/GDScript подключение через `127.0.0.1:6005` по умолчанию;
  - `initialize` / `initialized` / `shutdown` / `exit` поверх TCP;
  - безопасная обработка socket error/disconnect;
  - совместимый с stdio transport набор сигналов для `LspManager`.
- `core/lsp_protocol.py`:
  - обратное преобразование `file:// URI -> Path` для навигации из diagnostics.

### Document synchronization

- `didOpen` при открытии сохранённого файла проекта;
- debounced `didChange` после редактирования;
- full-document change payload с монотонно растущей `version`;
- `didSave` после успешной записи файла;
- `didClose` при закрытии вкладки;
- Save As закрывает старый URI и синхронизирует новый путь;
- после перезапуска language server актуальные открытые документы отправляются заново;
- при смене проекта старое LSP document/diagnostic state очищается;
- открытые вкладки вне нового active project не синхронизируются в новый workspace;
- недоступный server получает retry cooldown, поэтому Astra не пытается переподключаться на каждое нажатие клавиши.

### Diagnostics / Problems

В нижнюю панель добавлена вкладка **Проблемы**:

- группировка diagnostics по файлам;
- Error / Warning / Information / Hint;
- фильтр ошибок;
- фильтр предупреждений;
- фильтр info/hint;
- режим «только текущий файл»;
- отображение строки/колонки/source/code;
- клик по diagnostic открывает нужный файл и переводит курсор на строку/колонку;
- пустая `publishDiagnostics` очищает исправленную проблему;
- закрытие документа удаляет его diagnostics из Problems.

### Godot / GDScript

- `LspServerRegistry.resolve()` теперь умеет разрешать `external_tcp` configs;
- GDScript больше не является только декларацией в каталоге B1 — Astra может реально подключаться к встроенному LSP Godot;
- если Godot не запущен, отказ соединения обрабатывается как контролируемая LSP failure, без блокировки GUI;
- повторные попытки ограничены cooldown на уровне manager.

### Tests

- добавлен `tests/test_lsp_b2.py`;
- добавлены pure tests document versioning, diagnostics normalization/stale protection и URI roundtrip;
- добавлен test GDScript external TCP resolution;
- добавлены static integration checks main ↔ Problems ↔ LSP manager;
- добавлен runtime stdio document-sync/diagnostics test с fake LSP server;
- добавлен runtime TCP initialize/shutdown test с локальным socket LSP server;
- fake LSP server расширен поддержкой `didOpen/didChange/didSave/didClose` и test diagnostics;
- создан единый `TEST_REGISTRY_3_X.md` со всеми автоматическими и будущими ручными тестами.

### B2 gate

- `compileall`: PASS;
- static smoke: PASS;
- unittest suite: **55 collected / 51 PASS / 4 SKIPPED / 0 FAILED**;
- четыре skipped test — Qt runtime integration tests, которые требуют PySide6-capable environment и остаются обязательными для финального Windows test после 3.3.

## B3 — Interactive Editor Features

Дата блока: 2026-08-23

B3 завершает функциональный scope Release 3.1: поверх transport и document/diagnostic слоя добавлены интерактивные IDE-возможности LSP и управляемое состояние language servers.

### LSP status / install UI

Добавлена отдельная страница **LSP / Outline**:

- таблица статуса для всех 20 языков/форматов Astra;
- состояния `ready`, запуск/инициализация, отсутствующий server, отключённая конфигурация и внешний server;
- GDScript до успешного TCP-соединения явно показывается как ожидающий внешний Godot server, а не как локально установленный LSP;
- явные кнопки start/stop и safe install/update;
- project-local server discovery по-прежнему имеет приоритет над глобальным PATH;
- перед update/install уже запущенный owned language server корректно останавливается, чтобы Windows не держала заменяемые tool files открытыми.

Curated safe-install планы добавлены только там, где есть понятный пакетный путь:

- Python → BasedPyright в Python-окружение проекта;
- JavaScript/TypeScript → TypeScript Language Server + TypeScript через npm;
- HTML/CSS/JSON → `vscode-langservers-extracted`;
- YAML → `yaml-language-server`;
- Shell → `bash-language-server`;
- PHP → `intelephense`;
- C++ → clangd через WinGet package `LLVM.LLVM`;
- C# → `csharp-ls` как global dotnet tool;
- TypeScript Language Server install preflight blocks an active Node.js older than 22.22.2, matching the current server engine requirement;
- GDScript → внешний built-in LSP Godot, отдельная установка language server не выполняется.

Astra не придумывает автоматическую установку для неоднозначных серверов: если безопасного плана нет, остаётся ручной `lsp_servers.json`/будущий StaffedUp workflow. Для `csharp-ls` добавлена проверка активного SDK и понятное предупреждение при .NET ниже 10. После установки LLVM текущий процесс Astra дополнительно знает стандартный путь `C:\Program Files\LLVM\bin`.

### Interactive LSP requests

Добавлен `core/lsp_features.py` и routing интерактивных JSON-RPC requests через `LspManager`:

- completion (`Ctrl+Space`);
- hover (`Ctrl+Shift+H`);
- signature help (`Ctrl+Shift+Space`);
- Go to Definition (`F12`);
- Find References (`Shift+F12`);
- Rename Symbol (`F2`);
- Document Symbols / Outline (`Ctrl+Shift+O`).

Client capabilities объявляют эти функции обоим transport: stdio и external TCP. Snippet completion пока намеренно не рекламируется (`snippetSupport=false`), чтобы server не передавал snippet placeholders в обычную текстовую вставку B3.

### Completion / hover / navigation

- Completion normalizes `CompletionList` и обычный список completion items;
- поддерживается стандартный `TextEdit` range;
- hover/markup преобразуется в безопасный tooltip;
- signature help показывает активную сигнатуру и активный параметр;
- Location и LocationLink нормализуются для definition/references;
- одиночное definition открывается сразу, несколько locations показываются в диалоге;
- устаревшие completion/hover/signature/definition/reference responses игнорируются, если файл/версия уже изменились.

### Rename safety

Rename реализован как ограниченная и проверяемая WorkspaceEdit-транзакция:

- edits вне активного проекта полностью отклоняются;
- Create/Rename/Delete resource operations не применяются автоматически;
- пересекающиеся text edits отклоняются;
- позиции закрытых файлов переводятся по UTF-16 semantics LSP;
- CP1251 closed files сохраняют исходную кодировку;
- CRLF closed files не нормализуются в LF только из-за rename;
- временные файлы имеют уникальные имена в том же каталоге;
- при ошибке atomic replace уже заменённые closed files откатываются;
- открытые файлы остаются modified/unsaved, чтобы пользователь мог использовать обычный Undo.

### Document Outline

- иерархические `DocumentSymbol` отображаются отдельным Outline tree;
- SymbolInformation также нормализуется;
- double-click открывает соответствующую строку/колонку;
- stale symbols response после редактирования/смены вкладки не заменяет актуальный outline.

### Project/lifecycle safety

- интерактивные requests имеют token с document path/version;
- pending interactive requests сбрасываются при stop/failure/restart;
- очередь запроса, ожидающего initialization, очищается при смене project root;
- language-server restart не может применить устаревший B3 response к новому документу.

### B3 tests / gate

- добавлен `tests/test_lsp_b3.py`;
- fake LSP server отвечает на completion, hover, signatureHelp, definition, references, rename и documentSymbol;
- pure tests покрывают normalization, UTF-16 positions, CRLF preservation, resource-operation guards и overlap rejection;
- static tests проверяют B3 UI/actions/capabilities/install safety hooks;
- Qt runtime integration test для полного interactive request path добавлен и сохранён для финального Windows gate.

Итог B3 gate:

- `compileall`: PASS;
- static smoke: PASS;
- unittest suite: **72 collected / 67 PASS / 5 SKIPPED / 0 FAILED**;
- все 5 skipped — уже написанные Qt/PySide6 runtime integration tests, которые остаются обязательными после Release 3.3.

**Release 3.1 implementation scope завершён и внутренне заморожен.** Ручной Windows acceptance test владельца по прежнему выполняется только после полного 3.x integration gate.
