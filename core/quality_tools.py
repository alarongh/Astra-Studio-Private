from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
from typing import Iterable


FORMATTER_BY_LANGUAGE: dict[str, str] = {
    "Python": "ruff",
    "JavaScript": "prettier",
    "TypeScript": "prettier",
    "HTML": "prettier",
    "CSS": "prettier",
    "JSON": "prettier",
    "YAML": "prettier",
    "Markdown": "prettier",
    "C++": "clang-format",
    "Luau": "stylua",
    "Lua": "stylua",
}

LINTER_BY_LANGUAGE: dict[str, str] = {
    "Python": "ruff",
    "JavaScript": "eslint",
    "TypeScript": "eslint",
}


@dataclass(frozen=True, slots=True)
class QualityCommand:
    tool_id: str
    display_name: str
    kind: str  # formatter | linter | installer
    program: str
    arguments: tuple[str, ...]
    workdir: Path
    stdin_text: str | None = None
    parser: str = ""
    accepted_exit_codes: tuple[int, ...] = (0,)


@dataclass(frozen=True, slots=True)
class QualityDiagnostic:
    path: Path
    line: int
    character: int
    end_line: int
    end_character: int
    severity: int
    message: str
    source: str
    code: str = ""


def formatter_tool_for_language(language: str) -> str | None:
    return FORMATTER_BY_LANGUAGE.get(str(language or ""))


def linter_tool_for_language(language: str) -> str | None:
    return LINTER_BY_LANGUAGE.get(str(language or ""))


def _node_bin_names(name: str) -> tuple[str, ...]:
    if os.name == "nt":
        return (f"{name}.cmd", f"{name}.exe", name)
    return (name,)


def _candidate_paths(project_root: Path, names: Iterable[str]) -> Iterable[Path]:
    root = Path(project_root)
    for name in names:
        yield root / "node_modules" / ".bin" / name
        yield root / ".venv" / "Scripts" / name
        yield root / "venv" / "Scripts" / name
        yield root / ".venv" / "bin" / name
        yield root / "venv" / "bin" / name


def resolve_quality_executable(tool_id: str, project_root: Path, python_executable: str | None = None) -> str | None:
    tool_id = str(tool_id or "").strip().lower()
    root = Path(project_root)
    if tool_id in {"prettier", "eslint", "stylua"}:
        names = _node_bin_names("stylua" if tool_id == "stylua" else tool_id)
    elif tool_id == "clang-format":
        names = ("clang-format.exe", "clang-format") if os.name == "nt" else ("clang-format",)
    elif tool_id == "ruff":
        names = ("ruff.exe", "ruff") if os.name == "nt" else ("ruff",)
    else:
        names = (tool_id,)

    for candidate in _candidate_paths(root, names):
        if candidate.is_file():
            return str(candidate)

    if tool_id == "ruff" and python_executable:
        py = Path(python_executable)
        script_dir = py.parent
        for name in names:
            candidate = script_dir / name
            if candidate.is_file():
                return str(candidate)

    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved

    if os.name == "nt" and tool_id == "clang-format":
        for candidate in (
            Path(r"C:\Program Files\LLVM\bin\clang-format.exe"),
            Path(r"C:\msys64\ucrt64\bin\clang-format.exe"),
            Path(r"C:\msys64\mingw64\bin\clang-format.exe"),
            Path(r"C:\msys64\clang64\bin\clang-format.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
    return None


def formatter_command(
    language: str,
    file_path: Path,
    project_root: Path,
    source_text: str,
    python_executable: str | None = None,
) -> QualityCommand | None:
    tool_id = formatter_tool_for_language(language)
    if not tool_id:
        return None
    program = resolve_quality_executable(tool_id, project_root, python_executable)
    if not program:
        return None
    path = Path(file_path)
    root = Path(project_root)
    if tool_id == "ruff":
        args = ("format", "--stdin-filename", str(path), "-")
        name = "Ruff Formatter"
    elif tool_id == "prettier":
        args = ("--stdin-filepath", str(path))
        name = "Prettier"
    elif tool_id == "clang-format":
        args = ("-style=file", "-fallback-style=LLVM", f"-assume-filename={path}")
        name = "clang-format"
    elif tool_id == "stylua":
        args = ("--verify", "--stdin-filepath", str(path), "-")
        name = "StyLua"
    else:
        return None
    return QualityCommand(
        tool_id=tool_id,
        display_name=name,
        kind="formatter",
        program=program,
        arguments=args,
        workdir=root,
        stdin_text=source_text,
        accepted_exit_codes=(0,),
    )


def linter_command(
    language: str,
    file_path: Path,
    project_root: Path,
    source_text: str,
    python_executable: str | None = None,
) -> QualityCommand | None:
    tool_id = linter_tool_for_language(language)
    if not tool_id:
        return None
    program = resolve_quality_executable(tool_id, project_root, python_executable)
    if not program:
        return None
    path = Path(file_path)
    root = Path(project_root)
    if tool_id == "ruff":
        args = ("check", "--stdin-filename", str(path), "--output-format", "json", "-")
        return QualityCommand(
            tool_id="ruff",
            display_name="Ruff",
            kind="linter",
            program=program,
            arguments=args,
            workdir=root,
            stdin_text=source_text,
            parser="ruff-json",
            accepted_exit_codes=(0, 1),
        )
    if tool_id == "eslint":
        # ESLint can lint stdin while using the actual filename for config and parser selection.
        args = ("--stdin", "--stdin-filename", str(path), "--format", "json", "--no-color")
        return QualityCommand(
            tool_id="eslint",
            display_name="ESLint",
            kind="linter",
            program=program,
            arguments=args,
            workdir=root,
            stdin_text=source_text,
            parser="eslint-json",
            accepted_exit_codes=(0, 1),
        )
    return None


def install_plan_for_quality_tool(
    tool_id: str,
    project_root: Path,
    python_executable: str | None = None,
) -> QualityCommand | None:
    tool_id = str(tool_id or "").strip().lower()
    root = Path(project_root)
    if tool_id == "ruff":
        if python_executable:
            return QualityCommand(
                tool_id=tool_id,
                display_name="Ruff",
                kind="installer",
                program=str(python_executable),
                arguments=("-m", "pip", "install", "--upgrade", "ruff"),
                workdir=root,
            )
        return None
    if tool_id in {"prettier", "eslint"}:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
        if not npm or not (root / "package.json").is_file():
            return None
        if tool_id == "prettier":
            args = ("install", "--save-dev", "--save-exact", "prettier")
            name = "Prettier"
        else:
            args = ("install", "--save-dev", "--save-exact", "eslint")
            name = "ESLint"
        return QualityCommand(tool_id, name, "installer", npm, args, root)
    if tool_id == "stylua":
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
        if not npm or not (root / "package.json").is_file():
            return None
        return QualityCommand(
            tool_id,
            "StyLua",
            "installer",
            npm,
            ("install", "--save-dev", "--save-exact", "@johnnymorganz/stylua-bin"),
            root,
        )
    if tool_id == "clang-format" and os.name == "nt":
        winget = shutil.which("winget.exe") or shutil.which("winget")
        if winget:
            return QualityCommand(
                tool_id,
                "clang-format (LLVM)",
                "installer",
                winget,
                (
                    "install", "--id", "LLVM.LLVM", "-e", "--accept-package-agreements", "--accept-source-agreements",
                ),
                root,
            )
    return None


def _severity_from_eslint(value: object) -> int:
    try:
        severity = int(value)
    except (TypeError, ValueError):
        severity = 1
    return 1 if severity >= 2 else 2


def parse_ruff_json(output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    try:
        payload = json.loads(output or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    result: list[QualityDiagnostic] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        loc = item.get("location") or {}
        end = item.get("end_location") or loc
        filename = item.get("filename") or str(fallback_path)
        try:
            path = Path(filename)
            line = max(0, int(loc.get("row", 1)) - 1)
            column = max(0, int(loc.get("column", 1)) - 1)
            end_line = max(line, int(end.get("row", line + 1)) - 1)
            end_column = max(0, int(end.get("column", column + 1)) - 1)
        except (TypeError, ValueError):
            continue
        result.append(QualityDiagnostic(
            path=path,
            line=line,
            character=column,
            end_line=end_line,
            end_character=end_column,
            severity=2,
            message=str(item.get("message") or "Ruff diagnostic"),
            source="Ruff",
            code=str(item.get("code") or ""),
        ))
    return result


def parse_eslint_json(output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    try:
        payload = json.loads(output or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    result: list[QualityDiagnostic] = []
    for file_result in payload:
        if not isinstance(file_result, dict):
            continue
        path = Path(file_result.get("filePath") or fallback_path)
        messages = file_result.get("messages") or []
        if not isinstance(messages, list):
            continue
        for item in messages:
            if not isinstance(item, dict):
                continue
            try:
                line = max(0, int(item.get("line") or 1) - 1)
                column = max(0, int(item.get("column") or 1) - 1)
                end_line = max(line, int(item.get("endLine") or line + 1) - 1)
                end_column = max(0, int(item.get("endColumn") or column + 1) - 1)
            except (TypeError, ValueError):
                continue
            result.append(QualityDiagnostic(
                path=path,
                line=line,
                character=column,
                end_line=end_line,
                end_character=end_column,
                severity=_severity_from_eslint(item.get("severity")),
                message=str(item.get("message") or "ESLint diagnostic"),
                source="ESLint",
                code=str(item.get("ruleId") or ""),
            ))
    return result


def parse_javac_output(output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    """Parse standard and localized javac diagnostics from a single-file compile."""
    lines = str(output or "").replace("\r\n", "\n").splitlines()
    pattern = re.compile(
        r"^(?P<path>.+?\.java):(?P<line>\d+):\s*"
        r"(?P<severity>error|warning|ошибка|предупреждение):\s*(?P<message>.*)$",
        re.IGNORECASE,
    )
    result: list[QualityDiagnostic] = []
    for index, line_text in enumerate(lines):
        match = pattern.match(line_text.strip())
        if not match:
            continue
        severity_text = match.group("severity").lower()
        severity = 2 if severity_text in {"warning", "предупреждение"} else 1
        character = 0
        # javac normally prints source text followed by a caret line.
        for candidate in lines[index + 1:index + 4]:
            caret = candidate.find("^")
            if caret >= 0:
                character = caret
                break
        try:
            line_number = max(0, int(match.group("line")) - 1)
        except ValueError:
            line_number = 0
        result.append(QualityDiagnostic(
            path=Path(fallback_path),
            line=line_number,
            character=character,
            end_line=line_number,
            end_character=character + 1,
            severity=severity,
            message=match.group("message").strip() or "javac diagnostic",
            source="javac",
        ))
    return result


def parse_cpp_compiler_output(output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    """Parse GCC/Clang diagnostics, including Windows drive-letter paths."""
    pattern = re.compile(
        r"^(?P<path>.+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?P<severity>fatal error|error|warning|note):\s*(?P<message>.+)$",
        re.IGNORECASE,
    )
    result: list[QualityDiagnostic] = []
    seen: set[tuple[int, int, str]] = set()
    for raw_line in str(output or "").replace("\r\n", "\n").splitlines():
        match = pattern.match(raw_line.strip())
        if not match:
            continue
        try:
            line = max(0, int(match.group("line")) - 1)
            character = max(0, int(match.group("column")) - 1)
        except ValueError:
            continue
        severity_text = match.group("severity").lower()
        severity = 1 if severity_text in {"error", "fatal error"} else (2 if severity_text == "warning" else 3)
        message = match.group("message").strip() or "C++ compiler diagnostic"
        key = (line, character, message)
        if key in seen:
            continue
        seen.add(key)
        result.append(QualityDiagnostic(
            path=Path(fallback_path),
            line=line,
            character=character,
            end_line=line,
            end_character=character + 1,
            severity=severity,
            message=message,
            source="C++ compiler",
        ))
    return result


def parse_python_compile_output(output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    """Parse ``python -m py_compile`` syntax diagnostics."""
    lines = str(output or "").replace("\r\n", "\n").splitlines()
    location = re.compile(r'^\s*File "(?P<path>.+)", line (?P<line>\d+)\s*$')
    result: list[QualityDiagnostic] = []
    for index, line_text in enumerate(lines):
        match = location.match(line_text)
        if not match:
            continue
        character = 0
        message = "Python syntax error"
        for candidate in lines[index + 1:index + 6]:
            caret = candidate.find("^")
            if caret >= 0:
                character = caret
            stripped = candidate.strip()
            if stripped.startswith(("SyntaxError:", "IndentationError:", "TabError:")):
                message = stripped
                break
        line_number = max(0, int(match.group("line")) - 1)
        result.append(QualityDiagnostic(
            path=Path(fallback_path),
            line=line_number,
            character=character,
            end_line=line_number,
            end_character=character + 1,
            severity=1,
            message=message,
            source="Python compiler",
        ))
    return result


def parse_node_diagnostic_output(output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    """Parse Node.js syntax/runtime diagnostics that start with ``path:line``."""
    lines = str(output or "").replace("\r\n", "\n").splitlines()
    location = re.compile(r"^(?P<path>.+\.(?:js|mjs|cjs|jsx)):(?P<line>\d+)\s*$", re.IGNORECASE)
    result: list[QualityDiagnostic] = []
    seen: set[tuple[int, int, str]] = set()
    for index, line_text in enumerate(lines):
        match = location.match(line_text.strip())
        if not match:
            continue
        character = 0
        message = "JavaScript error"
        for candidate in lines[index + 1:index + 8]:
            caret = candidate.find("^")
            if caret >= 0:
                character = caret
            stripped = candidate.strip()
            if re.match(r"^(?:SyntaxError|ReferenceError|TypeError|RangeError|URIError|EvalError):", stripped):
                message = stripped
                break
        line_number = max(0, int(match.group("line")) - 1)
        key = (line_number, character, message)
        if key in seen:
            continue
        seen.add(key)
        result.append(QualityDiagnostic(
            path=Path(fallback_path),
            line=line_number,
            character=character,
            end_line=line_number,
            end_character=character + 1,
            severity=1,
            message=message,
            source="Node.js",
        ))
    return result


def parse_java_runtime_output(output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    """Parse Java stack frames and point Problems at the user's source line."""
    pattern = re.compile(r"\bat\s+[\w.$<>]+\((?P<file>[^():]+\.java):(?P<line>\d+)\)")
    message = next(
        (line.strip() for line in str(output or "").splitlines() if "Exception" in line or "Error" in line),
        "Java runtime error",
    )
    for line_text in str(output or "").replace("\r\n", "\n").splitlines():
        match = pattern.search(line_text)
        if not match:
            continue
        line_number = max(0, int(match.group("line")) - 1)
        return [QualityDiagnostic(
            path=Path(fallback_path),
            line=line_number,
            character=0,
            end_line=line_number,
            end_character=1,
            severity=1,
            message=message,
            source="Java runtime",
        )]
    return []


def parse_linter_output(parser: str, output: str, fallback_path: Path) -> list[QualityDiagnostic]:
    if parser == "ruff-json":
        return parse_ruff_json(output, fallback_path)
    if parser == "eslint-json":
        return parse_eslint_json(output, fallback_path)
    if parser == "javac":
        return parse_javac_output(output, fallback_path)
    if parser in {"gcc", "g++", "clang", "clang++", "cpp-compiler"}:
        return parse_cpp_compiler_output(output, fallback_path)
    if parser == "python-compile":
        return parse_python_compile_output(output, fallback_path)
    if parser in {"node-check", "node-runtime"}:
        return parse_node_diagnostic_output(output, fallback_path)
    if parser == "java-runtime":
        return parse_java_runtime_output(output, fallback_path)
    return []
