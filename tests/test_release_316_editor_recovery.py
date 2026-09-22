from __future__ import annotations

from pathlib import Path

import pytest

from core.language_completion import completion_query


ROOT = Path(__file__).resolve().parents[1]


def _items(language: str, text: str):
    query = completion_query(language, text, len(text))
    return {item.label: item for item in query.items} if query else {}


def test_context_completion_covers_python_javascript_html_and_css():
    assert "append()" in _items("Python", "items = []\nitems.ap")
    assert _items("Python", "pri")["print"].insert_text == "print()"
    assert "log()" in _items("JavaScript", "console.lo")
    html = _items("HTML", "<sec")["section"]
    assert html.insert_text == "section></section>"
    assert html.cursor_offset == len("section>")
    css = _items("CSS", ".card {\n  backg")["background"]
    assert css.insert_text == "background: ;"
    assert css.cursor_offset == len("background: ")


def test_editor_auto_indent_pairing_folding_and_live_error_line():
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QTextCursor
    from main import ACCENTS, CodeEditor, DEFAULT_ACCENT, DEFAULT_THEME, THEMES

    theme = dict(THEMES[DEFAULT_THEME])
    theme["accent"] = ACCENTS[DEFAULT_ACCENT]
    editor = CodeEditor(theme, "Python")
    editor.setPlainText("def demo():\n    print('ok')\n    return 1\n\nprint(demo())")
    assert editor.is_foldable_line(0)
    assert editor.toggle_fold(0)
    assert not editor.document().findBlockByNumber(1).isVisible()
    assert editor.toggle_fold(0)
    assert editor.document().findBlockByNumber(1).isVisible()

    editor.setPlainText("if True:")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    assert editor._smart_newline()
    assert editor.toPlainText() == "if True:\n    "

    editor.setPlainText("if True:\n    print('missing'")
    editor._refresh_live_syntax_diagnostics()
    assert editor._syntax_diagnostics
    assert editor._syntax_diagnostics[0]["line"] == 1
    assert "closed" in editor._syntax_diagnostics[0]["message"].lower() or "never" in editor._syntax_diagnostics[0]["message"].lower()


def test_wallpaper_scope_and_compact_layout_are_not_full_window():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'self.workspace_surface.setObjectName("WorkspaceSurface")' in source
    assert "self.background_label.setParent(self.workspace_surface)" in source
    assert "self.wallpaper_dim_overlay.setParent(self.workspace_surface)" in source
    assert "compact = self.width() < 1220 and not self.tools_drawer.isHidden()" in source
    assert "self.project_panel.setVisible(False)" in source
    assert "self.wallpaper_all_windows = False" in source
    assert "self.setMinimumSize(760, 520)" in source


def test_experimental_synthetic_input_entry_is_removed_from_ui():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "self.btn_enter_typer.setVisible(False)" in source
