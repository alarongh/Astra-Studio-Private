from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Iterable, Mapping


JAVA_UTF8_SYSTEM_PROPERTIES = (
    "-Dfile.encoding=UTF-8",
    "-Dstdout.encoding=UTF-8",
    "-Dstderr.encoding=UTF-8",
)
JAVAC_UTF8_ARGUMENTS = tuple(f"-J{option}" for option in JAVA_UTF8_SYSTEM_PROPERTIES) + (
    "-encoding",
    "UTF-8",
)


def javac_arguments(source_path: str | Path) -> list[str]:
    """Build javac arguments with UTF-8 source and pipe encodings."""
    return [*JAVAC_UTF8_ARGUMENTS, str(source_path)]


def java_arguments(classpath: str | Path, class_name: str) -> list[str]:
    """Build java arguments whose stdout/stderr are deterministic UTF-8."""
    return [*JAVA_UTF8_SYSTEM_PROPERTIES, "-cp", str(classpath), str(class_name)]


@dataclass(frozen=True, slots=True)
class JavaRuntime:
    javac: Path
    java: Path
    home: Path
    source: str


def _executable(path: Path) -> bool:
    return path.exists() and path.is_file()


def _paired_home(path: str | Path | None) -> Path | None:
    if not path:
        return None
    executable = Path(path)
    if executable.parent.name.lower() != "bin":
        return None
    return executable.parent.parent


def _standard_java_homes(env: Mapping[str, str]) -> Iterable[Path]:
    roots: list[Path] = []
    for name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        value = env.get(name)
        if value:
            roots.append(Path(value))
    patterns = (
        ("Eclipse Adoptium", "jdk-*"),
        ("Java", "jdk-*"),
        ("Microsoft", "jdk-*"),
        ("Amazon Corretto", "jdk*"),
        ("BellSoft", "LibericaJDK*"),
        ("Azul Systems", "Zulu*"),
        ("Programs", "Eclipse Adoptium", "jdk-*"),
        ("Programs", "Java", "jdk-*"),
    )
    seen: set[str] = set()
    for root in roots:
        for pattern in patterns:
            parent = root.joinpath(*pattern[:-1])
            if not parent.exists():
                continue
            try:
                matches = sorted(parent.glob(pattern[-1]), key=lambda item: item.name.lower(), reverse=True)
            except OSError:
                continue
            for home in matches:
                key = str(home).lower()
                if key not in seen:
                    seen.add(key)
                    yield home


def discover_java_runtime(
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    extra_homes: Iterable[Path | str] = (),
    search_standard_homes: bool = True,
) -> JavaRuntime | None:
    """Find a paired javac/java toolchain, never mixing executables from different JDKs."""
    environment = dict(os.environ if env is None else env)
    which_fn = shutil.which if which is None else which
    candidates: list[tuple[Path, str]] = []
    for variable in ("JAVA_HOME", "JDK_HOME"):
        value = environment.get(variable)
        if value:
            candidates.append((Path(value), variable))
    candidates.extend((Path(home), "configured") for home in extra_homes)

    javac_on_path = which_fn("javac.exe" if os.name == "nt" else "javac") or which_fn("javac")
    java_on_path = which_fn("java.exe" if os.name == "nt" else "java") or which_fn("java")
    javac_home = _paired_home(javac_on_path)
    java_home = _paired_home(java_on_path)
    if javac_home is not None:
        candidates.append((javac_home, "PATH javac"))
    if java_home is not None:
        candidates.append((java_home, "PATH java"))
    if search_standard_homes and os.name == "nt":
        candidates.extend((home, "Windows install roots") for home in _standard_java_homes(environment))

    exe_suffix = ".exe" if os.name == "nt" else ""
    seen: set[str] = set()
    for raw_home, source in candidates:
        try:
            home = raw_home.expanduser().resolve()
        except OSError:
            home = raw_home.expanduser()
        key = str(home).lower()
        if key in seen:
            continue
        seen.add(key)
        javac = home / "bin" / f"javac{exe_suffix}"
        java = home / "bin" / f"java{exe_suffix}"
        if _executable(javac) and _executable(java):
            return JavaRuntime(javac=javac, java=java, home=home, source=source)
    return None


def java_version(runtime: JavaRuntime, timeout: int = 8) -> str:
    try:
        completed = subprocess.run(
            [str(runtime.javac), "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return "version unavailable"
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return output.splitlines()[0][:180] if output else "version unavailable"
