from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
CORE = ROOT / "core"
SCRIPTS = ROOT / "scripts"

REQUIRED_LANGUAGES = {
    "Python", "C++", "Java", "HTML", "CSS", "JavaScript", "TypeScript", "Luau",
    "GDScript", "PHP", "PowerShell", "C#", "SQL", "JSON", "YAML", "Markdown",
    "TOML", "XML", "Shell", "Dockerfile",
}


def _main_tree() -> ast.Module:
    return ast.parse(MAIN.read_text(encoding="utf-8"))


def _literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(name)


def _language_names(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LANGUAGES" for t in node.targets):
            return {ast.literal_eval(key) for key in node.value.keys}
    raise AssertionError("LANGUAGES")


def _function_language_branches(tree: ast.Module, name: str) -> set[str]:
    fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    result: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name) or node.left.id != "language":
            continue
        if len(node.ops) != 1 or len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if isinstance(node.ops[0], ast.Eq) and isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            result.add(comparator.value)
        elif isinstance(node.ops[0], ast.In) and isinstance(comparator, (ast.Set, ast.Tuple, ast.List)):
            values = ast.literal_eval(comparator)
            result.update(value for value in values if isinstance(value, str))
    return result


def test_final_release_identity_and_runtime_tree_has_no_dev_paths():
    tree = _main_tree()
    assert _literal_assignment(tree, "APP_VERSION") == "Release 3.15"
    runtime_files = [MAIN, *sorted(CORE.glob("*.py")), *sorted(SCRIPTS.glob("*.ps1")), *sorted(ROOT.glob("*.bat")), *sorted(ROOT.glob("*.vbs"))]
    forbidden = ("/mnt/data", "Astra_Studio_Release_2_3", "Astra_Studio_Release_3_3_pre_", "Release 2.3")
    for path in runtime_files:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for token in forbidden:
            assert token not in text, f"stale runtime token {token!r} in {path.relative_to(ROOT)}"
    main_text = MAIN.read_text(encoding="utf-8")
    assert "Диагностика инструментов Release 3.1 рассчитана" not in main_text
    assert "Автоматический установщик Release 3.1 рассчитан" not in main_text


def test_all_roadmap_scope_before_final_gate_is_closed():
    text = (ROOT / "ROADMAP_3_X.md").read_text(encoding="utf-8")
    before_gate = text.split("## Final integration gate before 4.0", 1)[0]
    assert "- [ ]" not in before_gate
    for marker in (
        "Release 3.0", "Release 3.1", "Release 3.2", "Release 3.3",
        "D1", "D2", "D3",
    ):
        assert marker in before_gate


def test_every_supported_language_has_compile_and_run_route():
    tree = _main_tree()
    languages = _language_names(tree)
    assert languages == REQUIRED_LANGUAGES
    assert _function_language_branches(tree, "compile_code") == languages
    assert _function_language_branches(tree, "run_code") == languages


def test_lsp_catalog_matches_all_supported_languages():
    sys.path.insert(0, str(ROOT))
    from core.lsp_servers import DEFAULT_LSP_SERVER_CONFIGS  # noqa: PLC0415
    assert set(DEFAULT_LSP_SERVER_CONFIGS) == REQUIRED_LANGUAGES


def test_runtime_assets_scripts_and_build_inputs_exist():
    assets = [
        "assets/astra.ico", "assets/astra.png", "assets/astra_angel404.ico", "assets/astra_angel404.png", "assets/astra_studio_title.png",
        *[f"assets/wallpapers/{name}" for name in (
            "astra_neon_core.png", "astra_deep_space.png", "astra_blue_horizon.png", "astra_eclipse.png",
            "astra_crown_night.png", "astra_sakura_dusk.png", "astra_cyber_ritual.png", "astra_crimson_prayer.png",
            "angel_404.png",
        )],
        "assets/fonts/minecraft.ttf",
    ]
    scripts = [
        "_common_installer.ps1", "install_python.ps1", "install_uv.ps1", "install_node.ps1",
        "install_git.ps1", "install_powershell.ps1", "install_cpp.ps1", "install_java.ps1",
        "install_godot.ps1", "install_php.ps1", "install_all.ps1", "update_all.ps1",
        "create_desktop_shortcut.ps1",
    ]
    for rel in assets:
        assert (ROOT / rel).is_file(), rel
    for name in scripts:
        assert (SCRIPTS / name).is_file(), name
    assert (ROOT / "astra_studio.spec").is_file()
    assert (ROOT / "update_channel.json").is_file()
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for dependency in ("PySide6", "pyinstaller", "PyYAML"):
        assert dependency.lower() in requirements.lower()


def test_windows_batch_wrappers_are_cmd_safe_crlf_ascii():
    batches = sorted(ROOT.glob("*.bat"))
    assert batches
    for path in batches:
        data = path.read_bytes()
        assert data, path.name
        assert data.count(b"\n") == data.count(b"\r\n"), f"LF-only line endings in {path.name}"
        assert not data.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM in {path.name}"
        data.decode("ascii")


def test_batch_and_git_command_safety_regression_guards():
    batch_text = "\n".join(path.read_text(encoding="utf-8-sig", errors="replace") for path in ROOT.glob("*.bat"))
    assert "%errorlevel%" not in batch_text.lower()
    build = (ROOT / "build_exe.bat").read_text(encoding="utf-8-sig", errors="replace")
    assert "--clean" in build
    assert "astra_studio.spec" in build
    spec = (ROOT / "astra_studio.spec").read_text(encoding="utf-8")
    assert '("assets", "assets")' in spec
    assert 'name="Astra Studio"' in spec
    production = "\n".join([MAIN.read_text(encoding="utf-8"), *(path.read_text(encoding="utf-8") for path in CORE.glob("*.py"))])
    assert "shell=True" not in production
    git_text = (CORE / "git_tools.py").read_text(encoding="utf-8")
    for token in ("reset --hard", "clean -f", "push --force", "--force-with-lease"):
        assert token not in git_text


def test_shutdown_paths_cover_tasks_lsp_run_terminal_and_installer():
    text = MAIN.read_text(encoding="utf-8")
    close_start = text.index("    def closeEvent(self, event):")
    close_end = text.index("\n\ndef set_windows_app_user_model_id", close_start)
    close = text[close_start:close_end]
    for token in (
        "task_manager.cancel_and_wait",
        "lsp_manager.shutdown_all(wait=True)",
        '_stop_process_safely(self.run_process, "запуск программы")',
        '_stop_process_safely(self.terminal_process, "терминал")',
        '_stop_process_safely(self.install_process, "установщик")',
        "_confirm_unsaved_before_exit",
    ):
        assert token in close
    task_text = (CORE / "task_manager.py").read_text(encoding="utf-8")
    assert "def cancel_and_wait" in task_text
    assert "process.terminate()" in task_text and "process.kill()" in task_text


def test_python_project_environment_does_not_adopt_unrelated_virtualenv(tmp_path):
    sys.path.insert(0, str(ROOT))
    from core.python_environment import detect_project_environment  # noqa: PLC0415

    project = tmp_path / "project"
    foreign = tmp_path / "foreign"
    project.mkdir()
    foreign.mkdir()
    if os.name == "nt":
        py = foreign / "Scripts" / "python.exe"
    else:
        py = foreign / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("stub", encoding="utf-8")
    with patch.dict(os.environ, {"VIRTUAL_ENV": str(foreign)}, clear=False):
        info = detect_project_environment(project)
    assert info.environment_dir is None
    assert info.python_executable is None


def test_python_mutation_ui_keeps_global_environment_guarded():
    text = MAIN.read_text(encoding="utf-8")
    for fn, guard_fragment in (
        ("install_project_python_dependencies", "У проекта ещё нет собственного Python-окружения"),
        ("update_project_pip", "У проекта нет собственного Python-окружения"),
        ("export_project_requirements", "Экспорт requirements.txt разрешён только из проектного"),
    ):
        start = text.index(f"    def {fn}(")
        next_def = text.find("\n    def ", start + 10)
        body = text[start: next_def if next_def != -1 else len(text)]
        assert guard_fragment in body
        assert "valid_override" in body


def test_settings_loader_and_saver_keys_remain_symmetric():
    text = MAIN.read_text(encoding="utf-8")
    load_start = text.index("    def _load_settings(self):")
    save_start = text.index("    def _save_settings(self):")
    load_text = text[load_start:save_start]
    save_end = text.find("\n    def ", save_start + 20)
    save_text = text[save_start: save_end if save_end != -1 else len(text)]
    loaded = set(re.findall(r'data\.get\("([^"]+)"\)', load_text))
    saved = set(re.findall(r'"([^"]+)"\s*:', save_text))
    assert loaded == saved
    assert len(loaded) >= 40


def test_legacy_settings_and_project_migration_paths_are_preserved():
    text = MAIN.read_text(encoding="utf-8")
    assert 'Path.home() / ".astra_studio" / "settings.json"' in text
    assert "shutil.copy2(legacy_settings_path, self.settings_path)" in text
    assert 'data.get("defaultLanguage"' in text
    assert 'int_value("tabSize"' in text
    assert 'int_value("indentSize"' in text
    assert 'settings.get("insertSpaces")' in text
    assert "portable_project_path" in text
    assert "if not path.is_absolute():" in text and "path = config_path.parent / path" in text


def test_test_registry_exactly_matches_pytest_collection():
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=True,
    )
    collected = {line.strip() for line in completed.stdout.splitlines() if line.strip().startswith("tests/") and "::" in line}
    registry = (ROOT / "TEST_REGISTRY_3_X.md").read_text(encoding="utf-8")
    registered = set(re.findall(r'^- `([^`]+::[^`]+)`$', registry, flags=re.MULTILINE))
    assert collected == registered


def test_final_docs_no_longer_claim_d3_is_next():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG_RELEASE_3_3.md").read_text(encoding="utf-8")
    assert "D3 AI-adjacent workflow NEXT" not in readme
    assert "Release 3.15" in readme
    assert "Final Integration Gate" in readme
    assert "D1–D3" in changelog


def test_python_registry_json_records_full_parity():
    import json
    sys.path.insert(0, str(ROOT))
    from core.python_library_registry import LIBRARY_BUNDLES, PYTHON_LIBRARY_REGISTRY  # noqa: PLC0415

    payload = json.loads((ROOT / "data" / "python_libraries.json").read_text(encoding="utf-8"))
    json_records = {item["import_name"]: item for item in payload["libraries"]}
    py_records = {item["import_name"]: item for item in PYTHON_LIBRARY_REGISTRY}
    assert set(json_records) == set(py_records)
    fields = ("import_name", "pip_name", "display_name", "category", "description", "safe", "size", "aliases", "warning", "experimental")
    for key in py_records:
        assert {field: py_records[key].get(field) for field in fields} == {field: json_records[key].get(field) for field in fields}
    assert LIBRARY_BUNDLES == payload["bundles"]


def test_runtime_classes_do_not_accidentally_redefine_methods():
    for path in (MAIN, *sorted(CORE.glob("*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            names: dict[str, int] = {}
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names[child.name] = names.get(child.name, 0) + 1
            duplicates = sorted(name for name, count in names.items() if count > 1)
            assert not duplicates, f"duplicate methods in {path.relative_to(ROOT)}::{node.name}: {duplicates}"


def test_owner_acceptance_registry_keeps_final_windows_checks_pending():
    registry = (ROOT / "TEST_REGISTRY_3_X.md").read_text(encoding="utf-8")
    for number in range(13, 17):
        assert f'- [ ] `FINAL-{number:02d}`' in registry
