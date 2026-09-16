from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable

from .project_templates import TEMPLATE_SCHEMA_VERSION, get_project_template, rendered_template_files
from .python_environment import detect_project_environment


@dataclass(frozen=True, slots=True)
class HealthCheck:
    key: str
    label: str
    status: str  # ok | warn | error | info
    detail: str
    fix_id: str = ""

    @property
    def fixable(self) -> bool:
        return bool(self.fix_id)


@dataclass(frozen=True, slots=True)
class StaffedUpHealthReport:
    template_id: str
    profile: str
    checks: tuple[HealthCheck, ...]

    @property
    def fixable_count(self) -> int:
        return sum(1 for item in self.checks if item.fixable)

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.checks if item.status == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.checks if item.status == "warn")


@dataclass(frozen=True, slots=True)
class HealthFixResult:
    changed_files: tuple[Path, ...]
    actions: tuple[str, ...]
    warnings: tuple[str, ...]


_PROFILE_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "web-typescript": {
        "dirs": ("src", "docs"),
        "files": ("package.json", "tsconfig.json", "index.html"),
    },
    "yandex-games-typescript": {
        "dirs": ("src", "src/platform", "docs"),
        "files": ("package.json", "tsconfig.json", "index.html"),
    },
    "roblox-luau": {
        "dirs": ("src/server", "src/client", "src/shared", "docs"),
        "files": ("default.project.json",),
    },
    "godot": {
        "dirs": ("scenes", "scripts", "docs"),
        "files": ("project.godot",),
    },
    "python-app": {
        "dirs": ("app", "tests", "docs"),
        "files": ("pyproject.toml",),
    },
    "telegram-bot": {
        "dirs": ("app", "tests", "docs"),
        "files": ("requirements.txt", "bot.py"),
    },
    "static-website": {
        "dirs": ("docs",),
        "files": ("index.html", "styles.css", "script.js"),
    },
    "empty": {
        "dirs": ("docs",),
        "files": (),
    },
}

_SUPPORT_BASENAMES = {"README.md", ".gitignore", ".env.example"}


def _which(root: Path, tool_id: str) -> str | None:
    tool = str(tool_id or "").strip().lower()
    if not tool:
        return None
    if tool == "python":
        env = detect_project_environment(root)
        return env.python_executable or shutil.which("python.exe") or shutil.which("python") or shutil.which("py.exe") or shutil.which("py")
    if tool == "uv":
        return detect_project_environment(root).uv_executable or shutil.which("uv.exe") or shutil.which("uv")
    names: dict[str, tuple[str, ...]] = {
        "node": ("node.exe", "node"),
        "npm": ("npm.cmd", "npm.exe", "npm"),
        "git": ("git.exe", "git"),
        "godot": ("godot4.exe", "godot.exe", "godot4", "godot"),
        "rojo": ("rojo.exe", "rojo"),
        "luau-analyze": ("luau-analyze.exe", "luau-analyze"),
    }
    candidates = names.get(tool, (f"{tool}.exe", tool))
    # Prefer project-local Node shims for tools that can be installed per project.
    bin_dir = root / "node_modules" / ".bin"
    for name in candidates:
        local = bin_dir / name
        if local.is_file():
            return str(local)
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


def _read_text_preserving_encoding(path: Path) -> tuple[str, str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig", newline
    try:
        return raw.decode("utf-8"), "utf-8", newline
    except UnicodeDecodeError:
        return raw.decode("cp1251"), "cp1251", newline


def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.astra-", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode(encoding))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _gitignore_pattern_list(text: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result


def _gitignore_patterns(text: str) -> set[str]:
    return set(_gitignore_pattern_list(text))


def _template_support_files(template_id: str, project_name: str) -> dict[Path, str]:
    rendered = rendered_template_files(template_id, project_name)
    result: dict[Path, str] = {}
    for path, content in rendered.items():
        if path.name in _SUPPORT_BASENAMES or (path.parts and path.parts[0].lower() == "docs"):
            result[path] = content
    return result


def _project_config_path(root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    return root / "astral.project.json"


def _config_checks(
    root: Path,
    config_path: Path,
    template_id: str,
    metadata: dict[str, object],
) -> list[HealthCheck]:
    checks: list[HealthCheck] = []
    template = get_project_template(template_id)
    if not config_path.is_file():
        checks.append(HealthCheck("config", "astral.project.json", "error", "файл проекта Astra не найден; автоматическое восстановление небезопасно"))
        return checks
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        checks.append(HealthCheck("config", "astral.project.json", "error", f"не удалось прочитать JSON: {exc}"))
        return checks

    checks.append(HealthCheck("config", "astral.project.json", "ok", "конфигурация читается"))
    staffed = data.get("staffedUp") if isinstance(data.get("staffedUp"), dict) else {}
    actual_template = str(staffed.get("template") or metadata.get("template") or "")
    if actual_template == template.template_id:
        checks.append(HealthCheck("metadata_template", "StaffedUp template", "ok", template.template_id))
    else:
        checks.append(HealthCheck("metadata_template", "StaffedUp template", "error", f"ожидался {template.template_id}, найден {actual_template or '—'}"))

    expected_profile = template.health_profile
    actual_profile = str(staffed.get("healthProfile") or metadata.get("healthProfile") or "")
    if actual_profile == expected_profile:
        checks.append(HealthCheck("metadata_profile", "Health profile", "ok", expected_profile))
    else:
        checks.append(HealthCheck("metadata_profile", "Health profile", "warn", f"ожидался {expected_profile}, найден {actual_profile or '—'}", "metadata"))

    raw_version = staffed.get("templateVersion", metadata.get("templateVersion"))
    try:
        version = int(raw_version)
    except (TypeError, ValueError):
        version = 0
    if version == TEMPLATE_SCHEMA_VERSION:
        checks.append(HealthCheck("metadata_version", "Template schema", "ok", str(version)))
    elif version <= 0:
        checks.append(HealthCheck("metadata_version", "Template schema", "warn", "версия шаблона не записана", "metadata"))
    elif version < TEMPLATE_SCHEMA_VERSION:
        checks.append(HealthCheck("metadata_version", "Template schema", "info", f"проект создан на старой схеме {version}; миграция исходников не выполняется автоматически"))
    else:
        checks.append(HealthCheck("metadata_version", "Template schema", "warn", f"проект использует более новую схему {version}; текущая Astra знает {TEMPLATE_SCHEMA_VERSION}"))

    commands = data.get("commands") if isinstance(data.get("commands"), dict) else {}
    for kind, expected in template.commands.items():
        expected = str(expected or "").strip()
        actual = str(commands.get(kind) or "").strip()
        if not expected:
            continue
        if actual:
            state = "ok" if actual == expected else "info"
            detail = actual if actual == expected else f"кастомная команда: {actual}"
            checks.append(HealthCheck(f"command_{kind}", f"Project command · {kind}", state, detail))
        else:
            checks.append(HealthCheck(f"command_{kind}", f"Project command · {kind}", "warn", f"стандартная команда отсутствует: {expected}", "config_commands"))
    return checks


def inspect_staffedup_project(
    root: Path,
    project_name: str,
    metadata: dict[str, object] | None,
    config_path: Path | None = None,
) -> StaffedUpHealthReport | None:
    root = Path(root)
    metadata = dict(metadata or {})
    template_id = str(metadata.get("template") or "").strip()
    if not template_id:
        return None
    try:
        template = get_project_template(template_id)
    except KeyError:
        return StaffedUpHealthReport(
            template_id=template_id,
            profile=str(metadata.get("healthProfile") or "unknown"),
            checks=(HealthCheck("unknown_template", "StaffedUp template", "error", f"неизвестный template id: {template_id}"),),
        )

    checks: list[HealthCheck] = []
    if not root.is_dir():
        return StaffedUpHealthReport(template.template_id, template.health_profile, (HealthCheck("root", "Папка проекта", "error", str(root)),))

    rules = _PROFILE_RULES.get(template.health_profile, {"dirs": (), "files": ()})
    for relative in rules.get("dirs", ()):
        path = root / relative
        checks.append(HealthCheck(f"dir:{relative}", f"Структура · {relative}/", "ok" if path.is_dir() else "error", "найдено" if path.is_dir() else "обязательная папка отсутствует"))
    for relative in rules.get("files", ()):
        path = root / relative
        checks.append(HealthCheck(f"file:{relative}", f"Структура · {relative}", "ok" if path.is_file() else "error", "найдено" if path.is_file() else "обязательный файл отсутствует"))

    support_files = _template_support_files(template.template_id, project_name)
    readme = root / "README.md"
    if readme.is_file():
        try:
            readme_text, _enc, _nl = _read_text_preserving_encoding(readme)
            status = "ok" if readme_text.strip() else "warn"
            detail = "найден" if status == "ok" else "файл пуст; заполните описание проекта"
        except (OSError, UnicodeError) as exc:
            status, detail = "warn", f"не удалось прочитать: {exc}"
        checks.append(HealthCheck("docs_readme", "Документация · README.md", status, detail))
    else:
        checks.append(HealthCheck("docs_readme", "Документация · README.md", "warn", "README.md отсутствует", "support_files" if Path("README.md") in support_files else ""))

    docs_candidates = [path for path in support_files if path.parts and path.parts[0].lower() == "docs"]
    docs_dir = root / "docs"
    if docs_candidates:
        present = [path for path in docs_candidates if (root / path).is_file()]
        if present:
            checks.append(HealthCheck("docs_project", "Документация · docs/", "ok", ", ".join(str(path) for path in present)))
        else:
            checks.append(HealthCheck("docs_project", "Документация · docs/", "warn", "профильный документ отсутствует", "support_files"))
    elif docs_dir.is_dir():
        checks.append(HealthCheck("docs_project", "Документация · docs/", "ok", "найдена"))

    canonical_gitignore = support_files.get(Path(".gitignore"), "")
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        try:
            current, _enc, _nl = _read_text_preserving_encoding(gitignore)
            required = _gitignore_patterns(canonical_gitignore)
            missing = sorted(required - _gitignore_patterns(current))
            if missing:
                checks.append(HealthCheck("gitignore", ".gitignore", "warn", "не хватает: " + ", ".join(missing), "gitignore"))
            else:
                checks.append(HealthCheck("gitignore", ".gitignore", "ok", "обязательные StaffedUp patterns присутствуют"))
        except (OSError, UnicodeError) as exc:
            checks.append(HealthCheck("gitignore", ".gitignore", "warn", f"не удалось прочитать: {exc}"))
    else:
        checks.append(HealthCheck("gitignore", ".gitignore", "error", "файл отсутствует", "gitignore" if canonical_gitignore else ""))

    canonical_env = support_files.get(Path(".env.example"))
    env_example = root / ".env.example"
    if canonical_env is not None:
        if env_example.is_file():
            try:
                env_text, _enc, _nl = _read_text_preserving_encoding(env_example)
                checks.append(HealthCheck("env_example", ".env.example", "ok" if env_text.strip() else "warn", "найден" if env_text.strip() else "файл пуст; проверьте публичный список переменных"))
            except (OSError, UnicodeError) as exc:
                checks.append(HealthCheck("env_example", ".env.example", "warn", f"не удалось прочитать: {exc}"))
        else:
            checks.append(HealthCheck("env_example", ".env.example", "error", "пример переменных окружения отсутствует", "support_files"))
    else:
        local_envs = [path for path in root.glob(".env*") if path.name != ".env.example" and path.is_file()]
        if local_envs and not env_example.exists():
            checks.append(HealthCheck("env_untracked_example", ".env.example", "warn", "найден локальный .env*, но sanitized .env.example отсутствует; создайте его вручную без секретов"))
        else:
            checks.append(HealthCheck("env_example", ".env.example", "info", "для этого шаблона не обязателен"))

    for tool_id in template.required_tools:
        resolved = _which(root, tool_id)
        checks.append(HealthCheck(f"tool_required:{tool_id}", f"Required tool · {tool_id}", "ok" if resolved else "error", resolved or "не найден"))
    for tool_id in template.recommended_tools:
        resolved = _which(root, tool_id)
        checks.append(HealthCheck(f"tool_recommended:{tool_id}", f"Recommended tool · {tool_id}", "ok" if resolved else "info", resolved or "не найден"))

    if (root / "package.json").is_file():
        checks.append(HealthCheck("deps_node", "Node dependencies", "ok" if (root / "node_modules").is_dir() else "warn", "node_modules найден" if (root / "node_modules").is_dir() else "зависимости ещё не установлены; используйте Install Project"))
    env = detect_project_environment(root)
    if env.dependency_files:
        has_project_env = bool(env.python_executable and env.source in {".venv", "venv", "project"})
        checks.append(HealthCheck("deps_python_env", "Python project environment", "ok" if has_project_env else "warn", f"{env.source}: {env.python_executable}" if has_project_env else "project-local .venv/venv не найден; создайте окружение перед установкой зависимостей"))

    git_cli = _which(root, "git")
    if "git" in template.recommended_tools and git_cli:
        in_repo = (root / ".git").exists()
        if not in_repo:
            # A StaffedUp project may intentionally live inside a monorepo. Check ancestors without invoking Git.
            in_repo = any((parent / ".git").exists() for parent in root.parents)
        checks.append(HealthCheck("git_repository", "Git repository", "ok" if in_repo else "warn", "репозиторий найден" if in_repo else "Git установлен, но репозиторий для проекта не обнаружен"))

    checks.extend(_config_checks(root, _project_config_path(root, config_path), template.template_id, metadata))
    return StaffedUpHealthReport(template.template_id, template.health_profile, tuple(checks))


def _append_gitignore_patterns(root: Path, template_id: str, project_name: str, changed: list[Path], actions: list[str]) -> None:
    canonical = _template_support_files(template_id, project_name).get(Path(".gitignore"), "")
    if not canonical:
        return
    path = root / ".gitignore"
    if not path.exists():
        _atomic_write_text(path, canonical if canonical.endswith("\n") else canonical + "\n")
        changed.append(path)
        actions.append("создан .gitignore из StaffedUp-профиля")
        return
    current, encoding, newline = _read_text_preserving_encoding(path)
    current_patterns = _gitignore_patterns(current)
    missing = [pattern for pattern in _gitignore_pattern_list(canonical) if pattern not in current_patterns]
    if not missing:
        return
    updated = current
    if updated and not updated.endswith(("\n", "\r")):
        updated += newline
    updated += newline + "# StaffedUp required ignores" + newline + newline.join(missing) + newline
    _atomic_write_text(path, updated, encoding)
    changed.append(path)
    actions.append("добавлены отсутствующие StaffedUp patterns в .gitignore")


def _create_missing_support_files(root: Path, template_id: str, project_name: str, changed: list[Path], actions: list[str]) -> None:
    for relative, content in _template_support_files(template_id, project_name).items():
        if relative == Path(".gitignore"):
            continue
        target = root / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create avoids overwriting a file that appeared between inspect/fix.
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        except FileExistsError:
            continue
        changed.append(target)
        actions.append(f"создан отсутствующий support-файл {relative.as_posix()}")


def _repair_config(config_path: Path, template_id: str, changed: list[Path], actions: list[str], warnings: list[str]) -> None:
    if not config_path.is_file():
        warnings.append("astral.project.json отсутствует — Astra не создаёт его автоматически поверх неизвестного проекта")
        return
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        warnings.append(f"astral.project.json не исправлен: {exc}")
        return
    template = get_project_template(template_id)
    staffed = data.get("staffedUp") if isinstance(data.get("staffedUp"), dict) else {}
    staffed = dict(staffed)
    mutated = False
    canonical_meta = {
        "template": template.template_id,
        "healthProfile": template.health_profile,
        "requiredTools": list(template.required_tools),
        "recommendedTools": list(template.recommended_tools),
    }
    for key, value in canonical_meta.items():
        if staffed.get(key) != value:
            staffed[key] = value
            mutated = True
    if not staffed.get("templateVersion"):
        staffed["templateVersion"] = TEMPLATE_SCHEMA_VERSION
        mutated = True
    data["staffedUp"] = staffed

    commands = data.get("commands") if isinstance(data.get("commands"), dict) else {}
    commands = dict(commands)
    for kind, expected in template.commands.items():
        if str(expected or "").strip() and not str(commands.get(kind) or "").strip():
            commands[kind] = expected
            mutated = True
    data["commands"] = commands
    if not mutated:
        return
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    _atomic_write_text(config_path, rendered, "utf-8")
    changed.append(config_path)
    actions.append("восстановлены безопасные StaffedUp metadata/отсутствующие project commands")


def apply_safe_staffedup_fixes(
    root: Path,
    project_name: str,
    metadata: dict[str, object] | None,
    config_path: Path | None = None,
) -> HealthFixResult:
    root = Path(root)
    metadata = dict(metadata or {})
    template_id = str(metadata.get("template") or "").strip()
    if not template_id:
        return HealthFixResult((), (), ("проект не содержит StaffedUp template metadata",))
    try:
        get_project_template(template_id)
    except KeyError:
        return HealthFixResult((), (), (f"неизвестный StaffedUp template: {template_id}",))
    if not root.is_dir():
        return HealthFixResult((), (), (f"папка проекта недоступна: {root}",))

    changed: list[Path] = []
    actions: list[str] = []
    warnings: list[str] = []
    try:
        _append_gitignore_patterns(root, template_id, project_name, changed, actions)
    except (OSError, UnicodeError) as exc:
        warnings.append(f".gitignore не исправлен: {exc}")
    try:
        _create_missing_support_files(root, template_id, project_name, changed, actions)
    except (OSError, UnicodeError) as exc:
        warnings.append(f"support-файлы исправлены не полностью: {exc}")
    _repair_config(_project_config_path(root, config_path), template_id, changed, actions, warnings)

    # Preserve stable ordering while removing duplicates (config can theoretically be same path twice).
    unique: list[Path] = []
    seen: set[str] = set()
    for path in changed:
        key = os.path.normcase(str(path.resolve(strict=False)))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return HealthFixResult(tuple(unique), tuple(actions), tuple(warnings))
