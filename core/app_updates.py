from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Mapping
from urllib.parse import urlparse


MAX_MANIFEST_BYTES = 256 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^(?:Release\s+)?(\d+(?:\.\d+){1,3})$", re.IGNORECASE)


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    download_url: str
    sha256: str
    size: int
    channel: str = "stable"
    published_at: str = ""
    notes_url: str = ""


def release_version_tuple(value: str) -> tuple[int, int, int, int]:
    match = VERSION_RE.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f"Unsupported Astra release version: {value!r}")
    parts = [int(part) for part in match.group(1).split(".")]
    return tuple((parts + [0, 0, 0, 0])[:4])


def is_newer_release(candidate: str, current: str) -> bool:
    return release_version_tuple(candidate) > release_version_tuple(current)


def _https_url(value: object, field: str, *, optional: bool = False) -> str:
    text = str(value or "").strip()
    if optional and not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{field} must be an HTTPS URL without embedded credentials")
    return text


def parse_update_manifest(payload: bytes | str | Mapping[str, object]) -> UpdateManifest:
    if isinstance(payload, bytes):
        if len(payload) > MAX_MANIFEST_BYTES:
            raise ValueError("Update manifest is too large")
        raw: object = json.loads(payload.decode("utf-8-sig"))
    elif isinstance(payload, str):
        if len(payload.encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise ValueError("Update manifest is too large")
        raw = json.loads(payload)
    else:
        raw = dict(payload)

    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Unsupported update manifest schema")

    version = str(raw.get("version") or "").strip()
    release_version_tuple(version)
    sha256 = str(raw.get("sha256") or "").strip().lower()
    if not SHA256_RE.fullmatch(sha256):
        raise ValueError("Update manifest contains an invalid SHA-256")
    size = raw.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("Update manifest contains an invalid artifact size")

    channel = str(raw.get("channel") or "stable").strip().lower()
    if channel not in {"stable", "test"}:
        raise ValueError("Update manifest contains an unsupported channel")

    return UpdateManifest(
        version=version,
        download_url=_https_url(raw.get("download_url"), "download_url"),
        sha256=sha256,
        size=size,
        channel=channel,
        published_at=str(raw.get("published_at") or "").strip(),
        notes_url=_https_url(raw.get("notes_url"), "notes_url", optional=True),
    )


def configured_manifest_url(channel_path: Path, environ: Mapping[str, str] | None = None) -> str:
    environment = os.environ if environ is None else environ
    override = str(environment.get("ASTRA_UPDATE_MANIFEST_URL") or "").strip()
    if override:
        return _https_url(override, "ASTRA_UPDATE_MANIFEST_URL")

    path = Path(channel_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return ""
    url = str(data.get("manifest_url") or "").strip()
    return _https_url(url, "manifest_url") if url else ""
