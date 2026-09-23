from __future__ import annotations

import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from core.java_runtime import discover_java_runtime, java_arguments, javac_arguments
from core.language_completion import completion_query
from core.lsp_servers import DEFAULT_LSP_SERVER_CONFIGS
from core.quality_tools import parse_javac_output


ROOT = Path(__file__).resolve().parents[1]


def _labels(text: str) -> list[str]:
    query = completion_query("Java", text, len(text))
    return [item.label for item in query.items] if query else []


def test_java_registration_and_lsp_language_id_are_consistent():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '"Java": {"extension": ".java"' in source
    assert DEFAULT_LSP_SERVER_CONFIGS["Java"].language_id == "java"
    assert 'elif language == "Java":' in source


def test_java_keyword_local_member_and_standard_class_completion():
    assert "public" in _labels("pub")
    assert "class" in _labels("cla")
    assert "count" in _labels("class Main { void run() { int count = 1; cou")
    members = _labels('class Main { void run() { String text = "hi"; text.')
    assert {"length()", "substring()", "isEmpty()"}.issubset(members)
    query = completion_query("Java", "class Main { ArrayL", len("class Main { ArrayL"))
    assert query is not None
    array_list = next(item for item in query.items if item.label == "ArrayList")
    assert array_list.additional_edits
    assert "import java.util.ArrayList;" in array_list.additional_edits[0].new_text


def test_java_completion_is_suppressed_in_comments_and_strings():
    assert completion_query("Java", "// pub", len("// pub")) is None
    assert completion_query("Java", 'String text = "pub', len('String text = "pub')) is None
    assert completion_query("Java", "/* text.", len("/* text.")) is None


def test_main_snippet_is_exact_and_keyword_prefix_is_not_hijacked():
    pytest.importorskip("PySide6")
    from main import ACCENTS, CodeEditor, DEFAULT_ACCENT, DEFAULT_THEME, THEMES

    theme = dict(THEMES[DEFAULT_THEME])
    theme["accent"] = ACCENTS[DEFAULT_ACCENT]
    editor = CodeEditor(theme, "Java")
    assert editor.find_snippet_for_token("main")["label"] == "main"
    assert editor.find_snippet_for_token("mai") is None
    assert editor.find_snippet_for_token("cla") is None


def test_editor_applies_standard_class_completion_and_import():
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QTextCursor
    from main import ACCENTS, CodeEditor, DEFAULT_ACCENT, DEFAULT_THEME, THEMES

    theme = dict(THEMES[DEFAULT_THEME])
    theme["accent"] = ACCENTS[DEFAULT_ACCENT]
    editor = CodeEditor(theme, "Java")
    editor.setPlainText("public class Main { ArrayL")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    query = completion_query("Java", editor.toPlainText(), cursor.position())
    assert query is not None
    item = next(candidate for candidate in query.items if candidate.label == "ArrayList")
    display = f"{item.label}    {item.detail}"
    editor._builtin_completion_query = query
    editor._builtin_completion_items = {display: item}
    assert editor._insert_builtin_completion(display)
    assert editor.toPlainText().startswith("import java.util.ArrayList;\n\n")
    assert "public class Main { ArrayList" in editor.toPlainText()


def test_javac_diagnostics_include_line_column_severity_and_message(tmp_path: Path):
    source = tmp_path / "Main.java"
    output = f"{source}:3: error: ';' expected\n        int count = 1\n                     ^\n1 error\n"
    diagnostics = parse_javac_output(output, source)
    assert len(diagnostics) == 1
    item = diagnostics[0]
    assert item.path == source
    assert item.line == 2
    assert item.character > 0
    assert item.severity == 1
    assert item.source == "javac"
    assert "expected" in item.message


def test_java_runtime_discovery_pairs_java_with_javac(tmp_path: Path):
    first = tmp_path / "jdk-21"
    second = tmp_path / "legacy-jre"
    suffix = ".exe" if os.name == "nt" else ""
    for home in (first, second):
        (home / "bin").mkdir(parents=True)
    (first / "bin" / f"javac{suffix}").write_bytes(b"")
    (first / "bin" / f"java{suffix}").write_bytes(b"")
    (second / "bin" / f"java{suffix}").write_bytes(b"")

    def fake_which(name: str) -> str | None:
        return str(first / "bin" / f"javac{suffix}") if "javac" in name else str(second / "bin" / f"java{suffix}")

    runtime = discover_java_runtime(env={}, which=fake_which, search_standard_homes=False)
    assert runtime is not None
    assert runtime.javac.parent == runtime.java.parent == first / "bin"
    assert runtime.source == "PATH javac"


def test_missing_java_runtime_is_reported_only_when_pair_is_absent():
    runtime = discover_java_runtime(env={}, which=lambda _name: None, search_standard_homes=False)
    assert runtime is None
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '"Java": "JDK"' in source
    assert 'f"{tool_name} найден и запущен; переустановка не требуется."' in source
    assert 'if language in ("C++", "Java")' not in source


def test_java_commands_force_utf8_for_source_stdout_and_stderr():
    compile_args = javac_arguments("Main.java")
    run_args = java_arguments("build", "Main")
    assert "-encoding" in compile_args and "UTF-8" in compile_args
    assert "-J-Dstdout.encoding=UTF-8" in compile_args
    assert "-J-Dstderr.encoding=UTF-8" in compile_args
    assert "-Dfile.encoding=UTF-8" in run_args
    assert "-Dstdout.encoding=UTF-8" in run_args
    assert "-Dstderr.encoding=UTF-8" in run_args


def test_explicit_process_encoding_decodes_windows_cyrillic_without_mojibake():
    pytest.importorskip("PySide6")
    from main import _decode_process_output

    expected = "Привет, Astra Studio!"
    assert _decode_process_output(expected.encode("cp1251"), "cp1251") == expected
    assert _decode_process_output(expected.encode("utf-8"), "utf-8") == expected


def test_javac_compile_error_updates_problems_without_opening_installer(tmp_path: Path):
    pytest.importorskip("PySide6")
    from main import AstraStudio

    source = tmp_path / "Main.java"
    source.write_text("public class Main { int broken = ; }", encoding="utf-8")
    output = f"{source}:1: error: illegal start of expression\npublic class Main {{ int broken = ; }}\n                                 ^\n1 error\n"

    class Console:
        def __init__(self):
            self.lines: list[str] = []

        def appendPlainText(self, text: str):
            self.lines.append(str(text))

    diagnostics = []
    installer_requests = []
    fake = SimpleNamespace(
        active_task_context={
            "task_id": "compile_java",
            "mode": "compile",
            "language": "Java",
            "source_path": str(source),
            "javac_path": "C:/jdk/bin/javac.exe",
            "stdout_chunks": [],
            "stderr_chunks": [output],
        },
        last_run_language="Java",
        last_run_source_path=source,
        output_console=Console(),
        _set_quality_diagnostics=lambda _path, items: diagnostics.extend(items),
        write_log=lambda _text: None,
        _ask_install_now=lambda language: installer_requests.append(language),
        _finish_task_ui=lambda _success, _cancelled: None,
    )
    AstraStudio._on_task_finished(fake, "compile_java", 1, False)
    assert diagnostics and diagnostics[0].source == "javac"
    assert installer_requests == []
    assert any("переустановка не требуется" in line for line in fake.output_console.lines)


@pytest.mark.skipif(discover_java_runtime() is None, reason="paired JDK is unavailable")
def test_real_jdk_compiles_runs_and_reports_syntax_errors(tmp_path: Path):
    runtime = discover_java_runtime()
    assert runtime is not None
    source = tmp_path / "Main.java"
    expected = "ASTRA_JAVA_OK · Привет, мир!"
    source.write_text(
        'public class Main { public static void main(String[] args) { System.out.print("'
        + expected
        + '"); } }\n',
        encoding="utf-8",
    )
    compiled = subprocess.run(
        [str(runtime.javac), *javac_arguments(source)], cwd=tmp_path, capture_output=True, timeout=20
    )
    assert compiled.returncode == 0, (compiled.stdout + compiled.stderr).decode("utf-8", errors="replace")
    launched = subprocess.run(
        [str(runtime.java), *java_arguments(tmp_path, "Main")], cwd=tmp_path, capture_output=True, timeout=20
    )
    assert launched.returncode == 0
    assert launched.stdout.decode("utf-8") == expected

    source.write_text("public class Main { public static void main(String[] args) { int broken = ; } }\n", encoding="utf-8")
    failed = subprocess.run(
        [str(runtime.javac), *javac_arguments(source)], cwd=tmp_path, capture_output=True, timeout=20
    )
    assert failed.returncode != 0
    diagnostics = parse_javac_output((failed.stdout + failed.stderr).decode("utf-8", errors="replace"), source)
    assert diagnostics and diagnostics[0].severity == 1
