from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
import unittest

try:
    from PySide6.QtCore import QCoreApplication
    HAVE_PYSIDE6 = True
except ImportError:
    QCoreApplication = None
    HAVE_PYSIDE6 = False

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.lsp_features import (  # noqa: E402
    LspTextEdit,
    apply_text_edits,
    hover_text,
    normalize_completion_items,
    normalize_document_symbols,
    normalize_locations,
    normalize_workspace_edit,
    signature_help_text,
    workspace_edit_has_resource_operations,
)
from core.lsp_protocol import path_to_uri  # noqa: E402
from core.lsp_servers import (  # noqa: E402
    LspServerRegistry,
    ResolvedLspServer,
    install_plan_for_language,
)

if HAVE_PYSIDE6:
    from core.lsp_transport import LspManager  # noqa: E402
else:
    LspManager = None


class CompletionNormalizationTests(unittest.TestCase):
    def test_completion_list_is_normalized_and_sorted(self):
        items = normalize_completion_items({
            "isIncomplete": False,
            "items": [
                {"label": "beta", "sortText": "2", "detail": "B"},
                {"label": "alpha", "sortText": "1", "documentation": {"kind": "markdown", "value": "docs"}},
            ],
        })
        self.assertEqual([item["label"] for item in items], ["alpha", "beta"])
        self.assertEqual(items[0]["documentation"], "docs")

    def test_completion_text_edit_is_preserved(self):
        items = normalize_completion_items([{
            "label": "print",
            "textEdit": {
                "range": {"start": {"line": 1, "character": 2}, "end": {"line": 1, "character": 4}},
                "newText": "print",
            },
        }])
        self.assertEqual(items[0]["text_edit"]["newText"], "print")


class HoverSignatureTests(unittest.TestCase):
    def test_hover_markup_content_becomes_text(self):
        self.assertEqual(hover_text({"contents": {"kind": "markdown", "value": "**demo**"}}), "**demo**")

    def test_signature_help_contains_active_parameter(self):
        text = signature_help_text({
            "activeSignature": 0,
            "activeParameter": 1,
            "signatures": [{
                "label": "sum(a: int, b: int)",
                "documentation": "Adds values",
                "parameters": [
                    {"label": "a: int"},
                    {"label": "b: int", "documentation": "second value"},
                ],
            }],
        })
        self.assertIn("sum(a: int, b: int)", text)
        self.assertIn("b: int", text)
        self.assertIn("second value", text)


class NavigationNormalizationTests(unittest.TestCase):
    def test_location_and_location_link_are_supported(self):
        locations = normalize_locations([
            {
                "uri": "file:///tmp/a.py",
                "range": {"start": {"line": 1, "character": 2}, "end": {"line": 1, "character": 5}},
            },
            {
                "targetUri": "file:///tmp/b.py",
                "targetSelectionRange": {"start": {"line": 3, "character": 4}, "end": {"line": 3, "character": 7}},
            },
        ])
        self.assertEqual(len(locations), 2)
        self.assertEqual((locations[1].line, locations[1].character), (3, 4))

    def test_hierarchical_document_symbols_keep_depth(self):
        symbols = normalize_document_symbols([{
            "name": "Demo",
            "kind": 5,
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 5, "character": 0}},
            "selectionRange": {"start": {"line": 0, "character": 6}, "end": {"line": 0, "character": 10}},
            "children": [{
                "name": "run",
                "kind": 6,
                "range": {"start": {"line": 1, "character": 4}, "end": {"line": 3, "character": 0}},
                "selectionRange": {"start": {"line": 1, "character": 8}, "end": {"line": 1, "character": 11}},
            }],
        }])
        self.assertEqual([(item.name, item.depth) for item in symbols], [("Demo", 0), ("run", 1)])


class WorkspaceEditTests(unittest.TestCase):
    def test_workspace_edit_changes_and_document_changes_are_normalized(self):
        uri_a = "file:///tmp/a.py"
        uri_b = "file:///tmp/b.py"
        edits = normalize_workspace_edit({
            "changes": {uri_a: [{
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
                "newText": "A",
            }]},
            "documentChanges": [{
                "textDocument": {"uri": uri_b, "version": 2},
                "edits": [{
                    "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 1}},
                    "newText": "B",
                }],
            }],
        })
        self.assertEqual({edit.uri for edit in edits}, {uri_a, uri_b})

    def test_resource_operations_are_detected_and_can_be_rejected_by_ui(self):
        edit = {"documentChanges": [{"kind": "rename", "oldUri": "file:///tmp/a.py", "newUri": "file:///tmp/b.py"}]}
        self.assertTrue(workspace_edit_has_resource_operations(edit))
        self.assertFalse(workspace_edit_has_resource_operations({"changes": {}}))

    def test_text_edit_positions_follow_utf16_lsp_columns(self):
        text = "😀foo\nbar\n"
        edit = LspTextEdit(
            uri="file:///tmp/a.py",
            start_line=0,
            start_character=2,
            end_line=0,
            end_character=5,
            new_text="baz",
        )
        self.assertEqual(apply_text_edits(text, [edit]), "😀baz\nbar\n")

    def test_overlapping_text_edits_are_rejected(self):
        edits = [
            LspTextEdit("file:///tmp/a", 0, 1, 0, 4, "x"),
            LspTextEdit("file:///tmp/a", 0, 3, 0, 5, "y"),
        ]
        with self.assertRaises(ValueError):
            apply_text_edits("abcdef", edits)

    def test_text_edits_preserve_crlf_when_source_keeps_crlf(self):
        text = "alpha\r\nbeta\r\n"
        edit = LspTextEdit("file:///tmp/a", 1, 0, 1, 4, "BETA")
        self.assertEqual(apply_text_edits(text, [edit]), "alpha\r\nBETA\r\n")


class SafeInstallCatalogTests(unittest.TestCase):
    def test_staffedup_safe_install_plans_exist_for_core_servers(self):
        for language in ("Python", "TypeScript", "JavaScript", "HTML", "CSS", "JSON", "YAML", "Shell", "PHP", "C++", "C#"):
            with self.subTest(language=language):
                plan = install_plan_for_language(language)
                self.assertIsNotNone(plan)
                self.assertTrue(plan.safe)

    def test_gdscript_install_plan_is_external_not_auto_install(self):
        plan = install_plan_for_language("GDScript")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.kind, "external")
        self.assertFalse(plan.safe)


class StaticB3IntegrationTests(unittest.TestCase):
    def test_main_contains_all_b3_actions_and_shortcuts(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        for token in (
            "LspServerTable",
            "LspOutlineTree",
            'QKeySequence("Ctrl+Space")',
            'QKeySequence("Ctrl+Shift+H")',
            'QKeySequence("Ctrl+Shift+Space")',
            'QKeySequence("F12")',
            'QKeySequence("Shift+F12")',
            'QKeySequence("F2")',
            'QKeySequence("Ctrl+Shift+O")',
            "_apply_lsp_workspace_rename",
            'status = "ожидает внешний сервер"',
            '"needs_dotnet10"',
            '"needs_node22"',
            '(22, 22, 2)',
            'Path(r"C:\\Program Files\\LLVM\\bin")',
            'self._queued_lsp_requests.clear()',
            'self.lsp_manager.stop_server(language, wait=True)',
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_transport_routes_interactive_requests_with_tokens(self):
        text = (ROOT / "core" / "lsp_transport.py").read_text(encoding="utf-8")
        self.assertIn("interactiveResult", text)
        self.assertIn("def request_feature", text)
        for method in (
            "textDocument/completion",
            "textDocument/hover",
            "textDocument/signatureHelp",
            "textDocument/definition",
            "textDocument/references",
            "textDocument/rename",
            "textDocument/documentSymbol",
        ):
            self.assertIn(method, (ROOT / "core" / "lsp_features.py").read_text(encoding="utf-8"))

    def test_client_capabilities_advertise_b3_features_without_snippets(self):
        for name in ("lsp_transport.py", "lsp_tcp_transport.py"):
            text = (ROOT / "core" / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIn('"snippetSupport": False', text)
                self.assertIn('"hierarchicalDocumentSymbolSupport": True', text)
                self.assertIn('"documentChanges": True', text)


@unittest.skipUnless(HAVE_PYSIDE6, "PySide6 is not installed in this sandbox")
class LspInteractiveRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.fake_server = ROOT / "tests" / "fake_lsp_server.py"

    def wait_until(self, predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.005)
        self.app.processEvents()
        return bool(predicate())

    def test_manager_routes_completion_hover_signature_navigation_rename_and_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "demo.py"
            source.write_text("demo\n", encoding="utf-8")
            resolved = ResolvedLspServer(
                language="Python",
                language_id="python",
                executable=sys.executable,
                arguments=(str(self.fake_server),),
                restart_enabled=False,
            )
            manager = LspManager(project_root=root)
            manager.registry.resolve = lambda language, project_root=None: resolved if language == "Python" else None
            results = []
            manager.interactiveResult.connect(lambda language, feature, token, result, error: results.append((language, feature, token, result, error)))
            manager.open_document("Python", source, "demo\n")
            self.assertTrue(self.wait_until(lambda: manager.server_state("Python") == "ready"))
            for feature, extra in (
                ("completion", None),
                ("hover", None),
                ("signature_help", None),
                ("definition", None),
                ("references", None),
                ("rename", {"newName": "renamed"}),
                ("document_symbols", None),
            ):
                request_id = manager.request_feature("Python", feature, source, 0, 1, token={"feature": feature}, extra=extra)
                self.assertIsNotNone(request_id)
            self.assertTrue(self.wait_until(lambda: len(results) == 7))
            self.assertEqual({item[1] for item in results}, {
                "completion", "hover", "signature_help", "definition", "references", "rename", "document_symbols"
            })
            self.assertTrue(all(item[4] is None for item in results))
            manager.shutdown_all(wait=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
