# TEST REPORT — Astra Studio Release 3.2 C2

Дата: 2026-08-23

## Scope

C2 добавляет Test Explorer поверх замороженных Release 3.0, Release 3.1 и C1:

- generic test adapter model в `core/test_explorer.py`;
- detection/discovery pytest и unittest;
- npm project test script с распознаванием Vitest/Jest;
- `dotnet test`;
- Test Explorer UI;
- Run All / safe Run Selected / Rerun Last;
- pass/fail/skip/error tree;
- source navigation;
- сохранение последнего результата в `astral.project.json`;
- защита от запуска внешних тестов по устаревшей версии файлов на диске.

C3 Git в этот gate намеренно не входит.

## Automated gate

В sandbox выполнены:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m pytest -q
```

Результат последнего полного прогона:

```text
Static smoke: PASS
Tests collected: 109
Passed: 103
Failed: 0
Skipped: 6
Subtests passed: 88
Languages/formats: 20
Python registry entries: 41
Bundled assets checked: 11
Installer scripts checked: 13
LSP language configs: 20
```

## C2 automated coverage

Новый `tests/test_test_explorer_c2.py` проверяет:

- detection pytest по конфигурации/dependencies;
- detection unittest без ложного принудительного выбора pytest;
- detection npm/Vitest/Jest по `package.json`;
- detection dotnet-проектов;
- Python static discovery функций/классов и корректных строк;
- unittest importable test IDs;
- JavaScript/TypeScript `*.test.*` и `*.spec.*` discovery;
- .NET common test attributes (`Fact`, `Theory`, `Test`, `TestCase`, `TestMethod`);
- исключение generated directories;
- построение команд pytest/unittest/npm/dotnet;
- pytest verbose parser;
- unittest verbose parser;
- Vitest/Jest ANSI-safe parser;
- dotnet console parser;
- serialization/restore последнего результата;
- наличие Test Explorer UI/actions в `main.py`;
- сохранение `testExplorerLastRun` в project payload;
- блокировку test run при несохранённых project files;
- реальный запуск pytest process + разбор результатов;
- реальный запуск unittest process + разбор результатов.

Вся regression suite Release 3.0 / 3.1 / C1 продолжает проходить.

## Adapter safety review

### Python

- Test Explorer использует активный project Python, тот же interpreter policy, что Run/Environment Manager.
- pytest не скачивается автоматически.
- unittest использует стандартную библиотеку Python.
- Run Selected разрешён только по явно обнаруженному pytest node id или unittest test id.

### Node / Vitest / Jest

- Astra выполняет только существующий `scripts.test` из `package.json`.
- package manager определяется по lockfile (`npm`, `pnpm`, `yarn`, `bun`).
- bare `npx` не используется.
- Test Explorer не устанавливает framework автоматически.
- точечный запуск намеренно не угадывается между несовместимыми CLI Vitest/Jest; C2 безопасно запускает весь project test script.

### .NET

- используется локально доступный `dotnet` CLI;
- команда: `dotnet test --logger console;verbosity=normal --nologo`;
- точечный filter намеренно не генерируется из неполной статической информации C#, чтобы не запускать неверный test target.

## Discovery review

Static discovery ограничен и не исполняет код проекта.

Исключаются:

```text
.git
node_modules
.venv / venv
__pycache__
build / dist
.pytest_cache / .mypy_cache / .ruff_cache
.next / .cache / .godot
coverage
vendor
target
bin / obj / out
```

Обычные static tests отображаются до запуска. Dynamic/parameterized tests могут появляться из runtime output, даже если статически они не были перечислены.

## Unsaved-buffer safety

Внешние test runners читают файлы с диска. Поэтому C2 не запускает Test Explorer, если открытый файл активного проекта изменён, но не сохранён. Это предотвращает ситуацию, когда пользователь видит один код в editor buffer, а тестируется старая версия файла.

## Result persistence

Последний запуск сохраняется в `astral.project.json` как `testExplorerLastRun`:

- adapter id;
- display name;
- exit code;
- overall status;
- summary;
- timestamp;
- result nodes.

Для защиты project config от чрезмерного роста persisted tree ограничен 2000 nodes. При повторном открытии Astra-проекта последний result tree восстанавливается.

## Runtime integration tests deferred

Текущая Linux sandbox-среда всё ещё не содержит PySide6. Поэтому остаются 6 ранее написанных runtime tests:

1. `test_lsp_b1.py::LspProcessLifecycleTests::test_initialize_server_request_and_graceful_shutdown`
2. `test_lsp_b1.py::LspProcessLifecycleTests::test_unexpected_exit_restarts_with_backoff`
3. `test_lsp_b2.py::LspDocumentIntegrationTests::test_manager_syncs_documents_and_collects_diagnostics`
4. `test_lsp_b2.py::LspTcpTransportTests::test_external_tcp_initialize_and_shutdown`
5. `test_lsp_b3.py::LspInteractiveRuntimeTests::test_manager_routes_completion_hover_signature_navigation_rename_and_symbols`
6. `test_quality_c1_qt.py::QualityTaskRuntimeTests::test_task_manager_streams_stdin_to_formatter_process`

C2 pytest/unittest external-process integration удалось выполнить прямо в sandbox, потому что она не требует Qt GUI. Полные UI, npm/Vitest/Jest и dotnet Windows/toolchain сценарии внесены в `TEST_REGISTRY_3_X.md` и остаются обязательными для финального Windows gate после Release 3.3.

## Manual test status

Ручное Windows-тестирование владельцем сейчас не выполняется по утверждённому процессу. C2 manual IDs `C2-TEST-01` — `C2-TEST-22` добавлены в единый registry.

## Result

**PASS — Release 3.2 C2 implementation gate completed.**

C2 можно заморозить как основу для C3 Git.
