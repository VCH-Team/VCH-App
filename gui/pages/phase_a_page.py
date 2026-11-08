import math
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from gui.widgets import DSpin, ISpin
from gui.workers import PhaseAWorker, start_in_thread

PLACEHOLDER = "Press “Generate design charts” to run the Phase A sweep."


class PhaseAPage(QWidget):
    coil_selected = Signal(float, int)  # R_coil, n_turns

    def __init__(self):
        super().__init__()
        self.cfg = self.mat = self.outdir = None
        self.n_fit = 1
        self._pix = None
        self._thread = self._worker = None

        # sweep settings
        g1 = QGroupBox("Phase A · design sweep")
        f = QFormLayout(g1)
        self.num_R = ISpin(3, 1, 5)
        self.min_R = DSpin(0.1, 0.01, 20, 3, 0.05, " m")
        self.max_R = DSpin(0.4, 0.01, 20, 3, 0.05, " m")
        self.max_turns = ISpin(10, 1, 500)
        self.btn_gen = QPushButton("Generate design charts")
        self.btn_gen.setObjectName("primary")
        self.bar = QProgressBar()
        self.lbl_state = QLabel("")
        self.lbl_state.setWordWrap(True)
        f.addRow("Radii to compare (1–5)", self.num_R)
        f.addRow("Minimum radius", self.min_R)
        f.addRow("Maximum radius", self.max_R)
        f.addRow("Maximum turns to test", self.max_turns)
        f.addRow(self.btn_gen)
        f.addRow(self.bar)
        f.addRow(self.lbl_state)

        # coil choice
        self.g2 = QGroupBox("Select coil")
        f = QFormLayout(self.g2)
        self.sel_R = DSpin(0.3, 0.01, 20, 3, 0.05, " m")
        self.sel_n = ISpin(1, 1, 500)
        self.lbl_coil = QLabel("")
        self.lbl_coil.setWordWrap(True)
        self.btn_run = QPushButton("Run 3D simulation  →")
        self.btn_run.setObjectName("primary")
        f.addRow("Coil radius", self.sel_R)
        f.addRow("Number of turns", self.sel_n)
        f.addRow(self.lbl_coil)
        f.addRow(self.btn_run)
        self.g2.setEnabled(False)

        left = QVBoxLayout()
        left.addWidget(g1)
        left.addWidget(self.g2)
        left.addStretch()
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(330)

        self.img = QLabel(PLACEHOLDER)
        self.img.setAlignment(Qt.AlignCenter)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.img)

        root = QHBoxLayout(self)
        root.addWidget(left_w)
        root.addWidget(self.scroll, 1)

        self.btn_gen.clicked.connect(self._generate)
        self.btn_run.clicked.connect(self._emit_selection)
        self.sel_R.valueChanged.connect(self._update_coil)
        self.sel_n.valueChanged.connect(self._update_coil)

    # ------------------------------------------------------------ public
    def set_config(self, cfg, mat, outdir):
        self.cfg, self.mat, self.outdir = cfg, mat, outdir
        r_in, d_out = cfg["r_inner"], cfg["d_out"]
        r_lim = max(0.02, r_in - d_out / 2.0 - 1e-4)
        for w in (self.min_R, self.max_R, self.sel_R):
            w.setRange(0.01, r_lim)
        self.min_R.setValue(min(0.3 * r_in, r_lim))
        self.max_R.setValue(min(0.9 * r_in, r_lim))
        self.n_fit = max(1, int(cfg["L_avail"] / d_out))
        for w in (self.max_turns, self.sel_n):
            w.setRange(1, self.n_fit)
        self.max_turns.setValue(self.n_fit)
        self._pix = None
        self.img.setPixmap(QPixmap())
        self.img.setText(PLACEHOLDER)
        self.g2.setEnabled(False)
        self.bar.setValue(0)
        self.lbl_state.setText("")

    def shutdown(self):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(60000)

    # ------------------------------------------------------------ sweep
    def _generate(self):
        if self.num_R.value() > 1 and self.min_R.value() >= self.max_R.value():
            QMessageBox.warning(self, "Radii", "Maximum radius must be larger than the minimum radius.")
            return
        os.makedirs(self.outdir, exist_ok=True)
        out = os.path.join(self.outdir, "design_charts_phases.png")
        self.bar.setRange(0, self.num_R.value())
        self.bar.setValue(0)
        self.btn_gen.setEnabled(False)
        self.lbl_state.setText("Running sweep… (first run compiles code and can take a while)")

        w = PhaseAWorker(self.cfg, self.mat, self.min_R.value(), self.max_R.value(),
                         self.num_R.value(), self.max_turns.value(), out)
        w.progress.connect(self._on_progress)
        w.result.connect(self._on_result)
        w.failed.connect(self._on_failed)
        w.done.connect(self._on_worker_done)
        self._worker = w
        self._thread = start_in_thread(w, self)

    def _on_progress(self, i, n):
        self.bar.setValue(i)

    def _on_worker_done(self):
        self.btn_gen.setEnabled(True)

    def _on_result(self, path, radii):
        self._pix = QPixmap(path)
        self._rescale()
        self.sel_R.setValue(radii[-1])
        self.sel_n.setValue(max(1, self.max_turns.value() // 2))
        self.g2.setEnabled(True)
        self.lbl_state.setText(f"Chart saved: {path}")
        self._update_coil()

    def _on_failed(self, tb):
        self.lbl_state.setText("Sweep failed.")
        QMessageBox.critical(self, "Phase A failed", tb)

    def _emit_selection(self):
        self.coil_selected.emit(self.sel_R.value(), self.sel_n.value())

    # ------------------------------------------------------------ coil validation
    def _update_coil(self, *_):
        if not self.cfg:
            return
        R, n = self.sel_R.value(), self.sel_n.value()
        d_out, L_avail, r_in = self.cfg["d_out"], self.cfg["L_avail"], self.cfg["r_inner"]
        pitch = L_avail / n
        text = f"Coil length {2 * math.pi * R * n:.2f} m · pitch {pitch * 100:.1f} cm (tube {d_out * 100:.1f} cm)"
        problem = None
        if R + d_out / 2.0 > r_in:
            problem = "Coil radius is too large for the tank."
        elif pitch < d_out:
            problem = f"Turns too tight. Max turns for this tank is {self.n_fit}."
        if problem:
            self.lbl_coil.setObjectName("warn")
            text += "\n" + problem
        else:
            self.lbl_coil.setObjectName("")
        self.lbl_coil.style().unpolish(self.lbl_coil)
        self.lbl_coil.style().polish(self.lbl_coil)
        self.lbl_coil.setText(text)
        self.btn_run.setEnabled(problem is None)

    # ------------------------------------------------------------ image scaling
    def _rescale(self):
        if self._pix is None or self._pix.isNull():
            return
        w = max(400, self.scroll.viewport().width() - 10)
        self.img.setPixmap(self._pix.scaledToWidth(w, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()