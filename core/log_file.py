from __future__ import annotations

from pathlib import Path


UTF8_BOM = b"\xef\xbb\xbf"


def ensure_utf8_bom_log(path: Path) -> None:
    """Create or migrate Astra's text log to UTF-8 with a BOM.

    Windows PowerShell 5.x treats a BOM-less UTF-8 file as the active ANSI
    code page, which turns Russian diagnostics into mojibake. Astra owns this
    log, so legacy UTF-8 and CP1251 text can both be migrated safely.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(UTF8_BOM)
        return

    raw = target.read_bytes()
    if raw.startswith(UTF8_BOM):
        return
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    target.write_text(text, encoding="utf-8-sig", newline="")


def append_utf8_bom_log(path: Path, text: str) -> None:
    """Append Unicode text while keeping exactly one BOM at file start."""
    target = Path(path)
    ensure_utf8_bom_log(target)
    with target.open("a", encoding="utf-8", newline="") as stream:
        stream.write(str(text))
