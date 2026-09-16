from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.test_explorer import (
    STATUS_FAILED,
    STATUS_PASSED,
    build_test_command,
    detect_test_adapters,
    discover_tests,
    parse_test_output,
    restore_test_run,
)


class AdapterDetectionTests(unittest.TestCase):
    def test_pytest_detected_from_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
            (root / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
            adapters = detect_test_adapters(root, "python")
            self.assertIn("pytest", {item.adapter_id for item in adapters})

    def test_unittest_detected_without_forcing_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test_demo.py").write_text(
                "import unittest\nclass Demo(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            adapters = detect_test_adapters(root, "python")
            ids = {item.adapter_id for item in adapters}
            self.assertIn("unittest", ids)
            self.assertNotIn("pytest", ids)

    @patch("core.test_explorer._manager_executable", return_value="npm")
    def test_vitest_jest_npm_adapter_detected_from_package_json(self, _manager):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({
                "scripts": {"test": "vitest run"},
                "devDependencies": {"vitest": "1.0.0"},
            }), encoding="utf-8")
            adapters = detect_test_adapters(root, None)
            npm = next(item for item in adapters if item.adapter_id == "npm")
            self.assertIn("Vitest", npm.display_name)
            self.assertTrue(npm.available)

    @patch("core.test_explorer.shutil.which")
    def test_dotnet_adapter_detected(self, which):
        which.return_value = "dotnet"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Demo.Tests.csproj").write_text("<Project />", encoding="utf-8")
            adapters = detect_test_adapters(root, None)
            self.assertIn("dotnet", {item.adapter_id for item in adapters})


class DiscoveryTests(unittest.TestCase):
    def test_pytest_discovery_preserves_node_ids_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            path = tests / "test_math.py"
            path.write_text(
                "def test_sum():\n    assert 1 + 1 == 2\n\nclass TestGroup:\n    def test_value(self):\n        assert True\n",
                encoding="utf-8",
            )
            nodes = discover_tests(root, "pytest")
            ids = {node.test_id for node in nodes}
            self.assertIn("tests/test_math.py::test_sum", ids)
            self.assertIn("tests/test_math.py::TestGroup::test_value", ids)
            self.assertEqual(next(node for node in nodes if node.label == "test_sum").line, 0)

    def test_unittest_discovery_builds_importable_test_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "test_demo.py"
            path.write_text(
                "import unittest\nclass Demo(unittest.TestCase):\n    def test_ok(self):\n        pass\n",
                encoding="utf-8",
            )
            nodes = discover_tests(root, "unittest")
            self.assertEqual(nodes[0].test_id, "test_demo.Demo.test_ok")

    def test_js_discovery_finds_test_and_spec_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "math.test.ts"
            path.write_text("test('adds numbers', () => {});\nit(\"subtracts\", () => {});\n", encoding="utf-8")
            nodes = discover_tests(root, "npm")
            self.assertEqual({node.label for node in nodes}, {"adds numbers", "subtracts"})

    def test_dotnet_discovery_finds_common_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "DemoTests.cs"
            path.write_text(
                "public class DemoTests {\n[Fact]\npublic void Works() {}\n[TestMethod]\npublic void AlsoWorks() {}\n}\n",
                encoding="utf-8",
            )
            nodes = discover_tests(root, "dotnet")
            self.assertEqual({node.label for node in nodes}, {"Works", "AlsoWorks"})

    def test_discovery_ignores_generated_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "bad.test.js").write_text("test('bad', () => {})", encoding="utf-8")
            (root / "good.test.js").write_text("test('good', () => {})", encoding="utf-8")
            nodes = discover_tests(root, "npm")
            self.assertEqual([node.label for node in nodes], ["good"])


class CommandTests(unittest.TestCase):
    def test_pytest_command_can_target_single_node(self):
        root = Path("/tmp/project")
        command = build_test_command(root, "pytest", "/python", "tests/test_a.py::test_x")
        self.assertEqual(command.program, "/python")
        self.assertIn("tests/test_a.py::test_x", command.arguments)
        self.assertIn("--tb=short", command.arguments)

    def test_unittest_command_can_target_single_test_id(self):
        root = Path("/tmp/project")
        command = build_test_command(root, "unittest", "/python", "test_demo.Demo.test_ok")
        self.assertEqual(command.arguments, ("-m", "unittest", "-v", "test_demo.Demo.test_ok"))

    @patch("core.test_explorer._manager_executable", return_value="npm")
    def test_npm_command_uses_existing_project_test_script(self, _manager):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8")
            command = build_test_command(root, "npm")
            self.assertEqual(command.program, "npm")
            self.assertEqual(command.arguments, ("run", "test"))

    @patch("core.test_explorer.shutil.which", return_value="dotnet")
    def test_dotnet_command_uses_console_logger(self, _which):
        command = build_test_command(Path("/tmp/project"), "dotnet")
        self.assertEqual(command.program, "dotnet")
        self.assertIn("console;verbosity=normal", command.arguments)


class ResultParserTests(unittest.TestCase):
    def test_pytest_verbose_output_updates_discovered_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test_demo.py").write_text("def test_ok(): pass\ndef test_bad(): pass\n", encoding="utf-8")
            discovered = discover_tests(root, "pytest")
            output = "test_demo.py::test_ok PASSED [ 50%]\ntest_demo.py::test_bad FAILED [100%]\n"
            result = parse_test_output("pytest", output, "", 1, discovered)
            statuses = {node.label: node.status for node in result.nodes}
            self.assertEqual(statuses["test_ok"], STATUS_PASSED)
            self.assertEqual(statuses["test_bad"], STATUS_FAILED)
            self.assertEqual(result.status, STATUS_FAILED)

    def test_unittest_output_parser(self):
        discovered = []
        stderr = "test_ok (test_demo.Demo.test_ok) ... ok\ntest_bad (test_demo.Demo.test_bad) ... FAIL\n"
        result = parse_test_output("unittest", "", stderr, 1, discovered)
        self.assertEqual(sum(node.status == STATUS_PASSED for node in result.nodes), 1)
        self.assertEqual(sum(node.status == STATUS_FAILED for node in result.nodes), 1)

    def test_vitest_jest_output_parser_strips_ansi(self):
        output = "\x1b[32m✓ adds numbers 5ms\x1b[0m\n\x1b[31m× subtracts\x1b[0m\n"
        result = parse_test_output("npm", output, "", 1, [])
        statuses = {node.label: node.status for node in result.nodes}
        self.assertEqual(statuses["adds numbers"], STATUS_PASSED)
        self.assertEqual(statuses["subtracts"], STATUS_FAILED)

    def test_dotnet_output_parser(self):
        output = "Passed Demo.Works [12 ms]\nFailed Demo.Breaks [3 ms]\n"
        result = parse_test_output("dotnet", output, "", 1, [])
        self.assertEqual({node.status for node in result.nodes}, {STATUS_PASSED, STATUS_FAILED})

    def test_last_run_round_trip(self):
        result = parse_test_output("pytest", "test_demo.py::test_ok PASSED\n", "", 0, [])
        restored = restore_test_run(result.to_dict())
        self.assertIsNotNone(restored)
        self.assertEqual(restored.adapter_id, "pytest")
        self.assertEqual(restored.status, STATUS_PASSED)
        self.assertEqual(restored.nodes[0].status, STATUS_PASSED)

    def test_invalid_last_run_is_ignored(self):
        self.assertIsNone(restore_test_run({"exitCode": "not-an-int"}))


class RuntimeCommandTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("pytest"), "pytest not installed in sandbox")
    def test_real_pytest_command_and_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test_demo.py").write_text(
                "def test_ok():\n    assert 2 + 2 == 4\n\ndef test_fail():\n    assert False\n",
                encoding="utf-8",
            )
            discovered = discover_tests(root, "pytest")
            command = build_test_command(root, "pytest", sys.executable)
            proc = subprocess.run([command.program, *command.arguments], cwd=root, capture_output=True, text=True, timeout=30)
            result = parse_test_output("pytest", proc.stdout, proc.stderr, proc.returncode, discovered)
            statuses = {node.label: node.status for node in result.nodes}
            self.assertEqual(statuses["test_ok"], STATUS_PASSED)
            self.assertEqual(statuses["test_fail"], STATUS_FAILED)

    def test_real_unittest_command_and_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test_demo.py").write_text(
                "import unittest\nclass Demo(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(2 + 2, 4)\n",
                encoding="utf-8",
            )
            discovered = discover_tests(root, "unittest")
            command = build_test_command(root, "unittest", sys.executable)
            proc = subprocess.run([command.program, *command.arguments], cwd=root, capture_output=True, text=True, timeout=30)
            result = parse_test_output("unittest", proc.stdout, proc.stderr, proc.returncode, discovered)
            self.assertEqual(result.status, STATUS_PASSED)
            self.assertEqual(result.nodes[0].status, STATUS_PASSED)


class MainIntegrationStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

    def test_test_explorer_ui_and_actions_present(self):
        for token in (
            "TestExplorerTree",
            "open_test_explorer",
            "discover_project_tests",
            "run_tests_from_explorer",
            "rerun_last_tests",
            '"mode": "test_explorer"',
        ):
            self.assertIn(token, self.source)

    def test_test_explorer_persists_last_run_in_project_payload(self):
        self.assertIn('"testExplorerLastRun"', self.source)
        self.assertIn("restore_test_run(test_last_run)", self.source)

    def test_unsaved_project_files_block_external_test_run(self):
        self.assertIn("Перед запуском тестов сохрани изменённые файлы проекта", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
