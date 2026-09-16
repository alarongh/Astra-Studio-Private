# TEST REPORT — Astra Studio Release 3.0

Дата финального gate: 2026-08-23

Статус: **INTERNAL GATE PASSED / FROZEN BASELINE**

## Цель gate

Закрыть Release 3.0 как стабильную внутреннюю основу перед началом Release 3.1. Ручное Windows-тестирование владельцем проекта сознательно отложено до завершения всего цикла 3.x.

## Что проверено

| Проверка | Результат | Комментарий |
|---|---|---|
| Python syntax / compile checks | PASS | `main.py` и модули `core/` проходят компиляцию |
| Unit/static tests | PASS | 31/31 тестов |
| Static smoke suite | PASS | 20 языков, 41 Python package record, 11 assets, 13 installer scripts |
| Python registry ↔ JSON parity | PASS | Полные записи, bundles и stdlib allow/ignore list синхронизированы |
| Release identity | PASS | `APP_VERSION = "Release 3.0"`; временная ветка 2.3 не используется в runtime-коде |
| Bundled assets | PASS | Все прямые и wallpaper-ресурсы существуют |
| Installer scripts | PASS | Все обязательные `.ps1` присутствуют; common installer использует stop-on-error |
| Embedded installer | PASS | Добавлено безопасное разрешение `.Source` / `.FullName` для объектов `Get-Command` и `Get-Item` |
| Desktop shortcut icon | PASS | EXE использует собственную embedded icon; launcher fallback использует стабильный `assets/astra.ico`, без `_MEIPASS` |
| Search / Replace | PASS | Повторный scan перед Replace All, двухфазная запись, CP1251→UTF-8 только после подтверждения |
| Settings load/save parity | PASS | Наборы ключей `_load_settings` и `_save_settings` совпадают |
| Project preference migration | PASS (static) | `defaultLanguage`, editor indent/font settings из project payload восстанавливаются |
| Python environment isolation | PASS | Внешний `VIRTUAL_ENV` не принимается за окружение другого проекта |
| Project command detection | PASS | npm/pnpm/Yarn Classic/Yarn Berry/Bun, Godot, CMake, .NET, Maven, Rojo, Python covered |
| Language Run/Check matrix | PASS (static) | Все 20 языков/форматов имеют явную ветку Run и Check/Compile либо осознанный non-executable path |
| TaskManager cancellation lifecycle | PASS (static) | Task slot держится до terminal signal; synchronous cancel-and-wait есть |
| Background output decoding | PASS | UTF-8 + Windows CP866/CP1251 fallback |
| Dev-path scan | PASS | `/mnt/data` и временные Release 2.3 paths не попали в runtime tree |

## Исправления, найденные именно на финальном gate

1. Embedded installer мог получить `FileInfo` через `Get-Item` и затем обратиться к отсутствующему `.Source`. Добавлен `Resolve-ToolPath`, поддерживающий `Source`, `FullName`, `Path` и `Definition`.
2. Embedded desktop shortcut мог использовать иконку из временного PyInstaller `_MEIPASS`. Теперь EXE shortcut использует сам EXE как icon source, а script/launcher shortcut — стабильный `assets/astra.ico`.
3. Standalone shortcut script приведён к той же безопасной логике.
4. `TaskManager` раньше декодировал фоновые процессы только как UTF-8 с replacement. Добавлен Windows fallback `cp866` / `cp1251`, чтобы сообщения CLI не превращались в `�`.
5. Исправлен устаревший regression-test для двухфазного Search/Replace: тест теперь проверяет реальный `target_encoding`.
6. Убрана устаревшая пользовательская формулировка `MVP` там, где Release 3.0 уже описывает полноценный текущий режим.

## Матрица Run / Check для 20 языков и форматов

| Язык/формат | Check / Compile | Run |
|---|---|---|
| Python | `py_compile` | выбранный project/global Python |
| C++ | g++ / clang++ | compile → binary |
| Java | javac | compile → java |
| JavaScript | `node --check` | node |
| TypeScript | `tsc --noEmit` | tsx / ts-node |
| Luau | luau-analyze | luau CLI |
| GDScript | Godot headless project check | Godot project |
| PHP | `php -l` | php CLI |
| PowerShell | parser/scriptblock check | pwsh / Windows PowerShell |
| Shell | `bash -n` | bash |
| C# | dotnet/csc path | compile → run |
| JSON / JSONC | local parser | non-executable |
| YAML | PyYAML if available | non-executable |
| TOML | local parser | non-executable |
| XML | local parser | non-executable |
| Markdown | save-only check | non-executable |
| Dockerfile | save-only check / project command | non-executable directly |
| SQL | save-only unless DB/project command configured | non-executable directly |
| HTML | no compile required | browser |
| CSS | no compile required | non-executable directly |

## Ограничения среды текущего gate

Этот gate выполнен в Linux sandbox без полноценного Windows GUI, WinGet, MSYS2, PowerShell и PySide6 runtime. Поэтому следующие вещи **не объявляются физически проверенными на Windows**:

- реальное открытие GUI Astra Studio;
- WinGet install/upgrade;
- PowerShell execution policy / COM shortcut creation;
- C++/Java/PHP/Godot/Node installation on Windows;
- PyInstaller-produced Windows EXE launch;
- визуальная проверка тем, обоев, splitter state и диалогов;
- interactive cancellation timing against real Windows child processes.

Эти проверки остаются в итоговом пользовательском regression test после завершения 3.3, как и было запланировано.

## Решение по Release 3.0

Release 3.0 закрыт как **internal frozen baseline**. Новые функции в 3.0 больше не добавляются. Следующий этап — **Release 3.1 / B1: LSP transport**.
