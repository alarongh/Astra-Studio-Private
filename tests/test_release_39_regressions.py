from __future__ import annotations

import subprocess
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
COMMON = ROOT / "scripts" / "_common_installer.ps1"
JAVA_INSTALLER = ROOT / "scripts" / "install_java.ps1"


def test_release_39_identity_is_current_runtime_version():
    main_text = MAIN.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'APP_VERSION = "Release 3.19"' in main_text
    assert "Release 3.19" in readme


def test_java_installer_uses_stderr_safe_version_probe_everywhere():
    common = COMMON.read_text(encoding="utf-8-sig")
    java = JAVA_INSTALLER.read_text(encoding="utf-8-sig")
    main_text = MAIN.read_text(encoding="utf-8")
    for text in (common, main_text):
        assert "function Invoke-NativeVersionProbe" in text
        assert "RedirectStandardError" in text
        assert "System.Diagnostics.ProcessStartInfo" in text
        assert "$process.ExitCode -eq 0" in text
    assert 'Invoke-NativeVersionProbe $javaPath @("-version")' in java
    assert 'Invoke-NativeVersionProbe $javacPath @("-version")' in java
    assert '& $javaPath -version 2>&1' not in java
    assert '& $javaPath -version 2>&1' not in main_text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell native-stderr behavior is Windows-specific")
def test_windows_powershell_probe_accepts_successful_stderr_version():
    java_path = shutil.which("java")
    if not java_path:
        pytest.skip("java executable is unavailable")
    common = str(COMMON).replace("'", "''")
    executable = java_path.replace("'", "''")
    command = (
        f". '{common}'; "
        f"if (-not (Invoke-NativeVersionProbe '{executable}' @('-version'))) {{ exit 41 }}; "
        "Write-Host 'STDERR_VERSION_PROBE_OK'; exit 0"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "version" in result.stdout.lower()
    assert "STDERR_VERSION_PROBE_OK" in result.stdout
