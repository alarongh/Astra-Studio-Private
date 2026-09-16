from __future__ import annotations

from PySide6.QtCore import Qt


def apply_topmost_hint(window, enabled: bool) -> bool:
    """Apply only Qt's top-most hint and preserve all caption/system-menu flags.

    Returns True when a flag transition was performed and False when the window
    was already in the requested state.
    """
    desired = bool(enabled)
    current = bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    if current == desired:
        return False

    was_visible = window.isVisible()
    was_maximized = window.isMaximized()
    was_fullscreen = window.isFullScreen()
    geometry = window.saveGeometry()

    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, desired)
    window.restoreGeometry(geometry)

    if was_visible:
        if was_fullscreen:
            window.showFullScreen()
        elif was_maximized:
            window.showMaximized()
        else:
            window.show()
        window.raise_()
        window.activateWindow()
    return True
