from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .lsp_protocol import path_to_uri


LSP_SEVERITY_ERROR = 1
LSP_SEVERITY_WARNING = 2
LSP_SEVERITY_INFORMATION = 3
LSP_SEVERITY_HINT = 4


@dataclass(slots=True)
class TrackedLspDocument:
    language: str
    language_id: str
    path: Path
    uri: str
    text: str
    version: int = 1


class LspDocumentStore:
    """In-memory state of files Astra has offered to language servers.

    Transport code owns the actual notifications. This store deliberately has no
    Qt dependency so document/version behavior can be tested in the sandbox.
    """

    def __init__(self):
        self._documents: dict[str, TrackedLspDocument] = {}

    def clear(self):
        self._documents.clear()

    def open_or_update(
        self,
        language: str,
        language_id: str,
        path: Path | str,
        text: str,
    ) -> tuple[TrackedLspDocument, bool]:
        resolved = Path(path).resolve()
        uri = path_to_uri(resolved)
        existing = self._documents.get(uri)
        if existing is None:
            document = TrackedLspDocument(
                language=str(language),
                language_id=str(language_id),
                path=resolved,
                uri=uri,
                text=text or "",
                version=1,
            )
            self._documents[uri] = document
            return document, True

        changed_language = existing.language != language or existing.language_id != language_id
        existing.language = str(language)
        existing.language_id = str(language_id)
        existing.path = resolved
        existing.text = text or ""
        if changed_language:
            existing.version += 1
        return existing, False

    def change(self, path: Path | str, text: str) -> TrackedLspDocument | None:
        uri = path_to_uri(Path(path).resolve())
        document = self._documents.get(uri)
        if document is None:
            return None
        document.version += 1
        document.text = text or ""
        return document

    def get(self, path_or_uri: Path | str) -> TrackedLspDocument | None:
        if isinstance(path_or_uri, Path):
            key = path_to_uri(path_or_uri.resolve())
        else:
            text = str(path_or_uri)
            key = text if text.startswith("file:") else path_to_uri(Path(text).resolve())
        return self._documents.get(key)

    def close(self, path: Path | str) -> TrackedLspDocument | None:
        uri = path_to_uri(Path(path).resolve())
        return self._documents.pop(uri, None)

    def documents_for_language(self, language: str) -> list[TrackedLspDocument]:
        return [doc for doc in self._documents.values() if doc.language == language]

    def documents(self) -> list[TrackedLspDocument]:
        return list(self._documents.values())


@dataclass(frozen=True, slots=True)
class LspDiagnostic:
    uri: str
    line: int
    character: int
    end_line: int
    end_character: int
    severity: int
    message: str
    source: str = ""
    code: str = ""
    tags: tuple[int, ...] = field(default_factory=tuple)

    @property
    def severity_name(self) -> str:
        return {
            LSP_SEVERITY_ERROR: "Ошибка",
            LSP_SEVERITY_WARNING: "Предупреждение",
            LSP_SEVERITY_INFORMATION: "Информация",
            LSP_SEVERITY_HINT: "Подсказка",
        }.get(self.severity, "Диагностика")

    def as_record(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "line": self.line,
            "character": self.character,
            "end_line": self.end_line,
            "end_character": self.end_character,
            "severity": self.severity,
            "severity_name": self.severity_name,
            "message": self.message,
            "source": self.source,
            "code": self.code,
            "tags": list(self.tags),
        }


def _nonnegative_int(value: Any, default: int = 0) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    return default


def parse_publish_diagnostics(params: Any) -> tuple[str, int | None, list[LspDiagnostic]]:
    """Normalize an LSP textDocument/publishDiagnostics payload.

    Invalid individual diagnostics are ignored instead of poisoning the full
    notification. The notification itself must contain a non-empty URI.
    """

    if not isinstance(params, dict):
        return "", None, []
    uri = str(params.get("uri") or "").strip()
    if not uri:
        return "", None, []
    raw_version = params.get("version")
    version = raw_version if isinstance(raw_version, int) and not isinstance(raw_version, bool) else None
    diagnostics: list[LspDiagnostic] = []
    raw_items = params.get("diagnostics", [])
    if not isinstance(raw_items, list):
        raw_items = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        range_value = raw.get("range")
        if not isinstance(range_value, dict):
            continue
        start = range_value.get("start") if isinstance(range_value.get("start"), dict) else {}
        end = range_value.get("end") if isinstance(range_value.get("end"), dict) else {}
        line = _nonnegative_int(start.get("line"))
        character = _nonnegative_int(start.get("character"))
        end_line = _nonnegative_int(end.get("line"), line)
        end_character = _nonnegative_int(end.get("character"), character)
        if end_line < line or (end_line == line and end_character < character):
            end_line, end_character = line, character

        severity = raw.get("severity", LSP_SEVERITY_ERROR)
        if not isinstance(severity, int) or isinstance(severity, bool) or severity not in {1, 2, 3, 4}:
            severity = LSP_SEVERITY_ERROR
        message = str(raw.get("message") or "").strip()
        if not message:
            continue
        source = str(raw.get("source") or "").strip()
        code_value = raw.get("code")
        code = "" if code_value is None else str(code_value)
        raw_tags = raw.get("tags", [])
        tags = tuple(item for item in raw_tags if isinstance(item, int) and not isinstance(item, bool)) if isinstance(raw_tags, list) else ()
        diagnostics.append(
            LspDiagnostic(
                uri=uri,
                line=line,
                character=character,
                end_line=end_line,
                end_character=end_character,
                severity=severity,
                message=message,
                source=source,
                code=code,
                tags=tags,
            )
        )
    return uri, version, diagnostics


class LspDiagnosticsStore:
    def __init__(self):
        self._by_uri: dict[str, list[LspDiagnostic]] = {}
        self._versions: dict[str, int | None] = {}

    def clear(self):
        self._by_uri.clear()
        self._versions.clear()

    def clear_uri(self, uri: str) -> bool:
        existed = uri in self._by_uri or uri in self._versions
        self._by_uri.pop(uri, None)
        self._versions.pop(uri, None)
        return existed

    def update(self, params: Any) -> tuple[str, list[LspDiagnostic]]:
        uri, version, diagnostics = parse_publish_diagnostics(params)
        if not uri:
            return "", []
        previous_version = self._versions.get(uri)
        # Ignore stale diagnostics when both notifications are versioned.
        if version is not None and previous_version is not None and version < previous_version:
            return uri, list(self._by_uri.get(uri, []))
        self._versions[uri] = version
        self._by_uri[uri] = list(diagnostics)
        return uri, list(diagnostics)

    def for_uri(self, uri: str) -> list[LspDiagnostic]:
        return list(self._by_uri.get(uri, []))

    def all(self) -> list[LspDiagnostic]:
        items: list[LspDiagnostic] = []
        for diagnostics in self._by_uri.values():
            items.extend(diagnostics)
        return items

    def items(self) -> Iterable[tuple[str, list[LspDiagnostic]]]:
        for uri, diagnostics in self._by_uri.items():
            yield uri, list(diagnostics)
