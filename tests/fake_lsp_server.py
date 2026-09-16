from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        text = line.decode("ascii").strip()
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def write_message(payload):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crash-once-marker", default="")
    parser.add_argument("--event-log", default="")
    args = parser.parse_args()
    marker = Path(args.crash_once_marker) if args.crash_once_marker else None
    event_log = Path(args.event_log) if args.event_log else None

    def log_event(method, params):
        if not event_log:
            return
        event_log.parent.mkdir(parents=True, exist_ok=True)
        with event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"method": method, "params": params}, ensure_ascii=False) + "\n")

    def publish_diagnostics(uri, text, version=None):
        diagnostics = []
        marker_text = "BROKEN"
        if marker_text in text:
            before = text.split(marker_text, 1)[0]
            line = before.count("\n")
            character = len(before.rsplit("\n", 1)[-1])
            diagnostics.append({
                "range": {
                    "start": {"line": line, "character": character},
                    "end": {"line": line, "character": character + len(marker_text)},
                },
                "severity": 1,
                "source": "astra-fake",
                "code": "BROKEN_TOKEN",
                "message": "Found BROKEN token",
            })
        params = {"uri": uri, "diagnostics": diagnostics}
        if version is not None:
            params["version"] = version
        write_message({
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": params,
        })

    while True:
        message = read_message()
        if message is None:
            return 0
        method = message.get("method")
        request_id = message.get("id")

        if method == "initialize":
            if marker and not marker.exists():
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("crashed", encoding="utf-8")
                sys.stderr.write("intentional test crash\n")
                sys.stderr.flush()
                os._exit(17)
            write_message({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "capabilities": {
                        "textDocumentSync": {
                            "openClose": True,
                            "change": 1,
                            "save": {"includeText": True},
                        },
                        "completionProvider": {"triggerCharacters": ["."]},
                        "hoverProvider": True,
                        "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
                        "definitionProvider": True,
                        "referencesProvider": True,
                        "renameProvider": True,
                        "documentSymbolProvider": True,
                    },
                    "serverInfo": {"name": "Astra fake LSP", "version": "1"},
                },
            })
        elif method == "initialized":
            # Exercise a server -> client request handled entirely by B1.
            write_message({
                "jsonrpc": "2.0",
                "id": 900,
                "method": "workspace/configuration",
                "params": {"items": [{"section": "astra"}]},
            })
        elif method == "textDocument/didOpen":
            params = message.get("params") or {}
            log_event(method, params)
            document = params.get("textDocument") or {}
            publish_diagnostics(str(document.get("uri") or ""), str(document.get("text") or ""), document.get("version"))
        elif method == "textDocument/didChange":
            params = message.get("params") or {}
            log_event(method, params)
            document = params.get("textDocument") or {}
            changes = params.get("contentChanges") or []
            text = str(changes[-1].get("text") or "") if changes and isinstance(changes[-1], dict) else ""
            publish_diagnostics(str(document.get("uri") or ""), text, document.get("version"))
        elif method == "textDocument/didSave":
            log_event(method, message.get("params") or {})
        elif method == "textDocument/didClose":
            params = message.get("params") or {}
            log_event(method, params)
            document = params.get("textDocument") or {}
            publish_diagnostics(str(document.get("uri") or ""), "")
        elif method == "textDocument/completion":
            write_message({"jsonrpc": "2.0", "id": request_id, "result": {"items": [
                {"label": "alpha", "detail": "fake completion", "insertText": "alpha"},
                {"label": "beta", "insertText": "beta"},
            ]}})
        elif method == "textDocument/hover":
            write_message({"jsonrpc": "2.0", "id": request_id, "result": {"contents": {"kind": "markdown", "value": "**fake hover**"}}})
        elif method == "textDocument/signatureHelp":
            write_message({"jsonrpc": "2.0", "id": request_id, "result": {
                "signatures": [{"label": "demo(value: int)", "parameters": [{"label": "value", "documentation": "input value"}]}],
                "activeSignature": 0, "activeParameter": 0,
            }})
        elif method in {"textDocument/definition", "textDocument/references"}:
            params = message.get("params") or {}
            uri = str((params.get("textDocument") or {}).get("uri") or "")
            location = {"uri": uri, "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 4}}}
            result = [location] if method.endswith("references") else location
            write_message({"jsonrpc": "2.0", "id": request_id, "result": result})
        elif method == "textDocument/rename":
            params = message.get("params") or {}
            uri = str((params.get("textDocument") or {}).get("uri") or "")
            new_name = str(params.get("newName") or "renamed")
            write_message({"jsonrpc": "2.0", "id": request_id, "result": {"changes": {uri: [{
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 4}},
                "newText": new_name,
            }]}}})
        elif method == "textDocument/documentSymbol":
            write_message({"jsonrpc": "2.0", "id": request_id, "result": [{
                "name": "demo", "kind": 12,
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 4}},
                "selectionRange": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 4}},
            }]})
        elif method == "shutdown":
            write_message({"jsonrpc": "2.0", "id": request_id, "result": None})
        elif method == "exit":
            return 0
        elif "id" in message and "method" not in message:
            # Response to the fake server's workspace/configuration request.
            continue
        elif request_id is not None:
            write_message({"jsonrpc": "2.0", "id": request_id, "result": None})


if __name__ == "__main__":
    raise SystemExit(main())
