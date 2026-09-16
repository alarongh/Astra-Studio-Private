from __future__ import annotations

import sys


_windows_qapplication = None


def pytest_sessionstart(session) -> None:
    """Start one widget-capable Qt application before any core-only Qt tests.

    A QCoreApplication cannot be upgraded to QApplication later in the same
    process.  The full Windows suite used to create QCoreApplication first and
    then terminate natively when the caption regression constructed a widget.
    """
    if sys.platform != "win32" or session.config.option.collectonly:
        return

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return

    global _windows_qapplication
    _windows_qapplication = QApplication.instance() or QApplication([])
    if not isinstance(_windows_qapplication, QApplication):
        raise RuntimeError("Windows acceptance requires QApplication before Qt runtime tests")
    _windows_qapplication.setQuitOnLastWindowClosed(False)
