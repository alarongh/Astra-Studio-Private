# Astra Studio — Release 3.6

## Windows runtime acceptance hotfix

Release 3.6 is a post-gate acceptance patch. It does not expand the 3.x feature scope.

### Fixed

- Removed raw Win32 `SetWindowPos` topmost handling that produced Windows error 1400 during startup.
- Replaced full `setWindowFlags` fallback with a focused `WindowStaysOnTopHint` transition that preserves native caption/system-menu flags.
- Startup no longer mutates topmost flags when Always on Top is disabled.
- Made the TaskManager stdin formatter runtime test portable across LF/CRLF child-process output.
- Normalized decoded source line endings to LF when building `PROJECT_CONTEXT.md`; source files are not modified.
- Added UTF-8 BOM migration/creation for `astra_studio.log` so Windows PowerShell 5.x reads Russian diagnostics correctly.
- Migrates both BOM-less UTF-8 and legacy CP1251 Astra logs before appending new Unicode diagnostics.
- Fixed a Qt TCP-LSP shutdown race where `processEvents()` could clear the socket before the blocking shutdown loop used it.

### Regression coverage

- Added byte-level log migration/append regressions for Russian UTF-8 and CP1251 text.
- Added static proof that the main window uses the native caption and `closeEvent`, with no custom title-bar hit target or close-button wiring.
- Added a Qt runtime test that toggles topmost on/off, verifies native caption flags are preserved and reaches `closeEvent`.
- Added a Windows-only native regression that sends the caption's `SC_CLOSE` command to the active HWND after topmost on/off.
- Added explicit Windows CRLF → LF AI-context coverage.
- Added manual acceptance IDs `R36-WIN-01 … R36-WIN-10`.

### Final Windows closure

- Fixed the acceptance runner so negative native-crash exit codes cannot be reported as success.
- Added a session-scoped Windows `QApplication` bootstrap for the complete mixed Qt test suite.
- Added a production onedir PyInstaller spec that filters foreign ICU DLLs responsible for `QtCore: WinError 127`.
- Added a safe, publisher-configurable HTTPS application-update feed with size and SHA-256 verification.
- Added a deterministic update-manifest generator and portable/source distribution instructions.
- Completed the full Windows gate: **228 collected / 226 passed / 2 skipped / 0 failed**, plus 88 passing subtests.
- Launched the built executable and verified that the real native caption X closes the application.

### Angel 404 appearance pack

- Added the supplied 1672×941 Angel 404 wallpaper as a bundled preset.
- Added a dedicated black/violet syntax and interface palette plus neon accent.
- Bundled and registered the supplied `Minecraft Rus` TTF.
- Added a global font selector; the chosen family reaches the full UI, editor, consoles, menus and Qt dialogs and persists in settings.
- Added a one-click Angel 404 profile that applies theme, accent, wallpaper, visibility settings and Minecraft font together.
- Added four automated asset/wiring/runtime regressions; current Windows result is **230 passed / 2 skipped / 0 failed**.
