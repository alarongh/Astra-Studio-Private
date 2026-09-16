from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


HAS_QT = importlib.util.find_spec("PySide6") is not None
HAS_GIT = shutil.which("git") is not None


@unittest.skipUnless(HAS_QT and HAS_GIT, "PySide6 and git are required for QProcess Git integration")
class GitTaskRuntimeTests(unittest.TestCase):
    def test_task_manager_preserves_nul_delimited_unicode_git_status(self):
        from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
        from core.git_tools import parse_porcelain_v2_z, status_command
        from core.task_manager import ProcessTaskSpec, TaskManager

        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "astra@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Astra Test"], check=True)
            (root / "база.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "база.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
            (root / "база.txt").write_text("base\nchange\n", encoding="utf-8")
            (root / "новый файл.txt").write_text("new\n", encoding="utf-8")

            command = status_command(root, shutil.which("git"))
            manager = TaskManager()
            loop = QEventLoop()
            chunks: list[str] = []
            result = {"exit": None}
            manager.taskOutput.connect(lambda _task_id, text, stream: chunks.append(text) if stream == "stdout" else None)
            manager.taskFinished.connect(lambda _task_id, code, _cancelled: (result.__setitem__("exit", code), loop.quit()))
            manager.taskFailed.connect(lambda _task_id, _message: loop.quit())
            manager.start_process(ProcessTaskSpec(
                task_id="git_status_qt",
                title="Git status Qt test",
                program=command.program,
                arguments=list(command.arguments),
                workdir=command.workdir,
                indeterminate=True,
            ))
            QTimer.singleShot(8000, loop.quit)
            loop.exec()

            self.assertEqual(result["exit"], 0)
            state = parse_porcelain_v2_z("".join(chunks), root)
            paths = {entry.path for entry in state.entries}
            self.assertIn("база.txt", paths)
            self.assertIn("новый файл.txt", paths)
        _ = app


if __name__ == "__main__":
    unittest.main()
