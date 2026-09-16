from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
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

from core.lsp_documents import (  # noqa: E402
    LspDiagnosticsStore,
    LspDocumentStore,
    parse_publish_diagnostics,
)
from core.lsp_protocol import path_to_uri, uri_to_path  # noqa: E402
from core.lsp_servers import LspServerRegistry, ResolvedLspServer  # noqa: E402

if HAVE_PYSIDE6:
    from core.lsp_tcp_transport import LspTcpConnection  # noqa: E402
    from core.lsp_transport import LspManager  # noqa: E402
else:
    LspTcpConnection = None
    LspManager = None


class DocumentStoreTests(unittest.TestCase):
    def test_document_versions_increase_on_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.py"
            store = LspDocumentStore()
            doc, created = store.open_or_update("Python", "python", path, "print(1)\n")
            self.assertTrue(created)
            self.assertEqual(doc.version, 1)
            changed = store.change(path, "print(2)\n")
            self.assertIsNotNone(changed)
            self.assertEqual(changed.version, 2)
            self.assertEqual(store.documents_for_language("Python")[0].text, "print(2)\n")

    def test_close_removes_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.ts"
            store = LspDocumentStore()
            store.open_or_update("TypeScript", "typescript", path, "const x = 1")
            closed = store.close(path)
            self.assertIsNotNone(closed)
            self.assertIsNone(store.get(path))


class DiagnosticNormalizationTests(unittest.TestCase):
    def test_publish_diagnostics_is_normalized(self):
        uri = "file:///tmp/demo.py"
        parsed_uri, version, diagnostics = parse_publish_diagnostics({
            "uri": uri,
            "version": 3,
            "diagnostics": [{
                "range": {
                    "start": {"line": 4, "character": 2},
                    "end": {"line": 4, "character": 7},
                },
                "severity": 2,
                "source": "pyright",
                "code": "reportDemo",
                "message": "Demo warning",
            }],
        })
        self.assertEqual(parsed_uri, uri)
        self.assertEqual(version, 3)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].line, 4)
        self.assertEqual(diagnostics[0].severity_name, "Предупреждение")
        self.assertEqual(diagnostics[0].source, "pyright")

    def test_stale_versioned_diagnostics_are_ignored(self):
        uri = "file:///tmp/demo.py"
        store = LspDiagnosticsStore()
        store.update({"uri": uri, "version": 5, "diagnostics": [{
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
            "severity": 1,
            "message": "new",
        }]})
        store.update({"uri": uri, "version": 4, "diagnostics": []})
        current = store.for_uri(uri)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].message, "new")


class UriConversionTests(unittest.TestCase):
    def test_file_uri_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "папка с пробелом" / "file.py"
            path.parent.mkdir()
            uri = path_to_uri(path)
            restored = uri_to_path(uri)
            self.assertIsNotNone(restored)
            self.assertEqual(restored.resolve(), path.resolve())

    def test_non_file_uri_is_not_converted(self):
        self.assertIsNone(uri_to_path("untitled:demo.py"))


class ExternalTcpRegistryTests(unittest.TestCase):
    def test_gdscript_resolves_to_external_tcp(self):
        resolved = LspServerRegistry().resolve("GDScript", Path.cwd())
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.transport, "external_tcp")
        self.assertEqual(resolved.host, "127.0.0.1")
        self.assertEqual(resolved.port, 6005)


class StaticB2IntegrationTests(unittest.TestCase):
    def test_main_contains_problems_panel_and_document_sync_hooks(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        for token in (
            "ProblemsTree",
            "_on_lsp_diagnostics_published",
            "_ensure_editor_lsp_open",
            "_sync_editor_lsp_change",
            "close_document(editor.language_name, editor.file_path)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_transport_routes_publish_diagnostics(self):
        text = (ROOT / "core" / "lsp_transport.py").read_text(encoding="utf-8")
        self.assertIn('method == "textDocument/publishDiagnostics"', text)
        self.assertIn('"textDocument/didOpen"', text)
        self.assertIn('"textDocument/didChange"', text)
        self.assertIn('"textDocument/didSave"', text)
        self.assertIn('"textDocument/didClose"', text)


@unittest.skipUnless(HAVE_PYSIDE6, "PySide6 is not installed in this sandbox")
class LspDocumentIntegrationTests(unittest.TestCase):
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

    def test_manager_syncs_documents_and_collects_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "demo.py"
            source.write_text("BROKEN\n", encoding="utf-8")
            event_log = root / "events.jsonl"
            resolved = ResolvedLspServer(
                language="Python",
                language_id="python",
                executable=sys.executable,
                arguments=(str(self.fake_server), "--event-log", str(event_log)),
                restart_enabled=False,
            )
            manager = LspManager(project_root=root)
            manager.registry.resolve = lambda language, project_root=None: resolved if language == "Python" else None
            published = []
            manager.diagnosticsPublished.connect(lambda _lang, _uri, items: published.append(list(items)))
            manager.open_document("Python", source, "BROKEN\n")
            self.assertTrue(self.wait_until(lambda: any(items for items in published)))
            self.assertEqual(manager.all_diagnostics()[0].message, "Found BROKEN token")

            manager.change_document("Python", source, "fixed\n")
            self.assertTrue(self.wait_until(lambda: published and published[-1] == []))
            manager.save_document("Python", source, "fixed\n")
            manager.close_document("Python", source)
            self.assertTrue(self.wait_until(lambda: event_log.exists()))
            manager.shutdown_all(wait=True)

            methods = [json.loads(line)["method"] for line in event_log.read_text(encoding="utf-8").splitlines()]
            self.assertIn("textDocument/didOpen", methods)
            self.assertIn("textDocument/didChange", methods)
            self.assertIn("textDocument/didSave", methods)
            self.assertIn("textDocument/didClose", methods)


class _SocketLspServer:
    def __init__(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.error = None

    def start(self):
        self.thread.start()

    @staticmethod
    def _read_message(handle):
        headers = {}
        while True:
            line = handle.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            text = line.decode("ascii").strip()
            if ":" in text:
                key, value = text.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        size = int(headers.get("content-length", "0"))
        return json.loads(handle.read(size).decode("utf-8"))

    @staticmethod
    def _write_message(sock, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sock.sendall(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)

    def _run(self):
        try:
            conn, _addr = self.listener.accept()
            with conn:
                handle = conn.makefile("rb")
                while True:
                    message = self._read_message(handle)
                    if message is None:
                        return
                    method = message.get("method")
                    request_id = message.get("id")
                    if method == "initialize":
                        self._write_message(conn, {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {"capabilities": {"textDocumentSync": 1}},
                        })
                    elif method == "shutdown":
                        self._write_message(conn, {"jsonrpc": "2.0", "id": request_id, "result": None})
                    elif method == "exit":
                        return
        except Exception as exc:  # pragma: no cover - only visible in Qt-enabled integration runs
            self.error = exc
        finally:
            self.listener.close()


@unittest.skipUnless(HAVE_PYSIDE6, "PySide6 is not installed in this sandbox")
class LspTcpTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def wait_until(self, predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.005)
        self.app.processEvents()
        return bool(predicate())

    def test_external_tcp_initialize_and_shutdown(self):
        server = _SocketLspServer()
        server.start()
        with tempfile.TemporaryDirectory() as tmp:
            config = ResolvedLspServer(
                language="GDScript",
                language_id="gdscript",
                executable="",
                arguments=(),
                transport="external_tcp",
                host="127.0.0.1",
                port=server.port,
                restart_enabled=False,
            )
            connection = LspTcpConnection(config, Path(tmp))
            ready = []
            connection.initialized.connect(lambda _lang, caps: ready.append(caps))
            connection.start()
            self.assertTrue(self.wait_until(lambda: bool(ready)))
            self.assertEqual(connection.state, connection.READY)
            connection.shutdown_and_wait(1800)
            self.assertIn(connection.state, {connection.STOPPED, connection.FAILED})
            self.assertIsNone(server.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
