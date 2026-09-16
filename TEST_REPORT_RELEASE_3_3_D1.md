# TEST REPORT — Astra Studio Release 3.3 D1

Дата: 2026-08-23

Scope: StaffedUp Project Templates and portable Astra project configuration.

## Result

**D1 INTERNAL GATE: PASS**

Release 3.3 is not complete yet. D2 and D3 remain pending, and owner Windows acceptance is intentionally deferred until the complete 3.x integration gate.

## Automated gate

Commands executed from the Release 3.3 tree:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m pytest -q
```

Final result:

```text
static smoke        PASS
pytest collected     145
passed               138
failed                 0
skipped                7
subtests passed        88
```

The seven skipped tests are existing PySide6/Qt runtime integration tests from B1–C3. PySide6 is unavailable in the current Linux sandbox; those test names remain explicitly registered for the final Windows gate.

## D1 targeted coverage

`tests/test_staffedup_d1.py` contains 18 direct D1 tests and passes completely.

Validated automatically:

- all eight project templates are present and uniquely identified;
- rendered template paths are relative, unique and cannot contain `..` escape;
- all render tokens are resolved;
- unknown template ids fail safely;
- non-empty target folder is never overwritten;
- empty target folder can be used and staging is removed;
- every generated project contains valid `astral.project.json` + StaffedUp metadata;
- Web/TypeScript `package.json` and expected scripts are valid JSON;
- Yandex template isolates platform-specific code and supports local fallback;
- Roblox `default.project.json` has client/server/shared Rojo mappings;
- Godot project references a real main scene and GDScript;
- Python App `pyproject.toml` parses with stdlib `tomllib`;
- generated Python App really executes with the current Python interpreter;
- generated Python App unittest suite really passes;
- Telegram config unittest suite really passes without aiogram/network execution;
- Static/Empty templates do not invent package dependencies;
- generated Python files are syntactically valid;
- Russian project names render to portable slugs;
- project-local paths serialize relative to `astral.project.json`;
- external attached folders remain absolute;
- main.py integrates template dialog, StaffedUp metadata and portable paths.

## Safety properties reviewed

- Template creation performs no package-manager or network subprocesses.
- Non-empty directories are rejected before staging replacement.
- Project skeleton is assembled in a sibling temporary directory and moved only after successful render.
- `.env` is ignored in generated templates; only `.env.example` is tracked.
- Yandex template does not embed private credentials or an unverified SDK URL.
- Roblox/Godot generated output folders/binary artifacts are ignored where applicable.
- `astral.project.json` no longer requires the original developer's absolute project path for normal project-local content.

## Manual / Windows checks still required

All manual test names are recorded in `TEST_REGISTRY_3_X.md`. D1-specific owner checks are `D1-TPL-01` through `D1-TPL-26`.

Important deferred D1 checks include:

- actual Qt template-dialog interaction on Windows;
- Windows folder permission/UAC edge cases;
- project copy/clone to another Windows path;
- real Node/npm Vite install/run/build/test;
- real Rojo serve/build;
- real Godot Run;
- Telegram dependency install and bot startup only with a user-provided test token;
- Project tree visibility for special config filenames under real Qt.

No manual owner test is requested at this stage by design.

## Gate decision

D1 is safe to freeze as the implementation baseline for D2. No unresolved automated failure remains in D1.
