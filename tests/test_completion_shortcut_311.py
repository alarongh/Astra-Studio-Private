from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from core.language_completion import CompletionItem, CompletionQuery, completion_query


ROOT = Path(__file__).resolve().parents[1]


def _labels(language: str, text: str) -> set[str]:
    query = completion_query(language, text, len(text))
    return {item.label for item in query.items} if query else set()


def test_offline_completion_catalog_covers_major_astra_languages():
    cases = {
        ("Python", "pri"): "print",
        ("C++", "uniq"): "unique_ptr",
        ("JavaScript", "fetc"): "fetch",
        ("TypeScript", "interf"): "interface",
        ("C#", "Dict"): "Dictionary",
        ("PHP", "funct"): "function",
        ("PowerShell", "Get-Ch"): "Get-ChildItem",
        ("SQL", "SEL"): "SELECT",
        ("HTML", "<but"): "button",
        ("CSS", "backg"): "background",
        ("GDScript", "prel"): "preload",
        ("Luau", "pc"): "pcall",
        ("Shell", "pri"): "printf",
        ("Dockerfile", "ENT"): "ENTRYPOINT",
    }
    for (language, text), expected in cases.items():
        assert expected in _labels(language, text), (language, text, expected)


def test_java_completion_library_includes_more_classes_and_chained_members():
    assert "CompletableFuture" in _labels("Java", "CompletableF")
    assert "StringBuilder" in _labels("Java", "StringB")
    assert {"print()", "printf()", "println()"}.issubset(_labels("Java", "System.out.pr"))
    assert "append()" in _labels("Java", "StringBuilder builder = new StringBuilder(); builder.ap")


def test_tab_cycles_popup_without_inserting_and_space_commits_selection():
    pytest.importorskip("PySide6")
    from main import ACCENTS, CodeEditor, DEFAULT_ACCENT, DEFAULT_THEME, THEMES

    theme = dict(THEMES[DEFAULT_THEME])
    theme["accent"] = ACCENTS[DEFAULT_ACCENT]
    editor = CodeEditor(theme, "Java")
    editor.setPlainText("pr")
    query = CompletionQuery(
        0,
        2,
        "pr",
        (
            CompletionItem("private", "private", "Java keyword", "keyword"),
            CompletionItem("protected", "protected", "Java keyword", "keyword"),
        ),
    )
    labels = ["private    Java keyword", "protected    Java keyword"]
    editor._builtin_completion_query = query
    editor._builtin_completion_items = dict(zip(labels, query.items))
    editor._builtin_completion_model.setStringList(labels)
    editor._builtin_completer.setCompletionPrefix("pr")

    assert editor._cycle_builtin_completion()
    assert editor.toPlainText() == "pr"
    assert editor._builtin_completer.popup().currentIndex().row() == 0
    assert editor._cycle_builtin_completion()
    assert editor.toPlainText() == "pr"
    assert editor._builtin_completer.popup().currentIndex().row() == 1
    assert editor._cycle_builtin_completion()
    assert editor._builtin_completer.popup().currentIndex().row() == 0
    assert editor._cycle_builtin_completion()
    assert editor._accept_current_builtin_completion(trailing_space=True)
    assert editor.toPlainText() == "protected "


def test_shortcut_icon_variants_are_bundled_windows_icons():
    pytest.importorskip("PySide6")
    from main import SHORTCUT_ICON_OPTIONS

    assert set(SHORTCUT_ICON_OPTIONS) == {
        "Astra 3.11 — красно-синий",
        "Angel 404 — фиолетовый неон",
        "Astra Legacy — тёмная корона",
    }
    for relative in SHORTCUT_ICON_OPTIONS.values():
        path = ROOT / relative
        assert path.is_file() and path.stat().st_size > 1000
        assert path.read_bytes()[:4] == b"\x00\x00\x01\x00"


@pytest.mark.skipif(os.name != "nt" or shutil.which("powershell.exe") is None, reason="Windows shortcut COM test")
def test_shortcut_script_creates_lnk_with_selected_angel_icon(tmp_path: Path):
    app_dir = tmp_path / "app"
    desktop = tmp_path / "desktop"
    (app_dir / "assets").mkdir(parents=True)
    desktop.mkdir()
    (app_dir / "Astra Studio.exe").write_bytes(b"test executable placeholder")
    shutil.copy2(ROOT / "assets" / "astra_angel404.ico", app_dir / "assets" / "astra_angel404.ico")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "create_desktop_shortcut.ps1"),
            "-IconStyle",
            "angel404",
            "-DesktopPathOverride",
            str(desktop),
            "-AppDirOverride",
            str(app_dir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (desktop / "Astra Studio.lnk").is_file()
    assert "Icon style: angel404" in completed.stdout
