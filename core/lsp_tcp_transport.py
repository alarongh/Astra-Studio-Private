from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Any

from PySide6.QtCore import QObject, QCoreApplication, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

from .lsp_protocol import JsonRpcStreamParser, LspProtocolError, encode_jsonrpc_message, path_to_uri
from .lsp_servers import ResolvedLspServer


@dataclass(slots=True)
class PendingRequest:
    method: str
    created_at: float


class LspTcpConnection(QObject):
    """LSP client connection for externally-owned TCP servers such as Godot.

    Godot owns the language-server process, so Astra only manages the socket and
    protocol lifecycle. The public signals/methods intentionally mirror
    LspClientConnection so LspManager can treat both transports uniformly.
    """

    stateChanged = Signal(str, str)
    logMessage = Signal(str, str)
    initialized = Signal(str, object)
    notificationReceived = Signal(str, str, object)
    serverRequestReceived = Signal(str, str, object)
    responseReceived = Signal(str, object, object, object)
    crashed = Signal(str, int, str)
    restartScheduled = Signal(str, int, int)
    permanentFailure = Signal(str, str)

    STOPPED = "stopped"
    STARTING = "starting"
    INITIALIZING = "initializing"
    READY = "ready"
    RESTARTING = "restarting"
    SHUTTING_DOWN = "shutting_down"
    FAILED = "failed"

    def __init__(self, server: ResolvedLspServer, project_root: Path | str, parent: QObject | None = None):
        super().__init__(parent)
        if server.transport != "external_tcp":
            raise ValueError(f"Unsupported TCP LSP transport: {server.transport}")
        if not server.host or server.port is None:
            raise ValueError("TCP LSP server requires host and port")
        self.server = server
        self.project_root = Path(project_root).resolve()
        self.socket: QTcpSocket | None = None
        self.state = self.STOPPED
        self.server_capabilities: dict[str, Any] = {}
        self._parser = JsonRpcStreamParser()
        self._next_request_id = 1
        self._pending: dict[int | str, PendingRequest] = {}
        self._initialize_request_id: int | None = None
        self._shutdown_request_id: int | None = None
        self._expected_shutdown = False
        self._restart_attempts = 0
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(self._restart_after_disconnect)
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setSingleShot(True)
        self._shutdown_timer.timeout.connect(self._force_disconnect_after_timeout)
        self._failure_emitted = False

    @property
    def language(self) -> str:
        return self.server.language

    @property
    def process(self):
        # Compatibility for callers that only check whether a connection owns a
        # child QProcess. TCP servers are externally owned, so this is always None.
        return None

    def _set_state(self, state: str):
        if state == self.state:
            return
        self.state = state
        self.stateChanged.emit(self.language, state)

    def is_running(self) -> bool:
        return bool(self.socket and self.socket.state() != QAbstractSocket.SocketState.UnconnectedState)

    def start(self):
        if self.is_running() or self.state in {self.STARTING, self.INITIALIZING, self.READY}:
            return
        self._restart_timer.stop()
        self._shutdown_timer.stop()
        self._expected_shutdown = False
        self._failure_emitted = False
        self._parser.reset()
        self._pending.clear()
        self._initialize_request_id = None
        self._shutdown_request_id = None
        self.server_capabilities = {}

        socket = QTcpSocket(self)
        socket.connected.connect(self._on_connected)
        socket.readyRead.connect(self._read_socket)
        socket.errorOccurred.connect(self._on_socket_error)
        socket.disconnected.connect(self._on_disconnected)
        self.socket = socket
        self._set_state(self.STARTING)
        self.logMessage.emit(self.language, f"Connecting LSP TCP: {self.server.host}:{self.server.port}")
        socket.connectToHost(self.server.host, int(self.server.port))

    def _on_connected(self):
        if self._expected_shutdown:
            self._force_disconnect()
            return
        self._set_state(self.INITIALIZING)
        self._initialize_request_id = self.send_request("initialize", self._initialize_params())

    def _initialize_params(self) -> dict[str, Any]:
        root_uri = path_to_uri(self.project_root)
        return {
            "processId": os.getpid(),
            "clientInfo": {"name": "Astra Studio", "version": "3.1"},
            "locale": "ru",
            "rootPath": str(self.project_root),
            "rootUri": root_uri,
            "workspaceFolders": [{"uri": root_uri, "name": self.project_root.name or "workspace"}],
            "capabilities": {
                "workspace": {"workspaceFolders": True, "configuration": True},
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": False,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                        "didSave": True,
                    },
                    "completion": {
                        "completionItem": {
                            "snippetSupport": False,
                            "documentationFormat": ["markdown", "plaintext"],
                        }
                    },
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "signatureHelp": {
                        "signatureInformation": {
                            "documentationFormat": ["markdown", "plaintext"],
                            "parameterInformation": {"labelOffsetSupport": True},
                        }
                    },
                    "definition": {"linkSupport": True},
                    "references": {},
                    "rename": {"prepareSupport": False},
                    "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                },
                "workspace": {
                    "workspaceFolders": True,
                    "configuration": True,
                    "workspaceEdit": {"documentChanges": True},
                },
                "window": {"workDoneProgress": True},
            },
            "initializationOptions": dict(self.server.initialization_options),
            "trace": "off",
        }

    def send_request(self, method: str, params: Any = None) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._pending[request_id] = PendingRequest(method=method, created_at=time.monotonic())
        self._write_payload(payload)
        return request_id

    def send_notification(self, method: str, params: Any = None):
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._write_payload(payload)

    def _send_response(self, request_id: int | str, result: Any = None, error: dict[str, Any] | None = None):
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = result
        self._write_payload(payload)

    def _write_payload(self, payload: dict[str, Any]):
        socket = self.socket
        if not socket or socket.state() != QAbstractSocket.SocketState.ConnectedState:
            raise RuntimeError(f"LSP TCP socket for {self.language} is not connected")
        written = socket.write(encode_jsonrpc_message(payload))
        if written < 0:
            raise RuntimeError(f"Failed to write to LSP TCP socket for {self.language}")
        socket.flush()

    def _read_socket(self):
        socket = self.socket
        if not socket:
            return
        data = bytes(socket.readAll())
        if not data:
            return
        try:
            messages = self._parser.feed(data)
        except LspProtocolError as exc:
            self.logMessage.emit(self.language, f"LSP protocol error: {exc}")
            self._emit_failure_once(str(exc))
            self._expected_shutdown = True
            self._set_state(self.FAILED)
            self._force_disconnect()
            return
        for message in messages:
            self._handle_message(message)

    def _handle_message(self, message: dict[str, Any]):
        if "method" in message:
            method = str(message.get("method") or "")
            params = message.get("params")
            if "id" in message:
                self.serverRequestReceived.emit(self.language, method, params)
                self._handle_server_request(message.get("id"), method, params)
            else:
                self.notificationReceived.emit(self.language, method, params)
            return

        request_id = message.get("id")
        pending = self._pending.pop(request_id, None)
        result = message.get("result")
        error = message.get("error")
        self.responseReceived.emit(self.language, request_id, result, error)

        if request_id == self._initialize_request_id:
            self._initialize_request_id = None
            if error is not None:
                self._fail_initialization(error)
                return
            capabilities = result.get("capabilities", {}) if isinstance(result, dict) else {}
            self.server_capabilities = capabilities if isinstance(capabilities, dict) else {}
            self.send_notification("initialized", {})
            self._set_state(self.READY)
            self.initialized.emit(self.language, dict(self.server_capabilities))
            return

        if request_id == self._shutdown_request_id:
            self._shutdown_request_id = None
            self._shutdown_timer.stop()
            try:
                self.send_notification("exit")
            except RuntimeError:
                pass
            QTimer.singleShot(80, self._force_disconnect)
            return

        if pending is None:
            self.logMessage.emit(self.language, f"Received response for unknown request id {request_id!r}")

    def _handle_server_request(self, request_id: int | str, method: str, params: Any):
        if method == "workspace/configuration":
            items = params.get("items", []) if isinstance(params, dict) else []
            self._send_response(request_id, [None for _ in items])
            return
        if method in {"client/registerCapability", "client/unregisterCapability", "window/workDoneProgress/create"}:
            self._send_response(request_id, None)
            return
        if method == "workspace/workspaceFolders":
            self._send_response(
                request_id,
                [{"uri": path_to_uri(self.project_root), "name": self.project_root.name or "workspace"}],
            )
            return
        if method == "workspace/applyEdit":
            self._send_response(
                request_id,
                {"applied": False, "failureReason": "Workspace edits are implemented in a later Astra LSP stage."},
            )
            return
        self._send_response(request_id, error={"code": -32601, "message": f"Method not implemented by Astra LSP client: {method}"})

    def _fail_initialization(self, error: Any):
        summary = f"LSP initialize failed: {error}"
        self.logMessage.emit(self.language, summary)
        self._emit_failure_once(summary)
        self._expected_shutdown = True
        self._set_state(self.FAILED)
        self._force_disconnect()

    def _emit_failure_once(self, message: str):
        if self._failure_emitted:
            return
        self._failure_emitted = True
        self.permanentFailure.emit(self.language, message)

    def _on_socket_error(self, _error):
        socket = self.socket
        message = socket.errorString() if socket else "Unknown LSP TCP error"
        self.logMessage.emit(self.language, message)
        if self._expected_shutdown:
            return
        self._emit_failure_once(message)
        self._set_state(self.FAILED)

    def _on_disconnected(self):
        self._shutdown_timer.stop()
        self.socket = None
        self._pending.clear()
        self._initialize_request_id = None
        self._shutdown_request_id = None
        if self._expected_shutdown:
            if self.state != self.FAILED:
                self._set_state(self.STOPPED)
            return

        summary = "LSP TCP connection closed"
        self.crashed.emit(self.language, 0, summary)
        self.logMessage.emit(self.language, summary)
        if self.server.restart_enabled and self._restart_attempts < self.server.max_restarts:
            self._restart_attempts += 1
            delay = min(8000, max(0, self.server.restart_base_delay_ms) * (2 ** (self._restart_attempts - 1)))
            self._set_state(self.RESTARTING)
            self.restartScheduled.emit(self.language, self._restart_attempts, delay)
            self._restart_timer.start(delay)
        else:
            self._set_state(self.FAILED)
            self._emit_failure_once("External language server is not available. Start it and retry the LSP connection.")

    def _restart_after_disconnect(self):
        if not self._expected_shutdown:
            self.start()

    def restart(self):
        self._restart_attempts = 0
        self._expected_shutdown = True
        self._restart_timer.stop()
        self._force_disconnect()
        self._expected_shutdown = False
        self.start()

    def shutdown(self, timeout_ms: int = 1200):
        self._restart_timer.stop()
        previous_state = self.state
        self._expected_shutdown = True
        socket = self.socket
        if not socket or socket.state() == QAbstractSocket.SocketState.UnconnectedState:
            self.socket = None
            self._set_state(self.STOPPED)
            return
        self._set_state(self.SHUTTING_DOWN)
        if previous_state == self.READY and self._shutdown_request_id is None:
            try:
                self._shutdown_request_id = self.send_request("shutdown")
                self._shutdown_timer.start(max(100, int(timeout_ms)))
                return
            except RuntimeError:
                pass
        self._force_disconnect()

    def _force_disconnect_after_timeout(self):
        try:
            self.send_notification("exit")
        except RuntimeError:
            pass
        self._force_disconnect()

    def _force_disconnect(self):
        socket = self.socket
        if not socket:
            return
        socket.disconnectFromHost()
        if socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            socket.abort()

    def shutdown_and_wait(self, timeout_ms: int = 1800):
        self.shutdown(min(1200, max(100, int(timeout_ms))))
        deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
        app = QCoreApplication.instance()
        while self.socket and self.socket.state() != QAbstractSocket.SocketState.UnconnectedState and time.monotonic() < deadline:
            if app is not None:
                app.processEvents()
            # Processing the shutdown reply may synchronously run the socket's
            # disconnected handler and clear self.socket. Keep the lifecycle
            # check after processEvents so shutdown cannot dereference None.
            socket = self.socket
            if not socket or socket.state() == QAbstractSocket.SocketState.UnconnectedState:
                break
            socket.waitForReadyRead(20)
            if self.socket is socket:
                self._read_socket()
            time.sleep(0.005)
        if self.socket and self.socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            self.socket.abort()
        self.socket = None
        if self.state != self.FAILED:
            self._set_state(self.STOPPED)
