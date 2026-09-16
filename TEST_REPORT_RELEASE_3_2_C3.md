# TEST REPORT — Astra Studio Release 3.2 C3

Date: 2026-08-23

Status: **INTERNAL GATE PASSED**

Scope: **C3 — Git / Source Control**

This report covers only the internal automated/static gate for C3. It does **not** replace the final owner Windows acceptance test, which remains scheduled after Release 3.3.

## Implemented scope

C3 adds a dedicated Git layer in `core/git_tools.py` and integrates Source Control into Astra Studio.

Implemented:

- repository detection via `git rev-parse --show-toplevel`;
- support for projects opened inside a parent repository;
- porcelain-v2 NUL-delimited status parser;
- branch, detached HEAD, upstream, ahead/behind;
- staged / working-tree / untracked / conflict states;
- rename/copy original-path preservation;
- working and staged diff viewer;
- rename-aware diff using old + new path;
- Stage Selected / Unstage Selected;
- explicitly confirmed Stage All / Unstage All;
- first-commit unstage support;
- commit staged changes with required message, conflict guard and confirmation;
- Pull with clean-tree/upstream/detached guards and `--ff-only`;
- Push with upstream/detached guards and explicit confirmation;
- no force-push mode;
- TaskManager-based asynchronous Git operations;
- per-task `GIT_TERMINAL_PROMPT=0` for network operations;
- automatic status refresh after successful mutations;
- Git UI state reset on project switch;
- Git controls disabled according to state/background-task availability;
- monospaced no-wrap diff output.

## Automated test results

Final sandbox run:

```text
compileall          PASS
static smoke        PASS
pytest collected    127
pytest passed       120
pytest failed       0
pytest skipped      7
subtests passed     88
```

The 7 skipped tests are runtime checks that require PySide6/Qt. They are already registered in `TEST_REGISTRY_3_X.md` for the final Windows gate.

New C3 Qt deferred test:

```text
tests/test_git_c3_qt.py::GitTaskRuntimeTests::test_task_manager_preserves_nul_delimited_unicode_git_status
```

It specifically verifies the real `QProcess -> TaskManager -> porcelain parser` path with NUL-delimited Unicode Git paths.

## Real Git integration executed in sandbox

Unlike a static-only mock gate, C3 tests create real temporary Git repositories and execute the installed Git CLI.

Verified:

- repository probe from a nested project folder;
- status with staged, unstaged and untracked files;
- paths containing spaces and Cyrillic Unicode;
- staged rename parsing;
- rename-aware staged diff;
- rename unstage using both old and new path;
- Stage Selected;
- Unstage Selected;
- Stage All;
- Unstage All;
- unstage before the first commit;
- working-tree diff;
- staged diff;
- commit;
- clean status after commit.

## Local remote integration

Network semantics were tested without internet access by creating a local bare Git remote.

Verified:

- initial push/upstream setup in the test fixture;
- fast-forward pull through Astra's C3 command builder;
- push through Astra's C3 command builder;
- propagation of pushed content to another clone;
- divergent histories cause `git pull --ff-only` to fail;
- failed divergent pull leaves local `HEAD` unchanged;
- no merge commit is created automatically.

## Safety audit

Static safety scan confirmed:

- no `shell=True` in Astra Git integration;
- no runtime `git reset --hard`;
- no `git clean -f`;
- no `checkout --` destructive restore path;
- no force/force-with-lease push option in production Git command construction;
- path-targeting commands use `--` before file paths;
- commit message is passed as a direct argument, not interpolated into a shell command;
- Pull is `--ff-only`;
- dirty-tree Pull is blocked in the UI;
- no-upstream Pull/Push is blocked rather than guessing a remote;
- detached-head Pull/Push is blocked;
- Stage All and Unstage All require explicit confirmation;
- nested parent-repository Stage All warning is explicit.

## Regression checks

Full existing 3.x suite remains green after C3:

- Release 3.0 foundation tests remain passing;
- Release 3.1 LSP tests remain passing/deferred exactly as expected;
- Release 3.2 C1 formatter/linter tests remain passing/deferred;
- Release 3.2 C2 Test Explorer tests remain passing;
- static smoke still reports 20 language configs, 41 Python library registry entries, 11 assets and 13 installer scripts.

No runtime source references to temporary `/mnt/data` paths or `Astra_Studio_Release_3_2_pre_C3` were found.

## Deferred Windows/Qt checks

The current environment does not have PySide6, so UI/runtime checks requiring real Qt execution are not certified here.

The final Windows test registry includes, among others:

- Source Control UI rendering and control enable/disable states;
- QProcess Unicode/NUL Git status path;
- Git missing / non-repository behavior;
- double-click navigation for changed/deleted files;
- TaskManager cancellation of a long Git operation;
- real Windows credential-manager/network failure behavior;
- Pull/Push confirmation dialogs;
- project-switch source-control reset;
- no GUI freeze during Git operations.

These remain intentionally deferred until the single owner regression run after Release 3.3.

## Gate decision

**C3 INTERNAL GATE: PASSED**

Release 3.2 now has all planned C1–C3 functionality implemented and internally gated. It can be frozen as the baseline for Release 3.3.
