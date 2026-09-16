# CHANGELOG — Astra Studio Release 3.0

Status: **INTERNAL GATE PASSED / FROZEN BASELINE**

## Release reset

The long-delayed rebuild after Release 2.2 is numbered **Release 3.0**. The temporary 2.3 candidate name is retired and must not be used as a public release number.

## Stabilization carried into 3.0

- fixed custom message-box action roles and safe close semantics;
- hardened background task lifecycle, cancellation and stdout/stderr buffering;
- prevented startup examples from modifying user project folders;
- fixed Save As rollback and prevented running stale unsaved files;
- improved local-module detection for Python imports;
- improved project restore/state handling;
- moved slow tool diagnostics away from the GUI thread;
- hardened Windows launcher/install batch logic;
- improved Python discovery around Windows Store aliases and normal user installs.

## Language expansion — implemented in current stage

Added editor/file recognition and starter templates for:

- TypeScript;
- Luau/Lua;
- GDScript;
- PHP;
- PowerShell;
- JSON;
- YAML;
- Markdown;
- TOML;
- XML;
- Shell;
- Dockerfile.

Baseline syntax highlighting has been added for these formats. Project discovery now includes their common extensions and special filenames.

Run/check support in this stage:

- TypeScript: `tsc` check; direct run via `tsx` or `ts-node` when present;
- Luau: `luau-analyze` check and `luau` run when present;
- GDScript: Godot-project check/run when Godot 4 and `project.godot` are found;
- PHP: `php -l` and direct CLI run;
- PowerShell: parser check and script run;
- Shell: `bash -n` and direct Bash run;
- JSON/TOML/XML: local structural validation;
- YAML: validation through PyYAML when available;
- Markdown/Dockerfile: editing support; execution is intentionally project-command based.

## Installer compatibility

- Windows launch/install batch files retain the 2.x bug fixes and now look for Python 3.14 as well as 3.13/3.12/3.11.
- PowerShell Python installation preference now includes Python 3.14.

## Python environment — detection implemented

- Astra now detects project `.venv` / `venv`;
- dependency manifests (`pyproject.toml`, `uv.lock`, `requirements*.txt`, `Pipfile`, `poetry.lock`) are surfaced;
- project Python is preferred over the global interpreter for Python run/check/library/build operations;
- the Python libraries page shows the current project interpreter, dependency files and whether `uv` is available.

## Python Environment Manager actions — implemented

- create project `.venv`;
- prefer `uv venv --seed` when uv is available, otherwise use `python -m venv`;
- manually choose a project Python and persist it in `astral.project.json`;
- install dependencies from uv project metadata, `requirements.txt` or `pyproject.toml`;
- prefer `uv pip` for project package operations when available, with pip fallback;
- update pip;
- export `requirements.txt` only from a project/explicit environment to avoid accidentally freezing the global environment.

## Project workflow foundation — implemented

- generic project Run / Build / Test / Install commands with explicit overrides in `astral.project.json`;
- conservative auto-detection for Node, Python, Godot, .NET, Maven/Gradle, CMake and Rojo projects;
- project-wide search/replace with unsaved-file protection;
- Quick Open (`Ctrl+P`);
- Project Doctor with checks for Python/uv, Node/npm/TypeScript, Git, Godot, Luau/Rojo, PHP, Java, .NET, CMake, PowerShell, Bash and Docker where relevant.

## Windows toolchain installer — implemented for 3.0

The installer UI now exposes individual actions for:

- Python 3.14+ and `uv`;
- Node.js LTS plus global TypeScript/`tsx` tooling;
- Git;
- C++ / MSYS2;
- Java JDK;
- PowerShell 7;
- Godot;
- PHP 8.4.

`Install core StaffedUp toolchain` installs the common workstation set (Python + uv, Node/TypeScript, Git, PowerShell, C++ and Java). Godot and PHP remain explicit role/project installs to avoid forcing large or unnecessary toolchains on every team member.

The background diagnostic/update path was expanded for these tools. Luau/Rojo are detected by Project Doctor but remain project-specific in 3.0; standardized StaffedUp Roblox provisioning is scheduled for Release 3.3.

## Final gate — completed

Release 3.0 passed its internal gate on 2026-08-23.

Final-gate fixes included:

- embedded installer now resolves both `Get-Command` (`.Source`) and `Get-Item` (`.FullName`) tool objects safely;
- desktop shortcuts no longer depend on a temporary PyInstaller `_MEIPASS` icon path;
- background `TaskManager` output has UTF-8 plus Windows CP866/CP1251 decoding fallback;
- Search/Replace regression coverage was corrected and expanded;
- settings load/save parity, Python environment isolation, project-command matrix and all 20 language Run/Check branches are covered by automated/static tests.

Result: **31/31 unit/static tests PASS** and the Release 3.0 smoke suite passes. See `TEST_REPORT_RELEASE_3_0.md`.

Release 3.0 is now frozen as the internal baseline for Release 3.1. Manual Windows regression testing remains intentionally deferred until the complete 3.x cycle is implemented.
