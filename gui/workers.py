import os
import sys
import threading
import traceback

from PySide6.QtCore import QObject, QThread, Signal, Slot

from physics import phase_3d
from gui import phase_a, viewer_builder


class _Worker(QObject):
    failed = Signal(str)
    done = Signal()  # always emitted last

    @Slot()
    def run(self):
        try:
            self._work()
        except Exception:
            self.failed.emit(traceback.format_exc())
        finally:
            self.done.emit()


def start_in_thread(worker, parent):
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(thread.quit)
    thread.start()
    return thread


class PhaseAWorker(_Worker):
    progress = Signal(int, int)
    result = Signal(str, object)

    def __init__(self, cfg, mat, min_R, max_R, num_R, max_turns, out_path):
        super().__init__()
        self.args = (cfg, mat, min_R, max_R, num_R, max_turns, out_path)

    def _work(self):
        cfg, mat, min_R, max_R, num_R, max_turns, out = self.args
        radii = phase_a.render_design_chart(cfg, mat, min_R, max_R, num_R, max_turns, out,
                                            progress=lambda i, n: self.progress.emit(i, n))
        self.result.emit(out, radii.tolist())


class _LogStream:
    """Forwards print() output from the physics code to the GUI log (drops the \\r progress bar)."""
    def __init__(self, signal):
        self.signal = signal

    def write(self, text):
        for line in text.replace("\r", "\n").split("\n"):
            line = line.strip()
            if line and "Progress:" not in line:
                self.signal.emit(line)
        return len(text)

    def flush(self):
        pass


class SimWorker(_Worker):
    progress = Signal(float, float)  # overall pct, simulated hours
    log = Signal(str)
    result = Signal(object)

    def __init__(self, cfg, mat, R_coil, n_turns, outdir):
        super().__init__()
        self.cfg, self.mat, self.R, self.n, self.outdir = cfg, mat, R_coil, n_turns, outdir
        self.cancel_flag = threading.Event()

    def _work(self):
        old_stdout = sys.stdout
        sys.stdout = _LogStream(self.log)
        try:
            total_hr = self.cfg["N_cycles"] * (self.cfg["t_window_hr"] + self.cfg["t_cooldown_hr"])
            os.makedirs(self.outdir, exist_ok=True)

            def cb(info):
                self.progress.emit(min(100.0, info["t_hr"] / total_hr * 100.0), info["t_hr"])

            results = phase_3d.run_simulation(self.cfg, self.mat, self.R, self.n, self.outdir,
                                              progress_cb=cb, cancel_flag=self.cancel_flag)
            self.result.emit(results)
        finally:
            sys.stdout = old_stdout


class ViewerWorker(_Worker):
    result = Signal(str)

    def __init__(self, run_folder, shape):
        super().__init__()
        self.run_folder, self.shape = run_folder, shape

    def _work(self):
        self.result.emit(viewer_builder.build_viewer_html(self.run_folder, self.shape) or "")