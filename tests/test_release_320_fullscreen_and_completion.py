from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _labels(language: str, text: str) -> set[str]:
    from core.language_completion import completion_query

    query = completion_query(language, text, len(text))
    assert query is not None, (language, text)
    return {item.label for item in query.items}


def test_java_system_streams_and_common_io_are_reachable():
    assert {"out", "err", "in"}.issubset(_labels("Java", "System."))
    assert {"print()", "printf()", "println()"}.issubset(_labels("Java", "System.out."))
    assert {"read()", "readAllBytes()", "transferTo()"}.issubset(_labels("Java", "System.in."))


def test_all_six_release_languages_have_contextual_completion():
    assert {"getcwd()", "listdir()", "walk()"}.issubset(_labels("Python", "import os\nos."))
    assert {"push_back()", "size()", "reserve()"}.issubset(_labels("C++", "std::vector<int> items; items."))
    assert {"log()", "error()", "table()"}.issubset(_labels("JavaScript", "console."))
    assert {"getElementById()", "querySelector()", "createElement()"}.issubset(_labels("JavaScript", "document."))
    assert "dialog" in _labels("HTML", "<dia")
    assert "div" in _labels("HTML", "<div></")
    assert {"flex", "flow-root"}.issubset(_labels("CSS", ".panel { display: fl"))
    assert {"grid-template", "grid-template-columns"}.issubset(_labels("CSS", ".panel { grid-tem"))


def test_wallpaper_is_single_image_and_project_frame_is_stable():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "painter.drawTiledPixmap" not in source
    assert "painter.drawPixmap(x, y, self._wallpaper_tile)" in source
    assert 'self.main_splitter.setObjectName("MainSplitter")' in source
    assert "self.project_panel.setMinimumWidth(270)" in source
    assert "self.main_splitter.setHandleWidth(8)" in source


def test_settings_replace_editor_with_full_page(monkeypatch, tmp_path: Path):
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
    assert window.main_page_stack.currentWidget() is window.settings_page
    assert window.settings_page.width() >= 1000
    assert not window.root_splitter.isVisible()
    assert not window.tools_drawer.isVisible()

    window.close_settings_page()
    app.processEvents()
    assert window.main_page_stack.currentIndex() == 0
    assert window.root_splitter.isVisible()
    window.close()
    app.processEvents()
