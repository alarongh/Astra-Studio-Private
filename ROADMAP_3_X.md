# Astra Studio 3.x — Roadmap

## Release policy

- `3.0` — major rebuild after the 2.x line.
- `3.1`, `3.2`, `3.3` — feature increments inside the 3.x generation.
- `4.0` — reserved for the next major idea after the whole 3.x cycle is finished and manually tested.

Manual Windows testing by the owner is intentionally postponed until all 3.x implementation stages are completed. Each stage still gets automated/static checks so regressions are caught early.

## Execution model

We do not ask the owner to manually test between feature stages. Each implementation block gets its own automated/static gate, then development continues. Manual Windows regression testing happens only after the complete 3.x integration gate.

### What can be completed as one implementation block

- bounded UI/productivity features such as Quick Open, project search, Project Doctor, individual project templates or an AI-context export command;
- isolated language/toolchain adapters when they reuse the existing TaskManager and project-command infrastructure;
- documentation, registry and installer catalog updates.

### What must be split into multiple implementation blocks

- Python Environment Manager, because interpreter resolution affects run/check/build/package operations;
- LSP, because transport, document synchronization/diagnostics and interactive editor requests have different lifecycle and failure modes;
- Test Explorer, because adapters, execution, parsing and result state must be separated;
- Git UI, because read-only status/diff should be stabilized before mutating stage/commit/pull/push actions;
- StaffedUp mode, because templates, health rules and AI-context workflows are independent subsystems.

### Gate after every block

- Python sources compile;
- targeted smoke checks for the changed subsystem pass;
- no unrelated feature is deliberately rewritten;
- changelog/roadmap state is updated;
- only then continue to the next block.

## Stage A — Release 3.0: stabilization and platform foundation

### A1. Stabilization and release reset
- [x] Carry forward confirmed 2.2 bug fixes.
- [x] Rename rebuilt branch to Release 3.0.
- [x] Reconstruct complete release directory with code, assets, scripts and data.
- [x] Keep mutable data out of the installation directory.
- [x] Keep TaskManager fixes for cancellation/race/output handling.
- [x] Add static smoke-test harness.

### A2. Language expansion
- [x] Add TypeScript.
- [x] Add Luau/Lua.
- [x] Add GDScript.
- [x] Add PHP.
- [x] Add PowerShell.
- [x] Add JSON, YAML, Markdown, TOML, XML, Shell and Dockerfile editing.
- [x] Extend project file discovery.
- [x] Add starter templates.
- [x] Add baseline syntax highlighting.
- [x] Add direct run/check support where a stable CLI exists.
- [x] Extend installer/Project Doctor detection for all new toolchains.

### A3. Python Environment Manager
This is intentionally split because it changes how every Python run/install/build resolves its interpreter.

#### A3.1 Detection
- [x] Detect project `.venv` / `venv`.
- [x] Detect `pyproject.toml`, `requirements*.txt`, `uv.lock`, `Pipfile`, `poetry.lock`.
- [x] Resolve the active Python per project instead of globally for run/check/library/build operations.
- [x] Show active interpreter/environment in the Python libraries UI.

#### A3.2 Environment actions
- [x] Create `.venv`.
- [x] Prefer `uv` when available; fall back to `python -m venv` + pip.
- [x] Install project requirements / pyproject dependencies.
- [x] Export requirements from a project environment.
- [x] Update pip; safe library install/update continues to require configured confirmation rules.
- [x] Allow manual interpreter selection and persist it in `astral.project.json`.

### A4. Project commands
- [x] Add generic Run / Build / Test / Install commands to `astral.project.json`.
- [x] Detect common commands from package/project files when explicit commands are absent.
- [x] Run every command through TaskManager with cancellation/output/progress.

### A5. IDE productivity foundation
- [x] Search in files (`Ctrl+Shift+F`).
- [x] Replace in files with result preview, unsaved-file protection and explicit confirmation.
- [x] Quick Open (`Ctrl+P`).
- [x] Project Doctor: runtimes, dependency files, environment, missing tools and detected project commands.
- [x] Persist recent projects cleanly (carried forward and reviewed from 2.x fixes).

### A6. Release 3.0 internal final gate
- [x] Python compile/static test suite passes.
- [x] 31/31 unit/static tests pass.
- [x] Registry/JSON parity verified.
- [x] All required assets and installer scripts verified.
- [x] Runtime tree scanned for temporary Release 2.3/dev paths.
- [x] All 20 language/format Run + Check branches reviewed.
- [x] Python environment isolation and project interpreter guards reviewed.
- [x] Task cancellation/shutdown lifecycle reviewed.
- [x] Settings load/save parity and project preference migration reviewed.
- [x] Embedded/standalone installer path handling and shortcut icon lifetime fixed.
- [x] Release 3.0 frozen as baseline for 3.1.

> Manual Windows regression testing is still intentionally deferred until after Release 3.3. See `TEST_REPORT_RELEASE_3_0.md`.

## Stage B — Release 3.1: editor intelligence

LSP is a multi-stage system and must not be bolted onto the editor in one patch.

### B1. LSP transport
- [x] JSON-RPC process transport.
- [x] Initialize/shutdown lifecycle.
- [x] Per-language server configuration.
- [x] Crash/restart handling.

B1 gate: protocol framing/registry/static lifecycle tests pass. Two executable QProcess lifecycle tests are present but are skipped in the current Linux sandbox because PySide6 is not installed there; they remain part of the later Windows integration test. B1 intentionally stopped before document synchronization; that layer is now implemented and gated separately in B2.

### B2. Document synchronization and diagnostics
- [x] Godot/GDScript external TCP LSP adapter (default port 6005) before GDScript document sync.
- [x] didOpen/didChange/didSave/didClose.
- [x] Diagnostics collection with stale-version protection.
- [x] Problems panel with severity/current-file filters.
- [x] Click diagnostic -> open file/line/column.
- [x] Debounced full-document synchronization and document-version tracking.
- [x] Re-sync open documents after language-server restart.
- [x] Retry cooldown for unavailable language servers to avoid per-keystroke reconnect storms.

B2 gate: static smoke and full sandbox suite pass. Document/diagnostic normalization, URI conversion and GDScript TCP registry resolution run in the sandbox. Four Qt runtime integration tests (two B1 + B2 stdio document sync + B2 TCP lifecycle) are collected but deferred because PySide6 is unavailable in the current Linux sandbox. All of them are registered in `TEST_REGISTRY_3_X.md` for the final Windows gate.

### B3. Interactive editor features
- [x] LSP server availability/status UI plus explicit safe install/update entry points for the StaffedUp toolchain.
- [x] LSP completion.
- [x] Hover.
- [x] Signature help.
- [x] Go to definition.
- [x] Find references.
- [x] Rename symbol with guarded workspace edits.
- [x] Document outline/symbols.
- [x] Ignore stale interactive responses after document changes/project switches.
- [x] Preserve UTF-16 LSP positions, CP1251 content and CRLF line endings during safe rename of closed files.

B3 gate: `compileall` and static smoke pass; full sandbox suite collects 72 tests with 67 PASS / 5 SKIPPED / 0 FAILED. The fifth deferred Qt runtime test exercises completion, hover, signature help, navigation, rename and symbols against the fake LSP server. Safe install/update plans cover the primary StaffedUp servers where a stable package-manager path exists; GDScript is explicitly shown as an external Godot server, and unsupported/ambiguous installs remain manual rather than guessed. All B3 manual cases are registered in `TEST_REGISTRY_3_X.md`.

**Release 3.1 implementation status: feature-complete and internally gated.** Windows/PySide6 runtime acceptance remains intentionally deferred until after Release 3.3.

## Stage C — Release 3.2: quality and collaboration

### C1. Formatters/linters
- [x] Formatter/linter abstraction in `core/quality_tools.py`.
- [x] Format current file (`Shift+Alt+F`) and opt-in Format on Save.
- [x] Ruff format + Ruff JSON lint for Python.
- [x] Project-local Prettier format + ESLint JSON lint for JS/TS; Prettier also covers HTML/CSS/JSON/YAML/Markdown.
- [x] clang-format for C++ with project `.clang-format` discovery and LLVM fallback.
- [x] StyLua for Luau/Lua when available.
- [x] Quality diagnostics merge into the existing Problems panel.
- [x] Explicit safe install/update prompts; no implicit `npx` downloads.
- [x] TaskManager stdin streaming for formatter/linter processes.

C1 gate: `compileall` + static smoke pass; full sandbox suite collects 85 tests with 79 PASS / 6 SKIPPED / 0 FAILED. The added deferred Qt runtime test validates TaskManager stdin streaming. Manual formatter/linter/configuration/install cases are registered in `TEST_REGISTRY_3_X.md` and remain scheduled for the final Windows gate after Release 3.3.

### C2. Test Explorer
- [x] Generic test adapter model in `core/test_explorer.py`.
- [x] Static discovery + execution/parsing for pytest and unittest.
- [x] npm/Vitest/Jest project-script support without implicit package downloads.
- [x] `dotnet test` support with console result parsing.
- [x] Test Explorer UI with adapter selection, discovery, Run All, safe Run Selected where supported, rerun and source navigation.
- [x] Persist last run in `astral.project.json` and restore pass/fail tree on reopen.
- [x] Guard external test runs when project editors contain unsaved changes.
- [x] Ignore generated dependency/build directories during discovery.

C2 gate: `compileall` + static smoke pass; full sandbox suite collects **109 tests with 103 PASS / 6 SKIPPED / 0 FAILED** plus 88 passing subtests. Real pytest and unittest command/parser integration is executed in the sandbox. The six skipped tests are the existing Qt/PySide6 runtime checks from B1–C1 and remain registered for the final Windows gate. npm/Vitest/Jest and dotnet end-to-end Windows/toolchain cases are explicitly registered in `TEST_REGISTRY_3_X.md`.

### C3. Git
- [x] Repository detection, including projects opened from a nested folder inside a parent repository.
- [x] Porcelain-v2 branch/upstream/ahead/behind/status parsing with staged/working/untracked/conflict states.
- [x] Working-tree and staged diff viewer for a selected file, including rename-aware path pairs.
- [x] Stage/unstage selected files plus explicitly confirmed Stage All / Unstage All; unstaging never discards working-tree content.
- [x] Commit staged changes with a required message, conflict guard and explicit confirmation.
- [x] Pull/push only by explicit user action; pull is `--ff-only`, dirty pull and detached/no-upstream unsafe cases are blocked, and Astra never force-pushes.
- [x] Git operations run through TaskManager rather than the GUI thread and refresh status after successful mutations.
- [x] Network Git operations disable hidden terminal credential prompting and remain cancellable through the common task UI.

C3 gate: `compileall` + static smoke pass; full sandbox suite collects **127 tests with 120 PASS / 7 SKIPPED / 0 FAILED** plus 88 passing subtests. C3 includes real local Git repositories, rename/stage/unstage/commit operations and local bare-remote pull/push integration. The seventh skipped runtime test exercises NUL-delimited Unicode Git status through Qt `QProcess`/TaskManager and remains registered for the final Windows gate.

**Release 3.2 implementation status: feature-complete and internally gated.** C1–C3 are frozen as the baseline for Release 3.3.

## Stage D — Release 3.3: StaffedUp mode

### D1. Project templates
- [x] Web / TypeScript.
- [x] Yandex Games / TypeScript (added during D1 audit because it is a StaffedUp delivery target and was missing from the original template list).
- [x] Roblox / Luau.
- [x] Godot.
- [x] Python App.
- [x] Telegram Bot.
- [x] Static Website.
- [x] Empty project.
- [x] Atomic template creation: never overwrite a non-empty target folder and never run package managers/network actions implicitly.
- [x] Persist StaffedUp template/profile metadata in `astral.project.json`.
- [x] Serialize project-local paths relative to the project config so shared repositories do not contain another developer's absolute paths.

D1 gate: `compileall` + static smoke pass; full sandbox suite collects **145 tests with 138 PASS / 7 SKIPPED / 0 FAILED** plus 88 passing subtests. Template-specific tests create every StaffedUp skeleton in temporary directories, parse JSON/TOML manifests, run the generated Python App and Telegram configuration tests, verify atomic no-overwrite behavior and check portable project-path serialization. Qt/manual creation-dialog acceptance remains registered for the final Windows gate.

### D2. StaffedUp project health
- [x] Validate team-standard project structure per D1 health profile where applicable.
- [x] `.gitignore`, `.env.example`, README/docs, required/recommended tools and dependency-state checks.
- [x] One-click fix only for deterministic safe changes; never overwrite user code/docs, infer secrets, initialize Git or run package managers/network implicitly.

D2 gate: `compileall` + static smoke pass; full sandbox suite collects **162 tests with 155 PASS / 7 SKIPPED / 0 FAILED** plus 88 passing subtests. D2 adds profile-aware health inspection for every StaffedUp template and 17 dedicated automated tests covering safe-fix idempotency/no-overwrite, CP1251/CRLF `.gitignore` repair, metadata/command repair boundaries, malformed config refusal and structure/tool/dependency diagnostics. Qt Project Doctor acceptance remains in the manual Windows registry.

### D3. AI-adjacent workflow
- [x] Copy relative path / selection with line numbers.
- [x] Export project tree.
- [x] Export errors/terminal output.
- [x] Generate `PROJECT_CONTEXT.md` from explicitly selected project content.

D3 gate: `compileall` + static smoke pass; full sandbox suite collects **185 tests with 178 PASS / 7 SKIPPED / 0 FAILED** plus 88 passing subtests. D3 adds a local-only `core/ai_context.py`, explicit unchecked file selection, sensitive-file/symlink/binary/size guards, bounded console exports and atomic `PROJECT_CONTEXT.md` write. D3 manual cases `D3-AI-01 … D3-AI-36` are registered for the final Windows acceptance.

**Release 3.3 implementation status: feature-complete and internally gated. D1–D3 are frozen for the Final Integration Gate.**

## Final integration gate before 4.0

- [x] Requirement-to-feature traceability check: every Stage A–D item is DONE; Windows/PySide6 runtime acceptance is explicitly deferred to owner testing.
- [x] `compileall`, static smoke and full sandbox regression suite pass.
- [x] Registry/JSON full-record parity passes (41/41 records + bundles).
- [x] No missing required assets/scripts (11 runtime assets, 13 installer scripts).
- [x] Runtime stale-release/temp-path scan passes; stale user-facing 3.1 installer labels found by the gate were corrected to use `APP_VERSION`.
- [x] Check/Run routing reviewed for all 20 supported languages/formats; project Run/Build/Test/Install adapters covered by regression tests.
- [x] Python global/project environment isolation reviewed; unrelated `VIRTUAL_ENV` and invalid override guards covered by tests.
- [x] Task/LSP/run/terminal/install cancellation and shutdown paths reviewed; Qt runtime execution remains in the Windows test registry.
- [x] Legacy settings migration and project preference/path migration reviewed; load/save key parity remains covered.
- [x] Release 3.3 TEST BUILD archive rebuilt from a clean tree and ZIP integrity/manifest verified.
- [x] README, changelog, roadmap, final integration report and test registry synchronized to Release 3.3.
- [x] Release 3.3 handed off as the frozen TEST BUILD for owner Windows acceptance.
- [x] POST-GATE: first Windows acceptance defect became Release 3.4 — `cmd.exe` batch wrappers repackaged as ASCII-only + CRLF and guarded by regression tests.
- [x] POST-GATE: Windows usability feedback became Release 3.5 — inline console input, inline settings, visible project pane guard, editor/console appearance controls, arbitrary PyPI management and self-contained acceptance install/test scripts.
- [x] POST-GATE: Windows runtime acceptance became Release 3.6 — native caption/topmost repair, CRLF portability fixes, portable AI-context line endings and Windows PowerShell-readable UTF-8 logging.
- [x] Release 3.6 stabilization registry expanded to 232 collected tests, including byte-level log migration, Windows native caption `SC_CLOSE`, packaging, update-feed and Angel 404 font/theme regressions.
- [x] Full Windows automated gate completed: 230 PASS / 2 SKIPPED / 0 FAILED, plus 88 passing subtests.
- [x] Production onedir EXE launched and closed through the real Windows caption X; foreign ICU packaging collision removed.
- [x] Safe HTTPS update-manifest client and publisher tooling completed; public endpoint awaits publisher hosting configuration.
- [x] Angel 404 theme/wallpaper and global bundled Minecraft Rus font selector added and verified across UI/editor/consoles.
- [x] Release 3.9: Java/JDK installer validation no longer treats successful `java -version` stderr as a fatal PowerShell `NativeCommandError`.
- [x] Release 3.11 Windows gate: 252 collected / 250 passed / 2 platform-permission skips / 0 failed, plus 88 passing subtests.
- [x] Release 3.11 completion/shortcut patch: cyclic Tab selection, Space commit, multi-language offline catalogs and three verified desktop shortcut icon variants.
- [x] Release 3.12 Windows gate: 259 collected / 257 passed / 2 platform-permission skips / 0 failed, plus 88 passing subtests.
- [x] Release 3.12 layout/update patch: native-size wallpaper, complete project tree, six-language UI focus, expanded Java completion and verified GitHub updater replacement flow.
- [x] Release 3.13 Windows gate: 267 collected / 265 passed / 2 platform-permission skips / 0 failed, plus 88 passing subtests.
- [x] Release 3.13 C++/Python patch: type-aware C++20/23 completion, automatic standard headers, real g++ gate, 67 verified Python libraries and 12 safe curated bundles.
- [ ] POST-GATE: after stable manual sign-off, begin planning Release 4.0.


- [x] Release 3.14 update recovery: updater leaves the portable working directory, relaunches the current build on failure and reports the log path.
- [x] Release 3.14 visible scope: only Java, Python and C++ remain in language selection and installer actions; other implementations stay in source.
- [x] Public release identity moved from the misleading `Astra-Studio-Private` name to `Astra-Studio-Releases`.
- [x] Release 3.14 Windows gate: 271 collected / 269 passed / 2 platform-permission skips / 0 failed, plus 88 passing subtests.
- [x] Release 3.15 complete visibility gate: language combo, new-file dialog, LSP table, installer, file filters and project templates expose only Java, Python and C++.

**Final Integration Gate status: PASSED. Release 3.3 remains the frozen functional baseline. Owner acceptance continues on Release 3.15, which includes all 3.4–3.14 repairs plus updater recovery and complete three-language visibility; Release 4.0 planning remains blocked until 3.x owner sign-off.**
