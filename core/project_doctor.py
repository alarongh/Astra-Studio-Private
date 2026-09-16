from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .python_environment import detect_project_environment
from .project_commands import detect_project_commands
from .java_runtime import discover_java_runtime


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    key: str
    label: str
    status: str  # ok | warn | error | info
    detail: str


def _which(*names: str) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _project_tool(root: Path, *names: str) -> str | None:
    """Prefer project-local Node tool shims before the global PATH."""
    bin_dir = Path(root) / "node_modules" / ".bin"
    for name in names:
        candidates = [name]
        if os.name == "nt" and not Path(name).suffix:
            candidates = [f"{name}.cmd", f"{name}.exe", name]
        for candidate_name in candidates:
            candidate = bin_dir / candidate_name
            if candidate.is_file():
                return str(candidate)
    return _which(*names)


def _contains_matching_file(root: Path, patterns: tuple[str, ...], limit: int = 4000) -> bool:
    skipped = {
        ".git", "node_modules", ".venv", "venv", "build", "dist", "__pycache__", ".godot",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".cache", "coverage",
        "vendor", "target", "bin", "obj", "out",
    }
    seen = 0
    for _current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skipped]
        for filename in filenames:
            seen += 1
            if any(Path(filename).match(pattern) for pattern in patterns):
                return True
            if seen >= limit:
                return False
    return False


def _is_writable_directory(root: Path) -> bool:
    """Probe write access instead of trusting os.access on Windows ACLs."""
    probe = root / ".astra_doctor_write_test.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _find_rojo_project(root: Path) -> Path | None:
    for path in sorted(root.glob("*.project.json")):
        name = path.name.lower()
        if name == "default.project.json" or "rojo" in name:
            return path
    return None


def inspect_project(root: Path) -> list[DoctorCheck]:
    root = Path(root)
    checks: list[DoctorCheck] = []
    checks.append(DoctorCheck("root", "Папка проекта", "ok" if root.is_dir() else "error", str(root)))
    if not root.is_dir():
        return checks

    writable = _is_writable_directory(root)
    checks.append(DoctorCheck("writable", "Права на запись", "ok" if writable else "warn", "доступна" if writable else "папка может быть только для чтения"))

    git_cli = _which("git.exe", "git")
    git_repo = (root / ".git").exists()
    if git_repo and git_cli:
        checks.append(DoctorCheck("git", "Git", "ok", f"репозиторий · {git_cli}"))
    elif git_repo:
        checks.append(DoctorCheck("git", "Git", "warn", "найден .git, но git CLI не найден"))
    else:
        checks.append(DoctorCheck("git", "Git", "info", "репозиторий не инициализирован"))

    env = detect_project_environment(root)
    if env.python_executable:
        checks.append(DoctorCheck("python_env", "Python environment", "ok", f"{env.source}: {env.python_executable}"))
    elif env.dependency_files:
        checks.append(DoctorCheck("python_env", "Python environment", "warn", "есть Python dependency files, но .venv/venv не найден"))
    else:
        checks.append(DoctorCheck("python_env", "Python environment", "info", "Python-проект не определён"))
    if env.dependency_files:
        checks.append(DoctorCheck("python_deps", "Python dependencies", "ok", ", ".join(path.name for path in env.dependency_files)))
    if env.uv_executable:
        checks.append(DoctorCheck("uv", "uv", "ok", env.uv_executable))
    elif env.dependency_files:
        checks.append(DoctorCheck("uv", "uv", "info", "не найден; Astra использует venv/pip fallback"))

    has_js = _contains_matching_file(root, ("*.js", "*.mjs", "*.cjs", "*.jsx"))
    has_ts = (root / "tsconfig.json").is_file() or _contains_matching_file(root, ("*.ts", "*.tsx", "*.mts", "*.cts"))
    package_json = root / "package.json"
    if package_json.is_file() or has_js or has_ts:
        node = _which("node.exe", "node")
        npm = _which("npm.cmd", "npm.exe", "npm")
        checks.append(DoctorCheck("node", "Node.js", "ok" if node else "error", node or "JS/TS-проект найден, Node.js не найден"))
        checks.append(DoctorCheck("npm", "npm", "ok" if npm else "warn", npm or "npm не найден"))
        if (root / "pnpm-lock.yaml").is_file():
            pnpm = _which("pnpm.cmd", "pnpm.exe", "pnpm")
            checks.append(DoctorCheck("pnpm", "pnpm", "ok" if pnpm else "warn", pnpm or "pnpm-lock.yaml есть, pnpm не найден"))
        if (root / "yarn.lock").is_file():
            yarn = _which("yarn.cmd", "yarn.exe", "yarn")
            checks.append(DoctorCheck("yarn", "Yarn", "ok" if yarn else "warn", yarn or "yarn.lock есть, Yarn не найден"))
        if has_ts:
            tsc = _project_tool(root, "tsc")
            tsx = _project_tool(root, "tsx")
            checks.append(DoctorCheck("tsc", "TypeScript compiler", "ok" if tsc else "warn", tsc or "tsc не найден"))
            checks.append(DoctorCheck("tsx", "TypeScript runner", "ok" if tsx else "info", tsx or "tsx не найден; запуск TS потребует ts-node/tsx или project command"))

    if (root / "project.godot").is_file() or _contains_matching_file(root, ("*.gd",)):
        godot = _which("godot4.exe", "godot.exe", "godot4", "godot")
        checks.append(DoctorCheck("godot", "Godot", "ok" if godot else "error", godot or "GDScript/Godot-проект найден, Godot CLI не найден"))

    has_luau = _contains_matching_file(root, ("*.luau", "*.lua"))
    rojo_project = _find_rojo_project(root)
    if has_luau:
        luau = _which("luau.exe", "luau")
        luau_analyze = _which("luau-analyze.exe", "luau-analyze")
        checks.append(DoctorCheck("luau", "Luau CLI", "ok" if luau else "warn", luau or "Luau-файлы найдены, luau CLI не найден"))
        checks.append(DoctorCheck("luau_analyze", "Luau analyzer", "ok" if luau_analyze else "info", luau_analyze or "luau-analyze не найден"))
    if rojo_project:
        rojo = _which("rojo.exe", "rojo")
        checks.append(DoctorCheck("rojo", "Rojo", "ok" if rojo else "warn", rojo or f"{rojo_project.name} найден, Rojo не найден"))

    if _contains_matching_file(root, ("*.php",)):
        php = _which("php.exe", "php")
        checks.append(DoctorCheck("php", "PHP CLI", "ok" if php else "warn", php or "PHP-файлы найдены, php CLI не найден"))

    if _contains_matching_file(root, ("*.csproj", "*.sln")):
        dotnet = _which("dotnet.exe", "dotnet")
        checks.append(DoctorCheck("dotnet", ".NET SDK", "ok" if dotnet else "error", dotnet or "не найден"))

    if (root / "CMakeLists.txt").is_file():
        cmake = _which("cmake.exe", "cmake")
        checks.append(DoctorCheck("cmake", "CMake", "ok" if cmake else "warn", cmake or "не найден"))

    if _contains_matching_file(root, ("*.java",)):
        runtime = discover_java_runtime()
        detail = f"javac={runtime.javac}; java={runtime.java}" if runtime else "согласованная пара javac/java не найдена"
        checks.append(DoctorCheck("javac", "Java JDK", "ok" if runtime else "warn", detail))

    if _contains_matching_file(root, ("*.ps1",)):
        ps = _which("pwsh.exe", "pwsh", "powershell.exe", "powershell")
        checks.append(DoctorCheck("powershell", "PowerShell", "ok" if ps else "warn", ps or "не найден"))

    if _contains_matching_file(root, ("*.sh", "*.bash")):
        bash = _which("bash.exe", "bash")
        checks.append(DoctorCheck("bash", "Bash", "ok" if bash else "warn", bash or "Shell-файлы найдены, Bash не найден"))

    if (root / "Dockerfile").is_file() or (root / "Containerfile").is_file() or _contains_matching_file(root, ("Dockerfile.*", "*.dockerfile")):
        docker = _which("docker.exe", "docker")
        checks.append(DoctorCheck("docker", "Docker CLI", "ok" if docker else "info", docker or "Dockerfile найден, Docker CLI не найден"))

    detected = detect_project_commands(root)
    for kind, command in detected.items():
        checks.append(DoctorCheck(f"cmd_{kind}", f"Auto {kind}", "ok" if command else "info", command or "не определено"))

    return checks
