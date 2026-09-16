from __future__ import annotations

from pathlib import Path


def portable_project_path(path: Path | str, config_path: Path | str | None) -> str:
    """Serialize a path relative to the Astra project file when it is inside it.

    External attached folders intentionally remain absolute. This keeps a normal
    project repository portable while preserving explicit links to folders that
    genuinely live outside the repository.
    """

    candidate = Path(path)
    if not config_path:
        return str(candidate)
    config_parent = Path(config_path).parent
    try:
        candidate_resolved = candidate.resolve()
        parent_resolved = config_parent.resolve()
        relative = candidate_resolved.relative_to(parent_resolved)
    except (OSError, ValueError):
        return str(candidate)
    return "." if not relative.parts else relative.as_posix()


def portable_attached_folders(items: list[dict] | tuple[dict, ...], config_path: Path | str | None) -> list[dict]:
    output: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            continue
        output.append(
            {
                "alias": str(item.get("alias") or Path(raw_path).name or "Подключённая папка"),
                "path": portable_project_path(raw_path, config_path),
            }
        )
    return output
