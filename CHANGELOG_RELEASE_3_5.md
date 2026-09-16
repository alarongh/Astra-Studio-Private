# CHANGELOG — Astra Studio Release 3.5

Release 3.5 is a post-gate Windows acceptance/UX patch built on the frozen 3.3 feature baseline and the 3.4 launcher repair.

## Changed

- Returned Settings to an inline page inside the Astra tools drawer instead of an external dialog.
- Replaced separate stdin/terminal input line edits with protected inline input inside the program-output and terminal consoles.
- Prevented the project/file pane from restoring at effectively zero width.
- Expanded editor/console transparency to a genuinely visible range and added editor-background blur control; blur remains part of Astra's shared backdrop/wallpaper effect rather than a per-widget native Windows blur surface.
- Added arbitrary validated PyPI requirement install/update UI.
- Known import mappings still use the curated safe registry; unknown imports can use same-name PyPI fallback after confirmation or via explicit opt-in.
- Missing Python imports can be installed in one batch where safe/approved rather than forcing a repeated one-package loop.

## Acceptance packaging

- Added `requirements-test.txt` with pytest.
- `install_app.bat` installs bundled acceptance-test dependencies automatically.
- Added `reinstall_app.bat` for a complete clean `.venv` rebuild from the same archive.
- Added `run_acceptance_tests.bat` for one-click Windows pytest execution.
- Preserved Release 3.4 ASCII + CRLF batch-file guarantees for every root `.bat`.

## Safety

- Arbitrary package input accepts PyPI-style requirement strings, not URLs, local paths or direct-reference syntax.
- Unknown import auto-install is disabled by default.
- A package that installs successfully but does not satisfy the requested import no longer triggers an automatic rerun loop.

## Acceptance

Owner Windows acceptance should restart from Session 0 using the Release 3.5 TEST BUILD and the bundled `reinstall_app.bat` / `run_acceptance_tests.bat` flow.
