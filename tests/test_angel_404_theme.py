from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
WALLPAPER = ROOT / "assets" / "wallpapers" / "angel_404.png"
FONT = ROOT / "assets" / "fonts" / "minecraft.ttf"


def test_angel_404_assets_are_bundled_and_valid():
    wallpaper = WALLPAPER.read_bytes()
    assert wallpaper.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", wallpaper[16:24]) == (1672, 941)
    font = FONT.read_bytes()
    assert len(font) > 20_000
    assert font[:4] in {b"\x00\x01\x00\x00", b"OTTO"}


def test_angel_404_theme_profile_and_wallpaper_are_wired():
    text = MAIN.read_text(encoding="utf-8")
    assert 'ANGEL_404_THEME = "Angel 404: Фиолетовый сбой"' in text
    assert 'ANGEL_404_ACCENT = "Angel 404 неон"' in text
    assert 'ANGEL_404_WALLPAPER: "assets/wallpapers/angel_404.png"' in text
    assert "self.btn_apply_angel404_profile.clicked.connect(self.apply_angel404_profile)" in text
    assert 'self.global_font_name = "Minecraft Rus"' in text
    assert "def apply_angel404_profile(self):" in text


def test_minecraft_font_selection_is_global_and_persistent():
    text = MAIN.read_text(encoding="utf-8")
    assert '"Minecraft Rus": "assets/fonts/minecraft.ttf"' in text
    assert 'global_font_name = data.get("global_font_name")' in text
    assert '"global_font_name": self.global_font_name' in text
    assert "app.setFont(font)" in text
    assert "font-family: {ui_font_css};" in text
    assert "font-family: {code_font_css};" in text
    assert "editor.set_editor_font_family(custom_family)" in text
    assert "console_font = QFont(custom_family or \"Cascadia Code\")" in text


@pytest.mark.skipif(sys.platform != "win32", reason="bundled application-font runtime check is Windows-specific")
def test_minecraft_font_loads_and_reaches_editor_document():
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from main import ANGEL_404_ACCENT, ANGEL_404_THEME, ACCENTS, CodeEditor, THEMES

    app = QApplication.instance()
    assert app is not None
    font_id = QFontDatabase.addApplicationFont(str(FONT))
    families = QFontDatabase.applicationFontFamilies(font_id)
    assert families == ["Minecraft Rus"]
    theme = dict(THEMES[ANGEL_404_THEME])
    theme["accent"] = ACCENTS[ANGEL_404_ACCENT]
    editor = CodeEditor(theme, font_family=families[0])
    try:
        assert editor.font().family() == "Minecraft Rus"
        assert editor.document().defaultFont().family() == "Minecraft Rus"
        assert editor.viewport().font().family() == "Minecraft Rus"
    finally:
        editor.deleteLater()
