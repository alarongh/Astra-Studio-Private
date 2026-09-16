from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


DEPENDENCY_FILENAMES = (
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-prod.txt",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
)


@dataclass(frozen=True, slots=True)
class PythonEnvironmentInfo:
    project_root: Path
    python_executable: Path | None
    environment_dir: Path | None
    source: str
    dependency_files: tuple[Path, ...]
    uv_executable: str | None

    @property
    def is_project_environment(self) -> bool:
        return self.environment_dir is not None and self.python_executable is not None


def _python_in_environment(env_dir: Path) -> Path | None:
    candidates = []
    if os.name == "nt":
        candidates.extend([
            env_dir / "Scripts" / "python.exe",
            env_dir / "Scripts" / "pythonw.exe",
        ])
    else:
        candidates.extend([
            env_dir / "bin" / "python3",
            env_dir / "bin" / "python",
        ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def dependency_files(project_root: Path) -> tuple[Path, ...]:
    root = Path(project_root)
    files = []
    for name in DEPENDENCY_FILENAMES:
        path = root / name
        if path.is_file():
            files.append(path)
    # Also support split requirement files without hardcoding every environment name.
    for path in sorted(root.glob("requirements*.txt")):
        if path.is_file() and path not in files:
            files.append(path)
    return tuple(files)


def detect_project_environment(project_root: Path) -> PythonEnvironmentInfo:
    root = Path(project_root).resolve()
    env_candidates = [root / ".venv", root / "venv"]

    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        active_env = Path(virtual_env)
        try:
            active_env.resolve().relative_to(root)
            env_candidates.append(active_env)
        except (OSError, ValueError):
            # Never mistake Astra Studio's own activated environment for the
            # environment of an unrelated project.
            pass

    seen = set()
    for env_dir in env_candidates:
        try:
            resolved = env_dir.resolve()
        except OSError:
            resolved = env_dir
        key = str(resolved).lower() if os.name == "nt" else str(resolved)
        if key in seen:
            continue
        seen.add(key)
        python_exe = _python_in_environment(env_dir)
        if python_exe:
            source = ".venv" if env_dir.name == ".venv" else ("venv" if env_dir.name == "venv" else "VIRTUAL_ENV")
            return PythonEnvironmentInfo(
                project_root=root,
                python_executable=python_exe,
                environment_dir=env_dir,
                source=source,
                dependency_files=dependency_files(root),
                uv_executable=shutil.which("uv.exe") or shutil.which("uv"),
            )

    return PythonEnvironmentInfo(
        project_root=root,
        python_executable=None,
        environment_dir=None,
        source="global",
        dependency_files=dependency_files(root),
        uv_executable=shutil.which("uv.exe") or shutil.which("uv"),
    )
