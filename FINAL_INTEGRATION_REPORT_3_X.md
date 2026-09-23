# Astra Studio 3.x — Final Integration Report

Date: 2026-08-23  
Release under gate: **Astra Studio Release 3.3**  
Gate status: **PASSED — frozen for Windows owner acceptance**

## Scope

The Final Integration Gate does not add new features. It verifies that the completed 3.x implementation (3.0 foundation, 3.1 LSP, 3.2 quality/tests/Git, 3.3 StaffedUp Mode) is internally consistent, documented, regression-tested and cleanly packaged before the owner performs the Windows acceptance test.

## Traceability result

All Stage A–D roadmap items are closed before the Final Integration Gate. The gate reviewed the implemented feature families against source modules and regression suites:

| Release / stage | Main implementation areas | Main regression suites | Status |
| --- | --- | --- | --- |
| 3.0 Foundation | `main.py`, `core/task_manager.py`, `core/python_environment.py`, `core/project_commands.py`, `core/project_doctor.py`, Python library registry/installers | `tests/smoke_static.py`, `tests/test_release_3_2.py` | PASS |
| 3.1 B1–B3 | `core/lsp_protocol.py`, `lsp_servers.py`, `lsp_transport.py`, `lsp_tcp_transport.py`, `lsp_documents.py`, `lsp_features.py` | `test_lsp_b1.py`, `test_lsp_b2.py`, `test_lsp_b3.py` | PASS / Qt runtime deferred |
| 3.2 C1 | `core/quality_tools.py`, TaskManager stdin integration | `test_quality_c1.py`, `test_quality_c1_qt.py` | PASS / Qt runtime deferred |
| 3.2 C2 | `core/test_explorer.py` | `test_test_explorer_c2.py` | PASS |
| 3.2 C3 | `core/git_tools.py` | `test_git_c3.py`, `test_git_c3_qt.py` | PASS / Qt runtime deferred |
| 3.3 D1 | `core/project_templates.py`, `core/project_paths.py` | `test_staffedup_d1.py` | PASS |
| 3.3 D2 | `core/staffedup_health.py` | `test_staffedup_d2.py` | PASS |
| 3.3 D3 | `core/ai_context.py` | `test_staffedup_d3.py` | PASS |
| Final Gate | cross-release contracts, docs, packaging, migration, safety | `test_final_integration_3x.py` | PASS |

## Final automated gate

Commands executed from the clean Release 3.3 tree:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m pytest -q -rs
```

Final result:

```text
compileall               PASS
static smoke             PASS
pytest collected         201
pytest passed            194
pytest failed            0
pytest skipped           7
pytest subtests passed   88
```

The seven skipped tests are not treated as passed. They require PySide6/Qt runtime integration in the Windows acceptance environment:

1. Git status through Qt `QProcess` with NUL-delimited Unicode paths.
2. LSP stdio initialize/shutdown.
3. LSP stdio crash/restart.
4. LSP document sync + diagnostics.
5. LSP TCP initialize/shutdown (Godot-style transport).
6. LSP interactive completion/hover/navigation/rename/symbol routing.
7. TaskManager stdin streaming into formatter processes.

All seven remain registered in `TEST_REGISTRY_3_X.md`.

## Cross-release checks

### Registry / data parity

- Python library records: **41 / 41** exact shared-field parity between runtime registry and `data/python_libraries.json`.
- Library bundles: identical.
- Required import→pip mappings: verified.

### Language / toolchain matrix

Astra exposes **20 languages/formats**, and both `compile_code()` and `run_code()` contain explicit routes for all 20:

| Language / format | Check / build route | Run route |
| --- | --- | --- |
| Python | project interpreter + `py_compile` | project interpreter `-u` |
| C++ | g++/clang++ | compile then binary |
| Java | javac | java |
| HTML | save / no compile | default browser |
| CSS | save / no compile | informational (not standalone) |
| JavaScript | `node --check` | node |
| TypeScript | `tsc --noEmit` | `tsx` / `ts-node` |
| Luau | `luau-analyze` | Luau CLI / project workflow |
| GDScript | Godot headless project check | Godot project |
| PHP | `php -l` | PHP CLI |
| PowerShell | ScriptBlock parse | pwsh / Windows PowerShell |
| C# | `dotnet build` | `dotnet run --no-build` |
| SQL | save / DB-specific execution | informational / project command |
| JSON | JSON/JSONC parse | non-executable |
| YAML | PyYAML parse | non-executable |
| Markdown | save / no compile | non-executable |
| TOML | `tomllib` parse | non-executable |
| XML | ElementTree parse | non-executable |
| Shell | `bash -n` (`.env` excluded) | bash (`.env` excluded) |
| Dockerfile | save / project workflow | non-standalone / project command |

Project-level Run/Build/Test/Install adapter regression also covers Node/npm/pnpm/Yarn/Bun, Python/pytest, Godot, .NET, Maven/Gradle, CMake and Rojo scenarios.

### Required files

- Required runtime assets: **11 / 11**.
- Installer scripts: **13 / 13**.
- LSP language configurations: **20 / 20**.
- `requirements.txt` includes PySide6, PyInstaller and PyYAML.

### Python environment isolation

Reviewed and regression-tested:

- project `.venv` / `venv` takes precedence over global Python;
- unrelated external `VIRTUAL_ENV` is not adopted as the current project's environment;
- invalid saved interpreter override stops dependency mutation rather than falling back silently;
- update-pip and requirements export refuse accidental global-environment mutation/export;
- `uv` is preferred when available, with pip/venv fallback.

### Cancellation / shutdown

Reviewed:

- TaskManager reserves a task until terminal signal processing;
- synchronous `cancel_and_wait()` terminates then kills on timeout;
- LSP servers are shut down before process teardown and have bounded crash restart;
- run process, terminal and legacy installer process are stopped during application close;
- unsaved editor state is confirmed before exit.

Actual Qt process lifecycle execution remains part of the Windows acceptance because PySide6 is unavailable in the sandbox.

### Settings and migration

Reviewed:

- legacy `~/.astra_studio/settings.json` migration into current app data;
- global settings loader/saver parity;
- old project `defaultLanguage` and editor settings (`tabSize`, `indentSize`, `insertSpaces`, UI/editor/console font sizes) restore safely;
- project-local paths are serialized portably relative to `astral.project.json`;
- external attached folders remain explicitly absolute.

### Stale/dead path scan

Runtime source contains no temporary `/mnt/data` paths, old `Astra_Studio_Release_2_3` branch path, pre-audit folder name or Release 2.3 runtime identity. The gate found two user-facing installer strings still saying Release 3.1; both were corrected to use current `APP_VERSION`.

### Safety regression scan

- batch launch/build scripts do not use parse-time `%errorlevel%` logic;
- Git runtime does not use `shell=True`, force push, `reset --hard` or `clean -f`;
- Pull remains `--ff-only`;
- D3 AI Context remains local-only and explicitly selected;
- secret/private-key patterns remain blocked from source context export.

## Documentation consistency

The gate synchronized:

- `README.md`;
- `ROADMAP_3_X.md`;
- `CHANGELOG_RELEASE_3_3.md`;
- `TEST_REGISTRY_3_X.md`;
- this report;
- `WINDOWS_ACCEPTANCE_TEST_PLAN_3_X.md`.

At the frozen Release 3.3 gate the registry matched **201 automated tests**. Post-gate Releases 3.5–3.11 add acceptance regression coverage; the current tree/registry now match **252 automated tests**. The complete Windows automated gate is rerun for every portable candidate; owner-only manual checks remain separately tracked.

## Remaining work before 4.0

No feature-development task remains in Release 3.3. Remaining work is execution, not implementation:

1. run the seven deferred Qt/PySide6 integration tests on Windows;
2. execute the owner manual Windows registry in controlled batches;
3. record defects;
4. fix defects as Release 3.4 / 3.5 / ... if needed;
5. obtain stable owner sign-off;
6. only then plan Release 4.0.

**Conclusion: Release 3.3 passes the internal Final Integration Gate and is frozen as the Windows TEST BUILD.**


## Post-gate Windows acceptance note — Release 3.4

The first Session 0 launch of the frozen Release 3.3 TEST BUILD exposed a Windows `cmd.exe` packaging regression before application startup. Root-cause evidence was visible in the shell errors: fragments such as `level` and `hell` were executed separately, matching split portions of `errorlevel` and `powershell`. Inspection of the delivered archive confirmed that the root `.bat` wrappers were UTF-8 text with Unix LF-only line endings and non-ASCII Russian messages.

Release 3.4 does not change feature scope. It repackages all root batch wrappers as ASCII-only text with Windows CRLF endings, normalizes Windows-native `.ps1`/`.vbs` line endings, and adds an automated guard that fails if a root `.bat` has LF-only endings, a UTF-8 BOM, or non-ASCII bytes. Owner Windows acceptance must restart from Session 0 using Release 3.4.


## Post-gate Windows acceptance note — Release 3.5

After Release 3.4 started successfully on the owner Windows machine, first real UI use exposed acceptance/UX gaps rather than a new feature-scope request: the project pane could restore effectively hidden, settings were still external, stdin/terminal input used separate line edits, editor/console transparency had opaque alpha floors, and the Python package UI was still too dependent on the curated registry. The acceptance workflow also required a manual pytest install.

Release 3.5 addresses those acceptance findings while preserving the 3.3 feature baseline: settings are hosted in the main tools drawer, program/terminal consoles accept protected inline input, splitter restoration keeps the project pane visible, editor/console transparency has a useful range with an editor blur control, and arbitrary validated PyPI requirements are supported. Unknown import-name fallback remains confirmation/opt-in based so arbitrary imports are not silently trusted by default.

The Windows acceptance package is now self-contained: `requirements-test.txt`, `reinstall_app.bat`, and `run_acceptance_tests.bat` are delivered in the same archive and `install_app.bat` installs the test requirement set automatically. Owner acceptance restarts on the Release 3.5 TEST BUILD. The post-gate source tree now collects **210 pytest tests**; the registry is regenerated from the actual collection and remains the source of truth for automated/manual acceptance coverage.


## Post-gate Windows acceptance note — Release 3.6

The first full Windows automated run of Release 3.5 produced **206 PASS / 2 FAILED / 2 SKIPPED**. Both failures were portability findings rather than feature logic failures: QProcess formatter output used Windows CRLF while the test expected LF, and AI-context source decoding preserved CRLF while the portable Markdown context expected LF. The two skips were platform/permission-specific (`POSIX executable bit` and unavailable symlink creation).

The same user session exposed a native-window defect: startup attempted `SetWindowPos(HWND_NOTOPMOST)` while the window handle was not valid, logged Windows error **1400**, then reapplied full Qt window flags as a fallback. Release 3.6 removes the raw Win32 topmost path, toggles only Qt `WindowStaysOnTopHint`, avoids any startup flag transition when topmost is disabled, and adds a Qt runtime regression that verifies caption flags survive topmost on/off and the window can close.

Source inspection confirms that Astra has no custom/frameless title bar: the visible X is the native Windows caption control and routes to the existing `closeEvent`. Therefore the broken visual X was a native-window lifetime problem, not missing QPushButton wiring. Regression coverage now also sends Windows `SC_CLOSE` to the current HWND after a topmost on/off transition and verifies that `closeEvent` is reached.

Release 3.6 also normalizes exported AI-context text to LF and writes/migrates the diagnostic log as UTF-8 with BOM for readable Windows PowerShell 5.x output. The final stabilization pass additionally fixed a Qt TCP-LSP shutdown race found when all available integration tests were enabled. The remaining owner acceptance work is the explicit manual matrix, not the automated Windows gate.

## Final Windows closure — 2026-08-31

The Release 3.12 Windows gate collects **259 tests** and finishes with **257 PASS / 2 SKIPPED / 0 FAILED**, plus **88 passing subtests**. The two skips are explicitly platform/permission scoped: the POSIX executable-bit case and symlink creation unavailable to the current Windows account. Both Qt caption tests execute, including the native HWND/`SC_CLOSE` regression. Release 3.12 also executes a real isolated portable-folder replacement through the external updater.

The Release 3.13 Windows gate collects **267 tests** and finishes with **265 PASS / 2 SKIPPED / 0 FAILED**, plus **88 passing subtests**. It adds real C++23 compile/run coverage, type-aware standard-library completion checks, deterministic Python registry validation and verified Python/JSON parity. All 67 curated distribution names were separately resolved through the official PyPI JSON API.

Release 3.14 adds an updater regression that starts PowerShell from inside the portable `Astra Studio` directory, verifies that the updater leaves the native working directory before replacement, and requires visible recovery on failure. It also limits the visible language and installer scope to Java, Python and C++ without deleting deferred implementations, and moves the public update identity to `Astra-Studio-Releases`.

The Release 3.14 Windows gate collects **271 tests** and finishes with **269 PASS / 2 SKIPPED / 0 FAILED**, plus **88 passing subtests**.

Release 3.15 extends the visibility gate beyond the main language selector: LSP rows, new-file filters and project-template choices are now limited to Java, Python and C++, while existing hidden-language files remain openable and their implementations stay in source.

Release 3.17 retains the six focused languages and transactional updater from 3.16, simplifies appearance customization into a profile plus shared panel/wallpaper controls, and moves shortcut management from the language installer into Settings. C++ compiler output now becomes exact Problems/line diagnostics; a source error can no longer be misreported as a missing compiler. Synthetic input and duplicate blocking compile paths were removed, while deferred language engines remain preserved for later work.

Release 3.18 applies the same classification boundary to the other focused languages: once Python, Node.js, JDK or the C++ compiler has started, a non-zero result is treated as a source-code failure rather than a missing installation. Python/Java/JavaScript runtime locations and Python/Java/C++/JavaScript compile locations are normalized into Problems. HTML and CSS remain toolchain-independent for basic checking and cannot trigger a language-installer prompt.

## Release 3.9 installer correction

Owner runtime output confirmed that Temurin JDK 21 and `javac` were already healthy, but Windows PowerShell converted the normal stderr output of `java -version` into a terminating `NativeCommandError` because the installer uses `$ErrorActionPreference = "Stop"`. Release 3.9 runs version probes through `System.Diagnostics.Process` with separately redirected stdout/stderr and decides success from the child exit code. The complete Java installer has been rerun against Temurin 21.0.11 and exits successfully.

The final portable refresh adds the Angel 404 wallpaper/theme profile and registers the bundled Minecraft Rus TTF as a Qt application font. Runtime verification confirms the selected family reaches ordinary controls, tabs, code-editor document/viewport and consoles rather than only one settings widget.

Packaging validation also exposed and fixed a separate deployment defect: foreign Poppler ICU DLLs visible in the build environment were collected beside Qt and caused `QtCore: WinError 127` at startup. The production `astra_studio.spec` filters those unrelated DLLs, and the resulting onedir executable was launched and closed using the real Windows caption X.

Release 3.6 additionally includes an opt-in HTTPS application-update manifest with strict version, size, URL and SHA-256 validation. The public feed cannot be activated until the publisher supplies an actual HTTPS hosting endpoint; the shipped default therefore remains safely disabled.
