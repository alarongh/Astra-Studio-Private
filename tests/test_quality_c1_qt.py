from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

try:
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
    HAVE_PYSIDE6 = True
except ImportError:
    QCoreApplication = QEventLoop = QTimer = None
    HAVE_PYSIDE6 = False

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if HAVE_PYSIDE6:
    from core.task_manager import ProcessTaskSpec, TaskManager
else:
    ProcessTaskSpec = TaskManager = None


@unittest.skipUnless(HAVE_PYSIDE6, "PySide6 runtime integration test")
class QualityTaskRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_task_manager_streams_stdin_to_formatter_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = root / "formatter.py"
            helper.write_text(
                "import sys\ntext=sys.stdin.read()\nsys.stdout.write(text.upper())\n",
                encoding="utf-8",
            )
            manager = TaskManager()
            output = []
            result = []
            loop = QEventLoop()
            manager.taskOutput.connect(lambda _id, text, stream: output.append((stream, text)))
            manager.taskFinished.connect(lambda _id, code, cancelled: (result.append((code, cancelled)), loop.quit()))
            manager.taskFailed.connect(lambda _id, _message: loop.quit())
            manager.start_process(ProcessTaskSpec(
                task_id="quality-stdin",
                title="quality stdin",
                program=sys.executable,
                arguments=[str(helper)],
                workdir=root,
                stdin_data="hello, astra\n",
                indeterminate=True,
            ))
            QTimer.singleShot(5000, loop.quit)
            loop.exec()
            self.assertEqual(result, [(0, False)])
            stdout = "".join(text for stream, text in output if stream == "stdout")
            self.assertEqual(stdout.replace("\r\n", "\n").replace("\r", "\n"), "HELLO, ASTRA\n")


if __name__ == "__main__":
    unittest.main()
