from __future__ import annotations

import json
import os
from pathlib import Path
import stat
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

from core.lsp_servers import (  # noqa: E402
    DEFAULT_LSP_SERVER_CONFIGS,
    LspServerRegistry,
    ResolvedLspServer,
    find_server_executable,
)
from core.lsp_protocol import (  # noqa: E402
    JsonRpcStreamParser,
    LspProtocolError,
    encode_jsonrpc_message,
)

if HAVE_PYSIDE6:
    from core.lsp_transport import LspClientConnection  # noqa: E402
else:
    LspClientConnection = None


class JsonRpcFramingTests(unittest.TestCase):
    def test_fragmented_and_back_to_back_messages(self):
        first = {"jsonrpc": "2.0", "id": 1, "result": {"text": "привет"}}
        second = {"jsonrpc": "2.0", "method": "window/logMessage", "params": {"type": 3}}
        raw = encode_jsonrpc_message(first) + encode_jsonrpc_message(second)
        parser = JsonRpcStreamParser()
        parsed = []
        for chunk in (raw[:7], raw[7:31], raw[31:53], raw[53:]):
            parsed.extend(parser.feed(chunk))
        self.assertEqual(parsed, [first, second])

    def test_invalid_content_length_is_rejected(self):
        parser = JsonRpcStreamParser()
        with self.assertRaises(LspProtocolError):
            parser.feed(b"Content-Length: nope\r\n\r\n{}")

    def test_oversized_payload_is_rejected_before_body_allocation(self):
        parser = JsonRpcStreamParser()
        too_large = parser.MAX_CONTENT_BYTES + 1
        with self.assertRaises(LspProtocolError):
            parser.feed(f"Content-Length: {too_large}\r\n\r\n".encode("ascii"))


class LspRegistryTests(unittest.TestCase):
    def test_key_language_configs_are_explicit(self):
        self.assertEqual(DEFAULT_LSP_SERVER_CONFIGS["Python"].candidates[-1].command, "pyright-langserver")
        self.assertEqual(DEFAULT_LSP_SERVER_CONFIGS["TypeScript"].candidates[0].arguments, ("--stdio",))
        self.assertEqual(DEFAULT_LSP_SERVER_CONFIGS["C++"].candidates[0].command, "clangd")
        self.assertEqual(DEFAULT_LSP_SERVER_CONFIGS["Luau"].candidates[0].arguments, ("lsp",))
        self.assertEqual(DEFAULT_LSP_SERVER_CONFIGS["GDScript"].transport, "external_tcp")
        self.assertEqual(DEFAULT_LSP_SERVER_CONFIGS["GDScript"].port, 6005)

    def test_user_override_replaces_candidates_without_touching_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "lsp_servers.json"
            config_path.write_text(json.dumps({
                "servers": {
                    "Python": {
                        "candidates": [{"command": "custom-py-lsp", "args": ["--stdio"]}],
                        "max_restarts": 5,
                    }
                }
            }), encoding="utf-8")
            registry = LspServerRegistry(config_path)
            config = registry.config_for_language("Python")
            self.assertEqual(config.candidates[0].command, "custom-py-lsp")
            self.assertEqual(config.candidates[0].arguments, ("--stdio",))
            self.assertEqual(config.max_restarts, 5)
            self.assertEqual(DEFAULT_LSP_SERVER_CONFIGS["Python"].max_restarts, 3)

    def test_invalid_override_types_do_not_poison_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "lsp_servers.json"
            config_path.write_text(json.dumps({
                "Python": {
                    "max_restarts": "many",
                    "restart_base_delay_ms": "later",
                    "enabled": "yes",
                    "port": 99999,
                }
            }), encoding="utf-8")
            config = LspServerRegistry(config_path).config_for_language("Python")
            self.assertEqual(config.max_restarts, 3)
            self.assertEqual(config.restart_base_delay_ms, 500)
            self.assertIs(config.enabled, True)
            self.assertIsNone(config.port)

    def test_catalog_covers_every_astra_language(self):
        expected = {
            "Python", "C++", "Java", "HTML", "CSS", "JavaScript", "TypeScript", "Luau",
            "GDScript", "PHP", "PowerShell", "C#", "SQL", "JSON", "YAML", "Markdown",
            "TOML", "XML", "Shell", "Dockerfile",
        }
        self.assertEqual(set(DEFAULT_LSP_SERVER_CONFIGS), expected)

    @unittest.skipIf(os.name == "nt", "Executable-bit test is POSIX-specific")
    def test_project_local_node_bin_has_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_bin = root / "node_modules" / ".bin"
            local_bin.mkdir(parents=True)
            executable = local_bin / "typescript-language-server"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
            self.assertEqual(find_server_executable("typescript-language-server", root), str(executable))


@unittest.skipUnless(HAVE_PYSIDE6, "PySide6 is not installed in this sandbox")
class LspProcessLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.fake_server = ROOT / "tests" / "fake_lsp_server.py"

    def wait_until(self, predicate, timeout=4.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.005)
        self.app.processEvents()
        return bool(predicate())

    def make_server(self, *extra_args, max_restarts=2, restart_delay=20):
        return ResolvedLspServer(
            language="Test",
            language_id="test",
            executable=sys.executable,
            arguments=(str(self.fake_server), *map(str, extra_args)),
            restart_enabled=True,
            max_restarts=max_restarts,
            restart_base_delay_ms=restart_delay,
        )

    def test_initialize_server_request_and_graceful_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            connection = LspClientConnection(self.make_server(), Path(tmp))
            initialized = []
            requests = []
            connection.initialized.connect(lambda _lang, caps: initialized.append(caps))
            connection.serverRequestReceived.connect(lambda _lang, method, _params: requests.append(method))
            connection.start()
            self.assertTrue(self.wait_until(lambda: bool(initialized)))
            self.assertEqual(connection.state, LspClientConnection.READY)
            self.assertTrue(initialized[0].get("hoverProvider"))
            self.assertTrue(self.wait_until(lambda: "workspace/configuration" in requests))
            connection.shutdown_and_wait(1800)
            self.assertEqual(connection.state, LspClientConnection.STOPPED)
            self.assertFalse(connection.is_running())

    def test_unexpected_exit_restarts_with_backoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "crash.marker"
            connection = LspClientConnection(
                self.make_server("--crash-once-marker", marker, max_restarts=2, restart_delay=20),
                Path(tmp),
            )
            restarts = []
            initialized = []
            connection.restartScheduled.connect(lambda _lang, attempt, delay: restarts.append((attempt, delay)))
            connection.initialized.connect(lambda _lang, caps: initialized.append(caps))
            connection.start()
            self.assertTrue(self.wait_until(lambda: bool(initialized), timeout=5.0))
            self.assertGreaterEqual(len(restarts), 1)
            self.assertEqual(restarts[0][0], 1)
            self.assertEqual(connection.state, LspClientConnection.READY)
            connection.shutdown_and_wait(1800)
            self.assertEqual(connection.state, LspClientConnection.STOPPED)


if __name__ == "__main__":
    unittest.main()
