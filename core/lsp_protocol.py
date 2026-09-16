from __future__ import annotations

import json
from pathlib import Path
import os
from typing import Any
from urllib.parse import unquote, urlparse


class LspProtocolError(RuntimeError):
    pass


class JsonRpcStreamParser:
    """Incremental parser for LSP Content-Length framed JSON-RPC messages."""

    MAX_HEADER_BYTES = 64 * 1024
    MAX_CONTENT_BYTES = 64 * 1024 * 1024

    def __init__(self):
        self._buffer = bytearray()

    def reset(self):
        self._buffer.clear()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        if data:
            self._buffer.extend(data)
        messages: list[dict[str, Any]] = []
        while True:
            header_end = self._buffer.find(b"\r\n\r\n")
            delimiter_size = 4
            if header_end < 0:
                header_end = self._buffer.find(b"\n\n")
                delimiter_size = 2
            if header_end < 0:
                if len(self._buffer) > self.MAX_HEADER_BYTES:
                    raise LspProtocolError("LSP header exceeds safety limit")
                return messages
            if header_end > self.MAX_HEADER_BYTES:
                raise LspProtocolError("LSP header exceeds safety limit")

            raw_headers = bytes(self._buffer[:header_end])
            try:
                header_text = raw_headers.decode("ascii")
            except UnicodeDecodeError as exc:
                raise LspProtocolError("LSP header is not ASCII") from exc

            content_length: int | None = None
            for raw_line in header_text.replace("\r\n", "\n").split("\n"):
                if ":" not in raw_line:
                    continue
                name, value = raw_line.split(":", 1)
                if name.strip().lower() == "content-length":
                    try:
                        content_length = int(value.strip())
                    except ValueError as exc:
                        raise LspProtocolError("Invalid Content-Length header") from exc
                    break
            if content_length is None or content_length < 0:
                raise LspProtocolError("Missing or invalid Content-Length header")
            if content_length > self.MAX_CONTENT_BYTES:
                raise LspProtocolError("LSP payload exceeds safety limit")

            body_start = header_end + delimiter_size
            body_end = body_start + content_length
            if len(self._buffer) < body_end:
                return messages

            body = bytes(self._buffer[body_start:body_end])
            del self._buffer[:body_end]
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LspProtocolError("Invalid JSON-RPC payload") from exc
            if not isinstance(payload, dict):
                raise LspProtocolError("JSON-RPC payload must be an object")
            messages.append(payload)


def encode_jsonrpc_message(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def path_to_uri(path: Path | str) -> str:
    return Path(path).resolve().as_uri()

def uri_to_path(uri: str) -> Path | None:
    """Convert a file:// URI used by LSP back to a local filesystem path."""
    try:
        parsed = urlparse(str(uri or ""))
    except Exception:
        return None
    if parsed.scheme.lower() != "file":
        return None
    path_text = unquote(parsed.path or "")
    if parsed.netloc:
        path_text = f"//{parsed.netloc}{path_text}"
    if os.name == "nt" and len(path_text) >= 3 and path_text[0] == "/" and path_text[2] == ":":
        path_text = path_text[1:]
    try:
        return Path(path_text)
    except (TypeError, ValueError):
        return None

