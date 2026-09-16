from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Any

from PySide6.QtCore import QObject, QCoreApplication, QProcess, QProcessEnvironment, QTimer, Signal

from .lsp_servers import LspServerRegistry, ResolvedLspServer
from .lsp_documents import LspDocumentStore, LspDiagnosticsStore
from .lsp_features import LSP_FEATURE_METHODS, text_document_position_params
from .lsp_tcp_transport import LspTcpConnection

from .lsp_protocol import JsonRpcStreamParser, LspProtocolError, encode_jsonrpc_message, path_to_uri


@dataclass(slots=True)
class PendingRequest:
    method: str
    created_at: float


class LspClientConnection(QObject):
    """One long-lived stdio LSP server connection.

    Transport/lifecycle originated in B1; Release 3.1 now layers document
    synchronization, diagnostics and interactive editor requests on top.
    """

    stateChanged = Signal(str, str)  # language, state
    logMessage = Signal(str, str)  # language, message
    initialized = Signal(str, object)  # language, server capabilities
    notificationReceived = Signal(str, str, object)  # language, method, params
    serverRequestReceived = Signal(str, str, object)  # language, method, params
    responseReceived = Signal(str, object, object, object)  # language, id, result, error
    crashed = Signal(str, int, str)  # language, exit code, summary
    restartScheduled = Signal(str, int, int)  # language, attempt, delay ms
    permanentFailure = Signal(str, str)

    STOPPED = "stopped"
    STARTING = "starting"
    INITIALIZING = "initializing"
    READY = "ready"
    RESTARTING = "restarting"
    SHUTTING_DOWN = "shutting_down"
    FAILED = "failed"

    def __init__(
        self,
        server: ResolvedLspServer,
        project_root: Path | str,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        if server.transport != "stdio":
            raise ValueError(f"Unsupported LSP transport in B1: {server.transport}")
        self.server = server
        self.project_root = Path(project_root).resolve()
        self.process: QProcess | None = None
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
        self._restart_timer.timeout.connect(self._restart_after_crash)
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setSingleShot(True)
        self._shutdown_timer.timeout.connect(self._force_stop_after_shutdown_timeout)

    @property
    def language(self) -> str:
        return self.server.language

    def _set_state(self, state: str):
        if state == self.state:
            return
        self.state = state
        self.stateChanged.emit(self.language, state)

    def is_running(self) -> bool:
        return bool(self.process and self.process.state() != QProcess.ProcessState.NotRunning)

    def start(self):
        if self.is_running() or self.state in {self.STARTING, self.INITIALIZING, self.READY}:
            return
        self._restart_timer.stop()
        self._shutdown_timer.stop()
        self._expected_shutdown = False
        self._parser.reset()
        self._pending.clear()
        self._initialize_request_id = None
        self._shutdown_request_id = None
        self.server_capabilities = {}

        process = QProcess(self)
        process.setProgram(self.server.executable)
        process.setArguments([str(arg) for arg in self.server.arguments])
        process.setWorkingDirectory(str(self.project_root))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.started.connect(self._on_started)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.errorOccurred.connect(self._on_process_error)
        process.finished.connect(self._on_finished)
        self.process = process
        self._set_state(self.STARTING)
        self.logMessage.emit(self.language, f"Starting LSP: {self.server.executable} {' '.join(self.server.arguments)}".rstrip())
        process.start()

    def _on_started(self):
        if self._expected_shutdown:
            self._force_stop_process()
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
        process = self.process
        if not process or process.state() != QProcess.ProcessState.Running:
            raise RuntimeError(f"LSP process for {self.language} is not running")
        data = encode_jsonrpc_message(payload)
        written = process.write(data)
        if written < 0:
            raise RuntimeError(f"Failed to write to LSP process for {self.language}")

    def _read_stdout(self):
        process = self.process
        if not process:
            return
        data = bytes(process.readAllStandardOutput())
        if not data:
            return
        try:
            messages = self._parser.feed(data)
        except LspProtocolError as exc:
            self.logMessage.emit(self.language, f"LSP protocol error: {exc}")
            self.permanentFailure.emit(self.language, str(exc))
            self._set_state(self.FAILED)
            self._expected_shutdown = True
            self._force_stop_process()
            return
        for message in messages:
            self._handle_message(message)

    def _read_stderr(self):
        process = self.process
        if not process:
            return
        data = bytes(process.readAllStandardError())
        if not data:
            return
        text = data.decode("utf-8", errors="replace").rstrip()
        if text:
            self.logMessage.emit(self.language, text)

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
            QTimer.singleShot(300, self._force_stop_process)
            return

        if pending is None:
            self.logMessage.emit(self.language, f"Received response for unknown request id {request_id!r}")

    def _handle_server_request(self, request_id: int | str, method: str, params: Any):
        if method == "workspace/configuration":
            items = params.get("items", []) if isinstance(params, dict) else []
            self._send_response(request_id, [None for _ in items])
            return
        if method in {
            "client/registerCapability",
            "client/unregisterCapability",
            "window/workDoneProgress/create",
        }:
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
        self._send_response(
            request_id,
            error={"code": -32601, "message": f"Method not implemented by Astra B1 transport: {method}"},
        )

    def _fail_initialization(self, error: Any):
        summary = f"LSP initialize failed: {error}"
        self.logMessage.emit(self.language, summary)
        self.permanentFailure.emit(self.language, summary)
        self._expected_shutdown = True
        self._set_state(self.FAILED)
        self._force_stop_process()

    def _on_process_error(self, _error):
        process = self.process
        message = process.errorString() if process else "Unknown LSP process error"
        self.logMessage.emit(self.language, message)
        if process and process.error() == QProcess.ProcessError.FailedToStart:
            self.permanentFailure.emit(self.language, message)
            self._expected_shutdown = True
            self._set_state(self.FAILED)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        self._shutdown_timer.stop()
        self._read_stdout()
        self._read_stderr()
        self.process = None
        self._pending.clear()
        self._initialize_request_id = None
        self._shutdown_request_id = None

        if self._expected_shutdown:
            if self.state != self.FAILED:
                self._set_state(self.STOPPED)
            return

        status_name = "crashed" if exit_status == QProcess.ExitStatus.CrashExit else "exited"
        summary = f"LSP {status_name} with code {int(exit_code)}"
        self.crashed.emit(self.language, int(exit_code), summary)
        self.logMessage.emit(self.language, summary)
        if self.server.restart_enabled and self._restart_attempts < self.server.max_restarts:
            self._restart_attempts += 1
            delay = min(8000, max(0, self.server.restart_base_delay_ms) * (2 ** (self._restart_attempts - 1)))
            self._set_state(self.RESTARTING)
            self.restartScheduled.emit(self.language, self._restart_attempts, delay)
            self._restart_timer.start(delay)
        else:
            self._set_state(self.FAILED)
            self.permanentFailure.emit(self.language, "Language server stopped and automatic restart budget was exhausted.")

    def _restart_after_crash(self):
        if self._expected_shutdown:
            return
        self.start()

    def restart(self):
        self._restart_attempts = 0
        self._expected_shutdown = True
        self._restart_timer.stop()
        self._force_stop_process()
        self._expected_shutdown = False
        self.start()

    def shutdown(self, timeout_ms: int = 1200):
        self._restart_timer.stop()
        previous_state = self.state
        self._expected_shutdown = True
        process = self.process
        if not process or process.state() == QProcess.ProcessState.NotRunning:
            self.process = None
            self._set_state(self.STOPPED)
            return
        self._set_state(self.SHUTTING_DOWN)
        # The LSP shutdown request is valid only after a successful initialize.
        # If Astra closes while the server is still starting/initializing, stop the
        # child process directly rather than sending an out-of-order protocol request.
        if previous_state == self.READY and self._shutdown_request_id is None:
            try:
                self._shutdown_request_id = self.send_request("shutdown")
                self._shutdown_timer.start(max(100, int(timeout_ms)))
                return
            except RuntimeError:
                pass
        self._force_stop_process()

    def _force_stop_after_shutdown_timeout(self):
        process = self.process
        if process and process.state() != QProcess.ProcessState.NotRunning:
            try:
                self.send_notification("exit")
            except RuntimeError:
                pass
            QTimer.singleShot(100, self._force_stop_process)

    def _force_stop_process(self):
        process = self.process
        if not process or process.state() == QProcess.ProcessState.NotRunning:
            return
        process.terminate()
        if not process.waitForFinished(300):
            process.kill()

    def shutdown_and_wait(self, timeout_ms: int = 1800):
        self.shutdown(min(1200, max(100, int(timeout_ms))))
        deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
        app = QCoreApplication.instance()
        while self.process and self.process.state() != QProcess.ProcessState.NotRunning and time.monotonic() < deadline:
            if app is not None:
                app.processEvents()
            self.process.waitForReadyRead(20)
            self._read_stdout()
            self._read_stderr()
            time.sleep(0.005)
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self._force_stop_process()
        self.process = None
        if self.state != self.FAILED:
            self._set_state(self.STOPPED)


class LspManager(QObject):
    """Own LSP transports, document state, diagnostics and interactive requests."""

    stateChanged = Signal(str, str)
    logMessage = Signal(str, str)
    initialized = Signal(str, object)
    notificationReceived = Signal(str, str, object)
    responseReceived = Signal(str, object, object, object)
    crashed = Signal(str, int, str)
    restartScheduled = Signal(str, int, int)
    permanentFailure = Signal(str, str)
    diagnosticsPublished = Signal(str, str, object)  # language, uri, list[LspDiagnostic]
    diagnosticsReset = Signal()
    interactiveResult = Signal(str, str, object, object, object)  # language, feature, token, result, error

    def __init__(
        self,
        user_config_path: Path | str | None = None,
        project_root: Path | str | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.registry = LspServerRegistry(user_config_path)
        self.project_root = Path(project_root).resolve() if project_root else None
        self.connections: dict[str, QObject] = {}
        self._retiring_connections: list[QObject] = []
        self.documents = LspDocumentStore()
        self.diagnostics = LspDiagnosticsStore()
        self._opened_documents: dict[str, set[str]] = {}
        self._failure_retry_after: dict[str, float] = {}
        self._interactive_requests: dict[tuple[str, int | str], tuple[str, object]] = {}

    def set_project_root(self, project_root: Path | str | None):
        new_root = Path(project_root).resolve() if project_root else None
        if new_root == self.project_root:
            return
        self.shutdown_all(wait=False)
        self.documents.clear()
        self.diagnostics.clear()
        self._opened_documents.clear()
        self._failure_retry_after.clear()
        self._interactive_requests.clear()
        self.project_root = new_root
        self.diagnosticsReset.emit()

    def _make_connection(self, resolved: ResolvedLspServer):
        if resolved.transport == "stdio":
            return LspClientConnection(resolved, self.project_root, self)
        if resolved.transport == "external_tcp":
            return LspTcpConnection(resolved, self.project_root, self)
        return None

    def ensure_server(self, language: str):
        if self.project_root is None:
            return None
        existing = self.connections.get(language)
        existing_state = getattr(existing, "state", "") if existing else ""
        if existing and existing_state not in {"failed", "stopped"}:
            return existing
        if existing and existing_state == "failed":
            retry_after = self._failure_retry_after.get(language, 0.0)
            if time.monotonic() < retry_after:
                return None
        if existing:
            existing.deleteLater()
            self.connections.pop(language, None)
        resolved = self.registry.resolve(language, self.project_root)
        if resolved is None:
            return None
        connection = self._make_connection(resolved)
        if connection is None:
            return None
        self._wire_connection(connection)
        self.connections[language] = connection
        connection.start()
        return connection

    def connection_for_language(self, language: str):
        return self.connections.get(language)

    def restart_server(self, language: str) -> bool:
        self._failure_retry_after.pop(language, None)
        connection = self.connections.get(language)
        if connection is None:
            return self.ensure_server(language) is not None
        connection.restart()
        return True

    def stop_server(self, language: str, wait: bool = False):
        connection = self.connections.pop(language, None)
        self._opened_documents.pop(language, None)
        self._drop_interactive_requests(language)
        self._clear_language_diagnostics(language)
        if not connection:
            return
        self._retire_connection(connection, wait=wait)

    def shutdown_all(self, wait: bool = False):
        connections = list(self.connections.values())
        self.connections.clear()
        self._opened_documents.clear()
        self._interactive_requests.clear()
        for connection in connections:
            self._retire_connection(connection, wait=wait)
        if wait:
            for connection in list(self._retiring_connections):
                connection.shutdown_and_wait()
                self._finish_retiring_connection(connection)

    def _retire_connection(self, connection, wait: bool):
        if connection not in self._retiring_connections:
            self._retiring_connections.append(connection)
        if wait:
            connection.shutdown_and_wait()
            self._finish_retiring_connection(connection)
            return
        connection.stateChanged.connect(
            lambda _language, state, current=connection: self._on_retiring_state(current, state)
        )
        connection.shutdown()
        if connection.state in {"stopped", "failed"}:
            self._finish_retiring_connection(connection)

    def _on_retiring_state(self, connection, state: str):
        if state in {"stopped", "failed"}:
            self._finish_retiring_connection(connection)

    def _finish_retiring_connection(self, connection):
        try:
            self._retiring_connections.remove(connection)
        except ValueError:
            return
        connection.deleteLater()

    def available_languages(self) -> dict[str, bool]:
        return self.registry.availability(self.project_root)

    def _wire_connection(self, connection):
        connection.stateChanged.connect(self._on_connection_state_changed)
        connection.logMessage.connect(self.logMessage)
        connection.initialized.connect(self._on_connection_initialized)
        connection.notificationReceived.connect(self._on_notification)
        connection.responseReceived.connect(self._on_response)
        connection.crashed.connect(self.crashed)
        connection.restartScheduled.connect(self.restartScheduled)
        connection.permanentFailure.connect(self._on_permanent_failure)

    def _on_response(self, language: str, request_id: object, result: object, error: object):
        self.responseReceived.emit(language, request_id, result, error)
        pending = self._interactive_requests.pop((language, request_id), None)
        if pending is None:
            return
        feature, token = pending
        self.interactiveResult.emit(language, feature, token, result, error)

    def _drop_interactive_requests(self, language: str):
        stale = [key for key in self._interactive_requests if key[0] == language]
        for key in stale:
            feature, token = self._interactive_requests.pop(key)
            self.interactiveResult.emit(language, feature, token, None, {
                "code": -32800,
                "message": "Language server stopped before the request completed.",
            })

    def server_state(self, language: str) -> str:
        connection = self.connections.get(language)
        return str(getattr(connection, "state", "stopped")) if connection is not None else "stopped"

    def server_capabilities(self, language: str) -> dict[str, Any]:
        connection = self.connections.get(language)
        capabilities = getattr(connection, "server_capabilities", {}) if connection is not None else {}
        return dict(capabilities) if isinstance(capabilities, dict) else {}

    def supports_feature(self, language: str, feature: str) -> bool:
        capabilities = self.server_capabilities(language)
        key_map = {
            "completion": "completionProvider",
            "hover": "hoverProvider",
            "signature_help": "signatureHelpProvider",
            "definition": "definitionProvider",
            "references": "referencesProvider",
            "rename": "renameProvider",
            "document_symbols": "documentSymbolProvider",
        }
        key = key_map.get(str(feature))
        if not key:
            return False
        value = capabilities.get(key)
        return bool(value)

    def request_feature(
        self,
        language: str,
        feature: str,
        path: Path | str,
        line: int = 0,
        character: int = 0,
        *,
        token: object = None,
        extra: dict[str, Any] | None = None,
    ) -> int | None:
        method = LSP_FEATURE_METHODS.get(str(feature))
        if not method:
            return None
        document = self.documents.get(path)
        if document is None or document.language != language:
            return None
        connection = self.ensure_server(language)
        if connection is None or getattr(connection, "state", "") != "ready":
            return None
        if feature == "document_symbols":
            params: dict[str, Any] = {"textDocument": {"uri": document.uri}}
        else:
            params = text_document_position_params(document.path, line, character)
        if feature == "completion":
            params["context"] = {"triggerKind": 1}
        elif feature == "references":
            params["context"] = {"includeDeclaration": True}
        elif feature == "rename":
            new_name = str((extra or {}).get("newName") or "").strip()
            if not new_name:
                return None
            params["newName"] = new_name
        if extra:
            for key, value in extra.items():
                if key == "newName" and feature == "rename":
                    continue
                params[key] = value
        try:
            request_id = connection.send_request(method, params)
        except RuntimeError:
            return None
        self._interactive_requests[(language, request_id)] = (str(feature), token)
        return request_id

    def _on_permanent_failure(self, language: str, message: str):
        # Document edits are frequent; without a cooldown a missing Godot/Pyright
        # server would otherwise trigger a new process/socket attempt on every
        # debounced keystroke. Explicit Restart bypasses this delay.
        self._failure_retry_after[language] = time.monotonic() + 5.0
        self.permanentFailure.emit(language, message)

    def _on_connection_state_changed(self, language: str, state: str):
        if state != "ready":
            self._opened_documents.pop(language, None)
        if state in {"failed", "stopped", "restarting"}:
            self._drop_interactive_requests(language)
        self.stateChanged.emit(language, state)

    def _on_connection_initialized(self, language: str, capabilities: object):
        self._failure_retry_after.pop(language, None)
        connection = self.connections.get(language)
        self._opened_documents[language] = set()
        if connection is not None:
            self._sync_all_documents_for_language(language, connection)
        self.initialized.emit(language, capabilities)

    def _on_notification(self, language: str, method: str, params: object):
        if method == "textDocument/publishDiagnostics":
            uri, diagnostics = self.diagnostics.update(params)
            if uri:
                self.diagnosticsPublished.emit(language, uri, diagnostics)
        self.notificationReceived.emit(language, method, params)

    def _language_id(self, language: str) -> str | None:
        config = self.registry.config_for_language(language)
        if config is None or not config.enabled:
            return None
        return config.language_id

    def open_document(self, language: str, path: Path | str, text: str) -> bool:
        language_id = self._language_id(language)
        if not language_id:
            return False
        existing = self.documents.get(path)
        if existing is not None and existing.language == language:
            if existing.text != (text or ""):
                return self.change_document(language, path, text)
            document = existing
        else:
            if existing is not None:
                self.close_document(existing.language, path)
            document, _created = self.documents.open_or_update(language, language_id, path, text)
        connection = self.ensure_server(language)
        if connection is not None and getattr(connection, "state", "") == "ready":
            opened = self._opened_documents.setdefault(language, set())
            if document.uri not in opened:
                self._send_did_open(connection, document)
        return True

    def change_document(self, language: str, path: Path | str, text: str) -> bool:
        document = self.documents.get(path)
        if document is None or document.language != language:
            return self.open_document(language, path, text)
        if document.text == (text or ""):
            return True
        document = self.documents.change(path, text)
        if document is None:
            return False
        connection = self.ensure_server(language)
        if connection is not None and getattr(connection, "state", "") == "ready":
            opened = self._opened_documents.setdefault(language, set())
            if document.uri not in opened:
                self._send_did_open(connection, document)
            else:
                connection.send_notification(
                    "textDocument/didChange",
                    {
                        "textDocument": {"uri": document.uri, "version": document.version},
                        "contentChanges": [{"text": document.text}],
                    },
                )
        return True

    def save_document(self, language: str, path: Path | str, text: str) -> bool:
        document = self.documents.get(path)
        if document is None or document.language != language:
            self.open_document(language, path, text)
            document = self.documents.get(path)
        elif document.text != (text or ""):
            self.change_document(language, path, text)
            document = self.documents.get(path)
        if document is None:
            return False
        connection = self.ensure_server(language)
        if connection is None or getattr(connection, "state", "") != "ready":
            return True
        opened = self._opened_documents.setdefault(language, set())
        if document.uri not in opened:
            self._send_did_open(connection, document)
        params: dict[str, Any] = {"textDocument": {"uri": document.uri}}
        if self._server_wants_save_text(connection):
            params["text"] = document.text
        connection.send_notification("textDocument/didSave", params)
        return True

    def close_document(self, language: str, path: Path | str) -> bool:
        document = self.documents.get(path)
        if document is None:
            return False
        actual_language = document.language
        connection = self.connections.get(actual_language)
        opened = self._opened_documents.setdefault(actual_language, set())
        if connection is not None and getattr(connection, "state", "") == "ready" and document.uri in opened:
            try:
                connection.send_notification("textDocument/didClose", {"textDocument": {"uri": document.uri}})
            except RuntimeError:
                pass
        opened.discard(document.uri)
        self.documents.close(path)
        if self.diagnostics.clear_uri(document.uri):
            self.diagnosticsPublished.emit(actual_language, document.uri, [])
        return True

    def _send_did_open(self, connection, document):
        connection.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": document.uri,
                    "languageId": document.language_id,
                    "version": document.version,
                    "text": document.text,
                }
            },
        )
        self._opened_documents.setdefault(document.language, set()).add(document.uri)

    def _sync_all_documents_for_language(self, language: str, connection):
        for document in self.documents.documents_for_language(language):
            try:
                self._send_did_open(connection, document)
            except RuntimeError as exc:
                self.logMessage.emit(language, f"Document sync failed for {document.path}: {exc}")
                break

    def _server_wants_save_text(self, connection) -> bool:
        capabilities = getattr(connection, "server_capabilities", {}) or {}
        sync = capabilities.get("textDocumentSync") if isinstance(capabilities, dict) else None
        if not isinstance(sync, dict):
            return False
        save = sync.get("save")
        return bool(isinstance(save, dict) and save.get("includeText") is True)

    def diagnostics_for_uri(self, uri: str):
        return self.diagnostics.for_uri(uri)

    def all_diagnostics(self):
        return self.diagnostics.all()

    def _clear_language_diagnostics(self, language: str):
        changed = False
        for document in self.documents.documents_for_language(language):
            if self.diagnostics.clear_uri(document.uri):
                self.diagnosticsPublished.emit(language, document.uri, [])
                changed = True
        if changed:
            self.diagnosticsReset.emit()

