from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .lsp_protocol import path_to_uri, uri_to_path


LSP_FEATURE_METHODS: dict[str, str] = {
    "completion": "textDocument/completion",
    "hover": "textDocument/hover",
    "signature_help": "textDocument/signatureHelp",
    "definition": "textDocument/definition",
    "references": "textDocument/references",
    "rename": "textDocument/rename",
    "document_symbols": "textDocument/documentSymbol",
}


@dataclass(frozen=True, slots=True)
class LspLocation:
    uri: str
    line: int
    character: int
    end_line: int = 0
    end_character: int = 0

    @property
    def path(self) -> Path | None:
        return uri_to_path(self.uri)


@dataclass(frozen=True, slots=True)
class LspDocumentSymbol:
    name: str
    kind: int
    detail: str
    line: int
    character: int
    end_line: int
    end_character: int
    depth: int = 0


@dataclass(frozen=True, slots=True)
class LspTextEdit:
    uri: str
    start_line: int
    start_character: int
    end_line: int
    end_character: int
    new_text: str


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    return default


def text_document_position_params(path: Path | str, line: int, character: int) -> dict[str, Any]:
    return {
        "textDocument": {"uri": path_to_uri(Path(path).resolve())},
        "position": {"line": max(0, int(line)), "character": max(0, int(character))},
    }


def _markup_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        inner = value.get("value")
        return str(inner or "").strip()
    if isinstance(value, list):
        parts = [_markup_to_text(item) for item in value]
        return "\n\n".join(part for part in parts if part)
    return str(value).strip()


def normalize_completion_items(result: Any) -> list[dict[str, Any]]:
    raw_items: Any
    if isinstance(result, dict):
        raw_items = result.get("items", [])
    else:
        raw_items = result
    if not isinstance(raw_items, list):
        return []

    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "").strip()
        if not label:
            continue
        text_edit = raw.get("textEdit") if isinstance(raw.get("textEdit"), dict) else None
        # LSP 3.17 also permits InsertReplaceEdit. Astra B3 intentionally accepts
        # only the normal TextEdit form; servers were told snippetSupport=False.
        if text_edit is not None and "range" not in text_edit:
            text_edit = None
        insert_text = raw.get("insertText")
        if not isinstance(insert_text, str) or not insert_text:
            insert_text = label
        items.append({
            "label": label,
            "detail": str(raw.get("detail") or "").strip(),
            "documentation": _markup_to_text(raw.get("documentation")),
            "insert_text": insert_text,
            "filter_text": str(raw.get("filterText") or label),
            "sort_text": str(raw.get("sortText") or label),
            "kind": _int(raw.get("kind"), 0),
            "text_edit": text_edit,
        })
    items.sort(key=lambda item: (item["sort_text"].lower(), item["label"].lower()))
    return items


def hover_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    return _markup_to_text(result.get("contents"))


def signature_help_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    signatures = result.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return ""
    active = _int(result.get("activeSignature"), 0)
    active = min(active, len(signatures) - 1)
    signature = signatures[active]
    if not isinstance(signature, dict):
        return ""
    label = str(signature.get("label") or "").strip()
    documentation = _markup_to_text(signature.get("documentation"))
    active_parameter = result.get("activeParameter", signature.get("activeParameter"))
    parameter_text = ""
    parameters = signature.get("parameters")
    if isinstance(parameters, list) and isinstance(active_parameter, int) and 0 <= active_parameter < len(parameters):
        parameter = parameters[active_parameter]
        if isinstance(parameter, dict):
            param_label = parameter.get("label")
            if isinstance(param_label, str):
                parameter_text = param_label
            parameter_doc = _markup_to_text(parameter.get("documentation"))
            if parameter_doc:
                parameter_text = f"{parameter_text}\n{parameter_doc}".strip()
    parts = [part for part in (label, parameter_text, documentation) if part]
    return "\n\n".join(parts)


def _normalize_range(raw_range: Any) -> tuple[int, int, int, int] | None:
    if not isinstance(raw_range, dict):
        return None
    start = raw_range.get("start") if isinstance(raw_range.get("start"), dict) else None
    end = raw_range.get("end") if isinstance(raw_range.get("end"), dict) else None
    if start is None or end is None:
        return None
    line = _int(start.get("line"), 0)
    character = _int(start.get("character"), 0)
    end_line = _int(end.get("line"), line)
    end_character = _int(end.get("character"), character)
    if end_line < line or (end_line == line and end_character < character):
        end_line, end_character = line, character
    return line, character, end_line, end_character


def normalize_locations(result: Any) -> list[LspLocation]:
    if result is None:
        return []
    raw_items = result if isinstance(result, list) else [result]
    locations: list[LspLocation] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        # LocationLink uses targetUri + targetSelectionRange/targetRange.
        uri = str(raw.get("uri") or raw.get("targetUri") or "").strip()
        raw_range = raw.get("range")
        if raw_range is None:
            raw_range = raw.get("targetSelectionRange") or raw.get("targetRange")
        normalized = _normalize_range(raw_range)
        if not uri or normalized is None:
            continue
        locations.append(LspLocation(uri, *normalized))
    return locations


def normalize_document_symbols(result: Any) -> list[LspDocumentSymbol]:
    if not isinstance(result, list):
        return []
    symbols: list[LspDocumentSymbol] = []

    def visit(raw: Any, depth: int = 0):
        if not isinstance(raw, dict):
            return
        name = str(raw.get("name") or "").strip()
        if not name:
            return
        # DocumentSymbol has range/selectionRange; SymbolInformation has location.
        location = raw.get("location") if isinstance(raw.get("location"), dict) else None
        raw_range = raw.get("selectionRange") or raw.get("range")
        if raw_range is None and location:
            raw_range = location.get("range")
        normalized = _normalize_range(raw_range)
        if normalized is None:
            return
        symbols.append(LspDocumentSymbol(
            name=name,
            kind=_int(raw.get("kind"), 0),
            detail=str(raw.get("detail") or raw.get("containerName") or "").strip(),
            line=normalized[0],
            character=normalized[1],
            end_line=normalized[2],
            end_character=normalized[3],
            depth=max(0, depth),
        ))
        children = raw.get("children")
        if isinstance(children, list):
            for child in children:
                visit(child, depth + 1)

    for item in result:
        visit(item, 0)
    return symbols


def workspace_edit_has_resource_operations(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    document_changes = result.get("documentChanges")
    if not isinstance(document_changes, list):
        return False
    for change in document_changes:
        if not isinstance(change, dict):
            continue
        kind = str(change.get("kind") or "")
        if kind in {"create", "rename", "delete"}:
            return True
        if "textDocument" not in change and ("oldUri" in change or "newUri" in change or "uri" in change):
            return True
    return False


def normalize_workspace_edit(result: Any) -> list[LspTextEdit]:
    if not isinstance(result, dict):
        return []
    edits: list[LspTextEdit] = []

    def add(uri: str, raw_edits: Any):
        if not uri or not isinstance(raw_edits, list):
            return
        for raw in raw_edits:
            if not isinstance(raw, dict):
                continue
            normalized = _normalize_range(raw.get("range"))
            new_text = raw.get("newText")
            if normalized is None or not isinstance(new_text, str):
                continue
            edits.append(LspTextEdit(uri, *normalized, new_text))

    changes = result.get("changes")
    if isinstance(changes, dict):
        for uri, raw_edits in changes.items():
            add(str(uri), raw_edits)

    document_changes = result.get("documentChanges")
    if isinstance(document_changes, list):
        for change in document_changes:
            if not isinstance(change, dict):
                continue
            text_document = change.get("textDocument")
            if isinstance(text_document, dict):
                add(str(text_document.get("uri") or ""), change.get("edits"))
            # Create/Rename/DeleteFile resource operations are deliberately not
            # applied during B3 symbol rename. They require a separate reviewed
            # workspace-edit transaction layer.
    return edits


def _utf16_units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _utf16_column_to_index(line_text: str, column: int) -> int:
    target = max(0, int(column))
    units = 0
    for index, char in enumerate(line_text):
        char_units = _utf16_units(char)
        if units + char_units > target:
            return index
        units += char_units
        if units == target:
            return index + 1
    return len(line_text)


def position_to_text_offset(text: str, line: int, character: int) -> int:
    lines = text.splitlines(keepends=True)
    if not lines:
        return 0
    line_index = max(0, min(int(line), len(lines) - 1))
    prefix = sum(len(item) for item in lines[:line_index])
    current = lines[line_index]
    content = current.rstrip("\r\n")
    return prefix + _utf16_column_to_index(content, character)


def apply_text_edits(text: str, edits: Iterable[LspTextEdit]) -> str:
    operations: list[tuple[int, int, str]] = []
    for edit in edits:
        start = position_to_text_offset(text, edit.start_line, edit.start_character)
        end = position_to_text_offset(text, edit.end_line, edit.end_character)
        if end < start:
            end = start
        operations.append((start, end, edit.new_text))
    operations.sort(key=lambda item: (item[0], item[1]), reverse=True)
    output = text
    last_start = len(text) + 1
    for start, end, new_text in operations:
        # Overlapping edits are invalid for a TextEdit list. Refuse silently to
        # merge them in an unsafe order; callers can treat the unchanged overlap
        # as a server-side invalid edit instead of corrupting source text.
        if end > last_start:
            raise ValueError("Overlapping LSP text edits are not supported")
        output = output[:start] + new_text + output[end:]
        last_start = start
    return output
