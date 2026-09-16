from __future__ import annotations

# The module name starts with ``test_`` because it implements Test Explorer.
# Prevent pytest from mistaking production dataclasses for test classes.
__test__ = False

import ast
import json
import os
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SKIPPED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".cache", ".godot",
    "coverage", "vendor", "target", "bin", "obj", "out",
}

STATUS_PENDING = "pending"
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"


@dataclass(slots=True)
class TestCase:
    test_id: str
    label: str
    path: str = ""
    line: int = 0
    parent: str = ""
    kind: str = "test"
    status: str = STATUS_PENDING
    message: str = ""
    duration: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TestAdapter:
    adapter_id: str
    display_name: str
    available: bool
    reason: str = ""
    supports_selected: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TestCommand:
    adapter_id: str
    display_name: str
    program: str
    arguments: tuple[str, ...]
    workdir: Path
    selected_id: str = ""


@dataclass(slots=True)
class TestRunResult:
    adapter_id: str
    display_name: str
    exit_code: int
    status: str
    summary: str
    nodes: list[TestCase]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "adapterId": self.adapter_id,
            "displayName": self.display_name,
            "exitCode": self.exit_code,
            "status": self.status,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "nodes": [node.to_dict() for node in self.nodes[:2000]],
        }


def _which(name: str, root: Path | None = None) -> str | None:
    if root:
        suffix = ".cmd" if os.name == "nt" else ""
        candidate = root / "node_modules" / ".bin" / f"{name}{suffix}"
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def _package_json(root: Path) -> dict:
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _package_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "bun.lock").is_file() or (root / "bun.lockb").is_file():
        return "bun"
    return "npm"


def _manager_executable(manager: str) -> str | None:
    names = [f"{manager}.cmd", manager] if os.name == "nt" else [manager]
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _python_has_module(python_executable: str | None, module: str) -> bool:
    if not python_executable:
        return False
    # Do not import/execute arbitrary project code during detection. Presence of
    # dependency files is enough for UI detection; actual launch reports failure.
    return bool(module)


def detect_test_adapters(project_root: Path, python_executable: str | None = None) -> list[TestAdapter]:
    root = Path(project_root)
    adapters: list[TestAdapter] = []

    pyproject = root / "pyproject.toml"
    pytest_markers = [root / "pytest.ini", root / "conftest.py"]
    has_pytests = any(path.is_file() for path in pytest_markers)
    dependency_text = ""
    for dependency_file in [pyproject, root / "requirements.txt", root / "requirements-dev.txt", root / "requirements-test.txt"]:
        if not dependency_file.is_file():
            continue
        try:
            dependency_text += "\n" + dependency_file.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            pass
    has_pytests = has_pytests or "pytest" in dependency_text
    python_test_files = list(_walk_files(root, ("test*.py", "*_test.py"), limit=800))
    has_python_tests = bool(python_test_files)
    has_unittest = False
    for path in python_test_files[:200]:
        try:
            sample = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"\bimport\s+unittest\b|\bfrom\s+unittest\b|unittest\.TestCase", sample):
            has_unittest = True
            break
    if has_pytests:
        adapters.append(TestAdapter("pytest", "pytest", bool(python_executable), "Python interpreter not found" if not python_executable else "", True))
    if has_unittest or (has_python_tests and not has_pytests):
        adapters.append(TestAdapter("unittest", "unittest", bool(python_executable), "Python interpreter not found" if not python_executable else "", True))

    package = _package_json(root)
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        if isinstance(package.get(key), dict):
            deps.update(package[key])
    test_script = str(scripts.get("test") or "").strip()
    js_framework = ""
    lowered = " ".join([test_script, *[str(key) for key in deps]]).lower()
    if "vitest" in lowered:
        js_framework = "Vitest"
    elif "jest" in lowered:
        js_framework = "Jest"
    elif test_script:
        js_framework = "npm test"
    if test_script:
        manager = _package_manager(root)
        program = _manager_executable(manager)
        adapters.append(TestAdapter("npm", f"{js_framework} ({manager})", bool(program), f"{manager} not found" if not program else "", False))

    has_dotnet = bool(list(root.glob("*.sln")) or list(root.glob("*.csproj")))
    if has_dotnet:
        dotnet = shutil.which("dotnet.exe" if os.name == "nt" else "dotnet") or shutil.which("dotnet")
        adapters.append(TestAdapter("dotnet", "dotnet test", bool(dotnet), ".NET SDK not found" if not dotnet else "", False))

    return adapters


def _walk_files(root: Path, patterns: tuple[str, ...], limit: int = 4000) -> Iterable[Path]:
    count = 0
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIPPED_DIRS]
        current_path = Path(current)
        for filename in filenames:
            if not any(Path(filename).match(pattern) for pattern in patterns):
                continue
            yield current_path / filename
            count += 1
            if count >= limit:
                return


def _python_test_cases(root: Path, unittest_mode: bool = False) -> list[TestCase]:
    result: list[TestCase] = []
    for path in _walk_files(root, ("test*.py", "*_test.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                source = path.read_text(encoding="cp1251")
            except (OSError, UnicodeDecodeError):
                continue
        except OSError:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.name
        module = rel[:-3].replace("/", ".") if rel.endswith(".py") else rel.replace("/", ".")
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                test_id = f"{module}.{node.name}" if unittest_mode else f"{rel}::{node.name}"
                result.append(TestCase(test_id, node.name, str(path), max(0, node.lineno - 1), rel))
            elif isinstance(node, ast.ClassDef) and (node.name.startswith("Test") or unittest_mode):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test"):
                        test_id = f"{module}.{node.name}.{child.name}" if unittest_mode else f"{rel}::{node.name}::{child.name}"
                        result.append(TestCase(test_id, child.name, str(path), max(0, child.lineno - 1), f"{rel}::{node.name}"))
    return result


def _js_test_cases(root: Path) -> list[TestCase]:
    patterns = ("*.test.js", "*.test.ts", "*.test.jsx", "*.test.tsx", "*.spec.js", "*.spec.ts", "*.spec.jsx", "*.spec.tsx")
    call_re = re.compile(r"\b(?:it|test)\s*\(\s*([\"'`])(.+?)\1")
    result: list[TestCase] = []
    for path in _walk_files(root, patterns):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.name
        file_parent = rel
        found = False
        for match in call_re.finditer(text):
            found = True
            line = text.count("\n", 0, match.start())
            label = match.group(2).strip() or "test"
            result.append(TestCase(f"{rel}::{label}", label, str(path), line, file_parent))
        if not found:
            result.append(TestCase(rel, path.name, str(path), 0, file_parent, kind="file"))
    return result


def _dotnet_test_cases(root: Path) -> list[TestCase]:
    attr_re = re.compile(r"\[(?:Fact|Theory|Test|TestCase(?:\([^\]]*\))?|TestMethod)\][\s\S]{0,300}?\b(?:public|internal|private|protected)?\s*(?:async\s+)?(?:void|Task|ValueTask)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
    result: list[TestCase] = []
    for path in _walk_files(root, ("*.cs",)):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in attr_re.finditer(text):
            name = match.group(1)
            line = text.count("\n", 0, match.start())
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = path.name
            result.append(TestCase(f"{rel}::{name}", name, str(path), line, rel))
    return result


def discover_tests(project_root: Path, adapter_id: str) -> list[TestCase]:
    root = Path(project_root)
    adapter_id = str(adapter_id or "").lower()
    if adapter_id == "pytest":
        return _python_test_cases(root, unittest_mode=False)
    if adapter_id == "unittest":
        return _python_test_cases(root, unittest_mode=True)
    if adapter_id == "npm":
        return _js_test_cases(root)
    if adapter_id == "dotnet":
        return _dotnet_test_cases(root)
    return []


def build_test_command(project_root: Path, adapter_id: str, python_executable: str | None = None, selected_id: str = "") -> TestCommand | None:
    root = Path(project_root)
    adapter_id = str(adapter_id or "").lower()
    if adapter_id == "pytest":
        if not python_executable:
            return None
        args = ["-m", "pytest", "-vv", "--tb=short", "--disable-warnings"]
        if selected_id:
            args.append(selected_id)
        return TestCommand(adapter_id, "pytest", str(python_executable), tuple(args), root, selected_id)
    if adapter_id == "unittest":
        if not python_executable:
            return None
        if selected_id:
            args = ["-m", "unittest", "-v", selected_id]
        else:
            args = ["-m", "unittest", "discover", "-v"]
        return TestCommand(adapter_id, "unittest", str(python_executable), tuple(args), root, selected_id)
    if adapter_id == "npm":
        manager = _package_manager(root)
        program = _manager_executable(manager)
        package = _package_json(root)
        scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
        if not program or not scripts.get("test"):
            return None
        if manager == "yarn":
            args = ("test",)
        elif manager == "bun":
            args = ("run", "test")
        else:
            args = ("run", "test")
        return TestCommand(adapter_id, f"{manager} test", program, args, root, "")
    if adapter_id == "dotnet":
        program = shutil.which("dotnet.exe" if os.name == "nt" else "dotnet") or shutil.which("dotnet")
        if not program:
            return None
        return TestCommand(adapter_id, "dotnet test", program, ("test", "--logger", "console;verbosity=normal", "--nologo"), root, "")
    return None


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text or "")


def _match_discovered(nodes: list[TestCase], key: str) -> TestCase | None:
    if not key:
        return None
    exact = {node.test_id: node for node in nodes}
    if key in exact:
        return exact[key]
    short = key.replace("\\", "/")
    for node in nodes:
        test_id = node.test_id.replace("\\", "/")
        label = str(node.label or "")
        if test_id.endswith(short) or short.endswith(test_id) or label == key or (label and short.endswith(label)):
            return node
    return None


def _new_or_update(nodes: list[TestCase], key: str, status: str, message: str = "", duration: str = "") -> None:
    node = _match_discovered(nodes, key)
    if node is None:
        label = key.split("::")[-1].split(".")[-1] if key else "test"
        node = TestCase(key or label, label, status=status)
        nodes.append(node)
    node.status = status
    node.message = message
    node.duration = duration


def _parse_pytest(text: str, nodes: list[TestCase]) -> None:
    line_re = re.compile(r"^(\S.*?::\S.*?)\s+(PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)(?:\s+\[[^\]]+\])?\s*$")
    for raw in text.splitlines():
        line = raw.strip()
        match = line_re.match(line)
        if not match:
            continue
        key, word = match.groups()
        status = STATUS_PASSED if word in {"PASSED", "XPASS"} else STATUS_SKIPPED if word in {"SKIPPED", "XFAIL"} else STATUS_FAILED if word == "FAILED" else STATUS_ERROR
        _new_or_update(nodes, key, status)


def _parse_unittest(text: str, nodes: list[TestCase]) -> None:
    line_re = re.compile(r"^(test[^ ]+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped.*)$", re.IGNORECASE)
    for raw in text.splitlines():
        match = line_re.match(raw.strip())
        if not match:
            continue
        method, owner, word = match.groups()
        key = owner if owner.endswith(f".{method}") else f"{owner}.{method}"
        lower = word.lower()
        status = STATUS_PASSED if lower == "ok" else STATUS_SKIPPED if lower.startswith("skipped") else STATUS_FAILED if lower == "fail" else STATUS_ERROR
        _new_or_update(nodes, key, status, word)


def _parse_npm(text: str, nodes: list[TestCase]) -> None:
    current_file = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"^(PASS|FAIL)\s+(.+)$", line)
        if match:
            word, current_file = match.groups()
            file_key = current_file.strip().replace("\\", "/")
            matching = [node for node in nodes if str(node.path or "").replace("\\", "/").endswith(file_key)]
            if word == "PASS" and matching:
                for node in matching:
                    node.status = STATUS_PASSED
            else:
                _new_or_update(nodes, file_key, STATUS_PASSED if word == "PASS" else STATUS_FAILED)
            continue
        # Vitest/Jest verbose reporters commonly use check/cross symbols.
        match = re.match(r"^[✓✔]\s+(.+?)(?:\s+\d+ms)?$", line)
        if match:
            _new_or_update(nodes, match.group(1).strip(), STATUS_PASSED)
            continue
        match = re.match(r"^[×✕✗]\s+(.+?)(?:\s+\d+ms)?$", line)
        if match:
            _new_or_update(nodes, match.group(1).strip(), STATUS_FAILED)


def _parse_dotnet(text: str, nodes: list[TestCase]) -> None:
    line_re = re.compile(r"^(Passed|Failed|Skipped)\s+(.+?)(?:\s+\[([^\]]+)\])?$", re.IGNORECASE)
    for raw in text.splitlines():
        match = line_re.match(raw.strip())
        if not match:
            continue
        word, name, duration = match.groups()
        lower = word.lower()
        status = STATUS_PASSED if lower == "passed" else STATUS_SKIPPED if lower == "skipped" else STATUS_FAILED
        _new_or_update(nodes, name.strip(), status, duration=duration or "")


def parse_test_output(adapter_id: str, stdout: str, stderr: str, exit_code: int, discovered: list[TestCase] | None = None) -> TestRunResult:
    nodes = [TestCase(**node.to_dict()) for node in (discovered or [])]
    text = _strip_ansi("\n".join(part for part in (stdout, stderr) if part))
    adapter_id = str(adapter_id or "").lower()
    display = {"pytest": "pytest", "unittest": "unittest", "npm": "npm/Vitest/Jest", "dotnet": "dotnet test"}.get(adapter_id, adapter_id or "Tests")
    if adapter_id == "pytest":
        _parse_pytest(text, nodes)
    elif adapter_id == "unittest":
        _parse_unittest(text, nodes)
    elif adapter_id == "npm":
        _parse_npm(text, nodes)
    elif adapter_id == "dotnet":
        _parse_dotnet(text, nodes)

    passed = sum(node.status == STATUS_PASSED for node in nodes)
    failed = sum(node.status in {STATUS_FAILED, STATUS_ERROR} for node in nodes)
    skipped = sum(node.status == STATUS_SKIPPED for node in nodes)
    completed = passed + failed + skipped
    if exit_code == 0 and failed == 0:
        status = STATUS_PASSED
    else:
        status = STATUS_FAILED
    if not nodes:
        summary = "PASS" if exit_code == 0 else f"FAIL (exit {exit_code})"
    else:
        summary = f"{passed} passed · {failed} failed · {skipped} skipped · {max(0, len(nodes) - completed)} not reported"
    return TestRunResult(
        adapter_id=adapter_id,
        display_name=display,
        exit_code=int(exit_code),
        status=status,
        summary=summary,
        nodes=nodes,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def restore_test_run(value: object) -> TestRunResult | None:
    if not isinstance(value, dict):
        return None
    try:
        nodes_raw = value.get("nodes") if isinstance(value.get("nodes"), list) else []
        nodes = []
        for item in nodes_raw[:5000]:
            if not isinstance(item, dict):
                continue
            nodes.append(TestCase(
                test_id=str(item.get("test_id") or item.get("testId") or ""),
                label=str(item.get("label") or "test"),
                path=str(item.get("path") or ""),
                line=max(0, int(item.get("line") or 0)),
                parent=str(item.get("parent") or ""),
                kind=str(item.get("kind") or "test"),
                status=str(item.get("status") or STATUS_UNKNOWN),
                message=str(item.get("message") or ""),
                duration=str(item.get("duration") or ""),
            ))
        return TestRunResult(
            adapter_id=str(value.get("adapterId") or value.get("adapter_id") or ""),
            display_name=str(value.get("displayName") or value.get("display_name") or "Tests"),
            exit_code=int(value.get("exitCode") or value.get("exit_code") or 0),
            status=str(value.get("status") or STATUS_UNKNOWN),
            summary=str(value.get("summary") or ""),
            nodes=nodes,
            timestamp=str(value.get("timestamp") or ""),
        )
    except (TypeError, ValueError):
        return None
