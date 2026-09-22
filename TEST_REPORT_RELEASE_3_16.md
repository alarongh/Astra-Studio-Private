# Astra Studio Release 3.16 — Test Report

Дата: 2026-09-22

- Полный Windows gate: `276 collected`, `274 passed`, `2 skipped`, `0 failed`, `88 subtests passed`.
- Два пропуска остаются платформенными: POSIX executable-bit и создание symlink, недоступное текущей учётной записи Windows.
- Updater integration подтверждает замену папки с внешним native working directory и отдельный rollback при раннем завершении новой версии.
- Контекстные completion-тесты покрывают Python, JavaScript, HTML и CSS; предыдущие Java/C++ проверки сохранены.
- Qt editor gate покрывает автоотступ, сворачивание функции и живую строку Python syntax error.
- Визуальный smoke выполнен при размере `980×700`: проектная панель адаптивно скрыта, навигация остаётся непрозрачной, обои видны только под кодом и консолью.
- Production EXE дополнительно проверяется на заголовок `Astra Studio — Release 3.16`, публичный feed и штатное закрытие.
