from __future__ import annotations

from pathlib import Path
import os
import tempfile

import pytest

from core.project_templates import TEMPLATES, create_project_from_template
from core.staffedup_health import apply_safe_staffedup_fixes, inspect_staffedup_project

from core.ai_context import (
    CONTEXT_FILENAME,
    DEFAULT_MAX_FILE_BYTES,
    ProjectRoot,
    build_project_context,
    build_project_tree,
    format_problem_records,
    format_selected_text_with_line_numbers,
    format_selection_with_line_numbers,
    is_sensitive_context_path,
    normalize_roots,
    project_path_label,
    read_context_file,
    truncate_output,
    write_project_context,
)


def _roots(root: Path):
    return normalize_roots([("Main", root)])


def test_relative_path_label_for_main_and_attached_roots():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        main = base / "main"
        attached = base / "shared"
        (main / "src").mkdir(parents=True)
        (attached / "lib").mkdir(parents=True)
        roots = normalize_roots([("Main", main), ("Shared", attached)])
        assert project_path_label(main / "src", roots) == "src"
        assert project_path_label(attached / "lib", roots) == "@Shared/lib"


def test_project_under_ancestor_named_build_is_not_false_positive_excluded():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "build"
        root = base / "project"
        root.mkdir(parents=True)
        source = root / "app.py"
        source.write_text("print(1)\n", encoding="utf-8")
        assert read_context_file(source, _roots(root)).text == "print(1)\n"


def test_read_context_file_normalizes_windows_crlf_to_lf():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "windows.py"
        source.write_bytes(b"print(1)\r\nprint(2)\r\n")
        assert read_context_file(source, _roots(root)).text == "print(1)\nprint(2)\n"


def test_path_outside_project_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        root = base / "project"
        root.mkdir()
        outside = base / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        with pytest.raises(ValueError):
            read_context_file(outside, _roots(root))


def test_sensitive_files_are_blocked_but_env_example_is_allowed():
    assert is_sensitive_context_path(Path(".env"))
    assert is_sensitive_context_path(Path(".env.production"))
    assert is_sensitive_context_path(Path("id_ed25519"))
    assert is_sensitive_context_path(Path("server.key"))
    assert is_sensitive_context_path(Path("credentials.json"))
    assert not is_sensitive_context_path(Path(".env.example"))
    assert not is_sensitive_context_path(Path("secret_manager.py"))


def test_read_context_file_supports_utf8_and_cp1251():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        utf8 = root / "utf8.py"
        legacy = root / "legacy.cpp"
        utf8.write_text("print('Привет')\n", encoding="utf-8")
        legacy.write_bytes("// Привет\n".encode("cp1251"))
        roots = _roots(root)
        assert read_context_file(utf8, roots).encoding == "utf-8"
        decoded = read_context_file(legacy, roots)
        assert decoded.encoding == "cp1251"
        assert "Привет" in decoded.text


def test_binary_and_oversized_files_are_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        binary = root / "binary.txt"
        binary.write_bytes(b"a\x00b")
        with pytest.raises(ValueError, match="binary"):
            read_context_file(binary, _roots(root))
        huge = root / "huge.txt"
        huge.write_bytes(b"x" * (DEFAULT_MAX_FILE_BYTES + 1))
        with pytest.raises(ValueError, match="too large"):
            read_context_file(huge, _roots(root))


def test_symlink_file_is_rejected_even_when_target_is_inside_project():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "target.txt"
        target.write_text("hello", encoding="utf-8")
        link = root / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation unavailable")
        with pytest.raises(ValueError, match="Symlink"):
            read_context_file(link, _roots(root))


def test_selection_export_preserves_real_line_numbers_and_language_fence():
    text = "first\nsecond\nthird\nfourth\n"
    start = text.index("second") + 2
    end = text.index("fourth") - 1
    result = format_selection_with_line_numbers(text, start, end, "src/demo.py", "Python")
    assert "lines 2-3" in result
    assert "```python" in result
    assert "2 | cond" in result
    assert "3 | third" in result


def test_qt_selected_text_export_handles_utf16_emoji_and_paragraph_separators_without_offset_math():
    selected = "😀 value\u2029следующая строка"
    result = format_selected_text_with_line_numbers(selected, 7, "src/demo.py", "Python")
    assert "lines 7-8" in result
    assert "7 | 😀 value" in result
    assert "8 | следующая строка" in result


def test_selection_export_rejects_empty_selection():
    with pytest.raises(ValueError, match="No text selected"):
        format_selection_with_line_numbers("abc", 1, 1, "a.py", "Python")


def test_selection_export_uses_longer_fence_when_content_contains_backticks():
    text = "line ``` value\n"
    result = format_selection_with_line_numbers(text, 0, len(text), "README.md", "Markdown")
    assert "````markdown" in result
    assert "\n````\n" in result


def test_project_tree_excludes_generated_sensitive_context_and_symlinks():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("x=1", encoding="utf-8")
        (root / ".git").mkdir()
        (root / ".git" / "config").write_text("hidden", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "x.js").write_text("hidden", encoding="utf-8")
        (root / ".env").write_text("TOKEN=x", encoding="utf-8")
        (root / CONTEXT_FILENAME).write_text("old", encoding="utf-8")
        link = root / "external-link"
        try:
            link.symlink_to(root / "src", target_is_directory=True)
        except (OSError, NotImplementedError):
            pass
        tree = build_project_tree(_roots(root))
        assert "app.py" in tree
        assert ".git" not in tree
        assert "node_modules" not in tree
        assert ".env" not in tree
        assert CONTEXT_FILENAME not in tree
        assert "external-link" not in tree


def test_project_tree_is_deterministic_and_directories_sort_before_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "z.txt").write_text("z", encoding="utf-8")
        (root / "b").mkdir()
        (root / "a").mkdir()
        tree1 = build_project_tree(_roots(root))
        tree2 = build_project_tree(_roots(root))
        assert tree1 == tree2
        entries = [line.split("── ", 1)[1] for line in tree1.splitlines()[1:]]
        assert entries == ["a/", "b/", "z.txt"]


def test_problem_export_has_relative_location_severity_source_and_code():
    text = format_problem_records([
        {"path": "src/app.ts", "line": 12, "column": 4, "severity": "warning", "message": "Bad type", "source": "eslint", "code": "rule-x"}
    ])
    assert "WARNING" in text
    assert "src/app.ts:12:4" in text
    assert "Bad type" in text
    assert "eslint/rule-x" in text


def test_terminal_output_truncation_keeps_latest_output():
    text = "old-" + ("x" * 100) + "-latest"
    result = truncate_output(text, 20)
    assert "earlier characters omitted" in result
    assert result.endswith("-latest")
    assert "old-" not in result


def test_context_contains_only_explicitly_selected_files_and_no_absolute_paths():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        selected = root / "src.py"
        not_selected = root / "private_notes.txt"
        selected.write_text("print('selected')\n", encoding="utf-8")
        not_selected.write_text("DO NOT INCLUDE\n", encoding="utf-8")
        content = build_project_context(
            project_name="Demo",
            roots=_roots(root),
            selected_paths=[selected],
            release_name="Release 3.3",
            include_tree=False,
        )
        assert "print('selected')" in content
        assert "DO NOT INCLUDE" not in content
        assert str(root) not in content
        assert "src.py" in content


def test_context_optional_sections_are_opt_in():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "app.py"
        source.write_text("x=1\n", encoding="utf-8")
        base = build_project_context(
            project_name="Demo", roots=_roots(root), selected_paths=[source], release_name="Release 3.3", include_tree=False
        )
        assert "## Problems" not in base
        assert "## Terminal output" not in base
        assert "## Program / task output" not in base
        rich = build_project_context(
            project_name="Demo",
            roots=_roots(root),
            selected_paths=[source],
            release_name="Release 3.3",
            include_tree=False,
            problem_records=[{"path": "app.py", "line": 1, "column": 1, "severity": "error", "message": "Oops"}],
            terminal_output="terminal secret-ish output",
            program_output="program output",
        )
        assert "## Problems" in rich
        assert "terminal secret-ish output" in rich
        assert "program output" in rich


def test_context_rejects_sensitive_file_even_when_explicitly_selected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = root / ".env"
        env.write_text("TOKEN=123", encoding="utf-8")
        with pytest.raises(ValueError, match="Sensitive"):
            build_project_context(project_name="Demo", roots=_roots(root), selected_paths=[env], release_name="Release 3.3")


def test_context_requires_at_least_one_selected_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with pytest.raises(ValueError, match="Select at least one"):
            build_project_context(project_name="Demo", roots=_roots(root), selected_paths=[], release_name="Release 3.3")


def test_write_context_is_atomic_and_requires_explicit_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / CONTEXT_FILENAME
        write_project_context(target, "first\n")
        assert target.read_text(encoding="utf-8") == "first\n"
        with pytest.raises(FileExistsError):
            write_project_context(target, "second\n")
        assert target.read_text(encoding="utf-8") == "first\n"
        write_project_context(target, "second\n", overwrite=True)
        assert target.read_text(encoding="utf-8") == "second\n"
        assert not list(Path(tmp).glob(".astra_context_*.tmp"))


def test_all_staffedup_templates_gitignore_local_project_context_export():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for template in TEMPLATES:
            result = create_project_from_template(base / template.template_id, "Context Demo", template.template_id, "Release 3.3")
            gitignore = (result.project_dir / ".gitignore").read_text(encoding="utf-8")
            assert "PROJECT_CONTEXT.md" in gitignore, template.template_id


def test_staffedup_health_safe_fix_restores_context_gitignore_rule_without_touching_context_file():
    with tempfile.TemporaryDirectory() as tmp:
        result = create_project_from_template(Path(tmp) / "demo", "Context Demo", "python-app", "Release 3.3")
        gitignore = result.project_dir / ".gitignore"
        gitignore.write_text(gitignore.read_text(encoding="utf-8").replace("PROJECT_CONTEXT.md\n", ""), encoding="utf-8")
        context = result.project_dir / CONTEXT_FILENAME
        context.write_text("local private context\n", encoding="utf-8")
        report = inspect_staffedup_project(result.project_dir, "Context Demo", result.staffedup_metadata, result.config_path)
        check = next(item for item in report.checks if item.key == "gitignore")
        assert check.status == "warn"
        apply_safe_staffedup_fixes(result.project_dir, "Context Demo", result.staffedup_metadata, result.config_path)
        assert "PROJECT_CONTEXT.md" in gitignore.read_text(encoding="utf-8")
        assert context.read_text(encoding="utf-8") == "local private context\n"


def test_main_integrates_d3_ai_context_ui_and_explicit_selection_boundary():
    root = Path(__file__).resolve().parents[1]
    source = (root / "main.py").read_text(encoding="utf-8")
    assert 'QPushButton("✧  AI Context")' in source
    assert 'files_tree.setObjectName("AIContextFileTree")' in source
    assert "format_selected_text_with_line_numbers" in source
    assert "build_project_tree" in source
    assert "format_problem_records" in source
    assert "build_project_context" in source
    assert "write_project_context" in source
    assert "ничего не отправляла в сеть" in source
    assert "только файлы, которые ты явно отметил" in source
    assert "Sensitive file is blocked from AI context" in (root / "core" / "ai_context.py").read_text(encoding="utf-8")
