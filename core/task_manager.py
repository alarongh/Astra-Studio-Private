from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import time

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


def _decode_process_output(data: bytes, preferred_encoding: str | None = None) -> str:
    """Decode background-tool output without corrupting common Windows code pages."""
    if not data:
        return ""
    encodings = []
    if preferred_encoding:
        encodings.append(preferred_encoding)
    encodings.extend(("utf-8", "cp866", "cp1251") if os.name == "nt" else ("utf-8",))
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@dataclass(slots=True)
class ProcessTaskSpec:
    """Описание внешней фоновой задачи, запускаемой без блокировки GUI."""

    task_id: str
    title: str
    program: str
    arguments: list[str] = field(default_factory=list)
    workdir: str | Path | None = None
    progress_start: int = 0
    progress_end: int = 100
    indeterminate: bool = False
    environment: dict[str, str] = field(default_factory=dict)
    stdin_data: str | bytes | None = None
    output_encoding: str | None = None


class BackgroundProcessTask(QObject):
    """Неблокирующая обёртка над QProcess.

    GUI получает только сигналы. Виджеты из этой обёртки не трогаются.
    """

    started = Signal(str, str)
    outputReceived = Signal(str, str, str)  # task_id, text, stream
    progressChanged = Signal(str, int, str)  # task_id, percent/-1, label
    etaChanged = Signal(str, str)
    finished = Signal(str, int, bool)  # task_id, exit_code, cancelled
    failed = Signal(str, str)

    def __init__(self, spec: ProcessTaskSpec, parent: QObject | None = None):
        super().__init__(parent)
        self.spec = spec
        self.process: QProcess | None = None
        self.cancel_requested = False
        self._progress = max(0, min(100, int(spec.progress_start)))
        self._started_at = 0.0
        self._output_tails = {"stdout": "", "stderr": ""}
        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self._update_eta)

    def start(self):
        self._started_at = time.monotonic()
        self.cancel_requested = False
        self.process = QProcess(self)
        if self.spec.workdir:
            self.process.setWorkingDirectory(str(self.spec.workdir))
        self.process.setProgram(str(self.spec.program))
        self.process.setArguments([str(arg) for arg in self.spec.arguments])
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        for key, value in self.spec.environment.items():
            env.insert(str(key), str(value))
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(lambda: self._read_stream("stdout"))
        self.process.readyReadStandardError.connect(lambda: self._read_stream("stderr"))
        self.process.errorOccurred.connect(self._handle_error)
        self.process.finished.connect(self._handle_finished)
        if self.spec.stdin_data is not None:
            self.process.started.connect(self._write_stdin_data)

        self.started.emit(self.spec.task_id, self.spec.title)
        if self.spec.indeterminate:
            self.progressChanged.emit(self.spec.task_id, -1, self.spec.title)
            self.etaChanged.emit(self.spec.task_id, "Время зависит от размера проекта")
        else:
            self.progressChanged.emit(self.spec.task_id, self._progress, self.spec.title)
            self.etaChanged.emit(self.spec.task_id, "Расчёт времени…")
        self._eta_timer.start()
        self.process.start()

    def _write_stdin_data(self):
        if not self.process or self.spec.stdin_data is None:
            return
        data = self.spec.stdin_data
        if isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = bytes(data)
        if payload:
            self.process.write(payload)
        self.process.closeWriteChannel()

    def cancel(self):
        self.cancel_requested = True
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return
        self.process.terminate()
        QTimer.singleShot(1600, self._force_kill_if_running)

    def _force_kill_if_running(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def _read_stream(self, stream: str):
        if not self.process:
            return
        raw = self.process.readAllStandardOutput() if stream == "stdout" else self.process.readAllStandardError()
        text = _decode_process_output(raw.data(), self.spec.output_encoding)
        if not text:
            return
        visible = []
        combined = self._output_tails.get(stream, "") + text
        lines = combined.splitlines(True)
        self._output_tails[stream] = ""
        if lines and not lines[-1].endswith(("\n", "\r")):
            self._output_tails[stream] = lines.pop()
        for line in lines:
            clean = line.strip()
            if clean.startswith("ASTRA_PROGRESS:"):
                self._handle_progress_marker(clean.split(":", 1)[1])
            else:
                visible.append(line)
        if visible:
            self.outputReceived.emit(self.spec.task_id, "".join(visible), stream)

    def _handle_progress_marker(self, value: str):
        try:
            progress = int(value)
        except ValueError:
            return
        self._progress = max(0, min(100, progress))
        self.progressChanged.emit(self.spec.task_id, self._progress, f"Выполнение: {self._progress}%")

    def _update_eta(self):
        if self.spec.indeterminate or self._progress <= 0 or self._progress >= 100:
            if self.spec.indeterminate:
                self.etaChanged.emit(self.spec.task_id, "Время зависит от размера проекта")
            return
        elapsed = max(1.0, time.monotonic() - self._started_at)
        total = elapsed / (self._progress / 100.0)
        remaining = max(0, int(total - elapsed))
        minutes, seconds = divmod(remaining, 60)
        if minutes:
            eta = f"Осталось примерно: {minutes} мин {seconds:02d} сек"
        else:
            eta = f"Осталось примерно: {seconds} сек"
        self.etaChanged.emit(self.spec.task_id, eta)

    def _handle_error(self, error):
        message = "Не удалось запустить процесс. Проверь путь к инструменту и права доступа."
        if self.process:
            message = self.process.errorString() or message
            if self.process.state() == QProcess.ProcessState.NotRunning:
                self._eta_timer.stop()
        self.failed.emit(self.spec.task_id, message)

    def _handle_finished(self, exit_code: int, _exit_status):
        self._eta_timer.stop()
        # QProcess may finish with unread bytes still buffered. Drain both streams
        # first, then flush any final partial lines without mixing stdout/stderr.
        self._read_stream("stdout")
        self._read_stream("stderr")
        for stream in ("stdout", "stderr"):
            tail = self._output_tails.get(stream, "")
            if tail:
                self.outputReceived.emit(self.spec.task_id, tail, stream)
                self._output_tails[stream] = ""
        if not self.spec.indeterminate and not self.cancel_requested and exit_code == 0:
            self.progressChanged.emit(self.spec.task_id, min(100, self.spec.progress_end), "Выполнение: 100%")
        self.finished.emit(self.spec.task_id, int(exit_code), bool(self.cancel_requested))


class TaskManager(QObject):
    """Единая точка запуска и отмены долгих операций Astra Studio."""

    taskStarted = Signal(str, str)
    taskOutput = Signal(str, str, str)
    taskProgress = Signal(str, int, str)
    taskEta = Signal(str, str)
    taskFinished = Signal(str, int, bool)
    taskFailed = Signal(str, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.current_task: BackgroundProcessTask | None = None

    def has_active_task(self) -> bool:
        # Keep the task reserved until its terminal signal is processed.
        # Checking only QProcess.state() creates a race where a new task can replace
        # the old one before the old finished signal is delivered.
        return self.current_task is not None

    def start_process(self, spec: ProcessTaskSpec) -> BackgroundProcessTask:
        if self.has_active_task():
            raise RuntimeError("Фоновая задача уже выполняется")
        task = BackgroundProcessTask(spec, self)
        self.current_task = task
        task.started.connect(self.taskStarted)
        task.outputReceived.connect(self.taskOutput)
        task.progressChanged.connect(self.taskProgress)
        task.etaChanged.connect(self.taskEta)
        task.finished.connect(self._proxy_finished)
        task.failed.connect(self._proxy_failed)
        task.start()
        return task

    def cancel_current_task(self):
        if self.current_task:
            self.current_task.cancel()

    def _proxy_failed(self, task_id: str, message: str):
        task = self.sender()
        is_current = task is self.current_task
        process = getattr(task, "process", None)
        terminal_failure = process is None or process.state() == QProcess.ProcessState.NotRunning
        if is_current and terminal_failure:
            self.current_task = None
        self.taskFailed.emit(task_id, message)

    def _proxy_finished(self, task_id: str, exit_code: int, cancelled: bool):
        task = self.sender()
        # Only the task that is still current may clear the slot. This prevents a
        # late finished signal from an older process from wiping a newer task.
        if task is not self.current_task:
            return
        # Clear before emitting so UI handlers may safely start a follow-up task
        # (for example: windres -> C++ compile, or pip install -> rerun).
        self.current_task = None
        self.taskFinished.emit(task_id, exit_code, cancelled)

    def cancel_and_wait(self, timeout_ms: int = 1800):
        """Stop the current process synchronously during application shutdown."""
        task = self.current_task
        if not task:
            return
        task.cancel_requested = True
        process = task.process
        if process and process.state() != QProcess.ProcessState.NotRunning:
            process.terminate()
            if not process.waitForFinished(max(0, int(timeout_ms))):
                process.kill()
                process.waitForFinished(max(0, int(timeout_ms)))
        if self.current_task is task:
            self.current_task = None
