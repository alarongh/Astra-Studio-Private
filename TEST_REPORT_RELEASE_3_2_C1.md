# TEST REPORT — Astra Studio Release 3.2 C1

Дата: 2026-08-23

## Scope

C1 добавляет единый formatter/linter слой поверх замороженного Release 3.1:

- formatter/linter abstraction;
- Ruff Formatter + Ruff lint;
- Prettier + ESLint;
- clang-format;
- StyLua;
- Format Document;
- opt-in Format on Save;
- quality diagnostics в общей Problems panel;
- explicit safe install/update flows;
- stdin streaming через TaskManager.

C2 Test Explorer и C3 Git в этот gate намеренно не входят.

## Automated gate

В текущей sandbox-среде выполнены:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m pytest -q
```

Результат:

```text
Static smoke: PASS
Tests collected: 85
Passed: 79
Failed: 0
Skipped: 6
Subtests passed: 88
Languages/formats: 20
Python registry entries: 41
Bundled assets checked: 11
Installer scripts checked: 13
LSP language configs: 20
```

## C1 automated coverage

Pure/static tests подтверждают:

- обязательные formatter mappings Python / JS / TS / C++ / Luau / Lua;
- дополнительное Prettier-покрытие HTML / CSS / JSON / YAML / Markdown;
- Ruff/ESLint linter registry;
- безопасный разбор Ruff JSON diagnostics;
- безопасный разбор ESLint JSON diagnostics и severity mapping;
- malformed JSON не приводит parser к исключению;
- project-local `node_modules/.bin` имеет приоритет;
- formatter commands используют stdin и реальный filename;
- linter commands запрашивают machine-readable JSON;
- Prettier/ESLint/StyLua install plans остаются project-local exact devDependencies;
- TaskManager source содержит stdin lifecycle и закрывает write channel;
- main.py содержит C1 UI/settings/task/problem integration;
- вся regression suite 3.0 + 3.1 продолжает проходить.

## Runtime integration tests deferred

Текущая Linux sandbox-среда не содержит PySide6. Поэтому собраны, но не выполнены 6 runtime tests:

1. `test_lsp_b1.py::LspProcessLifecycleTests::test_initialize_server_request_and_graceful_shutdown`
2. `test_lsp_b1.py::LspProcessLifecycleTests::test_unexpected_exit_restarts_with_backoff`
3. `test_lsp_b2.py::LspDocumentIntegrationTests::test_manager_syncs_documents_and_collects_diagnostics`
4. `test_lsp_b2.py::LspTcpTransportTests::test_external_tcp_initialize_and_shutdown`
5. `test_lsp_b3.py::LspInteractiveRuntimeTests::test_manager_routes_completion_hover_signature_navigation_rename_and_symbols`
6. `test_quality_c1_qt.py::QualityTaskRuntimeTests::test_task_manager_streams_stdin_to_formatter_process`

Они уже присутствуют в проекте и остаются обязательными для финального Windows/PySide6 gate после Release 3.3.

## Formatter safety review

- исходник не отдаётся formatter на прямую перезапись;
- current editor buffer отправляется через stdin;
- поздний result не применяется после новых пользовательских изменений;
- formatter failure не заменяет исходный buffer;
- пустой stdout для непустого source считается ошибочным результатом;
- ручное форматирование применяется одним editor edit block;
- Format on Save не запускает себя рекурсивно;
- project filename передаётся Ruff/Prettier/clang-format/StyLua для поиска настроек;
- bare `npx` implicit download не используется.

## Linter / Problems review

- Ruff/ESLint получают текущий editor buffer через stdin;
- diagnostics нормализуются в единый internal record;
- Error/Warning severity совместимы с Problems filters;
- quality diagnostics объединяются с LSP diagnostics, а не заменяют их;
- clean re-lint очищает старые quality diagnostics файла;
- configuration/process errors не должны молча очищать предыдущий результат;
- Problems navigation продолжает использовать реальный project path.

## Installation review

Curated explicit plans:

- Ruff: установка через активный project Python;
- Prettier: `npm install --save-dev --save-exact prettier`;
- ESLint: `npm install --save-dev --save-exact eslint`;
- StyLua: `npm install --save-dev --save-exact @johnnymorganz/stylua-bin`;
- clang-format: LLVM/WinGet на Windows.

Для Node tools требуется `package.json`; произвольный проект не мутируется npm-установкой по догадке.

## External executable caveat

Ruff, Prettier, ESLint, clang-format и StyLua не установлены как runtime toolchain в текущем sandbox. Поэтому здесь проверены command construction, parsers, integration hooks и deferred QProcess stdin test, но реальные formatter/linter binaries должны быть прогнаны в финальном Windows acceptance после Release 3.3. Соответствующие manual IDs уже находятся в `TEST_REGISTRY_3_X.md`.

## Manual test status

Ручной Windows test владельцем сейчас **не выполняется**, согласно утверждённому процессу проекта. Все C1 manual cases сохранены в едином test registry и будут выполнены после завершения 3.3 и Final Integration Gate.

## Result

**PASS — Release 3.2 C1 implementation gate completed.**

C1 можно заморозить как основу для C2 Test Explorer.
