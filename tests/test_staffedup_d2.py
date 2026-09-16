from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from core.project_templates import TEMPLATES, create_project_from_template
from core.staffedup_health import apply_safe_staffedup_fixes, inspect_staffedup_project


def _create(base: Path, template_id: str, name: str = "Health Demo"):
    return create_project_from_template(base / template_id, name, template_id, "Release 3.3")


def _check_map(report):
    return {check.key: check for check in report.checks}


def test_all_staffedup_templates_have_health_reports_and_expected_profile():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for template in TEMPLATES:
            result = _create(base, template.template_id, f"{template.label} Demo")
            report = inspect_staffedup_project(
                result.project_dir,
                f"{template.label} Demo",
                result.staffedup_metadata,
                result.config_path,
            )
            assert report is not None
            assert report.template_id == template.template_id
            assert report.profile == template.health_profile
            checks = _check_map(report)
            assert checks["gitignore"].status == "ok"
            assert checks["docs_readme"].status == "ok"
            assert checks["metadata_template"].status == "ok"
            assert checks["metadata_profile"].status == "ok"


def test_non_staffedup_project_returns_no_profile_report():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        assert inspect_staffedup_project(root, "Plain", {}, root / "astral.project.json") is None


def test_unknown_template_is_reported_without_guessing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        metadata = {"template": "future-template", "healthProfile": "future"}
        report = inspect_staffedup_project(root, "Future", metadata, root / "astral.project.json")
        assert report is not None
        assert report.error_count == 1
        assert report.checks[0].key == "unknown_template"
        result = apply_safe_staffedup_fixes(root, "Future", metadata, root / "astral.project.json")
        assert not result.changed_files
        assert result.warnings


def test_missing_gitignore_is_fixable_and_recreated_without_touching_source():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "python-app")
        source = result.project_dir / "app" / "__main__.py"
        before = source.read_bytes()
        gitignore = result.project_dir / ".gitignore"
        gitignore.unlink()
        report = inspect_staffedup_project(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert _check_map(report)["gitignore"].fixable
        fixed = apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert gitignore in fixed.changed_files
        assert gitignore.is_file()
        assert source.read_bytes() == before


def test_gitignore_fix_appends_missing_patterns_and_preserves_custom_content_and_negation_order():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "telegram-bot")
        gitignore = result.project_dir / ".gitignore"
        custom = "# Мой комментарий\r\ncustom-cache/\r\n.env.*\r\n"
        gitignore.write_bytes(custom.encode("cp1251"))
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        raw = gitignore.read_bytes()
        text = raw.decode("cp1251")
        assert "Мой комментарий" in text
        assert "custom-cache/" in text
        assert ".env.*" in text
        assert "!.env.example" in text
        # Required patterns are appended in canonical order so the negation stays after .env.*.
        assert text.rfind("!.env.example") > text.find(".env.*")


def test_missing_support_files_are_recreated_but_missing_code_is_not():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "telegram-bot")
        readme = result.project_dir / "README.md"
        docs = result.project_dir / "docs" / "ARCHITECTURE.md"
        env_example = result.project_dir / ".env.example"
        code = result.project_dir / "bot.py"
        for path in (readme, docs, env_example, code):
            path.unlink()
        fixed = apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert readme.is_file()
        assert docs.is_file()
        assert env_example.is_file()
        assert not code.exists(), "Safe fix must never recreate/overwrite user code"
        assert all(path != code for path in fixed.changed_files)
        report = inspect_staffedup_project(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert _check_map(report)["file:bot.py"].status == "error"


def test_missing_standard_command_is_restored_but_custom_command_is_preserved():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "web-typescript")
        data = json.loads(result.config_path.read_text(encoding="utf-8"))
        data["commands"]["run"] = ""
        data["commands"]["build"] = "npm run custom-build"
        result.config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        repaired = json.loads(result.config_path.read_text(encoding="utf-8"))
        assert repaired["commands"]["run"] == "npm run dev"
        assert repaired["commands"]["build"] == "npm run custom-build"


def test_metadata_profile_and_tool_lists_are_repaired_without_forcing_old_template_version_upgrade():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "roblox-luau")
        data = json.loads(result.config_path.read_text(encoding="utf-8"))
        data["staffedUp"]["healthProfile"] = "wrong"
        data["staffedUp"]["requiredTools"] = []
        data["staffedUp"]["recommendedTools"] = []
        data["staffedUp"]["templateVersion"] = 1
        result.config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", data["staffedUp"], result.config_path)
        repaired = json.loads(result.config_path.read_text(encoding="utf-8"))["staffedUp"]
        assert repaired["healthProfile"] == "roblox-luau"
        assert repaired["requiredTools"] == ["rojo"]
        assert repaired["recommendedTools"] == ["git", "luau-analyze"]
        assert repaired["templateVersion"] == 1


def test_missing_template_version_is_safe_fixable():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "empty")
        data = json.loads(result.config_path.read_text(encoding="utf-8"))
        data["staffedUp"].pop("templateVersion")
        result.config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = inspect_staffedup_project(result.project_dir, "Health Demo", data["staffedUp"], result.config_path)
        assert _check_map(report)["metadata_version"].fixable
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", data["staffedUp"], result.config_path)
        repaired = json.loads(result.config_path.read_text(encoding="utf-8"))
        assert repaired["staffedUp"]["templateVersion"] == 1


def test_malformed_astra_config_is_reported_and_never_overwritten():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "empty")
        bad = b"{ definitely not json\n"
        result.config_path.write_bytes(bad)
        report = inspect_staffedup_project(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert _check_map(report)["config"].status == "error"
        fixed = apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert result.config_path.read_bytes() == bad
        assert fixed.warnings


def test_safe_fix_is_idempotent_on_healthy_support_files():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "web-typescript")
        first = apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        second = apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert not first.changed_files
        assert not second.changed_files


def test_local_env_without_example_is_warned_but_not_auto_generated_when_profile_has_no_canonical_example():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "python-app")
        (result.project_dir / ".env").write_text("SECRET=value\n", encoding="utf-8")
        report = inspect_staffedup_project(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        check = _check_map(report)["env_untracked_example"]
        assert check.status == "warn"
        assert not check.fixable
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert not (result.project_dir / ".env.example").exists()


def test_node_dependency_state_reports_missing_node_modules_without_installing_anything():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "web-typescript")
        report = inspect_staffedup_project(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert _check_map(report)["deps_node"].status == "warn"
        assert not (result.project_dir / "node_modules").exists()
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert not (result.project_dir / "node_modules").exists()


def test_required_structure_is_validated_but_never_recreated_by_safe_fix():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "roblox-luau")
        target = result.project_dir / "src" / "server"
        for child in target.iterdir():
            child.unlink()
        target.rmdir()
        report = inspect_staffedup_project(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert _check_map(report)["dir:src/server"].status == "error"
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert not target.exists(), "Safe fix must not invent missing source structure"



def test_safe_fix_never_overwrites_existing_custom_support_files():
    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "telegram-bot")
        readme = result.project_dir / "README.md"
        env_example = result.project_dir / ".env.example"
        readme.write_text("# Custom team documentation\n", encoding="utf-8")
        env_example.write_text("CUSTOM_PUBLIC_KEY=example\n", encoding="utf-8")
        (result.project_dir / ".gitignore").unlink()
        apply_safe_staffedup_fixes(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        assert readme.read_text(encoding="utf-8") == "# Custom team documentation\n"
        assert env_example.read_text(encoding="utf-8") == "CUSTOM_PUBLIC_KEY=example\n"


def test_required_and_recommended_tool_severity_is_profile_aware(monkeypatch):
    import core.staffedup_health as health

    with tempfile.TemporaryDirectory() as tmp:
        result = _create(Path(tmp), "roblox-luau")
        monkeypatch.setattr(health, "_which", lambda _root, _tool: None)
        report = health.inspect_staffedup_project(result.project_dir, "Health Demo", result.staffedup_metadata, result.config_path)
        checks = _check_map(report)
        assert checks["tool_required:rojo"].status == "error"
        assert checks["tool_recommended:git"].status == "info"
        assert checks["tool_recommended:luau-analyze"].status == "info"

def test_main_integrates_staffedup_health_ui_and_safe_fix_boundary():
    root = Path(__file__).resolve().parents[1]
    source = (root / "main.py").read_text(encoding="utf-8")
    assert "inspect_staffedup_project" in source
    assert "apply_safe_staffedup_fixes" in source
    assert 'tree.setObjectName("ProjectHealthTree")' in source
    assert 'QPushButton("Исправить безопасное")' in source
    assert "Safe fix никогда не перезаписывает пользовательский код" in source
