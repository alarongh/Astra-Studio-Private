from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Mapping
from urllib.parse import urlparse
import zipfile


MAX_MANIFEST_BYTES = 256 * 1024
MAX_ARCHIVE_ENTRIES = 20_000
MAX_UNPACKED_BYTES = 4 * 1024 * 1024 * 1024
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


def verify_update_archive(archive_path: Path, manifest: UpdateManifest) -> tuple[int, int]:
    """Verify the downloaded release before the running application is replaced.

    The stable channel distributes one portable ZIP whose root is ``Astra Studio``.
    Besides the signed size/hash, reject traversal, drive-qualified paths, symlinks,
    archive bombs and packages without the expected executable.
    """
    archive = Path(archive_path)
    if not archive.is_file():
        raise ValueError("Downloaded update archive is missing")
    actual_size = archive.stat().st_size
    if actual_size != manifest.size:
        raise ValueError(f"Update size mismatch: expected {manifest.size}, got {actual_size}")
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_hash = digest.hexdigest()
    if actual_hash.lower() != manifest.sha256.lower():
        raise ValueError("Update SHA-256 mismatch")

    total_unpacked = 0
    entry_count = 0
    executable_found = False
    try:
        with zipfile.ZipFile(archive) as package:
            for info in package.infolist():
                entry_count += 1
                if entry_count > MAX_ARCHIVE_ENTRIES:
                    raise ValueError("Update archive contains too many entries")
                name = info.filename.replace("\\", "/")
                parts = [part for part in name.split("/") if part not in {"", "."}]
                if not parts or name.startswith(("/", "\\")) or any(part == ".." for part in parts):
                    raise ValueError(f"Unsafe update archive entry: {info.filename!r}")
                if ":" in parts[0]:
                    raise ValueError(f"Drive-qualified update archive entry: {info.filename!r}")
                unix_mode = (info.external_attr >> 16) & 0xF000
                if unix_mode == 0xA000:
                    raise ValueError(f"Symlink entries are not allowed: {info.filename!r}")
                total_unpacked += max(0, int(info.file_size))
                if total_unpacked > MAX_UNPACKED_BYTES:
                    raise ValueError("Update archive expands beyond the safe size limit")
                if "/".join(parts).casefold() == "astra studio/astra studio.exe":
                    executable_found = True
    except zipfile.BadZipFile as exc:
        raise ValueError("Downloaded update is not a valid ZIP archive") from exc
    if not executable_found:
        raise ValueError("Update archive does not contain Astra Studio/Astra Studio.exe")
    return entry_count, total_unpacked


def windows_update_script() -> str:
    """Return the detached Windows updater used after the GUI exits."""
    return r'''param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$TargetDirectory,
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$LogPath,
    [switch]$SkipHealthCheck,
    [switch]$SuppressUi
)
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Write-UpdateLog([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $LogPath -Value "$stamp $Message" -Encoding UTF8
}

try {
    $archivePath = [IO.Path]::GetFullPath($Archive)
    $targetPath = [IO.Path]::GetFullPath($TargetDirectory).TrimEnd('\')
    $targetName = [IO.Path]::GetFileName($targetPath)
    if ($targetName -notmatch '^Astra Studio(?: .+)?$') { throw "Unsafe target directory: $targetPath" }
    if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { throw "Update archive is missing: $archivePath" }
    if (-not (Test-Path -LiteralPath (Join-Path $targetPath "Astra Studio.exe") -PathType Leaf)) { throw "Current Astra Studio executable is missing" }

    # A detached process inherits Astra's current directory by default. Windows
    # refuses to rename the application folder while the updater itself is
    # standing inside that folder, so leave it before waiting for Astra to exit.
    $updatesRoot = Split-Path -Parent $archivePath
    Set-Location -LiteralPath $updatesRoot
    [Environment]::CurrentDirectory = $updatesRoot

    Write-UpdateLog "Waiting for Astra Studio process $ParentPid"
    try { Wait-Process -Id $ParentPid -Timeout 90 -ErrorAction Stop } catch {
        if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) { throw "Astra Studio did not exit in time" }
    }

    $stagePath = Join-Path $updatesRoot ("stage-" + [guid]::NewGuid().ToString("N"))
    $backupPath = $targetPath + ".previous-" + (Get-Date -Format "yyyyMMddHHmmss")
    $failedPath = $targetPath + ".failed-" + (Get-Date -Format "yyyyMMddHHmmss")
    New-Item -ItemType Directory -Path $stagePath -Force | Out-Null
    Expand-Archive -LiteralPath $archivePath -DestinationPath $stagePath -Force
    $payloadPath = Join-Path $stagePath "Astra Studio"
    $newExecutable = Join-Path $payloadPath "Astra Studio.exe"
    if (-not (Test-Path -LiteralPath $newExecutable -PathType Leaf)) { throw "Expanded update payload is incomplete" }

    Write-UpdateLog "Installing verified update into $targetPath"
    Move-Item -LiteralPath $targetPath -Destination $backupPath
    try {
        Move-Item -LiteralPath $payloadPath -Destination $targetPath
    } catch {
        if (-not (Test-Path -LiteralPath $targetPath) -and (Test-Path -LiteralPath $backupPath)) {
            Move-Item -LiteralPath $backupPath -Destination $targetPath
        }
        throw
    }

    $installedExecutable = Join-Path $targetPath "Astra Studio.exe"
    $newProcess = Start-Process -FilePath $installedExecutable -WorkingDirectory $targetPath -PassThru
    if (-not $SkipHealthCheck) {
        Start-Sleep -Seconds 6
        $newProcess.Refresh()
        if ($newProcess.HasExited) {
            throw "The updated Astra Studio exited during the startup health check (exit code $($newProcess.ExitCode))"
        }
    }
    # A verified previous build is deliberately retained. It is the recovery
    # copy for a laptop that loses power or discovers a delayed compatibility
    # problem after the update. Never trade that safety for automatic cleanup.
    try { if (Test-Path -LiteralPath $stagePath) { Remove-Item -LiteralPath $stagePath -Recurse -Force } } catch { Write-UpdateLog ("STAGE CLEANUP FAILED: " + $_.Exception.Message) }
    try { if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force } } catch { Write-UpdateLog ("ARCHIVE CLEANUP FAILED: " + $_.Exception.Message) }
    Write-UpdateLog "Update installed successfully; previous build retained at $backupPath"
} catch {
    $failureMessage = $_.Exception.Message
    Write-UpdateLog ("UPDATE FAILED: " + $failureMessage)
    # Roll back even if the new folder was already moved into place and its EXE
    # managed to start but terminated during the health check.
    try {
        if (Test-Path -LiteralPath $backupPath) {
            if (Test-Path -LiteralPath $targetPath) {
                Move-Item -LiteralPath $targetPath -Destination $failedPath
                Write-UpdateLog "Failed update retained at $failedPath"
            }
            Move-Item -LiteralPath $backupPath -Destination $targetPath
            Write-UpdateLog "Previous Astra Studio restored to $targetPath"
        }
    } catch { Write-UpdateLog ("ROLLBACK FAILED: " + $_.Exception.Message) }
    # Never leave the user with an application that merely disappeared. The
    # existing or rolled-back build is started again and the failure is shown.
    try {
        $currentExecutable = Join-Path $targetPath "Astra Studio.exe"
        if (Test-Path -LiteralPath $currentExecutable -PathType Leaf) {
            Start-Process -FilePath $currentExecutable -WorkingDirectory $targetPath
        }
    } catch { Write-UpdateLog ("RECOVERY START FAILED: " + $_.Exception.Message) }
    try {
        if ($SuppressUi) { throw "UI suppressed" }
        Add-Type -AssemblyName PresentationFramework -ErrorAction Stop
        [System.Windows.MessageBox]::Show(
            "Astra Studio не удалось установить обновление.`n`n$failureMessage`n`nПодробности: $LogPath",
            "Обновление Astra Studio"
        ) | Out-Null
    } catch { Write-UpdateLog ("FAILURE DIALOG FAILED: " + $_.Exception.Message) }
    exit 1
}
'''
