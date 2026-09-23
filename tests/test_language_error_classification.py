from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from core.quality_tools import parse_linter_output


def test_python_compile_diagnostic_points_to_source_line():
    source = Path(r"C:\project\broken.py")
    output = (
        f'  File "{source}", line 3\n'
        "    if ???:\n"
        "       ^\n"
        "SyntaxError: invalid syntax\n"
    )
    diagnostics = parse_linter_output("python-compile", output, source)
    assert len(diagnostics) == 1
    assert diagnostics[0].line == 2
    assert diagnostics[0].source == "Python compiler"
    assert "SyntaxError" in diagnostics[0].message


def test_node_diagnostic_points_to_source_line():
    source = Path(r"C:\project\broken.js")
    output = (
        f"{source}:4\n"
        "  const = nonsense;\n"
        "        ^\n\n"
        "SyntaxError: Unexpected token '='\n"
    )
    diagnostics = parse_linter_output("node-check", output, source)
    assert len(diagnostics) == 1
    assert diagnostics[0].line == 3
    assert diagnostics[0].source == "Node.js"
    assert "Unexpected token" in diagnostics[0].message


def test_java_runtime_diagnostic_points_to_source_line():
    source = Path(r"C:\project\Main.java")
    output = (
        'Exception in thread "main" java.lang.NullPointerException: broken\n'
        "\tat Main.main(Main.java:7)\n"
    )
    diagnostics = parse_linter_output("java-runtime", output, source)
    assert len(diagnostics) == 1
    assert diagnostics[0].line == 6
    assert diagnostics[0].source == "Java runtime"


def test_real_python_and_javascript_compile_errors_never_open_installer(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    import main

    node = shutil.which("node.exe") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main, "app_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(main, "default_builds_dir", lambda: tmp_path / "builds")
    monkeypatch.setattr(main.AstraStudio, "start_terminal", lambda self: None)
    window = main.AstraStudio()
    asked: list[str] = []
    monkeypatch.setattr(window, "_ask_install_now", lambda language: asked.append(language))

    cases = [
        (
            "Python",
            "compile_python_probe",
            sys.executable,
            ["-m", "py_compile", str(tmp_path / "broken.py")],
            tmp_path / "broken.py",
            "def main():\n    print('ok')\n    if ???:\n        pass\n",
            2,
        ),
        (
            "JavaScript",
            "compile_js_probe",
            node,
            ["--check", str(tmp_path / "broken.js")],
            tmp_path / "broken.js",
            "function main() {\n  console.log('ok');\n  const = nonsense;\n}\n",
            2,
        ),
    ]

    for language, task_id, program, arguments, source_path, text, expected_line in cases:
        source_path.write_text(text, encoding="utf-8")
        window.last_run_language = language
        window.last_run_source_path = source_path
        loop = QEventLoop()
        result: dict[str, int] = {}

        def finished(done_task_id, code, _cancelled):
            if done_task_id == task_id:
                result["exit"] = int(code)
                loop.quit()

        window.task_manager.taskFinished.connect(finished)
        window._start_process_task(
            task_id,
            f"{language} error probe",
            program,
            arguments,
            tmp_path,
            {
                "mode": "compile",
                "language": language,
                "source_path": str(source_path),
                "tool_path": str(program),
                "stdout_chunks": [],
                "stderr_chunks": [],
            },
        )
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        window.task_manager.taskFinished.disconnect(finished)

        assert result.get("exit", 0) != 0
        diagnostics = window.quality_diagnostics[str(source_path.resolve())]
        assert diagnostics and diagnostics[0].line == expected_line
        assert "переустановка не требуется" in window.output_console.toPlainText()

    assert asked == []
    window.close()
    app.processEvents()


def test_html_and_css_checks_do_not_depend_on_language_installers(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication
    import main

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main, "app_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(main, "default_builds_dir", lambda: tmp_path / "builds")
    monkeypatch.setattr(main.AstraStudio, "start_terminal", lambda self: None)
    window = main.AstraStudio()
    asked: list[str] = []
    monkeypatch.setattr(window, "_ask_install_now", lambda language: asked.append(language))
    editor = window.current_editor()
    assert editor is not None

    editor.language_name = "HTML"
    editor.setPlainText("<!doctype html><p>ordinary text is valid HTML</p>")
    assert window.compile_code() is True
    assert "HTML не требует компиляции" in window.output_console.toPlainText()

    editor.language_name = "CSS"
    editor.setPlainText(".card { color: red; }")
    assert window.compile_code() is True
    assert "CSS не требует компиляции" in window.output_console.toPlainText()
    assert asked == []

    window.close()
    app.processEvents()
