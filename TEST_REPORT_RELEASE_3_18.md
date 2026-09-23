# Astra Studio Release 3.18 — Test Report

Дата: 2026-09-23

- Полный Windows gate: `287 collected`, `285 passed`, `2 skipped`, `0 failed`, `88 subtests passed`.
- Два пропуска остаются платформенными: POSIX executable-bit и создание symlink, недоступное текущей учётной записи Windows.
- Реальные Python, Node.js, JDK и `g++` прогоны подтвердили: неверный код даёт ошибку исходника с точным номером строки; запрос установщика не открывается.
- Parser unit gate покрывает Python compile, Node.js syntax/runtime и Java stack frames; прежние javac/GCC/Clang проверки сохранены.
- Qt runtime gate подтверждает, что HTML и CSS не зависят от language installer и не могут открыть его из-за текста файла.
- Production EXE проверен по заголовку `Astra Studio — Release 3.18` и штатному завершению с кодом 0.
