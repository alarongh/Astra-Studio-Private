from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable, Sequence


CONTEXT_FILENAME = "PROJECT_CONTEXT.md"
DEFAULT_MAX_FILE_BYTES = 256 * 1024
DEFAULT_MAX_OUTPUT_CHARS = 40_000
DEFAULT_MAX_CONTEXT_CHARS = 2_000_000
DEFAULT_MAX_SELECTED_FILES = 100
DEFAULT_MAX_TREE_ENTRIES = 2_000
DEFAULT_MAX_TREE_DEPTH = 10

EXCLUDED_DIR_NAMES = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".cache", ".godot",
    "coverage", "vendor", "target", "bin", "obj", "out", ".idea", ".vs",
})

_SENSITIVE_EXACT_NAMES = frozenset({
    ".env", "credentials.json", "service-account.json", "service_account.json",
    "secrets.json", "secret.json", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    ".npmrc", ".pypirc", "netrc", ".netrc",
})
_SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"})
_SAFE_ENV_NAMES = frozenset({".env.example", ".env.sample", ".env.template"})


@dataclass(frozen=True)
class ProjectRoot:
    alias: str
    path: Path


@dataclass(frozen=True)
class ContextFile:
    path: Path
    label: str
    text: str
    encoding: str


def normalize_roots(roots: Iterable[tuple[str, Path] | ProjectRoot]) -> list[ProjectRoot]:
    result: list[ProjectRoot] = []
    seen: set[str] = set()
    for item in roots:
        root = item if isinstance(item, ProjectRoot) else ProjectRoot(str(item[0]), Path(item[1]))
        path = Path(root.path)
        if not path.exists() or not path.is_dir():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        key = str(resolved).casefold() if os.name == "nt" else str(resolved)
        if key in seen:
            continue
        seen.add(key)
        result.append(ProjectRoot(root.alias.strip() or path.name or "Project", resolved))
    return result


def project_path_label(path: Path, roots: Sequence[ProjectRoot]) -> str:
    try:
        resolved = Path(path).resolve()
    except OSError:
        resolved = Path(path).absolute()
    for index, root in enumerate(roots):
        try:
            relative = resolved.relative_to(root.path)
        except ValueError:
            continue
        rel = relative.as_posix() or "."
        if index == 0:
            return rel
        return f"@{root.alias}/{rel}"
    raise ValueError(f"Path is outside active project roots: {path}")


def path_is_inside_roots(path: Path, roots: Sequence[ProjectRoot]) -> bool:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root.path)
            return True
        except ValueError:
            continue
    return False


def is_sensitive_context_path(path: Path) -> bool:
    name = Path(path).name.lower()
    if name in _SAFE_ENV_NAMES:
        return False
    if name in _SENSITIVE_EXACT_NAMES:
        return True
    if name.startswith(".env."):
        return True
    suffix = Path(name).suffix.lower()
    if suffix in _SENSITIVE_SUFFIXES:
        return True
    # Explicit credential/secret filenames are blocked, while ordinary code such as
    # secret_manager.py is not guessed to be sensitive solely from a substring.
    stem = Path(name).stem
    if stem in {"credentials", "credential", "secrets", "secret", "private_key"}:
        return True
    return False


def is_generated_or_excluded(path: Path, roots: Sequence[ProjectRoot] | None = None) -> bool:
    candidate = Path(path)
    parts = candidate.parts
    if roots:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate.absolute()
        for root in roots:
            try:
                relative = resolved.relative_to(root.path)
            except ValueError:
                continue
            parts = relative.parts
            break
    # Only directory components are relevant here; a normal source file named
    # "build" should not be rejected merely because its filename matches a build dir.
    return any(part in EXCLUDED_DIR_NAMES for part in parts[:-1])


def _decode_context_bytes(raw: bytes) -> tuple[str, str]:
    if b"\x00" in raw:
        raise ValueError("binary file")
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1251"), "cp1251"
        except UnicodeDecodeError as exc:
            raise ValueError("unsupported text encoding") from exc


def read_context_file(path: Path, roots: Sequence[ProjectRoot], max_bytes: int = DEFAULT_MAX_FILE_BYTES) -> ContextFile:
    candidate = Path(path)
    if candidate.is_symlink():
        raise ValueError(f"Symlink is not allowed in AI context: {candidate}")
    if not candidate.exists() or not candidate.is_file():
        raise ValueError(f"File is unavailable: {candidate}")
    if not path_is_inside_roots(candidate, roots):
        raise ValueError(f"File is outside active project roots: {candidate}")
    if is_sensitive_context_path(candidate):
        raise ValueError(f"Sensitive file is blocked from AI context: {candidate.name}")
    if is_generated_or_excluded(candidate, roots):
        raise ValueError(f"Generated/dependency file is blocked from AI context: {candidate}")
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise ValueError(f"Cannot stat file: {candidate}") from exc
    if size > max_bytes:
        raise ValueError(f"File is too large for AI context ({size} bytes): {candidate.name}")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise ValueError(f"Cannot read file: {candidate}") from exc
    text, encoding = _decode_context_bytes(raw)
    # PROJECT_CONTEXT.md is a portable Markdown artifact. Normalize decoded source
    # line endings so Windows CRLF files cannot create mixed or doubled endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return ContextFile(candidate, project_path_label(candidate, roots), text, encoding)


def _safe_fence(text: str) -> str:
    runs = [len(match.group(0)) for match in re.finditer(r"`+", text)]
    return "`" * max(3, (max(runs) + 1) if runs else 3)


def language_fence(language: str | None, path: Path | None = None) -> str:
    aliases = {
        "Python": "python", "C++": "cpp", "Java": "java", "HTML": "html", "CSS": "css",
        "JavaScript": "javascript", "TypeScript": "typescript", "Luau": "lua", "GDScript": "gdscript",
        "PHP": "php", "PowerShell": "powershell", "C#": "csharp", "SQL": "sql", "JSON": "json",
        "YAML": "yaml", "Markdown": "markdown", "TOML": "toml", "XML": "xml", "Shell": "bash",
        "Dockerfile": "dockerfile",
    }
    if language in aliases:
        return aliases[language]
    if path is not None:
        suffix = path.suffix.lower().lstrip(".")
        if suffix:
            return re.sub(r"[^a-z0-9_+-]", "", suffix)[:24]
    return "text"


def markdown_inline_code(text: str) -> str:
    value = str(text).replace("\n", " ").replace("\r", " ")
    runs = [len(match.group(0)) for match in re.finditer(r"`+", value)]
    fence = "`" * max(1, (max(runs) + 1) if runs else 1)
    return f"{fence}{value}{fence}"


def format_selected_text_with_line_numbers(
    selected_text: str,
    start_line: int,
    path_label: str,
    language: str | None = None,
) -> str:
    selected = str(selected_text).replace("\u2029", "\n").replace("\u2028", "\n")
    if not selected:
        raise ValueError("No text selected")
    first_line = max(1, int(start_line))
    lines = selected.splitlines()
    if not lines:
        lines = [""]
    last_line = first_line + len(lines) - 1
    width = max(len(str(first_line)), len(str(last_line)))
    numbered = "\n".join(f"{line_no:>{width}} | {line}" for line_no, line in enumerate(lines, first_line))
    fence = _safe_fence(numbered)
    lang = language_fence(language)
    return f"### {markdown_inline_code(path_label)} · lines {first_line}-{last_line}\n\n{fence}{lang}\n{numbered}\n{fence}\n"


def format_selection_with_line_numbers(
    full_text: str,
    selection_start: int,
    selection_end: int,
    path_label: str,
    language: str | None = None,
) -> str:
    start = max(0, min(int(selection_start), len(full_text)))
    end = max(0, min(int(selection_end), len(full_text)))
    if end < start:
        start, end = end, start
    if start == end:
        raise ValueError("No text selected")
    selected = full_text[start:end]
    start_line = full_text.count("\n", 0, start) + 1
    return format_selected_text_with_line_numbers(selected, start_line, path_label, language)


def _tree_children(path: Path):
    try:
        entries = list(path.iterdir())
    except OSError:
        return []
    return sorted(entries, key=lambda p: (not p.is_dir(), p.name.casefold()))


def build_project_tree(
    roots: Sequence[ProjectRoot],
    *,
    max_entries: int = DEFAULT_MAX_TREE_ENTRIES,
    max_depth: int = DEFAULT_MAX_TREE_DEPTH,
) -> str:
    lines: list[str] = []
    count = 0
    truncated = False

    def walk(root: ProjectRoot, folder: Path, prefix: str, depth: int) -> None:
        nonlocal count, truncated
        if truncated or depth > max_depth:
            return
        children = _tree_children(folder)
        visible: list[Path] = []
        for child in children:
            if child.is_symlink():
                continue
            if child.is_dir() and child.name in EXCLUDED_DIR_NAMES:
                continue
            if child.is_file() and (is_sensitive_context_path(child) or child.name == CONTEXT_FILENAME):
                continue
            visible.append(child)
        for idx, child in enumerate(visible):
            if count >= max_entries:
                lines.append(prefix + "└── … tree truncated …")
                truncated = True
                return
            count += 1
            last = idx == len(visible) - 1
            connector = "└── " if last else "├── "
            suffix = "/" if child.is_dir() else ""
            lines.append(prefix + connector + child.name + suffix)
            if child.is_dir() and depth < max_depth:
                walk(root, child, prefix + ("    " if last else "│   "), depth + 1)

    for idx, root in enumerate(roots):
        label = root.alias if len(roots) > 1 else root.path.name
        lines.append(f"{label}/")
        walk(root, root.path, "", 1)
        if idx != len(roots) - 1:
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def truncate_output(text: str, max_chars: int = DEFAULT_MAX_OUTPUT_CHARS) -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"[… {omitted} earlier characters omitted …]\n" + value[-max_chars:]


def format_problem_records(records: Iterable[dict], max_records: int = 1000) -> str:
    items = []
    omitted = 0
    for index, item in enumerate(records):
        if index >= max_records:
            omitted += 1
            continue
        path = str(item.get("path") or "")
        line = max(1, int(item.get("line", 1)))
        column = max(1, int(item.get("column", 1)))
        severity = str(item.get("severity") or "problem")
        source = str(item.get("source") or "")
        code = str(item.get("code") or "")
        message = str(item.get("message") or "").strip().replace("\n", " ")
        if len(message) > 2000:
            message = message[:2000] + "…"
        origin = source + (f"/{code}" if code else "")
        suffix = f" [{origin}]" if origin else ""
        items.append(f"- {severity.upper()} {markdown_inline_code(f'{path}:{line}:{column}')} — {message}{suffix}")
    if omitted:
        items.append(f"- … {omitted} additional problems omitted …")
    return "\n".join(items) if items else "No current problems."


def build_project_context(
    *,
    project_name: str,
    roots: Sequence[ProjectRoot],
    selected_paths: Sequence[Path],
    release_name: str,
    include_tree: bool = True,
    problem_records: Sequence[dict] | None = None,
    terminal_output: str | None = None,
    program_output: str | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> str:
    normalized = normalize_roots(roots)
    if not normalized:
        raise ValueError("No active project roots")
    if len(selected_paths) > DEFAULT_MAX_SELECTED_FILES:
        raise ValueError(f"Too many selected files (max {DEFAULT_MAX_SELECTED_FILES})")
    selected: list[ContextFile] = []
    seen: set[str] = set()
    total_chars = 0
    for raw in selected_paths:
        ctx = read_context_file(Path(raw), normalized, max_bytes=max_file_bytes)
        key = str(ctx.path.resolve()).casefold() if os.name == "nt" else str(ctx.path.resolve())
        if key in seen:
            continue
        seen.add(key)
        total_chars += len(ctx.text)
        if total_chars > DEFAULT_MAX_CONTEXT_CHARS:
            raise ValueError(f"Selected file content is too large (max {DEFAULT_MAX_CONTEXT_CHARS} characters)")
        selected.append(ctx)
    if not selected:
        raise ValueError("Select at least one project file for PROJECT_CONTEXT.md")

    parts = [
        f"# PROJECT CONTEXT — {project_name}",
        "",
        f"> Generated locally by Astra Studio {release_name}.",
        "> Only files explicitly selected in the AI Context dialog are embedded below.",
        "> Review this document before sending it to any external AI/service.",
        "",
    ]
    if include_tree:
        parts.extend(["## Project tree", "", "```text", build_project_tree(normalized).rstrip(), "```", ""])
    if problem_records is not None:
        parts.extend(["## Problems", "", format_problem_records(problem_records), ""])
    if terminal_output is not None:
        parts.extend(["## Terminal output", "", "```text", truncate_output(terminal_output).rstrip(), "```", ""])
    if program_output is not None:
        parts.extend(["## Program / task output", "", "```text", truncate_output(program_output).rstrip(), "```", ""])

    parts.extend(["## Selected files", ""])
    for ctx in selected:
        fence = _safe_fence(ctx.text)
        lang = language_fence(None, ctx.path)
        parts.extend([
            f"### {markdown_inline_code(ctx.label)}",
            "",
            f"{fence}{lang}",
            ctx.text.rstrip("\n"),
            fence,
            "",
        ])
    return "\n".join(parts).rstrip() + "\n"


def write_project_context(target: Path, content: str, *, overwrite: bool = False) -> None:
    target = Path(target)
    if target.exists() and target.is_symlink():
        raise ValueError("Refusing to overwrite a symlink PROJECT_CONTEXT.md")
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".astra_context_", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
