from __future__ import annotations

import json
from pathlib import Path

COMMAND_KEYS = ("run", "build", "test", "install")


def normalize_commands(value: object) -> dict[str, str]:
    result = {key: "" for key in COMMAND_KEYS}
    if isinstance(value, dict):
        for key in COMMAND_KEYS:
            raw = value.get(key)
            if isinstance(raw, str):
                result[key] = raw.strip()
    return result


def _package_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "bun.lock").is_file() or (root / "bun.lockb").is_file():
        return "bun"
    return "npm"


def _npm_script_command(manager: str, script: str) -> str:
    if manager == "yarn":
        return f"yarn {script}"
    if manager == "bun":
        return f"bun run {script}"
    return f"{manager} run {script}"


def _pyproject_declares_pytest(path: Path) -> bool:
    """Detect explicit pytest configuration without assuming every pyproject uses pytest."""
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "[tool.pytest." in text or "pytest" in text


def detect_project_commands(project_root: Path) -> dict[str, str]:
    """Return conservative default project commands.

    Placeholders are resolved by Astra at execution time:
    `{python}`, `{godot}`, `{rojo}`.
    """
    root = Path(project_root)
    commands = {key: "" for key in COMMAND_KEYS}

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
        manager = _package_manager(root)
        for candidate in ("dev", "start", "serve"):
            if candidate in scripts:
                commands["run"] = _npm_script_command(manager, candidate)
                break
        if "build" in scripts:
            commands["build"] = _npm_script_command(manager, "build")
        if "test" in scripts:
            commands["test"] = _npm_script_command(manager, "test")
        if manager == "npm" and (root / "package-lock.json").is_file():
            commands["install"] = "npm ci"
        elif manager == "yarn" and (root / "yarn.lock").is_file():
            # Yarn Berry (2+) prefers --immutable; Yarn Classic uses --frozen-lockfile.
            commands["install"] = "yarn install --immutable" if (root / ".yarnrc.yml").is_file() else "yarn install --frozen-lockfile"
        elif manager == "pnpm" and (root / "pnpm-lock.yaml").is_file():
            commands["install"] = "pnpm install --frozen-lockfile"
        elif manager == "bun":
            commands["install"] = "bun install --frozen-lockfile"
        else:
            commands["install"] = f"{manager} install"

    if (root / "project.godot").is_file():
        commands["run"] = commands["run"] or "{godot} --path ."

    if any(root.glob("*.csproj")) or any(root.glob("*.sln")):
        # dotnet run can be ambiguous for a solution with several projects, but is
        # still useful as a conservative default for the common single-project case.
        commands["run"] = commands["run"] or "dotnet run"
        commands["build"] = commands["build"] or "dotnet build"
        commands["test"] = commands["test"] or "dotnet test"

    if (root / "pom.xml").is_file():
        # There is no generic safe Maven run command: exec:java requires project-
        # specific plugin/main-class configuration. Build/test/install are stable.
        commands["build"] = commands["build"] or "mvn package"
        commands["test"] = commands["test"] or "mvn test"
        commands["install"] = commands["install"] or "mvn dependency:resolve"
    elif (root / "gradlew.bat").is_file() or (root / "gradlew").is_file():
        wrapper = "gradlew.bat" if (root / "gradlew.bat").is_file() else "./gradlew"
        commands["build"] = commands["build"] or f"{wrapper} build"
        commands["test"] = commands["test"] or f"{wrapper} test"

    if (root / "CMakeLists.txt").is_file():
        commands["build"] = commands["build"] or "cmake -S . -B build && cmake --build build"

    rojo_project = next(
        (
            path
            for path in sorted(root.glob("*.project.json"))
            if "rojo" in path.name.lower() or path.name.lower() == "default.project.json"
        ),
        None,
    )
    if rojo_project:
        commands["run"] = commands["run"] or f'{{rojo}} serve "{rojo_project.name}"'

    python_entry = next((root / name for name in ("main.py", "app.py", "bot.py", "server.py", "manage.py") if (root / name).is_file()), None)
    pyproject = root / "pyproject.toml"
    has_python_project = python_entry is not None or pyproject.is_file() or (root / "requirements.txt").is_file()
    if has_python_project:
        if python_entry:
            commands["run"] = commands["run"] or f'{{python}} "{python_entry.name}"'
        has_tests = (root / "tests").is_dir() or (root / "pytest.ini").is_file() or _pyproject_declares_pytest(pyproject)
        if has_tests:
            commands["test"] = commands["test"] or "{python} -m pytest"
        # Dedicated Python Environment Manager handles dependency install safely.
        commands["install"] = commands["install"] or "{python-deps}"

    return commands


def merge_project_commands(explicit: object, detected: dict[str, str]) -> dict[str, str]:
    explicit_commands = normalize_commands(explicit)
    return {key: explicit_commands.get(key) or detected.get(key, "") for key in COMMAND_KEYS}
