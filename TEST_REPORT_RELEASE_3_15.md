# Astra Studio Release 3.15 — Test Report

- Полная коллекция: **271 тест**.
- Проверенный итог: **269 PASS / 2 SKIPPED / 0 FAILED**, плюс **88 passing subtests**.
- Windows updater integration запускается из заменяемой portable-папки и подтверждает успешную замену после смены native current directory.
- UI smoke: language combo содержит `Java, Python, C++`; LSP table содержит только `C++, Java, Python`.
- Node.js, PHP, Godot, PowerShell и другие отложенные языковые кнопки скрыты; их реализации не удалены.
- Portable EXE проверяется на заголовок `Astra Studio — Release 3.15`, штатное закрытие и встроенный публичный feed.

Два пропуска относятся к POSIX executable-bit и недоступному созданию symlink на текущей Windows-конфигурации. Предупреждение pytest касается только `.pytest_cache` в OneDrive-пути.
