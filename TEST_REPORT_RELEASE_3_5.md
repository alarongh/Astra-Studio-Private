# TEST REPORT — Astra Studio Release 3.5

Status: **SANDBOX GATE PASSED / WINDOWS ACCEPTANCE REQUIRED**

Release 3.5 is a post-gate Windows acceptance patch based on the frozen Release 3.3 feature baseline and Release 3.4 launcher repair. It addresses the first real UI/usability findings from Windows and makes the test installation self-contained.

## Scope verified

- inline Settings page in the main tools drawer;
- integrated program stdin and terminal input inside protected console widgets;
- project/file splitter guard against a hidden zero-width project pane;
- effective editor/program-console/terminal transparency range and editor blur control;
- arbitrary validated PyPI requirement install/update;
- optional same-name fallback for unknown imports, disabled by default;
- batch installation of multiple approved missing imports;
- self-contained acceptance dependencies via `requirements-test.txt`;
- clean reinstall and one-click acceptance batch wrappers;
- preservation of Release 3.4 ASCII + Windows CRLF batch guarantees.

## Automated gate

Commands executed from the clean source tree:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m pytest -q -rs
```

Result:

```text
Static smoke: PASS
Languages/formats: 20
Python registry entries: 41
Required assets: 11
Installer scripts: 13
LSP configs: 20

pytest collected: 210
passed: 203
failed: 0
skipped: 7
subtests passed: 88
```

The seven skipped tests are existing Qt/PySide6 runtime integrations that cannot run in the Linux sandbox:

- Git status through TaskManager/QProcess;
- LSP stdio initialize/shutdown;
- LSP crash/restart;
- LSP document sync + diagnostics;
- Godot/external TCP LSP transport;
- interactive B3 LSP requests;
- formatter stdin through TaskManager/QProcess.

They remain required in the Windows acceptance registry and are not counted as passed here.

## Release 3.5 regression coverage

Eight dedicated automated tests were added in `tests/test_release_3_5.py` covering release identity, inline Settings, transparency alpha floors, integrated consoles, project-pane restoration guard, arbitrary PyPI/unknown-import fallback, bundled acceptance dependencies and root batch encoding/line-ending safety.

Thirty Release 3.5 manual acceptance cases (`R35-*`) were added to `TEST_REGISTRY_3_X.md` for UI scaling, transparency/blur, direct console stdin, file tree visibility, arbitrary package workflows, clean reinstall and acceptance runner behavior.

## Windows acceptance packaging

The TEST BUILD must contain all of the following together:

- `requirements.txt`;
- `requirements-test.txt`;
- `install_app.bat`;
- `reinstall_app.bat`;
- `run_acceptance_tests.bat`;
- the full source/test tree.

No separate pytest download step is required. `install_app.bat` installs both runtime and acceptance requirements. `reinstall_app.bat` removes `.venv` and rebuilds it from the same archive.

## Known interpretation from the first UI screenshot

The displayed console traceback referenced an older temporary source containing `int b`, while the editor in the screenshot had already been changed to `input(b)`. This is expected if code is edited after a failed run: previous output remains visible until Run is pressed again. `R35-RUN-01` records this behavior for acceptance.

The current editor expression `input(b)` is itself a Python program error if `b` has not already been defined. For an integer input the intended form is normally `b = int(input())`; this is application code behavior, not an Astra execution defect.

## Gate conclusion

Release 3.5 passes all automated checks available in the sandbox. The next authoritative step is Windows Session 0 using the unified Release 3.5 TEST BUILD, followed by the manual registry. Any defect found there becomes the next 3.x acceptance patch before Release 4.0 planning.
