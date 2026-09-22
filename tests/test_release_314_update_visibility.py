from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _assignment(module: ast.Module, name: str):
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing assignment: {name}")


def test_release_314_exposes_only_current_three_languages_and_preserves_hidden_implementations():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _assignment(tree, "VISIBLE_LANGUAGES") == ("Java", "Python", "C++")
    assert 'if language in VISIBLE_LANGUAGES:' in source
    assert "if editor.language_name in VISIBLE_LANGUAGES:" in source
    assert "if get_project_template(template_id).default_language in VISIBLE_LANGUAGES:" in source
    assert "[language for language in registry.supported_languages() if language in VISIBLE_LANGUAGES]" in source
    assert 'LANGUAGES[language]["filters"] for language in VISIBLE_LANGUAGES' in source
    for hidden in ("JavaScript", "HTML", "CSS", "TypeScript", "C#", "PHP", "Luau", "GDScript"):
        assert f'"{hidden}":' in source


def test_installer_ui_and_bulk_update_are_scoped_to_java_python_cpp():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'self.btn_install_all.setText("Установить Java + Python + C++")' in source
    assert "hidden_button.setVisible(False)" in source
    update_script = source.split('update_script = r"""', 1)[1].split('"""', 1)[0]
    assert "Python.Python.3.14" in update_script
    assert "astral-sh.uv" in update_script
    assert "MSYS2.MSYS2" in update_script
    assert "EclipseAdoptium.Temurin.21.JDK" in update_script
    for hidden_package in (
        "OpenJS.NodeJS.LTS",
        "GodotEngine.GodotEngine",
        "PHP.PHP.8.4",
        "Microsoft.PowerShell",
    ):
        assert hidden_package not in update_script


def test_detached_updater_uses_external_working_directory_and_recovers_visible_app():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    updater_source = (ROOT / "core" / "app_updates.py").read_text(encoding="utf-8")
    assert '("powershell.exe", args, str(script_path.parent))' in main_source
    assert "QProcess.startDetached(program, args, working_directory)" in main_source
    assert "Set-Location -LiteralPath $updatesRoot" in updater_source
    assert "[Environment]::CurrentDirectory = $updatesRoot" in updater_source
    assert "Never leave the user with an application that merely disappeared" in updater_source
    assert "Astra Studio не удалось установить обновление" in updater_source


def test_public_update_identity_no_longer_uses_private_repository_name():
    channel = (ROOT / "update_channel.json").read_text(encoding="utf-8")
    distribution = (ROOT / "UPDATE_DISTRIBUTION.md").read_text(encoding="utf-8")
    assert "Astra-Studio-Releases" in channel
    assert "Astra-Studio-Releases" in distribution
    assert "Astra-Studio-Private" not in channel
    assert "Astra-Studio-Private" not in distribution
