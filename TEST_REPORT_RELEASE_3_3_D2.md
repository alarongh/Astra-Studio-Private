# Astra Studio — Test Report Release 3.3 D2

## Scope

Stage: **Release 3.3 D2 — StaffedUp Project Health**.

D2 turns the existing generic Project Doctor into a profile-aware health checker for projects created from Release 3.3 D1 StaffedUp templates. The implementation is intentionally diagnostic-first: automatic repair is limited to deterministic changes that do not overwrite source code, infer secrets, initialize repositories, install tools/dependencies or perform network actions.

## Implemented

- Added `core/staffedup_health.py`.
- Profile-aware checks for all D1 templates:
  - Web / TypeScript;
  - Yandex Games / TypeScript;
  - Roblox / Luau;
  - Godot / GDScript;
  - Python App;
  - Telegram Bot / Python;
  - Static Website;
  - Empty Project.
- Project structure validation per health profile.
- `.gitignore` validation against the template's required patterns.
- `.env.example` checks only when the template defines a canonical safe example.
- Manual warning when local `.env*` exists but Astra has no safe canonical example to generate.
- README and profile-specific `docs/*` checks.
- Required vs recommended tool diagnostics.
- Node dependency-state check without implicit `npm install`.
- Python project-environment check without confusing global Python with project `.venv`/`venv`.
- Git repository check, including StaffedUp projects nested inside a parent monorepo.
- `astral.project.json` StaffedUp metadata/schema/project-command checks.
- Project Doctor UI upgraded to `ProjectHealthTree` with status/details/fixability columns.
- Explicit **Исправить безопасное** action and refresh action.

## Safe Fix boundary

Safe Fix may only:

1. Create a missing canonical `.gitignore`.
2. Append missing canonical ignore patterns without removing existing user lines.
3. Create missing support files that already exist in the D1 template definition (`README.md`, canonical `.env.example`, profile docs) and only when the destination does not exist.
4. Restore canonical StaffedUp metadata fields in a readable `astral.project.json`.
5. Restore a standard project command only when that command is empty/missing.

Safe Fix does **not**:

- recreate deleted source/code files or source directories;
- overwrite existing README/docs/`.env.example` content;
- copy or infer values from real `.env` files;
- auto-upgrade source structure from an older template schema;
- overwrite malformed `astral.project.json`;
- run package managers;
- install tools;
- initialize Git;
- access the network.

## Audit finding fixed during D2

The first implementation collected missing `.gitignore` patterns using sorted set order. That could place a negation pattern such as `!.env.example` before the broader `.env.*` rule, changing Git ignore semantics. D2 now preserves the canonical template order when appending missing rules.

The append path also preserves an existing `.gitignore` text encoding (`UTF-8`, UTF-8 BOM or CP1251) and its detected CRLF/LF line-ending convention.

## Automated gate

Commands executed from the Release 3.3 tree:

```text
python -m compileall -q .
python tests/smoke_static.py
python -m pytest -q
```

Result:

```text
compileall          PASS
static smoke        PASS

Tests collected     162
Passed              155
Failed                0
Skipped               7
Subtests passed      88
```

D2 contributes **17 dedicated automated tests** in `tests/test_staffedup_d2.py`.

Coverage includes:

- all eight profile reports;
- non-StaffedUp and unknown/future templates;
- missing `.gitignore` recovery;
- canonical ignore append order;
- CP1251/CRLF preservation;
- support-file recovery without source recovery;
- existing custom support-file preservation;
- standard-command restoration while preserving custom commands;
- metadata repair boundaries;
- missing/older template schema behavior;
- malformed project-config refusal;
- Safe Fix idempotency;
- real `.env` secret boundary;
- Node dependency-state diagnosis without installation;
- required/recommended tool severity;
- source-structure validation without automatic reconstruction;
- static Project Doctor / D2 UI integration.

## Deferred runtime/manual acceptance

The existing seven Qt/PySide6 runtime tests remain deferred because PySide6/Windows GUI runtime is not available in the current sandbox. D2 does not claim those tests passed.

D2-specific Windows acceptance cases are registered as `D2-HEALTH-01` through `D2-HEALTH-24` in `TEST_REGISTRY_3_X.md`. They include Project Doctor rendering/refresh, permission failures, tool detection on Windows, parent-repository behavior and explicit confirmation that Safe Fix performs no package-manager/network action.

## Gate conclusion

**D2 INTERNAL GATE: PASSED.**

D1 + D2 are suitable as the baseline for Release 3.3 D3. Owner manual Windows regression remains intentionally deferred until D3 and the final 3.x integration gate are complete.
