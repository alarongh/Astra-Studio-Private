# CHANGELOG — Astra Studio Release 3.4

Release 3.4 is a post-gate Windows launcher hotfix. No 3.x feature scope was added.

## Fixed

- Repacked `run.bat`, `run_astra.bat`, `install_app.bat`, and `build_exe.bat` as ASCII-only batch source with Windows CRLF line endings.
- Removed non-ASCII user-facing text from root `.bat` files so `cmd.exe` does not depend on source-file UTF-8 decoding to parse control flow.
- Kept `chcp 65001` only for child-process console output; batch syntax itself is ASCII-safe.
- Normalized Windows-native PowerShell/VBS scripts to CRLF while preserving required UTF-8 BOM on the Unicode shortcut script.
- Bumped runtime identity to `Release 3.4`.
- Added a regression test that rejects LF-only root batch files, UTF-8 BOMs in `.bat`, and non-ASCII batch source.

## Trigger

The first owner Windows acceptance run of Release 3.3 failed before Astra startup. `cmd.exe` reported command fragments including `level` and `hell`, corresponding to split portions of `errorlevel` and `powershell`, plus fragments of Russian messages. Archive inspection confirmed LF-only UTF-8 batch wrappers.

## Acceptance

Release 3.3 is superseded for Session 0. Restart Windows acceptance from `install_app.bat` using Release 3.4.
