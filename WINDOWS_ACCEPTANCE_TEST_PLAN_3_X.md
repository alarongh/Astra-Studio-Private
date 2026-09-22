# Astra Studio 3.x — Windows Acceptance Test Plan

Target build: **Release 3.16 — Windows verified portable build**
Source of truth: `TEST_REGISTRY_3_X.md`

This plan defines the order of the owner's Windows regression test. It does not replace the full registry; it groups the registry into manageable sessions so a failure can be isolated without losing coverage.

## Rule for testing

Do not fix a failure while continuing the same test session unless the failure prevents all later tests. Record the failing test ID, visible error, relevant console/log text and reproduction steps. Code fixes are made afterward as 3.6/3.7/... patches, then affected sections are rerun.

## Session 0 — clean reinstall and automated Windows gate

1. Close Astra Studio.
2. Use the Release 3.16 portable/source archive on Windows and extract it into a fresh normal writable folder. Do not reuse an older `.venv`.
3. Run `reinstall_app.bat` for a fully clean environment, or `install_app.bat` if the extracted folder has no `.venv`. The installer must install both `requirements.txt` and bundled `requirements-test.txt`; no manual `pip install pytest` step is required.
4. Launch Astra once through `run_astra.bat` or its generated shortcut, verify the main window opens, then close Astra before the automated test run.
5. Run `run_acceptance_tests.bat`. It runs compileall, static smoke and `.venv\Scripts\python.exe -m pytest -q -rs` in that order.

Expected target in the Release 3.16 source tree is **276 collected tests**. The verified Windows result is **274 PASS / 2 SKIPPED / 0 FAILED** and 88 passing subtests. The gate includes native caption handling, Angel 404 bundled-font runtime, cyclic/context completion, smart indentation, function folding, inline syntax diagnostics, desktop shortcut creation, Java UTF-8 output, real C++23 compile/run, Python registry validation, updater replacement plus health-check rollback from inside the portable working directory and the Windows PowerShell stderr-version probe.

This session also verifies the Release 3.4 batch regression, Release 3.5 unified-install/acceptance wrappers and Release 3.6 native-window/CRLF/log regressions.

For the X regression, confirm both the automated native `SC_CLOSE` test and manual IDs `R36-WIN-01` through `R36-WIN-07`. A passing `window.close()` alone is not treated as proof that the Windows caption hit target works.

Covers `FINAL-13`, `R34-BAT-*`, `R35-PKG-*`, `R36-WIN-*` and the deferred Qt runtime tests.

## Session 1 — Foundation / Release 3.0

Run all manual registry IDs beginning with `A-` plus Python Environment Manager and Search/Project Tools sections.

Count: **46 manual checks**.

Focus:

- startup / close / crash recovery;
- projects and project persistence;
- editor save/save-as/encoding;
- Run/Build flows;
- Python `.venv`, uv/pip and dependency safety;
- search/replace, Quick Open and Project Doctor.

If this session fails in basic file persistence, project loading or process shutdown, stop before later feature sessions and create a patch.

## Session 2 — LSP / Release 3.1

Run registry IDs:

- `B1-*` — 8 checks;
- `B2-*` — 26 checks;
- `B3-*` — 33 checks.

Total: **67 manual checks**.

Focus:

- stdio/TCP server lifecycle;
- diagnostics and Problems panel;
- completion/hover/signature;
- definition/references/rename;
- UTF-16/emoji correctness;
- LSP install/status UI;
- Godot TCP behavior.

## Session 3 — Quality / Tests / Git / Release 3.2

Run registry IDs:

- `C1-*` — 20 checks;
- `C2-*` — 22 checks;
- `C3-*` — 40 checks.

Total: **82 manual checks**.

Focus:

- formatters/linters and Problems integration;
- Test Explorer across Python/Node/.NET workflows;
- Git status/diff/stage/commit/pull/push;
- cancellation, Unicode paths, conflict and detached-head behavior.

Use a disposable Git repository and disposable local/remote repository for destructive-looking test scenarios. Do not use an important production repository for acceptance testing.

## Session 4 — StaffedUp Mode / Release 3.3

Run registry IDs:

- `D1-*` — 26 checks;
- `D2-*` — 24 checks;
- `D3-*` — 36 checks.

Total: **86 manual checks**.

Focus:

- all project templates;
- portable `astral.project.json`;
- Project Health and Safe Fix boundaries;
- no implicit package/network actions;
- AI Context selection and secret boundaries;
- `PROJECT_CONTEXT.md` safety and portability.

Use dummy secrets only. Do not place real credentials in files used for D3 tests.

## Session 5 — final regression sign-off

After Sessions 0–4 are green:

- `FINAL-14` — full workflow from an empty/clean machine state;
- `FINAL-15` — confirm no regression from the 3.0 baseline;
- `FINAL-16` — owner acceptance complete.

At this point:

- if no defects remain, the current Release 3.16 acceptance candidate receives owner sign-off while Release 3.3 remains the frozen feature baseline;
- if defects exist, create the next 3.x acceptance patch and rerun every directly affected section plus Session 5;
- Release 4.0 planning begins only after stable 3.x sign-off.

## What to send back for a failed test

For each failure, provide:

```text
Test ID:
Expected:
Actual:
Steps to reproduce:
Screenshot (if UI-related):
Astra output / terminal text:
Relevant astra_studio.log tail:
```

This is enough to patch the defect without rerunning unrelated test groups.
