# TEST REPORT — Astra Studio Release 3.3 D3

Дата: 2026-08-23  
Этап: **D3 — AI-adjacent Workflow**  
Статус: **INTERNAL GATE PASSED**

## Scope

D3 закрывает последний функциональный блок Release 3.3:

- copy relative project path;
- copy editor selection with real line numbers;
- project tree export;
- Problems export;
- Terminal / Program output export;
- local `PROJECT_CONTEXT.md` generation from explicitly selected project files.

D3 не добавляет AI API client и не выполняет сетевую отправку данных.

## Реализованные safety boundaries

- File list для `PROJECT_CONTEXT.md` стартует без выбранных source files.
- Реальные `.env` / `.env.*`, common credential files и private-key/certificate files блокируются.
- `.env.example`, `.env.sample`, `.env.template` допустимы как public templates.
- Symlink files не принимаются в context export.
- Binary/unsupported-encoding и oversized files отклоняются до записи результата.
- Generated/dependency/cache directories исключаются из project tree/content traversal.
- Absolute developer paths не встраиваются в context: используются project-relative labels; attached roots получают `@alias/...`.
- Terminal / Program output включаются только явно и после предупреждения о возможных secrets.
- Output bounded: для большого вывода сохраняется последний фрагмент с notice об omitted prefix.
- Existing `PROJECT_CONTEXT.md` требует явного overwrite confirmation.
- Regeneration блокируется, если `PROJECT_CONTEXT.md` открыт в editor, чтобы не затереть stale/unsaved content.
- Запись `PROJECT_CONTEXT.md` выполняется через temporary sibling и atomic `os.replace`.
- Сам context file не включается обратно в tree/candidate traversal.
- `PROJECT_CONTEXT.md` добавлен в canonical StaffedUp `.gitignore`; D2 Safe Fix восстанавливает отсутствующее ignore rule без изменения context content.

## D3 audit fix

Во время аудита найден и исправлен edge case generated-directory filter: абсолютный ancestor компьютера с именем `build`/`bin` мог ошибочно классифицировать обычный project file как generated. Проверка теперь применяется только к relative components внутри active project root.

Также bounded Problems export ограничивает число diagnostics и длину одного сообщения, а Markdown path labels не ломаются при backticks в имени файла.

Ещё один audit fix касается Qt/Unicode: позиции `QTextCursor` считаются в UTF-16, а Python строки индексируются Unicode code points. D3 больше не режет `toPlainText()` по Qt offsets; Copy Selection использует `selectedText()` + Qt block number, что устраняет сдвиг на emoji/non-BMP символах.

## Automated checks

Команды:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m pytest -q
```

Результат:

```text
compileall          PASS
static smoke        PASS

Tests collected     185
Passed              178
Failed                0
Skipped               7
Subtests passed      88
```

D3 добавляет `tests/test_staffedup_d3.py` с **20** pure/static tests.

Покрыто:

- main/attached relative path labels;
- refusal outside active roots;
- sensitive-file boundaries;
- UTF-8 + CP1251 reading;
- binary/oversized/symlink refusal;
- project path under an external ancestor named `build`;
- line-number selection formatting;
- safe Markdown fence selection;
- deterministic project tree and generated/sensitive exclusions;
- Problems formatting;
- bounded output tail;
- explicit selected-file-only content;
- optional tree/problems/terminal/program sections;
- sensitive file refusal even after explicit selection;
- required non-empty selected file set;
- atomic context write and explicit overwrite.
- template `.gitignore` integration and D2 Safe Fix restoration of the context ignore rule.

## Deferred runtime tests

Seven previously registered Qt/PySide6 runtime tests remain deferred because PySide6 is unavailable in the current Linux sandbox:

1. `tests/test_git_c3_qt.py::GitTaskRuntimeTests::test_task_manager_preserves_nul_delimited_unicode_git_status`
2. `tests/test_lsp_b1.py::LspProcessLifecycleTests::test_initialize_server_request_and_graceful_shutdown`
3. `tests/test_lsp_b1.py::LspProcessLifecycleTests::test_unexpected_exit_restarts_with_backoff`
4. `tests/test_lsp_b2.py::LspDocumentIntegrationTests::test_manager_syncs_documents_and_collects_diagnostics`
5. `tests/test_lsp_b2.py::LspTcpTransportTests::test_external_tcp_initialize_and_shutdown`
6. `tests/test_lsp_b3.py::LspInteractiveRuntimeTests::test_manager_routes_completion_hover_signature_navigation_rename_and_symbols`
7. `tests/test_quality_c1_qt.py::QualityTaskRuntimeTests::test_task_manager_streams_stdin_to_formatter_process`

Это не считается runtime PASS. Они остаются обязательными для финального Windows gate / owner acceptance.

## Manual registry

`TEST_REGISTRY_3_X.md` обновлён:

- automated section синхронизирован с реальными **185 collected tests**;
- D3 manual acceptance расширен до `D3-AI-01 … D3-AI-36`;
- отдельно зарегистрированы secret warnings, attached roots, explicit selection, CP1251, oversized/binary/symlink refusal, atomic overwrite, project switching и local-only boundary.

## Gate conclusion

**D3 INTERNAL GATE PASSED.**

Release 3.3 теперь feature-complete. D1–D3 не расширяются новыми функциями до завершения следующего этапа — **Final Integration Gate поколения 3.x**.

Ручное Windows-тестирование владельцем проекта по плану всё ещё не начинается на этом этапе; оно выполняется после Final Integration Gate.
