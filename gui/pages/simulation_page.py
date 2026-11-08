import json
import os
import time

import numpy as np
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from gui.workers import SimWorker, start_in_thread


def _np_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    raise TypeError(f"not serializable: {type(o)}")


def save_results_json(outdir, results):
    """Same content as the results.json written by main_cli.py."""
    clean = {k: float(results[k]) for k in
             ("total_extracted_kg", "total_filled_kg", "final_mass", "total_hr")}
    clean["cycle_metrics"] = [
        {k: (float(v) if isinstance(v, (np.floating, float)) else v)
         for k, v in c.items() if k != "snapshot_times"}
        for c in results["cycle_metrics"]
    ]
    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(clean, f, indent=4, default=_np_default)


class SimulationPage(QWidget):
    finished = Signal(str, object)  # outdir, results

    def __init__(self):
        super().__init__()
        self._thread = self._worker = None
        self._t0 = 0.0
        self._progress_text = ""
        self.args = None

        self.lbl_summary = QLabel("Choose a coil in Phase A first.")
        self.lbl_summary.setWordWrap(True)
        self.btn_start = QPushButton("▶  Start 3D simulation")
        self.btn_start.setObjectName("primary")
        self.btn_start.setEnabled(False)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.lbl_status = QLabel("")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_start)
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch()
        root = QVBoxLayout(self)
        root.addWidget(self.lbl_summary)
        root.addLayout(buttons)
        root.addWidget(self.bar)
        root.addWidget(self.lbl_status)
        root.addWidget(self.log, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self._cancel)

    def prepare(self, cfg, mat, R_coil, n_turns, outdir):
        self.args = (cfg, mat, R_coil, n_turns, outdir)
        hours = cfg["N_cycles"] * (cfg["t_window_hr"] + cfg["t_cooldown_hr"])
        steps = int(hours * 3600 / cfg["dt_sec"])
        self.lbl_summary.setText(
            f"Coil radius {R_coil:.3f} m · {n_turns} turns · grid {cfg['res']}³ · "
            f"{cfg['N_cycles']} cycle(s) = {hours:.1f} h simulated ({steps:,} steps).\n"
            f"Output folder: {outdir}")
        self.bar.setValue(0)
        self._progress_text = ""
        self.lbl_status.setText("")
        self.log.clear()
        self.btn_start.setEnabled(True)

    # ------------------------------------------------------------ run control
    def _start(self):
        cfg, mat, R, n, outdir = self.args
        w = SimWorker(cfg, mat, R, n, outdir)
        w.progress.connect(self._on_progress)
        w.log.connect(self.log.appendPlainText)
        w.result.connect(self._on_result)
        w.failed.connect(self._on_failed)
        w.done.connect(self._on_done)
        self._worker = w
        self.log.clear()
        self.log.appendPlainText("Starting… (first run compiles numba kernels and can take a minute)")
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self._progress_text = "Starting…"
        self._t0 = time.time()
        self.timer.start()
        self._thread = start_in_thread(w, self)

    def _cancel(self):
        if self._worker:
            self._worker.cancel_flag.set()
            self.btn_cancel.setEnabled(False)
            self._progress_text = "Cancelling…"

    def _tick(self):
        e = int(time.time() - self._t0)
        self.lbl_status.setText(f"{self._progress_text}  ·  elapsed {e // 60}m {e % 60:02d}s")

    def _on_progress(self, pct, t_hr):
        self.bar.setValue(int(pct * 10))
        self._progress_text = f"{pct:.1f}%  ·  simulated {t_hr:.2f} h"
        self._tick()

    def _on_result(self, results):
        outdir = self.args[4]
        if results.get("cancelled"):
            self.log.appendPlainText("Simulation cancelled.")
            self._progress_text = "Cancelled."
            return
        save_results_json(outdir, results)
        self.bar.setValue(1000)
        self.log.appendPlainText("Simulation complete.")
        self.finished.emit(outdir, results)

    def _on_failed(self, tb):
        self.log.appendPlainText(tb)
        self._progress_text = "Simulation failed."
        QMessageBox.critical(self, "Simulation failed", tb)

    def _on_done(self):
        self.timer.stop()
        self._tick()
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def shutdown(self):
        if self._thread and self._thread.isRunning():
            self._worker.cancel_flag.set()
            self._thread.quit()
            self._thread.wait(60000)