from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _theme():
    from main import ACCENTS, DEFAULT_ACCENT, DEFAULT_THEME, THEMES

    result = dict(THEMES[DEFAULT_THEME])
    result["accent"] = ACCENTS[DEFAULT_ACCENT]
    return result


def test_release_identity_update_fallback_and_shortcut_script_are_packaged():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    spec = (ROOT / "astra_studio.spec").read_text(encoding="utf-8")

    assert 'APP_VERSION = "Release 3.19"' in source
    assert 'PUBLIC_UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/alarongh/Astra-Studio-Releases/main/update/latest.json"' in source
    assert 'configured_manifest_url(resource_path("update_channel.json")) or PUBLIC_UPDATE_MANIFEST_URL' in source
    assert '("scripts/create_desktop_shortcut.ps1", "scripts")' in spec


def test_space_is_not_swallowed_and_commits_tab_selected_completion():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from main import CodeEditor

    app = QApplication.instance() or QApplication([])
    editor = CodeEditor(_theme(), "Java")
    editor.resize(720, 360)
    editor.show()
    editor.setFocus()

    editor.setPlainText("System.out.pr")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    from core.language_completion import completion_query

    query = completion_query("Java", editor.toPlainText(), cursor.position())
    assert query is not None and query.items
    labels = [f"{item.label}    {item.detail}" if item.detail else item.label for item in query.items]
    editor._builtin_completion_query = query
    editor._builtin_completion_items = dict(zip(labels, query.items))
    editor._builtin_completion_model.setStringList(labels)
    editor._builtin_completer.setCompletionPrefix(query.prefix)
    editor._builtin_completer.complete(editor.cursorRect())
    app.processEvents()
    popup = editor._builtin_completer.popup()
    assert popup.isVisible()

    QTest.keyClick(popup, Qt.Key.Key_Tab)
    app.processEvents()
    assert editor.toPlainText() == "System.out.pr"
    QTest.keyClick(popup, Qt.Key.Key_Space)
    app.processEvents()
    assert editor.toPlainText().startswith("System.out.pr")
    assert editor.toPlainText() != "System.out.pr"
    assert "(" in editor.toPlainText()
    assert " " in editor.toPlainText()

    editor.setPlainText("System.out.pr")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    query = completion_query("Java", editor.toPlainText(), cursor.position())
    assert query is not None and query.items
    labels = [f"{item.label}    {item.detail}" if item.detail else item.label for item in query.items]
    editor._builtin_completion_query = query
    editor._builtin_completion_items = dict(zip(labels, query.items))
    editor._builtin_completion_model.setStringList(labels)
    editor._builtin_completer.setCompletionPrefix(query.prefix)
    editor._builtin_completer.complete(editor.cursorRect())
    app.processEvents()
    assert popup.isVisible()
    QTest.keyClick(popup, Qt.Key.Key_Space)
    app.processEvents()
    assert editor.toPlainText() == "System.out.pr "
    editor.close()


def test_settings_drawer_expands_and_project_tree_yields_on_laptop(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    import main

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main, "app_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(main, "default_builds_dir", lambda: tmp_path / "builds")
    monkeypatch.setattr(main.AstraStudio, "start_terminal", lambda self: None)

    window = main.AstraStudio()
    window.resize(1366, 768)
    window.show()
    window.open_settings_page()
    app.processEvents()

    assert window.tools_drawer.width() >= 420
    assert window.project_panel.isHidden()
    assert window.workspace_surface.width() >= 500
    assert window._wallpaper_tile.size() == main.WALLPAPER_TILE_SIZE
    tile_cache_key = window._wallpaper_tile.cacheKey()

    window.resize(1600, 900)
    app.processEvents()
    assert window.tools_drawer.width() >= 500
    assert window.project_panel.isHidden()
    assert window._wallpaper_tile.cacheKey() == tile_cache_key
    assert window.background_label.pixmap().size() == window.workspace_surface.size()
    window.close()
    app.processEvents()
