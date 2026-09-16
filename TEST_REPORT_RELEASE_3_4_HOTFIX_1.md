# TEST REPORT — Astra Studio Release 3.4 Hotfix 1

Scope: Windows `cmd.exe` launcher packaging regression discovered during the first owner acceptance run.

## Root cause confirmed by artifact inspection

All four root `.bat` files in the delivered Release 3.3 archive used Unix LF-only line endings and contained UTF-8 non-ASCII Russian text. The observed `cmd.exe` errors executed fragments of legitimate batch tokens as commands (`level` from `errorlevel`, `hell` from `powershell`) and fragments of Russian messages. This is consistent with batch parser desynchronization at the packaging boundary rather than an Astra/Python runtime failure.

## Fix

- Root `.bat`: ASCII-only, no BOM, CRLF-only.
- Windows-native `.ps1` and `.vbs`: CRLF-normalized.
- Runtime identity: Release 3.4.
- Added automated regression guard for batch source encoding/line endings.

## Windows acceptance required

The Linux sandbox cannot execute Windows `cmd.exe`, so the definitive runtime verification remains the owner's Session 0: extract Release 3.4, run `install_app.bat`, then launch Astra. This test must be rerun before continuing later acceptance sessions.
