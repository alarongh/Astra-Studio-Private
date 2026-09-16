# CHANGELOG — Astra Studio Release 3.3

Дата начала ветки: 2026-08-23

Release 3.3 развивает замороженный Release 3.2 и добавляет StaffedUp-oriented workflows. Реализация разделена на D1 Project Templates, D2 Project Health и D3 AI-adjacent workflow. D1–D3 завершены, Final Integration Gate поколения 3.x пройден; Release 3.3 заморожен как Windows TEST BUILD.

## D1 — StaffedUp Project Templates

### Новый template layer

Добавлен `core/project_templates.py` с независимым от Qt каталогом шаблонов, renderer и атомарным созданием проекта.

Поддерживаемые шаблоны D1:

- Web / TypeScript;
- Yandex Games / TypeScript;
- Roblox / Luau;
- Godot / GDScript;
- Python App;
- Telegram Bot / Python;
- Static Website;
- Empty Project.

Yandex Games template добавлен во время D1-аудита: исходный roadmap StaffedUp Mode не включал отдельный Yandex Games skeleton, хотя platform boundary требуется уже при создании browser-game проекта.

### Project creation UI

Кнопка **Создать проект** теперь открывает StaffedUp template dialog. До создания пользователь видит:

- описание шаблона;
- required tools;
- recommended tools;
- Run/Build/Test/Install commands;
- полный список создаваемых файлов;
- родительскую папку проекта.

Создание шаблона само по себе не запускает `npm`, pip/uv, Rojo, Godot или сетевую установку. Зависимости остаются отдельным явным действием через Install Project / существующие tool workflows.

### Atomic no-overwrite creation

Шаблон полностью рендерится в sibling staging directory `.astra-project-*` и только после успешной генерации перемещается в целевую папку.

Защита:

- непустая существующая папка не перезаписывается;
- существующая пустая папка может быть использована;
- при ошибке staging очищается;
- template paths проверяются на absolute/`..` escape;
- package managers и network actions не вызываются из renderer.

### StaffedUp metadata

`astral.project.json` получает секцию `staffedUp`:

```json
{
  "staffedUp": {
    "template": "web-typescript",
    "templateVersion": 1,
    "healthProfile": "web-typescript",
    "requiredTools": ["node", "npm"],
    "recommendedTools": ["git"]
  }
}
```

Metadata сохраняется в runtime state Astra и переживает обычное сохранение project state. D2 будет использовать её для profile-specific health checks.

### Portable project config

Добавлен `core/project_paths.py`.

Проектные пути внутри репозитория теперь сериализуются относительно `astral.project.json`:

- `mainFolder`;
- `openFiles`;
- `activeFile`;
- attached folders, если они физически находятся внутри проекта.

Внешние attached folders остаются абсолютными намеренно. Это устраняет ситуацию, когда shared `astral.project.json` содержит путь пользователя с другого компьютера и перестаёт открываться после clone/copy.

### Template contents

#### Web / TypeScript

- Vite + TypeScript + Vitest;
- `package.json`, `tsconfig.json`;
- `src/main.ts`, styles и smoke test;
- `.env.example`;
- project-local npm dependency model;
- explicit npm Run/Build/Test/Install commands.

#### Yandex Games / TypeScript

- TypeScript/Vite browser-game skeleton;
- game logic отделена от `src/platform/`;
- local adapter работает без platform SDK;
- Yandex-specific calls изолированы в `src/platform/yandex.ts`;
- template не зашивает неподтверждённый внешний SDK URL/credential.

#### Roblox / Luau

- `default.project.json` для Rojo;
- `src/server`, `src/client`, `src/shared`;
- Run через `rojo serve`;
- Build в ignored `game.rbxlx`;
- generated Roblox binary assets исключены через `.gitignore`.

#### Godot

- Godot 4 `project.godot`;
- реальная main scene;
- `scripts/main.gd`;
- `.godot`/export/build state исключён из Git;
- export preset не придумывается без project-specific target configuration.

#### Python App

- package `app/`;
- `pyproject.toml`;
- `python -m app` Run command;
- standard-library unittest smoke test;
- project `.venv`/uv workflow совместим с существующим Python Environment Manager.

#### Telegram Bot

- aiogram 3 requirements;
- `python-dotenv`;
- `.env.example` + Git ignore для реального `.env`;
- config/token code отделён от network polling;
- unit tests конфигурации не требуют запуска Telegram client.

#### Static Website / Empty

- Static Website не требует frontend package manager; Run может использовать local Python HTTP server.
- Empty Project создаёт только базовый project shell без выдуманных runtime dependencies.

### Project tree visibility

Project tree дополнен special-file handling для StaffedUp config files, включая `.env.*`, `.gitignore` и `project.godot`, чтобы важные project files не исчезали только из-за нестандартного suffix.

## D1 tests / gate

Добавлен `tests/test_staffedup_d1.py`.

D1 checks включают:

- catalog coverage;
- Cyrillic → portable slug rendering;
- path safety и token rendering;
- no-overwrite/atomic creation;
- JSON/TOML validity;
- Web/Yandex/Roblox/Godot structure checks;
- реальный запуск сгенерированного Python App;
- реальный unittest run Python App;
- реальный unittest run Telegram config;
- portable project path serialization;
- main integration/source checks.

Итог D1 sandbox gate:

- `compileall`: PASS;
- static smoke: PASS;
- **145 collected / 138 PASS / 7 SKIPPED / 0 FAILED**;
- **88 subtests PASS**.

7 SKIPPED — уже зарегистрированные Qt/PySide6 runtime integration tests предыдущих блоков. D1 не добавляет новый ложноположительный runtime PASS: template-dialog и Windows toolchain cases остаются в manual registry для финального owner test после D3.

## Следующий блок

D2 — StaffedUp Project Health:

- profile-specific structure validation;
- `.gitignore`, `.env.example`, docs checks;
- dependency/tool verification;
- deterministic one-click fixes only where Astra can prove the change is safe.


## D2 — StaffedUp Project Health

### Profile-aware health engine

Добавлен `core/staffedup_health.py`. D2 использует `staffedUp.template`/`healthProfile` из `astral.project.json` и проверяет StaffedUp-проект по правилам конкретного D1 template. Поддержаны все восемь шаблонов: Web/TypeScript, Yandex Games, Roblox/Luau, Godot, Python App, Telegram Bot, Static Website и Empty Project.

Проверки включают required structure boundaries, `.gitignore`, `.env.example`, README/docs, required/recommended tools, Node/Python dependency state, Git repository presence и StaffedUp config metadata/project commands.

### Safe Fix boundary

Project Doctor получил отдельную StaffedUp Health секцию и кнопку **Исправить безопасное**. Автоматическое исправление допускает только детерминированные non-destructive операции:

- создать отсутствующий canonical `.gitignore`;
- дописать только недостающие ignore patterns;
- сохранить пользовательские строки, legacy CP1251 и CRLF при обновлении `.gitignore`;
- создать отсутствующие support-файлы (`README.md`, canonical `.env.example`, профильные `docs/*`) только если целевой файл отсутствует;
- восстановить canonical StaffedUp metadata и только пустые standard project commands в читаемом `astral.project.json`.

Safe Fix не восстанавливает source code/directories, не перезаписывает существующую документацию или env example, не копирует secrets из `.env`, не создаёт Git repository, не устанавливает dependencies/tools и не запускает network actions. Повреждённый `astral.project.json` не перезаписывается.

### D2 audit fixes

Во время реализации отдельно исправлен порядок добавления `.gitignore` patterns: canonical order сохраняется, поэтому negation rule `!.env.example` не может оказаться до более общего `.env.*` и потерять смысл. Existing CP1251 `.gitignore` с CRLF сохраняет кодировку/переводы строк при safe append.

### Tests / gate

Добавлен `tests/test_staffedup_d2.py` с 17 D2 tests. Проверяются все profile reports, unknown/non-StaffedUp projects, safe no-overwrite, support-file recovery, source-code non-recovery, command/custom-command boundary, metadata repair, malformed-config refusal, idempotency, env-secret boundary, dependency/tool severity и main UI integration.

Итог D2 sandbox gate: `compileall` PASS, static smoke PASS, **162 collected / 155 PASS / 7 SKIPPED / 0 FAILED**, **88 subtests PASS**. Семь skipped — ранее зарегистрированные Qt/PySide6 runtime integration tests; Project Doctor UI/manual Windows acceptance остаётся в общем `TEST_REGISTRY_3_X.md`.

## D3 — AI-adjacent Workflow

### Новый local-only context layer

Добавлен `core/ai_context.py` и кнопка **AI Context** в панели проекта. Astra не получает AI API client и не отправляет данные по сети. D3 только подготавливает переносимый контекст для ручной работы с внешним AI-инструментом.

Реализовано:

- relative path copy для main/attached project roots;
- selection copy с реальными line numbers и safe Markdown fence;
- deterministic project tree export;
- Problems export из LSP + quality diagnostics;
- Terminal и Program/Task output export с explicit secret-review warning и bounded tail;
- локальная генерация `PROJECT_CONTEXT.md` из явно выбранных файлов.

### Explicit-selection / secret boundary

D3-dialog стартует с unchecked file list. `.env`, `.env.*`, common credential/private-key/certificate files, symlinks, binary/unsupported text и oversized files блокируются. `.env.example`/`.env.sample` остаются допустимыми. Generated dependency/build/cache directories и сам `PROJECT_CONTEXT.md` не попадают в tree/candidate recursion.

PROJECT_CONTEXT не содержит absolute project paths. Problems/Terminal/Program output включаются отдельно; Terminal/Program требуют дополнительного предупреждения, потому что arbitrary console output нельзя надёжно secret-scan. Existing context file не перезаписывается без Yes, а открытый `PROJECT_CONTEXT.md` не регенерируется, чтобы избежать stale editor overwrite. Финальная запись атомарная через temporary sibling + `os.replace`.

`PROJECT_CONTEXT.md` добавлен в canonical StaffedUp `.gitignore` всех D1 templates и в `.gitignore` самой Astra. D2 Project Health автоматически видит отсутствие этого правила и умеет безопасно дописать **только ignore rule**, не изменяя уже существующий context file.

### D3 audit fixes

Во время D3-аудита исправлена потенциальная ложная блокировка project file, если один из **внешних ancestor directories** компьютера назывался `build`/`bin`: generated-dir filter теперь применяется только к relative components внутри project root. Problem export дополнительно bounded, длинные diagnostic messages ограничиваются, а Markdown path labels безопасно работают даже с backticks.

Дополнительно исправлена важная Qt/Unicode граница: `QTextCursor.selectionStart()/selectionEnd()` используют позиции Qt/UTF-16, которые нельзя напрямую применять как Python code-point offsets при emoji/non-BMP символах. Copy Selection теперь форматирует `QTextCursor.selectedText()` и берёт стартовую строку через Qt document cursor, поэтому emoji перед/внутри выделения не сдвигают экспорт.

### Tests / gate

Добавлен `tests/test_staffedup_d3.py` с 23 D3 tests: roots/relative labels, outside-root refusal, secret boundaries, UTF-8/CP1251, binary/size/symlink guards, line-number selection, Markdown fences, tree exclusions/order, Problems/output formatting, explicit selected-content boundary и atomic write.

Итог D3 sandbox gate: `compileall` PASS, static smoke PASS, **185 collected / 178 PASS / 7 SKIPPED / 0 FAILED**, **88 subtests PASS**. Семь skipped — уже существующие Qt/PySide6 runtime integration tests B1–C3/C1. D3 manual acceptance расширен до `D3-AI-01 … D3-AI-36` в едином `TEST_REGISTRY_3_X.md`.

**Release 3.3 implementation status: feature-complete and internally gated. Следующий этап — Final Integration Gate поколения 3.x; новые функции до него не добавляются.**


## Final Integration Gate — PASS

После D1–D3 выполнен отдельный интеграционный аудит всей ветки 3.x без расширения feature scope. Gate дополнительно добавил воспроизводимые `tests/test_final_integration_3x.py` и исправил две stale user-facing строки установщика, которые всё ещё называли диагностику/установщик Release 3.1 вместо текущего `APP_VERSION`. README также синхронизирован: D3 больше не помечен как NEXT.

Финальный sandbox regression: **201 collected / 194 PASS / 7 SKIPPED / 0 FAILED**, плюс **88 subtests PASS**. Семь skipped — существующие Qt/PySide6 runtime integration tests, которые не могут быть выполнены в текущем Linux sandbox и остаются обязательными для Windows acceptance.

Дополнительно подтверждены: полная Python registry ↔ JSON parity (41/41), 20/20 Check+Run routing branches, 20 LSP configs, 11 обязательных runtime assets, 13 installer scripts, settings load/save parity, project Python isolation, cancellation/shutdown contracts, legacy settings/project migration, отсутствие временных `/mnt/data`/Release 2.3 путей в runtime и clean ZIP packaging.

**Release 3.3 frozen for Windows TEST BUILD.** Следующая работа по ветке — только owner acceptance/regression. Найденные дефекты получают номера 3.4/3.5/...; Release 4.0 не планируется до стабильного sign-off 3.x.
