from __future__ import annotations

from pathlib import Path
import sys
import unittest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMainWindow
    HAVE_PYSIDE6 = True
    PYSIDE6_SKIP_REASON = ""
except ImportError as exc:
    Qt = QApplication = QMainWindow = None
    HAVE_PYSIDE6 = False
    PYSIDE6_SKIP_REASON = f"PySide6 runtime unavailable: {exc}"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if HAVE_PYSIDE6:
    from core.window_behavior import apply_topmost_hint
else:
    apply_topmost_hint = None


@unittest.skipUnless(HAVE_PYSIDE6, PYSIDE6_SKIP_REASON or "PySide6 runtime integration test")
class Release36WindowRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_topmost_transition_preserves_caption_flags_and_close(self):
        class TrackedWindow(QMainWindow):
            def __init__(self):
                super().__init__()
                self.close_events = 0

            def closeEvent(self, event):
                self.close_events += 1
                event.accept()

        window = TrackedWindow()
        decoration_mask = (
            Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        before = window.windowFlags() & decoration_mask
        window.show()
        self.app.processEvents()

        self.assertTrue(apply_topmost_hint(window, True))
        self.app.processEvents()
        after_on = window.windowFlags() & decoration_mask
        self.assertEqual(after_on, before)

        self.assertTrue(apply_topmost_hint(window, False))
        self.app.processEvents()
        after_off = window.windowFlags() & decoration_mask
        self.assertEqual(after_off, before)
        self.assertTrue(window.close())
        self.app.processEvents()
        self.assertEqual(window.close_events, 1)

    @unittest.skipUnless(sys.platform == "win32", "requires a real Windows native caption/HWND")
    def test_windows_native_close_command_reaches_close_event_after_topmost_toggle(self):
        import ctypes

        class TrackedWindow(QMainWindow):
            def __init__(self):
                super().__init__()
                self.close_events = 0

            def closeEvent(self, event):
                self.close_events += 1
                event.accept()

        window = TrackedWindow()
        window.show()
        self.app.processEvents()
        apply_topmost_hint(window, True)
        apply_topmost_hint(window, False)
        self.app.processEvents()

        hwnd = int(window.winId())
        self.assertNotEqual(hwnd, 0)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        send_message = user32.SendMessageW
        send_message.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send_message.restype = ctypes.c_ssize_t
        WM_SYSCOMMAND = 0x0112
        SC_CLOSE = 0xF060
        send_message(hwnd, WM_SYSCOMMAND, SC_CLOSE, 0)
        self.app.processEvents()
        self.assertEqual(window.close_events, 1)
        self.assertFalse(window.isVisible())


if __name__ == "__main__":
    unittest.main()
