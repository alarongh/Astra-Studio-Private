from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.project_commands import detect_project_commands  # noqa: E402
from core.project_doctor import inspect_project  # noqa: E402
from core.python_environment import dependency_files, detect_project_environment  # noqa: E402
from core.python_library_registry import extract_python_imports, package_record  # noqa: E402


class ProjectCommandsTests(unittest.TestCase):
    def test_plain_pyproject_does_not_invent_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8")
            commands = detect_project_commands(root)
            self.assertEqual(commands["test"], "")
            self.assertEqual(commands["install"], "{python-deps}")

    def test_pytest_config_enables_pytest_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts = "-q"\n', encoding="utf-8")
            self.assertEqual(detect_project_commands(root)["test"], "{python} -m pytest")

    def test_maven_does_not_invent_exec_java(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pom.xml").write_text("<project/>", encoding="utf-8")
            commands = detect_project_commands(root)
            self.assertEqual(commands["run"], "")
            self.assertEqual(commands["build"], "mvn package")
            self.assertEqual(commands["test"], "mvn test")

    def test_astra_project_file_is_not_rojo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "astral.project.json").write_text("{}", encoding="utf-8")
            commands = detect_project_commands(root)
            self.assertNotIn("rojo", commands["run"].lower())
            doctor_keys = {check.key for check in inspect_project(root)}
            self.assertNotIn("rojo", doctor_keys)

    def test_default_rojo_project_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "default.project.json").write_text("{}", encoding="utf-8")
            self.assertIn("{rojo} serve", detect_project_commands(root)["run"])
            doctor_keys = {check.key for check in inspect_project(root)}
            self.assertIn("rojo", doctor_keys)

    def test_node_lockfile_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": {"dev": "vite", "build": "vite build", "test": "vitest"}}), encoding="utf-8")
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            commands = detect_project_commands(root)
            self.assertEqual(commands["run"], "npm run dev")
            self.assertEqual(commands["build"], "npm run build")
            self.assertEqual(commands["test"], "npm run test")
            self.assertEqual(commands["install"], "npm ci")

    def test_yarn_classic_and_berry_install_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": {}}), encoding="utf-8")
            (root / "yarn.lock").write_text("", encoding="utf-8")
            self.assertEqual(detect_project_commands(root)["install"], "yarn install --frozen-lockfile")
            (root / ".yarnrc.yml").write_text("nodeLinker: node-modules\n", encoding="utf-8")
            self.assertEqual(detect_project_commands(root)["install"], "yarn install --immutable")

    def test_pnpm_bun_godot_cmake_dotnet_command_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": {"start": "node app.js"}}), encoding="utf-8")
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            commands = detect_project_commands(root)
            self.assertEqual(commands["run"], "pnpm run start")
            self.assertEqual(commands["install"], "pnpm install --frozen-lockfile")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": {}}), encoding="utf-8")
            (root / "bun.lock").write_text("", encoding="utf-8")
            self.assertEqual(detect_project_commands(root)["install"], "bun install --frozen-lockfile")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "project.godot").write_text("[application]\n", encoding="utf-8")
            self.assertEqual(detect_project_commands(root)["run"], "{godot} --path .")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
            self.assertEqual(detect_project_commands(root)["build"], "cmake -S . -B build && cmake --build build")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Demo.csproj").write_text("<Project />", encoding="utf-8")
            commands = detect_project_commands(root)
            self.assertEqual(commands["run"], "dotnet run")
            self.assertEqual(commands["build"], "dotnet build")
            self.assertEqual(commands["test"], "dotnet test")


class PythonEnvironmentTests(unittest.TestCase):
    def test_dependency_files_include_split_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("requests\n", encoding="utf-8")
            (root / "requirements-local.txt").write_text("pytest\n", encoding="utf-8")
            names = {path.name for path in dependency_files(root)}
            self.assertIn("requirements.txt", names)
            self.assertIn("requirements-local.txt", names)

    def test_project_environment_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = root / ".venv"
            python_path = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            python_path.parent.mkdir(parents=True)
            python_path.write_bytes(b"")
            info = detect_project_environment(root)
            self.assertEqual(info.environment_dir, env)
            self.assertEqual(info.python_executable, python_path)
            self.assertTrue(info.is_project_environment)

    def test_external_virtual_env_is_not_mistaken_for_project_env(self):
        with tempfile.TemporaryDirectory() as project_tmp, tempfile.TemporaryDirectory() as env_tmp:
            root = Path(project_tmp)
            old = os.environ.get("VIRTUAL_ENV")
            os.environ["VIRTUAL_ENV"] = env_tmp
            try:
                info = detect_project_environment(root)
            finally:
                if old is None:
                    os.environ.pop("VIRTUAL_ENV", None)
                else:
                    os.environ["VIRTUAL_ENV"] = old
            self.assertIsNone(info.environment_dir)
            self.assertIsNone(info.python_executable)
            self.assertEqual(info.source, "global")


class PythonRegistryTests(unittest.TestCase):
    def test_known_import_to_pip_mappings(self):
        expected = {
            "sklearn": "scikit-learn",
            "PIL": "Pillow",
            "cv2": "opencv-python",
            "bs4": "beautifulsoup4",
            "docx": "python-docx",
            "pptx": "python-pptx",
            "yaml": "PyYAML",
        }
        for import_name, pip_name in expected.items():
            with self.subTest(import_name=import_name):
                self.assertEqual(package_record(import_name)["pip_name"], pip_name)

    def test_relative_imports_are_not_external_dependencies(self):
        source = "from .utils import helper\nfrom ..core import item\nimport requests\n"
        self.assertEqual(extract_python_imports(source), ["requests"])


class TaskManagerStaticTests(unittest.TestCase):
    def test_background_output_has_windows_fallback_decoding(self):
        text = (ROOT / "core" / "task_manager.py").read_text(encoding="utf-8")
        self.assertIn('("utf-8", "cp866", "cp1251")', text)
        self.assertIn("_decode_process_output(raw.data(), self.spec.output_encoding)", text)
        self.assertIn("output_encoding: str | None = None", text)

    def test_task_slot_is_reserved_until_terminal_signal_and_shutdown_can_wait(self):
        text = (ROOT / "core" / "task_manager.py").read_text(encoding="utf-8")
        self.assertIn("return self.current_task is not None", text)
        self.assertIn("def cancel_and_wait", text)
        self.assertIn("process.waitForFinished", text)


class MainStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "main.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_release_number(self):
        assignment = next(
            node for node in self.tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "APP_VERSION" for target in node.targets)
        )
        self.assertEqual(ast.literal_eval(assignment.value), "Release 3.20")

    def test_jsonc_parser_accepts_comments_urls_and_trailing_commas(self):
        wanted = {"_strip_jsonc_comments", "_strip_jsonc_trailing_commas", "loads_jsonc"}
        nodes = [node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        self.assertEqual({node.name for node in nodes}, wanted)
        namespace = {"json": json}
        module = ast.Module(body=nodes, type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, "<jsonc-test>", "exec"), namespace)
        data = namespace["loads_jsonc"]('''{
            // comment
            "url": "https://example.com/a//b",
            "text": "/* not a comment */",
            "items": [1, 2,],
        }''')
        self.assertEqual(data["url"], "https://example.com/a//b")
        self.assertEqual(data["text"], "/* not a comment */")
        self.assertEqual(data["items"], [1, 2])

    def test_jsx_is_recognized_as_javascript(self):
        self.assertIn('".jsx"', self.source)
        self.assertIn('JavaScript (*.js *.mjs *.cjs *.jsx)', self.source)

    def test_search_replace_rescans_and_preserves_legacy_encoding(self):
        self.assertIn("Always rescan with the current query/options", self.source)
        self.assertIn('return path.read_text(encoding="cp1251"), "cp1251"', self.source)
        self.assertIn('path.write_text(updated, encoding=target_encoding)', self.source)


    def test_settings_load_save_key_parity(self):
        cls = next(node for node in self.tree.body if isinstance(node, ast.ClassDef) and node.name == "AstraStudio")
        load = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_load_settings")
        save = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_save_settings")

        loaded = set()
        for node in ast.walk(load):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "data"
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                loaded.add(node.args[0].value)

        saved = set()
        for node in ast.walk(save):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "data" for t in node.targets) and isinstance(node.value, ast.Dict):
                saved.update(
                    key.value for key in node.value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
        legacy_appearance_keys = {
            "aux_bg_transparency_percent",
            "console_bg_transparency_percent",
            "console_blur_percent",
            "editor_bg_transparency_percent",
            "editor_blur_percent",
            "project_bg_transparency_percent",
            "project_blur_percent",
            "settings_bg_transparency_percent",
            "settings_blur_percent",
        }
        self.assertLessEqual(saved, loaded)
        self.assertEqual(loaded - saved, legacy_appearance_keys)
        self.assertGreaterEqual(len(saved), 35)

    def test_all_languages_have_compile_and_run_branches(self):
        cls = next(node for node in self.tree.body if isinstance(node, ast.ClassDef) and node.name == "AstraStudio")
        methods = {node.name: ast.get_source_segment(self.source, node) or "" for node in cls.body if isinstance(node, ast.FunctionDef)}
        compile_source = methods["compile_code"]
        run_source = methods["run_code"]
        required = [
            "Python", "C++", "Java", "HTML", "CSS", "JavaScript", "TypeScript", "Luau",
            "GDScript", "PHP", "PowerShell", "C#", "SQL", "JSON", "YAML", "Markdown",
            "TOML", "XML", "Shell", "Dockerfile",
        ]
        for language in required:
            with self.subTest(language=language, mode="compile"):
                self.assertIn(f'"{language}"', compile_source)
            with self.subTest(language=language, mode="run"):
                self.assertIn(f'"{language}"', run_source)

    def test_embedded_installer_resolves_get_item_paths_and_uses_stable_shortcut_icon(self):
        self.assertIn("function Resolve-ToolPath($tool)", self.source)
        installer_start = self.source.index("    def _installer_script(self, kind: str) -> str:")
        installer_end = self.source.index("\n    def ", installer_start + 20)
        installer = self.source[installer_start:installer_end]
        self.assertNotIn("WScript.Shell", installer)
        self.assertNotIn("stableIcon", installer)
        self.assertIn("def create_or_update_desktop_shortcut(self):", self.source)
        for name in ("node", "npm", "uv", "git", "pwsh", "godot", "php"):
            self.assertIn(f"Resolve-ToolPath ${name}", self.source)

    def test_project_python_mutations_guard_invalid_override(self):
        self.assertIn("Сохранённый Python-интерпретатор проекта больше недоступен", self.source)
        self.assertIn("Экспорт остановлен, чтобы случайно не выгрузить глобальное окружение", self.source)

    def test_no_temporary_23_release_identity(self):
        self.assertNotIn("Release 2.3", self.source)
        self.assertNotIn("Astra_Studio_Release_2_3", self.source)


class LspIntegrationStaticTests(unittest.TestCase):
    def test_main_owns_lsp_manager_and_shuts_it_down(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from core.lsp_transport import LspManager", text)
        self.assertIn("self.lsp_manager = LspManager", text)
        self.assertLess(text.index("self._load_settings()"), text.index("self.lsp_manager = LspManager"))
        self.assertGreaterEqual(text.count("self.lsp_manager.set_project_root"), 2)
        self.assertIn("self.lsp_manager.shutdown_all(wait=True)", text)

    def test_lsp_transport_has_full_b1_lifecycle_and_restart_budget(self):
        text = (ROOT / "core" / "lsp_transport.py").read_text(encoding="utf-8")
        for token in (
            'send_request("initialize"',
            'send_notification("initialized"',
            'send_request("shutdown"',
            'send_notification("exit"',
            "restartScheduled",
            "max_restarts",
            "restart_base_delay_ms",
            "ProcessChannelMode.SeparateChannels",
        ):
            self.assertIn(token, text)
        self.assertNotIn("from .task_manager", text)
        self.assertNotIn("TaskManager(", text)

    def test_lsp_protocol_has_framing_safety_limits(self):
        text = (ROOT / "core" / "lsp_protocol.py").read_text(encoding="utf-8")
        self.assertIn("Content-Length", text)
        self.assertIn("MAX_HEADER_BYTES", text)
        self.assertIn("MAX_CONTENT_BYTES", text)



class InstallerStaticTests(unittest.TestCase):
    def test_common_installer_stops_on_powershell_errors(self):
        text = (ROOT / "scripts" / "_common_installer.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('$ErrorActionPreference = "Stop"', text)

    def test_existing_python_is_checked_before_winget(self):
        text = (ROOT / "scripts" / "install_python.ps1").read_text(encoding="utf-8-sig")
        self.assertLess(text.index("Find-WorkingPython"), text.index("Ensure-Winget"))

    def test_existing_cpp_is_checked_before_winget(self):
        text = (ROOT / "scripts" / "install_cpp.ps1").read_text(encoding="utf-8-sig")
        self.assertLess(text.index("Get-Command g++"), text.index("Ensure-Winget"))

    def test_existing_java_is_checked_before_winget(self):
        text = (ROOT / "scripts" / "install_java.ps1").read_text(encoding="utf-8-sig")
        self.assertLess(text.index("Get-Command javac"), text.index("Ensure-Winget"))

    def test_build_batch_stops_after_failed_steps(self):
        text = (ROOT / "build_exe.bat").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.lower().count("if errorlevel 1"), 3)
        self.assertIn("astra_studio.spec", text)
        self.assertIn('if not exist "dist\\Astra Studio\\Astra Studio.exe"', text)

    def test_standalone_installers_resolve_source_or_fullname(self):
        for name in ("install_node.ps1", "install_uv.ps1", "install_git.ps1", "install_powershell.ps1", "install_godot.ps1", "install_php.ps1"):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8-sig")
            with self.subTest(script=name):
                self.assertIn(".Source", text)
                self.assertIn(".FullName", text)

    def test_shortcut_script_uses_stable_app_directory_icon(self):
        text = (ROOT / "scripts" / "create_desktop_shortcut.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('$iconNames = @{ classic = "astra.ico"; angel404 = "astra_angel404.ico"; legacy = "legacy_astra.ico" }', text)
        self.assertIn('Join-Path $appDir "_internal\\assets\\$iconName"', text)
        self.assertIn("DesktopPathOverride", text)
        self.assertNotIn("_MEIPASS", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
