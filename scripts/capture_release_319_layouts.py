"""Create deterministic UI snapshots for Release 3.19 laptop QA."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402
import main  # noqa: E402


def capture(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_root = Path(tempfile.mkdtemp(prefix="astra-319-visual-"))
    main.app_data_dir = lambda: data_root / "data"
    main.default_builds_dir = lambda: data_root / "builds"
    main.AstraStudio.start_terminal = lambda self: None

    app = QApplication.instance() or QApplication([])
    window = main.AstraStudio()
    window.apply_angel404_profile()
    captures: list[Path] = []
    for width, height in ((1366, 768), (1600, 900)):
        window.resize(width, height)
        window.show()
        window.open_settings_page()
        for _ in range(4):
            app.processEvents()
        target = output_dir / f"astra_319_settings_{width}x{height}.png"
        if not window.grab().save(str(target), "PNG"):
            raise RuntimeError(f"Could not save {target}")
        captures.append(target)
    window.close()
    app.processEvents()
    return captures


if __name__ == "__main__":
    for path in capture(ROOT / ".pytest-tmp" / "release_319_visual"):
        print(path)
