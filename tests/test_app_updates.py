from __future__ import annotations

from pathlib import Path

import pytest

from core.app_updates import configured_manifest_url, is_newer_release, parse_update_manifest, release_version_tuple


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


def test_update_channel_is_disabled_until_publisher_sets_https_url(tmp_path: Path):
    channel = tmp_path / "update_channel.json"
    channel.write_text('{"schema_version": 1, "manifest_url": ""}', encoding="utf-8")
    assert configured_manifest_url(channel, {}) == ""
