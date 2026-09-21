# Astra Studio Release 3.12 — Test Report

Status: **WINDOWS AUTOMATED GATE PASSED / PORTABLE BUILD VERIFIED**

Date: **2026-09-22**
Platform: **Windows, PySide6 6.11.2, PyInstaller 6.22.2, Python 3.12.14**

## Исправленные блокирующие дефекты

- Qt-only переключение Always on Top без raw `SetWindowPos` и без полного сброса `windowFlags`.
- Сохранение системных minimize/maximize/close caption flags и прохождение native `SC_CLOSE` через существующий `closeEvent`.
- Переносимость LF/CRLF в formatter runtime и LF-нормализация `PROJECT_CONTEXT.md` без изменения исходников.
- UTF-8 BOM миграция диагностического лога, включая прежние BOM-less UTF-8 и CP1251 файлы.
- Исправление Qt TCP-LSP shutdown race.
- Один `QApplication` на pytest-сессию: полный Windows suite больше не падает при смешении Qt Core/Widgets тестов.
- Acceptance batch теперь считает отрицательный Windows exit code аварией, а не ложным успехом.
- PyInstaller onedir-сборка исключает чужие ICU DLL из окружения сборки; устранён startup crash `QtCore: WinError 127`.
- Подключён безопасный GitHub stable-канал: загрузка, проверка размера/SHA-256/ZIP layout, внешний installer с backup/rollback и перезапуском.
- Обои отвязаны от масштаба окна, глубина дерева исправлена, а строки/номера адаптированы к глобальному шрифту.

## Итоговый Windows gate

Команда `run_acceptance_tests.bat` выполнена целиком из проектного `.venv`:

```text
compileall          PASS
static smoke        PASS
pytest collected    259
passed              257
failed                0
skipped               2
subtests passed      88
```

Причины двух пропусков выведены pytest и не засчитаны как PASS:

- `tests/test_lsp_b1.py:115` — executable-bit test is POSIX-specific;
- `tests/test_staffedup_d3.py:121` — symlink creation unavailable для текущей Windows-учётной записи.

Оба Release 3.6 window runtime теста выполнены, включая Windows HWND/`SC_CLOSE`; отложенных из-за отсутствия Qt тестов больше нет.

## Angel 404 и глобальный шрифт

- Встроены исходные обои Angel 404 размером 1672×941 и пользовательский TTF `Minecraft Rus`.
- Добавлена отдельная палитра, неоновый акцент и кнопка единого профиля Angel 404.
- Шрифт зарегистрирован через Qt application-font API и проверен у `QApplication`, кнопок, combo box, вкладок, редактора, default font документа и обеих консолей.
- Выбор шрифта сохраняется в настройках; системный шрифт можно вернуть без удаления TTF.
- Полное окно отрисовано в изолированном профиле с темой, обоями и Minecraft-шрифтом.
- Отдельный Angel 404 icon сохранён как PNG и Windows ICO; вместе с классическим и Legacy icon он доступен в выборе оформления ярлыка.

## Completion и ярлык

- Проверен цикл popup: первый Tab выбирает строку 0 без вставки, следующие Tab переходят вперёд с возвратом к строке 0, Space фиксирует выбранный текст с пробелом.
- Offline-каталоги проверены для 14 дополнительных языков; Java отдельно проверена на новые классы, `System.out` и `StringBuilder` members.
- Standalone shortcut script создал настоящий `.lnk` через Windows COM в изолированной папке и применил выбранный Angel 404 ICO.
- Встроенный ярлык ищет Desktop через Windows SpecialFolder, registry, OneDrive и русские/английские имена папок.

## Release 3.12 UI и updater

- Обои сохраняют исходный размер изображения и центрируются; resize окна меняет только видимую область.
- Дерево проекта отображает до 32 уровней и 5000 элементов, не сокращает подписи через elide и пересчитывает ширину колонки.
- В интерфейсе видимы Java, Python, C++, JavaScript, HTML и CSS; остальные языки остаются зарегистрированными в коде.
- В изолированной Windows-папке внешний updater реально дождался завершения процесса, заменил portable payload, запустил новый EXE и очистил backup после успеха.
- ZIP validator проверен на корректном архиве и traversal-записи; неподписанный или структурно опасный payload отклоняется до закрытия приложения.

## Проверка настоящей сборки

- Собран windowed onedir executable `dist\Astra Studio\Astra Studio.exe`.
- В финальном payload отсутствуют конфликтующие `icuuc.dll` и `icudt78.dll`.
- EXE запущен независимо от Python launcher; ожидаемое главное окно — `Astra Studio — Release 3.12`.
- Системная кнопка X найдена как native caption control, нажата мышью и закрыла процесс.
- Spec, update config и runtime assets входят в source release; portable archive сохраняет всю onedir-папку, потому переносить один EXE отдельно нельзя.

## Канал обновлений

Клиент подключён к публичному `update/latest.json` в GitHub-репозитории. Manifest генерируется `scripts/make_update_feed.py` и содержит версию, HTTPS download URL, размер и SHA-256 portable ZIP. Кнопка устанавливает только проверенный архив; локальный source-mode ограничивается загрузкой и открытием папки.

## Область результата

Автоматический Windows gate и smoke-проверка реального portable EXE пройдены. Полная многостраничная ручная owner-матрица из `TEST_REGISTRY_3_X.md` остаётся отдельной процедурой приёмки; непроверенные вручную пункты не отмечены как выполненные.

## Release 3.9 StaffedUp installer regression

- Подтверждено, что JDK Temurin 21.0.11 и `javac` были исправны, а код 1 создавался только обработкой stderr в PowerShell.
- `Invoke-NativeVersionProbe` запускает native version command через `System.Diagnostics.Process`, раздельно читает оба потока и принимает решение по `ExitCode`.
- Реальный `java -version` успешно проверен в Windows PowerShell с `$ErrorActionPreference = "Stop"`.
- Полный `scripts/install_java.ps1` повторно выполнен на Windows и завершился кодом 0.

## Полный Java audit 2026-09-15

- Регистрация `Java`, `.java`, LSP language id `java`, syntax highlighting, snippets и compile/run routes сохранены и проверены.
- Найден конфликт PATH: `javac` указывал на Temurin 21.0.11, а bare `java` — на Oracle Java 8. Новый resolver выбрал парные `javac.exe`/`java.exe` из одного Temurin JDK и не зависит от номера версии или одного жёстко заданного каталога.
- Реальная программа с marker `ASTRA_JAVA_OK · Привет, мир!` скомпилирована и запущена парным runtime; её stdout побайтно декодирован как UTF-8 без искажения кириллицы. Отдельный некорректный исходник завершил `javac` ненулевым кодом и был разобран в diagnostic без вызова installer UX.
- Встроенный completion registry проверен на keywords (`pub`, `cla`), main snippet, локальном символе (`cou`), `String` member completion (`text.`), standard class (`ArrayL`) и автоматическом import.
- Проверено подавление suggestions внутри строк, line comments и block comments.
- `jdtls` на тестовой машине отсутствует; это не блокирует встроенный offline completion. Глубокий project-wide semantic analysis, overload resolution и сторонние библиотеки по-прежнему требуют настроенный Java language server.
- Найден источник искажения кириллицы: Temurin на Windows сообщал `stdout.encoding=Cp1251` и `stderr.encoding=Cp1251`, а прежний fallback Astra раньше выбирал CP866. Теперь `javac` и запускаемая JVM получают явные UTF-8 параметры, а фоновые процессы используют известную кодировку.
- Итог полного Windows gate: `250 passed, 2 skipped, 0 failed`, плюс `88 subtests passed`.
