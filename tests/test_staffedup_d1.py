from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.project_templates import (  # noqa: E402
    TEMPLATES,
    create_project_from_template,
    get_project_template,
    project_slug,
    project_template_choices,
    python_package_name,
    rendered_template_files,
)


EXPECTED_TEMPLATE_IDS = {
    "web-typescript",
    "yandex-games-typescript",
    "roblox-luau",
    "godot",
    "python-app",
    "telegram-bot",
    "static-website",
    "empty",
}


def _create(base: Path, template_id: str, name: str = "Тест Проект"):
    target = base / f"{template_id}-project"
    return create_project_from_template(target, name, template_id, "Release 3.3")


def test_template_catalog_contains_all_staffedup_profiles():
    assert {template.template_id for template in TEMPLATES} == EXPECTED_TEMPLATE_IDS
    assert {template_id for template_id, _label in project_template_choices()} == EXPECTED_TEMPLATE_IDS
    assert len({template.label for template in TEMPLATES}) == len(TEMPLATES)


def test_russian_project_names_get_portable_slugs():
    assert project_slug("Новый Проект 42") == "novyy-proekt-42"
    assert python_package_name("42 тест") == "app_42_test"


def test_all_template_paths_are_relative_unique_and_rendered():
    for template in TEMPLATES:
        files = rendered_template_files(template.template_id, "Демо Проект")
        assert files
        assert len(files) == len(set(files))
        for path, content in files.items():
            assert not path.is_absolute()
            assert ".." not in path.parts
            assert "{{PROJECT_" not in str(path)
            assert "{{PROJECT_" not in content
            assert "{{PYTHON_PACKAGE}}" not in content


def test_unknown_template_is_rejected():
    with pytest.raises(KeyError):
        get_project_template("does-not-exist")


def test_create_refuses_non_empty_target_without_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        target = base / "existing"
        target.mkdir()
        sentinel = target / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with pytest.raises(FileExistsError):
            create_project_from_template(target, "Demo", "empty", "Release 3.3")
        assert sentinel.read_text(encoding="utf-8") == "keep"
        assert sorted(path.name for path in target.iterdir()) == ["keep.txt"]


def test_existing_empty_target_is_supported_and_staging_is_cleaned():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        target = base / "empty-target"
        target.mkdir()
        result = create_project_from_template(target, "Demo", "empty", "Release 3.3")
        assert result.config_path.is_file()
        assert not list(base.glob(".astra-project-*"))


def test_every_template_writes_portable_astra_config_and_staffedup_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for template in TEMPLATES:
            result = _create(base, template.template_id, "Демо Проект")
            data = json.loads(result.config_path.read_text(encoding="utf-8"))
            assert data["mainFolder"] == "."
            assert data["astralStudioVersion"] == "Release 3.3"
            assert data["defaultLanguage"] == template.default_language
            assert data["staffedUp"]["template"] == template.template_id
            assert data["staffedUp"]["healthProfile"] == template.health_profile
            assert data["staffedUp"]["templateVersion"] == 1
            assert data["staffedUp"]["requiredTools"] == list(template.required_tools)
            assert data["staffedUp"]["recommendedTools"] == list(template.recommended_tools)
            assert data["commands"] == {
                key: value.replace("{{PROJECT_NAME}}", "Демо Проект")
                .replace("{{PROJECT_SLUG}}", "demo-proekt")
                .replace("{{PYTHON_PACKAGE}}", "demo_proekt")
                for key, value in template.commands.items()
            }


def test_web_typescript_template_has_build_test_and_env_boundaries():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "web-typescript", "Frontend Demo")
        package = json.loads((result.project_dir / "package.json").read_text(encoding="utf-8"))
        assert package["scripts"] == {
            "dev": "vite --host 127.0.0.1",
            "build": "tsc -p tsconfig.json --noEmit && vite build",
            "test": "vitest run",
        }
        assert {"typescript", "vite", "vitest"}.issubset(package["devDependencies"])
        assert (result.project_dir / ".env.example").is_file()
        assert (result.project_dir / "src/main.test.ts").is_file()
        assert "node_modules/" in (result.project_dir / ".gitignore").read_text(encoding="utf-8")


def test_yandex_games_template_keeps_platform_sdk_behind_adapter():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "yandex-games-typescript", "Yandex Demo")
        yandex = (result.project_dir / "src/platform/yandex.ts").read_text(encoding="utf-8")
        local = (result.project_dir / "src/platform/local.ts").read_text(encoding="utf-8")
        main = (result.project_dir / "src/main.ts").read_text(encoding="utf-8")
        assert "YaGames" in yandex
        assert 'kind: "local"' in local
        assert 'from "./platform"' in main
        assert "yandex.ru" not in (result.project_dir / "index.html").read_text(encoding="utf-8").lower()


def test_roblox_template_has_valid_rojo_mapping_and_boundaries():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "roblox-luau", "Roblox Demo")
        rojo = json.loads((result.project_dir / "default.project.json").read_text(encoding="utf-8"))
        tree = rojo["tree"]
        assert tree["ServerScriptService"]["Server"]["$path"] == "src/server"
        assert tree["StarterPlayer"]["StarterPlayerScripts"]["Client"]["$path"] == "src/client"
        assert tree["ReplicatedStorage"]["Shared"]["$path"] == "src/shared"
        assert (result.project_dir / "src/server/init.server.luau").is_file()
        assert (result.project_dir / "src/client/init.client.luau").is_file()


def test_godot_template_has_real_main_scene_and_script():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "godot", "Godot Demo")
        project = (result.project_dir / "project.godot").read_text(encoding="utf-8")
        scene = (result.project_dir / "scenes/main.tscn").read_text(encoding="utf-8")
        assert 'run/main_scene="res://scenes/main.tscn"' in project
        assert 'res://scripts/main.gd' in scene
        assert (result.project_dir / "scripts/main.gd").is_file()
        assert ".godot/" in (result.project_dir / ".gitignore").read_text(encoding="utf-8")


def test_python_app_template_toml_and_real_smoke_commands_work():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "python-app", "Python Demo")
        pyproject = tomllib.loads((result.project_dir / "pyproject.toml").read_text(encoding="utf-8"))
        assert pyproject["project"]["name"] == "python-demo"
        assert pyproject["tool"]["setuptools"]["packages"] == ["app"]
        run = subprocess.run(
            [sys.executable, "-m", "app"],
            cwd=result.project_dir,
            text=True,
            capture_output=True,
            timeout=15,
        )
        assert run.returncode == 0, run.stderr
        assert "Python Demo is ready" in run.stdout
        tests = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=result.project_dir,
            text=True,
            capture_output=True,
            timeout=15,
        )
        assert tests.returncode == 0, tests.stderr


def test_telegram_template_never_places_real_token_in_tracked_files_and_tests_run_without_aiogram():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "telegram-bot", "Bot Demo")
        env_example = (result.project_dir / ".env.example").read_text(encoding="utf-8")
        gitignore = (result.project_dir / ".gitignore").read_text(encoding="utf-8")
        assert "TELEGRAM_BOT_TOKEN=replace-me" in env_example
        assert ".env\n" in gitignore
        assert "aiogram>=3,<4" in (result.project_dir / "requirements.txt").read_text(encoding="utf-8")
        tests = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=result.project_dir,
            text=True,
            capture_output=True,
            timeout=15,
        )
        assert tests.returncode == 0, tests.stderr


def test_static_and_empty_templates_do_not_invent_package_dependencies():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        static = _create(base, "static-website", "Static Demo")
        empty = _create(base, "empty", "Empty Demo")
        assert not (static.project_dir / "package.json").exists()
        assert not (static.project_dir / "requirements.txt").exists()
        assert not (empty.project_dir / "package.json").exists()
        assert not (empty.project_dir / "requirements.txt").exists()
        assert json.loads(empty.config_path.read_text(encoding="utf-8"))["commands"] == {
            "run": "",
            "build": "",
            "test": "",
            "install": "",
        }


def test_generated_python_sources_compile_without_third_party_import_execution():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for template_id in ("python-app", "telegram-bot"):
            result = _create(base, template_id, f"{template_id} Demo")
            python_files = list(result.project_dir.rglob("*.py"))
            assert python_files
            for path in python_files:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

from core.project_paths import portable_attached_folders, portable_project_path  # noqa: E402


def test_portable_project_paths_keep_repository_local_state_relative():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        config = root / "astral.project.json"
        nested = root / "src" / "main.py"
        nested.parent.mkdir()
        nested.write_text("print('ok')\n", encoding="utf-8")
        outside = Path(tmp) / "shared"
        outside.mkdir()
        assert portable_project_path(root, config) == "."
        assert portable_project_path(nested, config) == "src/main.py"
        assert portable_project_path(outside, config) == str(outside)


def test_attached_folder_serialization_is_relative_only_inside_repository():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        inside = root / "packages" / "shared"
        inside.mkdir(parents=True)
        outside = Path(tmp) / "external"
        outside.mkdir()
        serialized = portable_attached_folders(
            [
                {"alias": "Inside", "path": str(inside)},
                {"alias": "Outside", "path": str(outside)},
            ],
            root / "astral.project.json",
        )
        assert serialized[0] == {"alias": "Inside", "path": "packages/shared"}
        assert serialized[1] == {"alias": "Outside", "path": str(outside)}


def test_main_integrates_template_dialog_metadata_and_portable_project_paths():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "Release 3.14"' in source
    assert 'dialog.setWindowTitle("Создать проект · StaffedUp")' in source
    assert "create_project_from_template(project_dir, name, selected_template_id(), APP_VERSION)" in source
    assert '"staffedUp": dict(self.project_staffedup_meta)' in source
    assert "portable_project_path(self.project_main_folder, config_path)" in source
    assert "portable_attached_folders(self.attached_project_folders, config_path)" in source
    assert 'lower_name in {"project.godot", ".gitignore"}' in source
