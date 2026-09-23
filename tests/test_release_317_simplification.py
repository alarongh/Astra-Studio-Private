from __future__ import annotations

from pathlib import Path

import pytest

from core.quality_tools import parse_linter_output


ROOT = Path(__file__).resolve().parents[1]


def test_cpp_compiler_diagnostic_points_to_actual_source_line():
    source = Path(r"C:\Users\student\project\main.cpp")
    output = (
        r"C:\Users\student\project\main.cpp:17:5: error: 'ds' was not declared in this scope"
        "\n"
        r"C:\Users\student\project\main.cpp:17:8: warning: left operand has no effect"
    )
    diagnostics = parse_linter_output("cpp-compiler", output, source)

    assert len(diagnostics) == 2
    assert diagnostics[0].path == source
    assert diagnostics[0].line == 16
    assert diagnostics[0].character == 4
    assert diagnostics[0].severity == 1
    assert diagnostics[0].source == "C++ compiler"


def test_cpp_failure_is_not_misreported_as_missing_compiler():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert '"C++": "cpp-compiler"' in source
    assert '"C++": "C++ компилятор"' in source
    assert 'f"{tool_name} найден и запущен; переустановка не требуется."' in source
    assert "elif language == \"C++\":\n                    self._ask_install_now(language)" not in source
    assert 'compiler = cpp_compiler_path()' in source


def test_customization_is_simplified_and_shortcut_moved_to_settings():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert 'QLabel("Стиль оформления")' in source
    assert 'self.design_profile_combo.addItems(APPEARANCE_PROFILES)' in source
    assert 'QLabel("ЯРЛЫК WINDOWS")' in source
    assert 'self.btn_desktop_shortcut.clicked.connect(self.create_or_update_desktop_shortcut)' in source
    assert 'installer_buttons_1.addWidget(self.shortcut_icon_combo)' not in source
    assert 'return common + python_script + uv_script + node_script + cpp_script + java_script + "Astra-Progress 100\\n"' in source
    assert "appearance_advanced_toggle" not in source
    assert "editor_transparency_slider" not in source
    assert "console_transparency_slider" not in source


def test_removed_synthetic_input_feature_is_not_shipped():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "Имитация ввода" not in source
    assert "ENTER_TYPER_TEMPLATE" not in source
    assert "btn_enter_typer" not in source
    assert "ensure_python_packages_for_enter_typer" not in source


def test_settings_page_owns_shortcut_and_simple_appearance_controls(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication
    import main

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main, "app_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(main, "default_builds_dir", lambda: tmp_path / "builds")
    monkeypatch.setattr(main.AstraStudio, "start_terminal", lambda self: None)

    window = main.AstraStudio()
    settings_card = window.settings_scroll.widget()
    installer_card = window.tools_stack.widget(0)

    assert settings_card.isAncestorOf(window.shortcut_icon_combo)
    assert settings_card.isAncestorOf(window.btn_desktop_shortcut)
    assert not installer_card.isAncestorOf(window.shortcut_icon_combo)
    assert window.design_profile_combo.count() == 2
    assert window.wallpaper_blur_slider.maximum() == 60
    assert window.panel_transparency_slider.maximum() == 70
    assert not hasattr(window, "appearance_advanced_toggle")
    assert not hasattr(window, "opacity_slider")

    window.close()
    app.processEvents()


def test_real_cpp_error_marks_line_without_opening_installer(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    import main

    compiler = main.cpp_compiler_path()
    if not compiler:
        pytest.skip("C++ compiler is not available")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main, "app_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(main, "default_builds_dir", lambda: tmp_path / "builds")
    monkeypatch.setattr(main.AstraStudio, "start_terminal", lambda self: None)
    window = main.AstraStudio()
    asked: list[str] = []
    monkeypatch.setattr(window, "_ask_install_now", lambda language: asked.append(language))

    source_path = tmp_path / "broken.cpp"
    source_path.write_text(
        "int main() {\n    int value = 1;\n    ds.jd,jsda\n    return value;\n}\n",
        encoding="utf-8",
    )
    window.last_run_language = "C++"
    window.last_run_source_path = source_path
    loop = QEventLoop()
    result: dict[str, int] = {}
    window.task_manager.taskFinished.connect(
        lambda _task_id, code, _cancelled: (result.__setitem__("exit", int(code)), loop.quit())
    )
    assert window._start_compile_cpp_task(source_path, run_after=False) is None
    QTimer.singleShot(15000, loop.quit)
    loop.exec()

    assert result.get("exit", 0) != 0
    assert asked == []
    diagnostics = window.quality_diagnostics[str(source_path.resolve())]
    assert diagnostics
    assert any(item.line == 2 for item in diagnostics)
    assert "переустановка не требуется" in window.output_console.toPlainText()

    window.close()
    app.processEvents()
