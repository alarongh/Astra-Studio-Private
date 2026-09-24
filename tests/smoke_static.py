from __future__ import annotations

import ast
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
CORE = ROOT / "core"
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"

REQUIRED_LANGUAGES = {
    "Python", "C++", "Java", "HTML", "CSS", "JavaScript", "TypeScript", "Luau",
    "GDScript", "PHP", "PowerShell", "C#", "SQL", "JSON", "YAML", "Markdown",
    "TOML", "XML", "Shell", "Dockerfile",
}
REQUIRED_ASSETS = [
    ROOT / "assets" / "astra.ico",
    ROOT / "assets" / "astra.png",
    ROOT / "assets" / "astra_angel404.ico",
    ROOT / "assets" / "astra_angel404.png",
    ROOT / "assets" / "astra_studio_title.png",
    *(ROOT / "assets" / "wallpapers" / name for name in [
        "astra_neon_core.png", "astra_deep_space.png", "astra_blue_horizon.png", "astra_eclipse.png",
        "astra_crown_night.png", "astra_sakura_dusk.png", "astra_cyber_ritual.png", "astra_crimson_prayer.png",
        "angel_404.png",
    ]),
    ROOT / "assets" / "fonts" / "minecraft.ttf",
]
REQUIRED_SCRIPTS = [
    "_common_installer.ps1", "install_python.ps1", "install_uv.ps1", "install_node.ps1",
    "install_git.ps1", "install_powershell.ps1", "install_cpp.ps1", "install_java.ps1",
    "install_godot.ps1", "install_php.ps1", "install_all.ps1", "update_all.ps1",
    "create_desktop_shortcut.ps1",
]


def literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Не найдено присваивание {name}")


def extract_language_names(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LANGUAGES" for t in node.targets):
            if not isinstance(node.value, ast.Dict):
                raise AssertionError("LANGUAGES должен быть словарём")
            return {ast.literal_eval(key) for key in node.value.keys}
    raise AssertionError("LANGUAGES не найден")


def main() -> None:
    for file in [
        MAIN, CORE / "task_manager.py", CORE / "python_library_registry.py", CORE / "python_environment.py",
        CORE / "project_commands.py", CORE / "project_doctor.py", CORE / "staffedup_health.py", CORE / "lsp_protocol.py",
        CORE / "lsp_servers.py", CORE / "lsp_documents.py", CORE / "lsp_features.py", CORE / "lsp_tcp_transport.py",
        CORE / "lsp_transport.py", CORE / "quality_tools.py", CORE / "language_completion.py", CORE / "test_explorer.py", CORE / "git_tools.py", CORE / "project_templates.py", CORE / "project_paths.py", CORE / "ai_context.py", CORE / "__init__.py",
    ]:
        py_compile.compile(str(file), doraise=True)

    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    assert literal_assignment(tree, "APP_VERSION") == "Release 3.20"

    languages = extract_language_names(tree)
    missing = REQUIRED_LANGUAGES - languages
    assert not missing, f"Не хватает языков: {sorted(missing)}"

    for asset in REQUIRED_ASSETS:
        assert asset.is_file(), f"Не найден ресурс: {asset.relative_to(ROOT)}"
    for script in REQUIRED_SCRIPTS:
        assert (SCRIPTS / script).is_file(), f"Не найден installer script: scripts/{script}"

    registry_json = json.loads((DATA / "python_libraries.json").read_text(encoding="utf-8"))
    libraries = {item["import_name"]: item for item in registry_json["libraries"]}
    expected = {
        "sklearn": "scikit-learn", "PIL": "Pillow", "cv2": "opencv-python",
        "docx": "python-docx", "pptx": "python-pptx", "bs4": "beautifulsoup4",
        "yaml": "PyYAML", "dotenv": "python-dotenv",
    }
    for import_name, pip_name in expected.items():
        assert libraries[import_name]["pip_name"] == pip_name, (import_name, libraries[import_name]["pip_name"])

    sys.path.insert(0, str(ROOT))
    from core.python_library_registry import PYTHON_LIBRARY_REGISTRY, LIBRARY_BUNDLES  # noqa: PLC0415
    from core.lsp_servers import DEFAULT_LSP_SERVER_CONFIGS, LspServerRegistry, install_plan_for_language  # noqa: PLC0415
    from core.quality_tools import FORMATTER_BY_LANGUAGE, LINTER_BY_LANGUAGE  # noqa: PLC0415

    assert set(DEFAULT_LSP_SERVER_CONFIGS) == REQUIRED_LANGUAGES, "LSP config must explicitly cover every Astra language"
    assert DEFAULT_LSP_SERVER_CONFIGS["GDScript"].transport == "external_tcp"
    assert DEFAULT_LSP_SERVER_CONFIGS["GDScript"].port == 6005
    gdscript_resolved = LspServerRegistry().resolve("GDScript", ROOT)
    assert gdscript_resolved is not None and gdscript_resolved.transport == "external_tcp"
    assert DEFAULT_LSP_SERVER_CONFIGS["Luau"].candidates[0].arguments == ("lsp",)
    for language in ("Python", "TypeScript", "JavaScript", "HTML", "CSS", "JSON", "YAML", "Shell", "PHP", "C++", "C#"):
        plan = install_plan_for_language(language)
        assert plan is not None and plan.safe, f"Safe LSP install plan missing: {language}"

    for language, tool in {"Python": "ruff", "TypeScript": "prettier", "C++": "clang-format", "Luau": "stylua"}.items():
        assert FORMATTER_BY_LANGUAGE.get(language) == tool, f"C1 formatter missing: {language}"
    assert LINTER_BY_LANGUAGE.get("Python") == "ruff"
    assert LINTER_BY_LANGUAGE.get("TypeScript") == "eslint"

    py_registry = {item["import_name"]: item for item in PYTHON_LIBRARY_REGISTRY}
    assert set(py_registry) == set(libraries), "Python/JSON library registry keys differ"
    for key, json_item in libraries.items():
        assert py_registry[key]["pip_name"] == json_item["pip_name"], f"pip mapping mismatch: {key}"
    assert LIBRARY_BUNDLES == registry_json["bundles"], "Python/JSON bundle definitions differ"

    main_text = MAIN.read_text(encoding="utf-8")
    for token in [
        "ProblemsTree",
        "_on_lsp_diagnostics_published",
        "_ensure_editor_lsp_open",
        "_sync_editor_lsp_change",
        "diagnosticsPublished",
        "LspServerTable",
        "LspOutlineTree",
        "request_lsp_completion",
        "request_lsp_hover",
        "request_lsp_signature_help",
        "request_lsp_definition",
        "request_lsp_references",
        "request_lsp_rename",
        "request_lsp_outline",
        "format_current_file",
        "lint_current_file",
        "format_on_save_enabled",
        "quality_diagnostics",
        "TestExplorerTree",
        "discover_project_tests",
        "run_tests_from_explorer",
        "testExplorerLastRun",
        "GitTree",
        "git_diff_view",
        "refresh_git_status",
        "git_stage_selected",
        "git_unstage_selected",
        "git_commit",
        "git_pull",
        "git_push",
        "create_project_from_template",
        "project_template_choices",
        "project_staffedup_meta",
        "portable_project_path",
        "inspect_staffedup_project",
        "apply_safe_staffedup_fixes",
        "ProjectHealthTree",
        "AIContextFileTree",
        "open_ai_context_dialog",
        "build_project_context",
        "format_selected_text_with_line_numbers",
    ]:
        assert token in main_text, f"B2/B3 integration token missing: {token}"

    transport_text = (CORE / "lsp_transport.py").read_text(encoding="utf-8")
    for token in [
        '"textDocument/didOpen"',
        '"textDocument/didChange"',
        '"textDocument/didSave"',
        '"textDocument/didClose"',
        'method == "textDocument/publishDiagnostics"',
        "interactiveResult",
        "def request_feature",
        '"snippetSupport": False',
    ]:
        assert token in transport_text, f"B2/B3 LSP token missing: {token}"
    for package_id in [
        "Python.Python.3.14", "astral-sh.uv", "OpenJS.NodeJS.LTS", "Git.Git",
        "Microsoft.PowerShell", "MSYS2.MSYS2", "EclipseAdoptium.Temurin.21.JDK",
        "GodotEngine.GodotEngine", "PHP.PHP.8.4",
    ]:
        assert package_id in main_text, f"Installer package id missing: {package_id}"

    print("PASS: Astra Studio Release 3.20 static smoke checks")
    print(f"Languages: {len(languages)}")
    print(f"Python registry entries: {len(registry_json['libraries'])}")
    print(f"Assets checked: {len(REQUIRED_ASSETS)}")
    print(f"Installer scripts checked: {len(REQUIRED_SCRIPTS)}")
    print(f"LSP language configs: {len(DEFAULT_LSP_SERVER_CONFIGS)}")


if __name__ == "__main__":
    main()
