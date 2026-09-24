from __future__ import annotations

import json
from pathlib import Path

from core.quality_tools import (
    FORMATTER_BY_LANGUAGE,
    LINTER_BY_LANGUAGE,
    formatter_tool_for_language,
    linter_tool_for_language,
    parse_eslint_json,
    parse_ruff_json,
)


def test_c1_formatter_registry_required_languages():
    assert formatter_tool_for_language("Python") == "ruff"
    assert formatter_tool_for_language("TypeScript") == "prettier"
    assert formatter_tool_for_language("JavaScript") == "prettier"
    assert formatter_tool_for_language("C++") == "clang-format"
    assert formatter_tool_for_language("Luau") == "stylua"
    assert formatter_tool_for_language("Lua") == "stylua"


def test_c1_prettier_covers_web_formats():
    for language in ("HTML", "CSS", "JSON", "YAML", "Markdown"):
        assert FORMATTER_BY_LANGUAGE[language] == "prettier"


def test_c1_linter_registry():
    assert LINTER_BY_LANGUAGE == {
        "Python": "ruff",
        "JavaScript": "eslint",
        "TypeScript": "eslint",
    }
    assert linter_tool_for_language("C++") is None


def test_c1_parse_ruff_json_positions(tmp_path: Path):
    source = tmp_path / "app.py"
    payload = [{
        "code": "F401",
        "message": "`os` imported but unused",
        "filename": str(source),
        "location": {"row": 2, "column": 1},
        "end_location": {"row": 2, "column": 10},
    }]
    diagnostics = parse_ruff_json(json.dumps(payload), source)
    assert len(diagnostics) == 1
    item = diagnostics[0]
    assert item.path == source
    assert (item.line, item.character, item.end_line, item.end_character) == (1, 0, 1, 9)
    assert item.source == "Ruff"
    assert item.code == "F401"
    assert item.severity == 2


def test_c1_parse_eslint_json_severity_and_positions(tmp_path: Path):
    source = tmp_path / "app.ts"
    payload = [{
        "filePath": str(source),
        "messages": [
            {"ruleId": "no-undef", "severity": 2, "message": "x is not defined", "line": 3, "column": 5, "endLine": 3, "endColumn": 6},
            {"ruleId": "semi", "severity": 1, "message": "Missing semicolon", "line": 4, "column": 9},
        ],
    }]
    diagnostics = parse_eslint_json(json.dumps(payload), source)
    assert len(diagnostics) == 2
    assert diagnostics[0].severity == 1
    assert diagnostics[1].severity == 2
    assert diagnostics[0].line == 2 and diagnostics[0].character == 4


def test_c1_invalid_linter_json_is_safe(tmp_path: Path):
    assert parse_ruff_json("not-json", tmp_path / "x.py") == []
    assert parse_eslint_json("{", tmp_path / "x.js") == []


def test_c1_resolve_project_local_node_tool(tmp_path: Path, monkeypatch):
    import core.quality_tools as qt
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    name = "prettier.cmd" if qt.os.name == "nt" else "prettier"
    tool = bin_dir / name
    tool.write_text("echo prettier", encoding="utf-8")
    assert qt.resolve_quality_executable("prettier", tmp_path) == str(tool)


def test_c1_formatter_commands_use_stdin_filepath(tmp_path: Path, monkeypatch):
    import core.quality_tools as qt
    fake = tmp_path / ("tool.exe" if qt.os.name == "nt" else "tool")
    fake.write_text("x", encoding="utf-8")
    monkeypatch.setattr(qt, "resolve_quality_executable", lambda *args, **kwargs: str(fake))
    path = tmp_path / "app.py"
    cmd = qt.formatter_command("Python", path, tmp_path, "print( 1 )")
    assert cmd is not None
    assert cmd.stdin_text == "print( 1 )"
    assert "--stdin-filename" in cmd.arguments and str(path) in cmd.arguments and cmd.arguments[-1] == "-"

    ts = tmp_path / "app.ts"
    cmd = qt.formatter_command("TypeScript", ts, tmp_path, "const x=1")
    assert cmd is not None
    assert cmd.arguments == ("--stdin-filepath", str(ts))


def test_c1_linter_commands_machine_readable(tmp_path: Path, monkeypatch):
    import core.quality_tools as qt
    fake = tmp_path / ("tool.exe" if qt.os.name == "nt" else "tool")
    fake.write_text("x", encoding="utf-8")
    monkeypatch.setattr(qt, "resolve_quality_executable", lambda *args, **kwargs: str(fake))
    py = qt.linter_command("Python", tmp_path / "a.py", tmp_path, "import os")
    assert py is not None
    assert py.parser == "ruff-json"
    assert "json" in py.arguments
    assert py.accepted_exit_codes == (0, 1)
    ts = qt.linter_command("TypeScript", tmp_path / "a.ts", tmp_path, "x")
    assert ts is not None
    assert ts.parser == "eslint-json"
    assert "--stdin" in ts.arguments and "--format" in ts.arguments and "json" in ts.arguments


def test_c1_node_quality_install_plans_are_project_local_and_exact(tmp_path: Path, monkeypatch):
    import core.quality_tools as qt

    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(qt.shutil, "which", lambda name: "/fake/npm" if "npm" in name else None)

    for tool_id, package in (("prettier", "prettier"), ("eslint", "eslint"), ("stylua", "@johnnymorganz/stylua-bin")):
        plan = qt.install_plan_for_quality_tool(tool_id, tmp_path)
        assert plan is not None
        assert plan.program == "/fake/npm"
        assert plan.workdir == tmp_path
        assert plan.arguments[:3] == ("install", "--save-dev", "--save-exact")
        assert plan.arguments[-1] == package


def test_c1_task_manager_has_stdin_support_source():
    source = (Path(__file__).parents[1] / "core" / "task_manager.py").read_text(encoding="utf-8")
    assert "stdin_data: str | bytes | None = None" in source
    assert "self.process.started.connect(self._write_stdin_data)" in source
    assert "self.process.closeWriteChannel()" in source


def test_c1_main_has_quality_ui_and_problem_merge():
    source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "Release 3.19"' in source
    assert 'QPushButton("↹  Форматировать")' in source
    assert 'Форматировать текущий файл · Shift+Alt+F' in source
    assert 'QCheckBox("Форматировать при сохранении")' in source
    assert 'def lint_current_file' in source
    assert 'self.quality_diagnostics' in source
    assert 'mode == "quality_lint"' in source
