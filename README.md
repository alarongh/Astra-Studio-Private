# Astra Studio

Версия: **Release 3.13 — Windows verified portable build**

Astra Studio — лёгкая локальная IDE, которая развивается как среда разработки для задач StaffedUp: web, Python, Roblox/Luau, Godot, Windows-скрипты и небольшие приложения. Цель 3.x — сохранить простой интерфейс Astra, но добавить проектные инструменты, окружения, диагностику и IDE-функции без необходимости превращать программу в копию VS Code.


## Статус Release 3.13

Release 3.0–3.3 остаются замороженным функциональным baseline. Патчи 3.4–3.12 закрыли Windows launcher/runtime, Java, шрифт, ярлык, layout и updater defects. **Release 3.13** добавляет type-aware C++20/23 autocomplete с безопасными `#include`, расширяет проверенный Python library registry с 41 до 67 пакетов и сохраняет публичный GitHub update feed. В интерфейсе временно показаны Java, Python, C++, JavaScript, HTML и CSS; реализации остальных языков сохранены внутри проекта и не удалены.

Тестовые зависимости теперь входят в единый установочный поток: `install_app.bat` устанавливает `requirements-test.txt`, `reinstall_app.bat` пересоздаёт `.venv` целиком, а `run_acceptance_tests.bat` запускает Windows acceptance suite без ручной докачки `pytest`.

## Что уже есть в ветке 3.x

- исправления стабильности, найденные при аудите Release 2.2;
- редактор, вкладки, консоль, терминал, проекты, темы, обои, сборка Python/C++ EXE;
- безопасный реестр Python-библиотек с import-name → pip-name;
- Python project environment detection (`.venv`, `venv`);
- поддержка `uv` как предпочтительного менеджера, если он установлен, с fallback на venv/pip;
- создание `.venv`, выбор интерпретатора проекта, установка зависимостей и экспорт `requirements.txt`;
- проектные Run / Build / Test / Install команды в `astral.project.json`;
- автоматическое определение базовых project commands для распространённых типов проектов;
- поиск по проекту (`Ctrl+Shift+F`) и безопасная массовая замена;
- Quick Open (`Ctrl+P`);
- Project Doctor;
- расширенный набор языков и форматов.

## Windows runtime acceptance — Release 3.6

- Always on Top больше не использует raw `SetWindowPos` и не переустанавливает полный набор `windowFlags`; меняется только `WindowStaysOnTopHint`, поэтому системные minimize/maximize/close hints сохраняются.
- при выключенном Always on Top startup вообще не мутирует native window flags; это закрывает наблюдавшийся Windows error 1400 и нерабочий системный крестик;
- у главного окна нет custom/frameless title bar: видимый X является штатной кнопкой Windows и приходит в существующий `closeEvent`; причиной сбоя был не сигнал кнопки, а пересоздание native HWND полным Qt fallback после невалидного `SetWindowPos`;
- runtime-тест formatter stdin сравнивает логический текст независимо от Windows CRLF/LF;
- `PROJECT_CONTEXT.md` получает нормализованные LF независимо от line endings исходника, не изменяя сам source-файл;
- `astra_studio.log` мигрируется/создаётся как UTF-8 with BOM, включая прежний BOM-less UTF-8 и CP1251, чтобы стандартный Windows PowerShell `Get-Content` показывал кириллицу без mojibake;
- добавлены отдельные Release 3.6 regression, Qt runtime и Windows native `SC_CLOSE` tests для caption/topmost поведения.
- текущий автоматический реестр содержит **252 pytest-теста**; итог Windows-прогона: **250 PASS / 2 SKIPPED / 0 FAILED**, плюс 88 passing subtests;
- portable EXE собирается как onedir через `astra_studio.spec`; переносить или публиковать один `Astra Studio.exe` без соседней `_internal` нельзя;
- встроена ручная проверка обновления Astra по HTTPS manifest с валидацией версии, размера и SHA-256; feed остаётся выключенным, пока издатель не задаст реальный URL.
- добавлен профиль **Angel 404**: фиолетово-чёрная тема, приложенные обои и встроенный `Minecraft Rus`; выбор шрифта применяется глобально ко всему тексту Astra и сохраняется между запусками.

## Windows acceptance UX — Release 3.5

- настройки открываются как внутренняя страница Astra, а не отдельное окно;
- редактор и обе консоли имеют более широкий диапазон прозрачности; для редактора добавлен отдельный control размытия фона;
- `Вывод программы` и `Терминал` используют inline-ввод прямо в текстовой консоли, без отдельной нижней строки ввода;
- первая панель main splitter не может схлопнуться до нулевой ширины, а сохранённые splitter sizes нормализуются при восстановлении;
- Python Libraries принимает произвольные PyPI requirement-строки (`httpx`, `rich>=13`, `fastapi[standard]`) с безопасной валидацией;
- известные import→distribution mappings по-прежнему берутся из безопасного registry, а неизвестные imports можно ставить по одноимённому PyPI-пакету только после подтверждения либо через отдельный opt-in;
- свежая/чистая установка включает runtime + acceptance-test dependencies одним потоком.

> Важно: визуальный blur в 3.5 по-прежнему реализуется через общий backdrop/wallpaper blur Astra. Слайдеры управляют вкладом соответствующей области в общий эффект; это не независимый нативный Windows Acrylic/Mica blur для каждого виджета.

## Языки и форматы

Основные языки:

- Python
- C++
- Java
- JavaScript
- TypeScript
- Luau / Lua
- GDScript
- PHP
- PowerShell
- C#
- SQL
- HTML
- CSS

Конфигурация и документация:

- JSON / JSONC
- YAML
- Markdown
- TOML
- XML
- Shell
- Dockerfile

Часть языков умеет запускаться/проверяться через локальные CLI-инструменты, а поддерживаемые language servers Release 3.1 дают diagnostics, completion и навигацию непосредственно в редакторе.

Встроенная offline-библиотека completion теперь покрывает Python, C++, Java, JavaScript, TypeScript, C#, PHP, PowerShell, SQL, HTML, CSS, GDScript, Luau, Shell и Dockerfile. Для Java дополнительно доступны локальные/document symbols, расширенный набор standard-library classes и методы известных типов даже без `jdtls`. При выборе `ArrayList` и других известных классов Astra добавляет отсутствующий import.

В открытом окне подсказок Tab больше не вставляет первый вариант сразу: первый Tab выбирает нулевую строку, последующие Tab циклически переходят дальше и после конца возвращаются к началу. Space фиксирует выбранный вариант и добавляет пробел; Enter и клик мышью фиксируют его без пробела. Exact snippets остаются отдельным точным Tab-механизмом.

На странице установщика можно выбрать оформление ярлыка — классический Astra, Angel 404 или Astra Legacy — и создать/обновить `Astra Studio.lnk` на рабочем столе. Поиск рабочего стола учитывает обычную, русскую и перенесённую в OneDrive папку.

Для Java Astra передаёт UTF-8 отдельно исходному коду, stdout и stderr JVM. Это устраняет «кракозябры» русских строк на Windows, где графически запущенный JDK может использовать `Cp1251` для консольных потоков даже при `file.encoding=UTF-8`.

## LSP — Release 3.1 B1 + B2 + B3

В `core/lsp_protocol.py`, `core/lsp_servers.py` и `core/lsp_transport.py` добавлен фундамент Language Server Protocol:

- JSON-RPC 2.0 поверх стандартного LSP `Content-Length` framing;
- безопасный incremental parser с ограничениями размера заголовка и payload;
- `initialize` → `initialized` → `shutdown` → `exit`;
- отдельные постоянные `QProcess` для language servers, не занимающие single-slot `TaskManager`;
- отдельные stdout/stderr каналы;
- обработка базовых server → client requests (`workspace/configuration`, capability registration, workspace folders);
- bounded automatic restart с exponential backoff после неожиданного завершения;
- graceful shutdown всех LSP-процессов при смене проекта и закрытии Astra;
- поиск server executable сначала в проектных `.venv` / `node_modules/.bin`, затем в PATH;
- пользовательские overrides через `%LOCALAPPDATA%\AstralStudio\lsp_servers.json` на Windows.

Каталог LSP явно покрывает все 20 языков/форматов Astra. Для GDScript используется внешний TCP LSP Godot (`127.0.0.1:6005`) через отдельный `core/lsp_tcp_transport.py`. PowerShell/XML по-прежнему не запускаются через выдуманную команду: для них оставлена явная конфигурация без ложного auto-start.

Пример пользовательского override:

```json
{
  "servers": {
    "Python": {
      "candidates": [
        {"command": "pyright-langserver", "args": ["--stdio"]}
      ],
      "max_restarts": 4
    }
  }
}
```

B3 добавляет отдельную страницу **LSP / Outline** со статусом серверов, start/stop и явными safe install/update entry points. Автоматическая установка доступна только для заранее описанных планов (например BasedPyright, TypeScript Language Server, YAML Language Server, clangd/LLVM и csharp-ls); неоднозначные серверы не устанавливаются по догадке. Для текущего TypeScript Language Server проверяется Node.js >=22.22.2, а для csharp-ls — .NET SDK >=10. GDScript использует LSP встроенного Godot и до соединения показывается как внешний ожидаемый server.

### Documents + Diagnostics — B2

B2 добавляет реальную связь редактора с language server:

- `didOpen`, debounced `didChange`, `didSave`, `didClose`;
- монотонные версии документов;
- повторный `didOpen` актуальных документов после restart language server;
- сбор `textDocument/publishDiagnostics`;
- защита от устаревших versioned diagnostics;
- вкладка **Проблемы** с Error / Warning / Information / Hint;
- фильтры severity и «только текущий файл»;
- навигация по клику к нужному файлу, строке и колонке;
- очистка diagnostics после исправления/закрытия файла;
- Godot/GDScript TCP adapter;
- cooldown на повторные подключения к недоступному server, чтобы не создавать reconnect storm при наборе текста.

Все названия автоматических и будущих ручных тестов поколений 3.x фиксируются в `TEST_REGISTRY_3_X.md`.

### Interactive Editor Features — B3

Release 3.1 добавляет:

- `Ctrl+Space` — LSP completion;
- `Ctrl+Shift+H` — Hover;
- `Ctrl+Shift+Space` — Signature Help;
- `F12` — Go to Definition;
- `Shift+F12` — Find References;
- `F2` — Rename Symbol;
- `Ctrl+Shift+O` — Document Outline / Symbols.

Interactive responses привязаны к path/version документа, поэтому устаревший ответ после редактирования или смены проекта не должен применяться к новому состоянию. Rename принимает только безопасные текстовые WorkspaceEdit внутри активного проекта: resource operations и edits вне проекта отклоняются, а closed-file edits учитывают UTF-16 LSP columns, legacy CP1251 и CRLF.

Все автоматические и будущие ручные проверки, включая B3, находятся в `TEST_REGISTRY_3_X.md`.

## Quality tools — Release 3.2 C1

Release 3.2 добавляет единый слой `core/quality_tools.py` и две команды редактора: **Форматировать** (`Shift+Alt+F`) и **Lint текущего файла**. Format on Save включается отдельно в настройках и по умолчанию выключен.

Поддерживаемые formatter paths:

- Python → Ruff (`ruff format`);
- JavaScript / TypeScript → project-local Prettier;
- HTML / CSS / JSON / YAML / Markdown → тот же безопасный project-local Prettier;
- C++ → clang-format;
- Luau / Lua → StyLua.

Lint:

- Python → Ruff JSON diagnostics;
- JavaScript / TypeScript → ESLint JSON diagnostics.

Astra передаёт текущий editor buffer инструментам через stdin, поэтому manual format/lint не требует предварительно перезаписывать файл на диске. Quality diagnostics объединяются с LSP diagnostics в общей вкладке **Проблемы**. Formatter output применяется только если текст редактора не изменился за время внешней операции; это защищает новые правки от позднего ответа formatter.

Для Node-инструментов Astra сначала ищет `node_modules/.bin` и не использует bare `npx`, который может незаметно скачать другую версию. Установка отсутствующих quality tools выполняется только после явного подтверждения: Ruff — через активный Python проекта, Prettier/ESLint/StyLua — как project-local exact devDependencies при наличии `package.json`, clang-format — через LLVM/WinGet на Windows.

## Test Explorer — Release 3.2 C2

Во вкладке **Тесты** Astra обнаруживает тестовые стеки текущего проекта и показывает результаты единым деревом. Поддерживаются:

- pytest;
- unittest;
- npm/Vitest/Jest через уже существующий `scripts.test`;
- `dotnet test`.

Test Explorer умеет Discover, Run All, Run Selected для адресуемых pytest/unittest tests, Rerun last и переход к исходному тесту двойным кликом. stdout/stderr остаются видимыми в обычной консоли, а parser параллельно строит pass/fail/skip/error tree.

Последний результат сохраняется в `astral.project.json` (`testExplorerLastRun`) и восстанавливается при повторном открытии Astra-проекта. Перед запуском Astra требует сохранить изменённые project files: внешний test runner работает с файлами на диске, а не с несохранённым editor buffer.

Discovery игнорирует generated directories (`node_modules`, `.venv`, `build`, `dist`, `bin`, `obj`, `target` и др.). Статический discovery предназначен для обычных тестов; динамические/parameterized cases могут появляться из runtime output после запуска.

Node test frameworks не устанавливаются автоматически и не запускаются через bare `npx`: Astra использует только уже заданный project test script/package manager.

## Git / Source Control — Release 3.2 C3

В панели проекта появилась кнопка **Git / Source Control**, а в нижней области — отдельная вкладка Git. C3 использует установленный Git CLI и новый независимый слой `core/git_tools.py`.

Поддерживаются:

- поиск реального корня репозитория, включая проект, открытый из вложенной папки монорепозитория;
- branch / upstream / ahead / behind;
- staged, unstaged, untracked и conflict states;
- working-tree diff и staged diff выбранного файла;
- rename-aware diff;
- Stage / Unstage выбранного файла;
- явно подтверждаемые Stage All / Unstage All;
- Commit staged changes с обязательным сообщением и подтверждением;
- Pull / Push только по явной кнопке пользователя.

Astra читает status через machine-readable `git status --porcelain=v2 -z --branch`, поэтому пути с пробелами и специальными символами не разбираются shell-строками. Git commands передаются как отдельные program/arguments через `QProcess`.

Безопасность C3:

- Unstage изменяет index и не удаляет working-tree содержимое;
- staged rename при Unstage обрабатывает оба пути rename;
- Stage All предупреждает, если активный проект находится внутри более крупного parent repository;
- Commit заблокирован при unresolved conflicts и без staged changes;
- Pull разрешён только для clean tree с upstream и выполняется как `git pull --ff-only`;
- diverged history не превращается в автоматический merge commit;
- Push не использует force-флаги;
- Astra не назначает remote/upstream автоматически;
- network operations запускаются с отключённым скрытым terminal credential prompt и остаются cancellable через TaskManager.

После успешных stage/unstage/commit/pull/push status автоматически обновляется. Для diff используется встроенное текстовое окно без external diff driver.

C3 sandbox tests создают реальные временные Git repositories и локальный bare remote, поэтому stage/unstage/commit/fast-forward pull/push проверяются не только статически. Qt runtime test для Unicode/NUL status уже написан и будет выполнен в финальном Windows gate.

## StaffedUp Project Templates — Release 3.3 D1

Кнопка **Создать проект** теперь открывает StaffedUp-oriented template dialog с предварительным просмотром структуры, required/recommended tools и project commands. Создание шаблона не запускает package manager и не скачивает зависимости автоматически.

Доступны шаблоны:

- Web / TypeScript;
- Yandex Games / TypeScript;
- Roblox / Luau;
- Godot / GDScript;
- Python App;
- Telegram Bot / Python;
- Static Website;
- Empty Project.

Каждый шаблон создаёт минимально достаточную структуру, `astral.project.json`, `.gitignore`, базовую документацию и Run/Build/Test/Install commands там, где они определимы безопасно. Web-шаблоны используют project-local npm dependencies после явного **Install Project**. Roblox получает Rojo structure с разделением client/server/shared; Godot — реальный `project.godot`, scene и GDScript; Python App и Telegram Bot готовы к project `.venv`.

D1 также добавляет StaffedUp metadata в `astral.project.json` (`template`, `templateVersion`, `healthProfile`, required/recommended tools). D2 использует эти данные как профиль проверок проекта.

При создании проект сначала полностью рендерится во временной sibling-directory и только затем атомарно перемещается на место. Непустая существующая папка никогда не перезаписывается. Путь основного проекта, открытые project files и внутренние attached folders сохраняются относительно `astral.project.json`, чтобы проектный конфиг оставался переносимым между компьютерами; внешние attached folders остаются абсолютными намеренно.

Yandex Games template был добавлен в D1 сверх первоначального списка, потому что отдельный platform-adapter skeleton нужен именно на стадии создания проекта. В шаблоне game logic отделена от `src/platform/`, локальная разработка использует fallback adapter, а конкретные platform SDK publishing requirements не зашиты как неподтверждённые URL/версии.

## StaffedUp Project Health — Release 3.3 D2

Project Doctor теперь объединяет общую диагностику окружения Astra с profile-specific StaffedUp Health. Если проект создан из D1 template, Astra читает `staffedUp.template` / `healthProfile` и проверяет структуру именно этого типа проекта, а не применяет один набор правил ко всем репозиториям.

D2 проверяет:

- обязательные структурные границы шаблона (например `src/platform` у Yandex Games, client/server/shared у Roblox, `project.godot` и сцены/scripts у Godot, `app/tests` у Python);
- `.gitignore` и обязательные StaffedUp patterns;
- `.env.example` там, где шаблон имеет безопасный канонический пример;
- README и профильную документацию в `docs/`;
- required/recommended tools из template metadata;
- наличие `node_modules` для Node-проектов без автоматической установки;
- project-local Python environment для Python dependency projects;
- наличие Git repository, включая проект внутри parent monorepo;
- StaffedUp metadata/schema и обязательные project commands в `astral.project.json`.

В Project Doctor появилась кнопка **Исправить безопасное**. Она намеренно ограничена изменениями, которые Astra может доказуемо выполнить без потери пользовательских данных:

- создать отсутствующий `.gitignore` из профиля;
- дописать только недостающие ignore-patterns, сохранив существующее содержимое и legacy CP1251/CRLF;
- создать отсутствующие `README.md`, `.env.example` и профильные docs-файлы только если их вообще нет;
- восстановить отсутствующие StaffedUp metadata/пустые standard project commands.

Safe fix **не** восстанавливает удалённые source-файлы/директории, не перезаписывает существующую документацию или `.env.example`, не извлекает значения из реального `.env`, не создаёт Git repository и не запускает npm/pip/uv/Rojo/Godot или сеть. Если `astral.project.json` повреждён, Astra сообщает об ошибке и не пытается переписать неизвестную конфигурацию.


## Python Environment Manager

Astra сначала ищет Python окружение проекта, затем использует глобальный Python. Во вкладке **Библиотеки Python** отображаются:

- активный интерпретатор;
- найденные dependency files;
- наличие `uv`;
- кнопки создания `.venv`, выбора Python, установки зависимостей, обновления pip и экспорта requirements.

Если `uv` доступен, Astra предпочитает его для проектных окружений и package operations. Если `uv` отсутствует, используется стандартный `venv` + pip.

## Project commands

В `astral.project.json` могут храниться:

```json
{
  "commands": {
    "run": "npm run dev",
    "build": "npm run build",
    "test": "npm run test",
    "install": "npm ci"
  }
}
```

Пустые команды могут быть автоматически определены Astra по структуре проекта. Поддерживаются безопасные базовые сценарии для Node/package.json, Python, Godot, .NET, Maven/Gradle, CMake и Rojo.


## Windows toolchain installer

Вкладка **Установщик** умеет проверять и ставить общий набор инструментов StaffedUp через WinGet и штатные package managers:

- Python + `uv`;
- Node.js LTS + TypeScript + `tsx`;
- Git;
- C++ / MSYS2;
- Java JDK;
- PowerShell 7;
- отдельно по роли/проекту — Godot и PHP 8.4.

Luau/Rojo диагностируются Project Doctor. D1 создаёт Rojo-compatible Roblox structure, а D2 проверяет required/recommended tools профиля; установка по-прежнему остаётся отдельным явным действием пользователя.

## Состояние ветки 3.x

Полный план находится в `ROADMAP_3_X.md`.

- Release 3.0 internal gate завершён; отчёт: `TEST_REPORT_RELEASE_3_0.md`;
- Release 3.1: B1 transport DONE; B2 document sync/diagnostics DONE; B3 interactive editor/status-install UI DONE (`TEST_REPORT_RELEASE_3_1_B3.md`); Release 3.1 internally gated;
- единый реестр автоматических и будущих ручных проверок: `TEST_REGISTRY_3_X.md`;
- Release 3.2: C1 formatters/linters DONE; C2 Test Explorer DONE; C3 Git / Source Control DONE (`TEST_REPORT_RELEASE_3_2_C3.md`); Release 3.2 internally gated and frozen;
- Release 3.3: D1 StaffedUp Project Templates DONE; D2 StaffedUp Project Health DONE; D3 AI-adjacent workflow DONE (`TEST_REPORT_RELEASE_3_3_D3.md`); функциональный scope 3.x закрыт;
- Final Integration Gate после D1–D3: PASS; Release 3.3 остаётся замороженным feature baseline;
- Release 3.4 исправил Windows batch launcher; Release 3.5 закрыл UX/package-manager acceptance feedback; Release 3.6 закрыл native-window/CRLF/log defects; текущий verified candidate — Release 3.13;
- только после стабильного Windows sign-off текущей ветки 3.x начинается планирование Release 4.0.

## Установка, переустановка и Windows acceptance

Для обычной свежей установки:

1. Запустить `install_app.bat`. Он создаст `.venv` и установит runtime-зависимости из `requirements.txt` вместе с acceptance-зависимостями из `requirements-test.txt`.
2. Запустить `run_astra.bat` для обычной работы или `run.bat` для запуска с видимой консолью.

Для полного пересоздания окружения из одного архива закройте Astra и запустите `reinstall_app.bat`: он удалит старую `.venv` и заново выполнит основной installer. Никакой отдельной докачки pytest-файла не требуется.

Для автоматического Windows acceptance после установки закройте Astra и запустите `run_acceptance_tests.bat`. Скрипт использует Python именно из `.venv` и выполняет `pytest -q -rs`.

## AI-adjacent Workflow — Release 3.3 D3

В панели проекта появилась кнопка **AI Context**. D3 не встраивает LLM и не отправляет проект во внешний сервис: все операции выполняются локально и заканчиваются буфером обмена либо локальным `PROJECT_CONTEXT.md`.

Быстрые действия:

- копирование относительного project path без developer-specific absolute path;
- копирование выделенного фрагмента редактора с настоящими номерами строк и Markdown code fence;
- экспорт дерева main/attached project roots;
- экспорт LSP + linter Problems;
- экспорт Terminal и Program/Task output только после отдельного предупреждения о возможных токенах/паролях.

`PROJECT_CONTEXT.md` строится только из файлов, которые пользователь **явно отметил** в D3-dialog. По умолчанию source files не отмечены. Можно отдельным явным действием отметить открытые eligible files. Дополнительно по opt-in можно включить project tree, Problems, Terminal и Program/Task output.

Защита контекста:

- реальные `.env`/`.env.*`, common credential files и private-key/certificate formats блокируются; `.env.example`/`.env.sample` остаются допустимыми public templates;
- symlink, binary/unsupported-encoding и oversized files не встраиваются;
- generated/dependency/cache directories исключаются из дерева и контента;
- selected file content ограничен по размеру и количеству, консольный output bounded;
- PROJECT_CONTEXT использует относительные labels и не встраивает абсолютный путь компьютера;
- existing `PROJECT_CONTEXT.md` требует явного overwrite confirmation, а открытая вкладка этого файла блокирует regeneration, чтобы не потерять несохранённые правки;
- запись выполняется через sibling temp + atomic `os.replace`;
- Astra напоминает просмотреть документ перед ручной передачей внешнему AI/сервису.

D3 sandbox gate: `compileall` PASS, static smoke PASS, **185 collected / 178 PASS / 7 SKIPPED / 0 FAILED**, **88 subtests PASS**. D3 добавляет 23 pure/static automated tests; семь skipped — уже зарегистрированные Qt/PySide6 runtime integration checks предыдущих стадий. Все D3 manual acceptance cases находятся в `TEST_REGISTRY_3_X.md`.

## Следующий этап

Final Integration Gate поколения 3.x пройден. Текущий рабочий portable build — **Release 3.13** — выпускается целой папкой `Astra Studio`; подробности запуска — в `PORTABLE_README.md`, публикации обновлений — в `UPDATE_DISTRIBUTION.md`. Ручная owner-матрица по `TEST_REGISTRY_3_X.md` остаётся отдельным этапом sign-off и не подменяется автоматическими тестами.
