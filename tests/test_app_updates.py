from __future__ import annotations

from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import zipfile

import pytest

from core.app_updates import (
    configured_manifest_url,
    is_newer_release,
    parse_update_manifest,
    release_version_tuple,
    verify_update_archive,
    windows_update_script,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_manifest(**updates):
    payload = {
        "schema_version": 1,
        "version": "Release 3.7",
        "channel": "stable",
        "download_url": "https://downloads.example.org/astra/Astra_Studio_3_7.zip",
        "notes_url": "https://downloads.example.org/astra/3.7.html",
        "sha256": "a" * 64,
        "size": 12345,
    }
    payload.update(updates)
    return payload


def test_release_versions_compare_numerically():
    assert release_version_tuple("Release 3.11") > release_version_tuple("Release 3.10")
    assert release_version_tuple("Release 3.10") > release_version_tuple("Release 3.9")
    assert is_newer_release("Release 3.11", "Release 3.9")
    assert is_newer_release("Release 3.11.1", "Release 3.11")
    assert not is_newer_release("Release 3.11", "Release 3.11")


def test_update_manifest_requires_https_sha256_and_positive_size():
    parsed = parse_update_manifest(valid_manifest())
    assert parsed.version == "Release 3.7"
    for override in (
        {"download_url": "http://example.org/astra.zip"},
        {"download_url": "https://user:secret@example.org/astra.zip"},
        {"sha256": "bad"},
        {"size": 0},
    ):
        with pytest.raises(ValueError):
            parse_update_manifest(valid_manifest(**override))


def test_update_manifest_rejects_oversized_payload():
    with pytest.raises(ValueError, match="too large"):
        parse_update_manifest(b" " * (256 * 1024 + 1))


def test_update_channel_uses_valid_environment_override(tmp_path: Path):
    channel = tmp_path / "update_channel.json"
    channel.write_text('{"schema_version": 1, "manifest_url": ""}', encoding="utf-8")
    url = "https://updates.example.org/astra/latest.json"
    assert configured_manifest_url(channel, {"ASTRA_UPDATE_MANIFEST_URL": url}) == url


def test_update_channel_accepts_published_https_url(tmp_path: Path):
    channel = tmp_path / "update_channel.json"
    url = "https://raw.githubusercontent.com/alarongh/Astra-Studio-Releases/main/update/latest.json"
    channel.write_text('{"schema_version": 1, "manifest_url": "' + url + '"}', encoding="utf-8")
    assert configured_manifest_url(channel, {}) == url


def test_update_archive_verifies_hash_size_layout_and_rejects_traversal(tmp_path: Path):
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("Astra Studio/Astra Studio.exe", b"MZ-test")
        package.writestr("Astra Studio/_internal/app.dat", b"payload")
    payload = valid_manifest(
        size=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    )
    count, unpacked = verify_update_archive(archive, parse_update_manifest(payload))
    assert count == 2
    assert unpacked == len(b"MZ-testpayload")

    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as package:
        package.writestr("../outside.exe", b"bad")
        package.writestr("Astra Studio/Astra Studio.exe", b"MZ")
    unsafe_manifest = parse_update_manifest(valid_manifest(
        size=unsafe.stat().st_size,
        sha256=hashlib.sha256(unsafe.read_bytes()).hexdigest(),
    ))
    with pytest.raises(ValueError, match="Unsafe"):
        verify_update_archive(unsafe, unsafe_manifest)


def test_windows_updater_has_wait_backup_rollback_and_restart_steps():
    script = windows_update_script()
    for required in (
        "Set-Location -LiteralPath $updatesRoot",
        "[Environment]::CurrentDirectory = $updatesRoot",
        "Wait-Process -Id $ParentPid",
        "Move-Item -LiteralPath $targetPath -Destination $backupPath",
        "Move-Item -LiteralPath $backupPath -Destination $targetPath",
        "Start-Process -FilePath $installedExecutable",
        "previous build retained",
        "Previous Astra Studio restored",
        "startup health check",
        "Astra Studio не удалось установить обновление",
    ):
        assert required in script


def test_release_319_bundles_public_github_channel_and_valid_latest_manifest():
    channel_url = configured_manifest_url(ROOT / "update_channel.json", {})
    assert channel_url == "https://raw.githubusercontent.com/alarongh/Astra-Studio-Releases/main/update/latest.json"
    manifest = parse_update_manifest((ROOT / "update" / "latest.json").read_bytes())
    assert manifest.version == "Release 3.19"
    assert manifest.download_url.endswith("/v3.19/Astra_Studio_Release_3_19.zip")
    assert manifest.notes_url.endswith("/releases/tag/v3.19")


@pytest.mark.skipif(os.name != "nt" or shutil.which("powershell.exe") is None, reason="Windows updater integration")
def test_windows_updater_replaces_portable_folder_in_isolated_directory(tmp_path: Path):
    target = tmp_path / "Astra Studio 3.15"
    payload = tmp_path / "payload" / "Astra Studio"
    target.mkdir()
    payload.mkdir(parents=True)
    helper_exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "where.exe"
    shutil.copy2(helper_exe, target / "Astra Studio.exe")
    (target / "old.txt").write_text("old", encoding="utf-8")
    shutil.copy2(helper_exe, payload / "Astra Studio.exe")
    (payload / "new.txt").write_text("new", encoding="utf-8")
    archive = tmp_path / "update.zip"
    with zipfile.ZipFile(archive, "w") as package:
        for path in payload.rglob("*"):
            if path.is_file():
                package.write(path, path.relative_to(payload.parent).as_posix())
    script = tmp_path / "install.ps1"
    log = tmp_path / "update.log"
    script.write_text(windows_update_script(), encoding="utf-8-sig")
    completed = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
            "-Archive", str(archive), "-TargetDirectory", str(target), "-ParentPid", "999999",
            "-LogPath", str(log), "-SkipHealthCheck", "-SuppressUi",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=target,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr + log.read_text(encoding="utf-8-sig")
    assert (target / "Astra Studio.exe").read_bytes() == helper_exe.read_bytes()
    assert (target / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (target / "old.txt").exists()
    log_text = log.read_text(encoding="utf-8-sig")
    assert "Update installed successfully" in log_text
    assert "previous build retained" in log_text
    assert list(tmp_path.glob("Astra Studio 3.15.previous-*"))


@pytest.mark.skipif(os.name != "nt" or shutil.which("powershell.exe") is None, reason="Windows updater integration")
def test_windows_updater_rolls_back_when_new_executable_exits_during_health_check(tmp_path: Path):
    target = tmp_path / "Astra Studio 3.15"
    payload = tmp_path / "payload" / "Astra Studio"
    target.mkdir()
    payload.mkdir(parents=True)
    helper_exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "where.exe"
    shutil.copy2(helper_exe, target / "Astra Studio.exe")
    (target / "old.txt").write_text("old", encoding="utf-8")
    shutil.copy2(helper_exe, payload / "Astra Studio.exe")
    (payload / "new.txt").write_text("new", encoding="utf-8")
    archive = tmp_path / "update.zip"
    with zipfile.ZipFile(archive, "w") as package:
        for path in payload.rglob("*"):
            if path.is_file():
                package.write(path, path.relative_to(payload.parent).as_posix())
    script = tmp_path / "install.ps1"
    log = tmp_path / "update.log"
    script.write_text(windows_update_script(), encoding="utf-8-sig")
    completed = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
            "-Archive", str(archive), "-TargetDirectory", str(target), "-ParentPid", "999999",
            "-LogPath", str(log), "-SuppressUi",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=target, timeout=30,
    )
    assert completed.returncode == 1
    assert (target / "old.txt").read_text(encoding="utf-8") == "old"
    assert not (target / "new.txt").exists()
    assert list(tmp_path.glob("Astra Studio 3.15.failed-*"))
    log_text = log.read_text(encoding="utf-8-sig")
    assert "startup health check" in log_text
    assert "Previous Astra Studio restored" in log_text
