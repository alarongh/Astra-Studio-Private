from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


def _source() -> str:
    return MAIN.read_text(encoding="utf-8")


def _tree() -> ast.Module:
    return ast.parse(_source())


def test_release_3_5_identity():
    tree = _tree()
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "APP_VERSION" for t in node.targets)
    )
    assert ast.literal_eval(assignment.value) == "Release 3.11"


def test_settings_are_inline_in_tools_drawer_not_external_dialog():
    source = _source()
    assert "self.tools_stack.addWidget(self.settings_scroll)" in source
    assert 'self._show_tools_drawer(1, "НАСТРОЙКИ")' in source
    assert "settings_dialog" not in source


def test_editor_and_console_transparency_are_not_artificially_clamped_opaque():
    source = _source()
    assert 'self._panel_rgba(self.theme["editor"], self.editor_bg_transparency_percent, 8)' in source
    assert 'self._panel_rgba(self.theme["console"], self.console_bg_transparency_percent, 8)' in source
    assert 'editor_blur_percent = data.get("editor_blur_percent")' in source
    assert '"editor_blur_percent": self.editor_blur_percent' in source
    assert 'self.editor_blur_slider.valueChanged.connect(lambda value: self.change_secondary_blur("editor", value))' in source


def test_integrated_console_replaces_separate_stdin_line_edits():
    source = _source()
    assert "class InteractiveConsole(QPlainTextEdit):" in source
    assert 'self.output_console = InteractiveConsole(prompt="› ")' in source
    assert 'self.terminal_console = InteractiveConsole(prompt="")' in source
    assert "self.output_console.set_submit_callback(self.send_run_stdin_text)" in source
    assert "self.terminal_console.set_submit_callback(self.send_terminal_command_text)" in source
    assert "run_input" not in source
    assert "terminal_input" not in source


def test_project_tree_cannot_restore_as_fully_collapsed():
    source = _source()
    assert "self.main_splitter.setCollapsible(0, False)" in source
    assert "main_sizes[0] = max(260" in source


def test_python_manager_supports_arbitrary_pypi_and_unknown_import_fallback():
    source = _source()
    assert "def install_arbitrary_pypi_requirement" in source
    assert "python_unknown_auto_install_enabled" in source
    assert "PyPI fallback по имени import" in source
    assert "_run_pip_for_records(candidates, rerun_after=True)" in source
    assert "Установить доступные пакеты одним действием" in source


def test_test_dependencies_and_one_click_acceptance_runner_are_bundled():
    requirements = (ROOT / "requirements-test.txt").read_text(encoding="ascii")
    assert "pytest" in requirements.lower()
    install = (ROOT / "install_app.bat").read_text(encoding="ascii")
    assert "requirements-test.txt" in install
    runner = (ROOT / "run_acceptance_tests.bat").read_text(encoding="ascii")
    assert "-m pytest -q -rs" in runner
    assert (ROOT / "reinstall_app.bat").is_file()


def test_all_batch_files_remain_ascii_crlf_after_3_5_changes():
    for path in ROOT.glob("*.bat"):
        data = path.read_bytes()
        assert data.count(b"\n") == data.count(b"\r\n"), path.name
        assert not data.startswith(b"\xef\xbb\xbf"), path.name
        data.decode("ascii")
