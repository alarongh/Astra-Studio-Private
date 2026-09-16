# CHANGELOG — Astra Studio Release 3.2

Дата начала ветки: 2026-08-23

Release 3.2 развивает замороженный Release 3.1 и посвящён качеству кода, тестированию и командной работе. Реализация шла независимыми блоками C1–C3. На этой контрольной точке завершены **C1 — Formatters / Linters**, **C2 — Test Explorer** и **C3 — Git / Source Control**. Release 3.2 теперь feature-complete и используется как замороженная основа для Release 3.3.

## C1 — Formatters / Linters

### Unified quality layer

Добавлен модуль `core/quality_tools.py` с единым описанием formatter/linter operations:

- определение инструмента по языку;
- project-local executable resolution;
- построение безопасной команды;
- stdin-based обработка текущего editor buffer;
- машинный разбор diagnostics;
- явные install/update plans без неявной загрузки неизвестного инструмента.

### Format Document

Добавлена команда **Форматировать** (`Shift+Alt+F`).

Поддержка:

- Python → Ruff Formatter;
- JavaScript / TypeScript → Prettier;
- HTML / CSS / JSON / YAML / Markdown → Prettier;
- C++ → clang-format;
- Luau / Lua → StyLua.

Formatter получает текущий текст редактора через stdin. Astra не отдаёт инструменту право молча переписывать исходный файл напрямую.

Защита результата:

- если пользователь изменил документ, пока formatter работал, поздний результат отбрасывается;
- ошибка formatter не заменяет исходный текст;
- ручное форматирование применяется как единый editor edit block и остаётся доступным для Undo;
- путь реального файла передаётся formatter для поиска проектного конфига и определения parser/language mode.

### Format on Save

В настройки добавлен opt-in переключатель **«Форматировать при сохранении»**. По умолчанию он выключен.

Алгоритм не создаёт рекурсивный save/format loop:

1. обычное сохранение;
2. асинхронный formatter;
3. проверка, что editor buffer не изменился;
4. применение результата;
5. одно повторное сохранение уже отформатированного текста без повторного запуска formatter.

Внутренние save paths для Run/Build/закрытия вкладки обходят Format on Save там, где параллельная TaskManager-задача могла бы создать гонку.

### Lint current file

Добавлена команда **Lint текущего файла**.

Поддержка:

- Python → `ruff check` с JSON output;
- JavaScript / TypeScript → ESLint с JSON output.

Lint также работает по текущему editor buffer через stdin, а сохранённый путь используется для project config и навигации.

### Problems integration

Diagnostics formatter/linter слоя не создают отдельную несовместимую панель. Они объединяются с LSP diagnostics в существующей вкладке **Проблемы**.

Сохраняются:

- severity filters;
- «только текущий файл»;
- группировка по файлу;
- переход к строке/колонке;
- source/rule code.

Повторный чистый lint очищает старые quality diagnostics конкретного файла. Ошибка запуска/configuration failure не должна молча уничтожать предыдущий полезный результат.

### Safe tool discovery

Приоритет инструментов:

1. project-local `node_modules/.bin`;
2. project `.venv` / `venv`;
3. PATH;
4. для clang-format на Windows — известные LLVM/MSYS2 locations.

Astra не использует bare `npx` как fallback, чтобы команда форматирования не могла незаметно скачать произвольную актуальную версию пакета.

### Explicit installation

При отсутствии инструмента Astra предлагает установку только после явного подтверждения.

- Ruff → активный Python проекта;
- Prettier → local exact npm devDependency;
- ESLint → local exact npm devDependency;
- StyLua → local exact `@johnnymorganz/stylua-bin` devDependency;
- clang-format → LLVM через WinGet на Windows.

Node quality tools автоматически не ставятся в проект без `package.json`.

### TaskManager stdin

`ProcessTaskSpec` расширен полем `stdin_data`. `BackgroundProcessTask` теперь умеет:

- дождаться старта `QProcess`;
- записать UTF-8/bytes stdin;
- закрыть write channel;
- продолжить существующий asynchronous stdout/stderr/progress/cancel lifecycle.

Это используется formatter/linter integration и не блокирует GUI thread.

### Tests / gate C1

Добавлены:

- `tests/test_quality_c1.py`;
- `tests/test_quality_c1_qt.py`;
- новые checks в `tests/smoke_static.py`;
- Release regression suite переведён на `test_release_3_2.py`;
- все текущие test names и будущие manual cases синхронизированы с `TEST_REGISTRY_3_X.md`.

Итог C1 sandbox gate:

- `compileall`: PASS;
- static smoke: PASS;
- **85 collected / 79 PASS / 6 SKIPPED / 0 FAILED**;
- 6 SKIPPED — уже написанные Qt/PySide6 runtime integration tests, оставленные для финального Windows gate после Release 3.3.

## C2 — Test Explorer

### Generic adapter model

Добавлен `core/test_explorer.py` с независимой от UI моделью тестовых адаптеров, discovery, безопасного запуска и разбора результатов. Astra может одновременно обнаружить несколько тестовых стеков в одном проекте и переключаться между ними в Test Explorer.

Поддержка C2:

- pytest;
- unittest;
- npm project test script с распознаванием Vitest/Jest;
- `dotnet test`.

Astra не запускает `npx` и не загружает test framework автоматически. Для Node-проектов используется существующий `scripts.test` и установленный package manager проекта.

### Discovery

Test Explorer выполняет ограниченное безопасное статическое обнаружение:

- Python `test*.py` / `*_test.py`, функции и методы `test*`;
- JavaScript/TypeScript `*.test.*` / `*.spec.*`;
- .NET методы с распространёнными test attributes (`Fact`, `Theory`, `Test`, `TestCase`, `TestMethod`).

`.git`, `node_modules`, `.venv`, `build`, `dist`, `bin`, `obj`, `target` и другие generated directories исключены. Динамически сгенерированные/parameterized cases могут дополнительно появляться из runtime output после запуска.

### Execution and parsing

- pytest запускается в verbose-режиме с короткими traceback и поддерживает Run Selected по node id;
- unittest запускается через `python -m unittest` и поддерживает Run Selected по importable test id;
- npm/Vitest/Jest выполняет только существующий project `test` script;
- .NET использует `dotnet test --logger console;verbosity=normal`;
- stdout/stderr продолжают отображаться в обычной консоли Astra и параллельно разбираются для дерева результатов.

Перед внешним запуском Test Explorer блокируется, если в открытых файлах текущего проекта есть несохранённые изменения, чтобы пользователь не сравнивал editor buffer с тестами версии на диске.

### UI and persistence

Добавлена вкладка **Тесты** и кнопка **Test Explorer** в панели проекта. В UI есть:

- выбор обнаруженного адаптера;
- Discover;
- Run All;
- Run Selected для безопасно адресуемых pytest/unittest tests;
- Rerun last;
- pass/fail/skip/error tree;
- двойной клик по тесту для перехода к исходному файлу и строке.

Последний результат сохраняется в `astral.project.json` как `testExplorerLastRun` (с ограничением размера дерева) и восстанавливается при повторном открытии проекта.

### Tests / gate C2

Добавлен `tests/test_test_explorer_c2.py`. Проверяются detection, discovery, command construction, parsers, persistence, generated-folder exclusions, UI integration tokens и реальные pytest/unittest processes.

Итог C2 sandbox gate:

- `compileall`: PASS;
- static smoke: PASS;
- **109 collected / 103 PASS / 6 SKIPPED / 0 FAILED**;
- **88 subtests PASS**;
- реальные pytest/unittest command + parser integration: PASS.

## C3 — Git / Source Control

### Git model and repository detection

Добавлен `core/git_tools.py`, который отделяет Git parsing/command construction от Qt UI. Astra использует установленный Git CLI и определяет реальный корень репозитория через `git rev-parse --show-toplevel`, поэтому проект может быть открыт как из корня repo, так и из вложенной папки монорепозитория.

Status читается через стабильный machine-readable `git status --porcelain=v2 -z --branch`. Разбираются:

- текущая ветка / detached HEAD;
- upstream;
- ahead / behind;
- staged и working-tree changes;
- untracked files;
- conflicts;
- rename/copy с сохранением исходного пути.

NUL-delimited формат выбран специально, чтобы пробелы и специальные символы в путях не требовали shell parsing. Все команды передаются `QProcess` как program + argument list, без shell interpolation.

### Source Control UI

В проектную панель добавлена кнопка **Git / Source Control**, а в нижнюю область — отдельная вкладка **Git**. Она показывает:

- branch/tracking summary;
- staged/working/conflict counts;
- список изменённых файлов;
- отдельные Index и Working Tree состояния;
- рабочий и staged diff выбранного файла;
- commit message field.

Двойной клик открывает существующий файл в редакторе. Для удалённого файла Astra показывает контролируемое сообщение вместо попытки открыть несуществующий путь. Если Git repo находится выше открытой project folder, UI явно помечает parent-repo, а Stage All дополнительно предупреждает, что действие затронет весь репозиторий.

### Stage / unstage

Реализованы:

- Stage selected;
- Unstage selected;
- Stage All;
- Unstage All.

Stage All / Unstage All требуют отдельного подтверждения. Unstage реализован через index-only `git reset`, поэтому working-tree содержимое не удаляется. Для staged rename Astra передаёт и новый, и исходный path, чтобы unstage не превращал rename в частично staged delete. Эта ветка покрыта реальным Git integration test.

### Diff

Diff выполняется без external diff drivers и цвета:

- working tree → `git diff --no-ext-diff --no-color`;
- staged → `git diff --cached`;
- path передаётся после `--`;
- rename/copy diff включает оба path, чтобы Git мог показать rename как единое изменение.

Untracked file не подменяется выдуманным diff: Astra прямо сообщает, что staged diff станет доступен после Stage.

### Commit

Commit выполняется только после:

- наличия staged changes;
- отсутствия unresolved conflicts;
- непустого commit message;
- явного подтверждения пользователя.

Astra не делает amend/rebase/auto-stage при commit и не передаёт shell command string. После успешного commit status автоматически обновляется.

### Pull / push safety

Network mutations максимально консервативны:

- Pull доступен только для clean working tree с настроенным upstream и не в detached HEAD;
- используется только `git pull --ff-only`, поэтому кнопка не создаёт неожиданный merge commit;
- Push требует upstream и явное подтверждение;
- Astra не использует `--force` или `--force-with-lease`;
- `GIT_TERMINAL_PROMPT=0` не позволяет невидимому terminal prompt повесить фоновую задачу;
- операции остаются cancellable через общий TaskManager UI.

Diverged-history test с локальным bare remote подтверждает, что `pull --ff-only` завершается ошибкой и не создаёт merge commit. Отдельный local-remote integration test подтверждает обычный fast-forward pull и push без обращения к интернету.

### TaskManager integration

Repository probe, status, diff, stage/unstage, commit, pull и push выполняются асинхронно через существующий TaskManager. Machine-readable status/diff output собирается отдельно от пользовательской console output. После успешной mutation Astra автоматически запускает новый status refresh.

`_start_process_task` получил опциональный per-task environment, который C3 использует для безопасной Git network environment настройки без глобальной модификации процесса Astra.

### Tests / gate C3

Добавлены:

- `tests/test_git_c3.py`;
- `tests/test_git_c3_qt.py`;
- Git integration checks в `tests/smoke_static.py`;
- расширенные manual cases в `TEST_REGISTRY_3_X.md`.

Проверяются реальные временные Git repositories, пробелы/Unicode paths, rename parsing, staged/unstaged states, first-commit unstage, diff, Stage/Unstage, commit, local bare-remote pull/push и отказ fast-forward-only pull при divergent history.

Итог C3 sandbox gate:

- `compileall`: PASS;
- static smoke: PASS;
- **127 collected / 120 PASS / 7 SKIPPED / 0 FAILED**;
- **88 subtests PASS**;
- real Git local repository operations: PASS;
- local bare-remote pull/push: PASS;
- diverged `pull --ff-only` refusal: PASS.

Седьмой SKIPPED — новый Qt/PySide6 runtime test, который прогоняет NUL-delimited Unicode Git status именно через `QProcess`/TaskManager. Он уже написан и остаётся обязательным для финального Windows gate после Release 3.3.

## Status

**C1 complete / internally gated.**  
**C2 complete / internally gated.**  
**C3 complete / internally gated.**

**Release 3.2 feature-complete / frozen for Release 3.3.**
