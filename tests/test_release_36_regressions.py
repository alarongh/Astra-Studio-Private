from __future__ import annotations

from pathlib import Path
import tempfile

from core.log_file import append_utf8_bom_log, ensure_utf8_bom_log

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
ACCEPTANCE_RUNNER = ROOT / "run_acceptance_tests.bat"
PYTEST_BOOTSTRAP = ROOT / "tests" / "conftest.py"
PYINSTALLER_SPEC = ROOT / "astra_studio.spec"


def test_release_36_version_and_topmost_no_longer_uses_raw_setwindowpos():
    text = MAIN.read_text(encoding="utf-8")
    assert 'APP_VERSION = "Release 3.20"' in text
    assert "ctypes.windll.user32.SetWindowPos" not in text
    assert "def _apply_always_on_top_windows" not in text
    start = text.index("    def _apply_always_on_top_qt(self):")
    end = text.index("    def apply_always_on_top(self):", start)
    block = text[start:end]
    assert "apply_topmost_hint" in block
    assert "setWindowFlags(" not in block


def test_release_36_startup_does_not_mutate_topmost_flags_when_disabled():
    text = MAIN.read_text(encoding="utf-8")
    assert "if self.always_on_top_enabled:\n            QTimer.singleShot(0, self.apply_always_on_top)" in text


def test_release_36_log_is_migrated_to_utf8_bom_for_windows_powershell():
    text = MAIN.read_text(encoding="utf-8")
    assert "def _ensure_log_utf8_bom" in text
    assert 'encoding="utf-8-sig"' in text


def test_release_36_log_migrates_bomless_utf8_and_appends_readable_russian():
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "astra_studio.log"
        log.write_bytes("Ошибка запуска\n".encode("utf-8"))
        ensure_utf8_bom_log(log)
        append_utf8_bom_log(log, "Окно закрыто корректно\n")
        raw = log.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")
        assert raw.count(b"\xef\xbb\xbf") == 1
        assert raw.decode("utf-8-sig") == "Ошибка запуска\nОкно закрыто корректно\n"


def test_release_36_log_migrates_legacy_cp1251_to_utf8_bom():
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "astra_studio.log"
        log.write_bytes("Ошибка Windows\n".encode("cp1251"))
        ensure_utf8_bom_log(log)
        assert log.read_bytes().decode("utf-8-sig") == "Ошибка Windows\n"


def test_release_36_main_window_uses_native_caption_not_custom_close_wiring():
    text = MAIN.read_text(encoding="utf-8")
    assert "FramelessWindowHint" not in text
    assert "WM_NCHITTEST" not in text
    assert "HTCLOSE" not in text
    assert "def closeEvent(self, event):" in text


def test_release_36_full_suite_bootstraps_qapplication_before_core_qt_tests():
    text = PYTEST_BOOTSTRAP.read_text(encoding="utf-8")
    assert 'sys.platform != "win32"' in text
    assert "QApplication.instance() or QApplication([])" in text
    assert "setQuitOnLastWindowClosed(False)" in text


def test_release_36_acceptance_runner_rejects_native_windows_crash_codes():
    text = ACCEPTANCE_RUNNER.read_text(encoding="ascii")
    pytest_call = '".venv\\Scripts\\python.exe" -m pytest -q -rs'
    start = text.index(pytest_call)
    block = text[start:text.index("echo.", start)]
    assert "if errorlevel 1 goto failed" in block
    assert "if not errorlevel 0 goto failed" in block


def test_release_36_pyinstaller_build_rejects_foreign_icu_and_uses_onedir():
    spec = PYINSTALLER_SPEC.read_text(encoding="utf-8")
    assert '{"icuuc.dll", "icudt78.dll"}' in spec
    assert "a.binaries = without_foreign_icu(a.binaries)" in spec
    assert "exclude_binaries=True" in spec
    assert "COLLECT(" in spec


def test_release_312_application_update_feed_downloads_verifies_and_installs():
    text = MAIN.read_text(encoding="utf-8")
    assert "self.btn_check_app_update.clicked.connect(self.check_app_update)" in text
    assert 'configured_manifest_url(resource_path("update_channel.json"))' in text
    assert "parse_update_manifest(payload)" in text
    assert "self._start_app_update_download(manifest)" in text
    assert "verify_update_archive(archive_path, manifest)" in text
    assert "windows_update_script()" in text
    assert "self.update_network.get(request)" in text
