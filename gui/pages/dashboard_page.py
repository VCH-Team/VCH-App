from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from gui.workers import ViewerWorker, start_in_thread

_LOADING = ("<body style='background:#121212;color:#ccc;font-family:sans-serif;"
            "display:flex;align-items:center;justify-content:center;height:90vh'>"
            "<h3>{}</h3></body>")

_COLUMNS = [("Cycle", "cycle", "{:.0f}"), ("Start Temp (°C)", "start_temp", "{:.1f}"),
            ("End Temp (°C)", "end_temp", "{:.1f}"), ("Mass Extracted (kg)", "extracted_kg", "{:.1f}"),
            ("Efficiency (%)", "efficiency_pct", "{:.1f}"), ("Energy Added (kWh)", "E_coil_kwh", "{:.2f}"),
            ("Energy Lost (kWh)", "E_loss_kwh", "{:.2f}")]


class DashboardPage(QWidget):
    new_run = Signal()

    def __init__(self):
        super().__init__()
        self.outdir = None
        self._thread = self._worker = None

        self.kpis = {}
        kpi_row = QHBoxLayout()
        for key, title in [("total_hr", "Total Time"), ("final_mass", "Final Mass"),
                           ("total_extracted_kg", "Total Extracted"), ("total_filled_kg", "Total Filled")]:
            frame = QFrame()
            frame.setObjectName("kpi")
            lay = QVBoxLayout(frame)
            t = QLabel(title)
            t.setAlignment(Qt.AlignCenter)
            v = QLabel("–")
            v.setObjectName("kpiValue")
            v.setAlignment(Qt.AlignCenter)
            lay.addWidget(t)
            lay.addWidget(v)
            kpi_row.addWidget(frame)
            self.kpis[key] = v

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)

        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addLayout(kpi_row)
        tl.addWidget(self.table)

        self.web = QWebEngineView()
        self.web.setHtml(_LOADING.format("Run a simulation to see the 3D viewer"))

        split = QSplitter(Qt.Vertical)
        split.addWidget(top)
        split.addWidget(self.web)
        split.setSizes([250, 650])

        self.btn_folder = QPushButton("Open run folder")
        self.btn_new = QPushButton("New run")
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(self.btn_folder)
        bottom.addWidget(self.btn_new)

        root = QVBoxLayout(self)
        root.addWidget(split, 1)
        root.addLayout(bottom)
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_new.clicked.connect(self.new_run.emit)

    def _open_folder(self):
        if self.outdir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.outdir))

    def show_results(self, outdir, results, shape):
        self.outdir = outdir
        self.kpis["total_hr"].setText(f"{results['total_hr']:.1f} hr")
        for k in ("final_mass", "total_extracted_kg", "total_filled_kg"):
            self.kpis[k].setText(f"{results[k]:.1f} kg")

        rows = results["cycle_metrics"]
        self.table.setRowCount(len(rows))
        for r, c in enumerate(rows):
            for col, (_, key, fmt) in enumerate(_COLUMNS):
                item = QTableWidgetItem(fmt.format(c[key]))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, col, item)

        self.web.setHtml(_LOADING.format("Building interactive 3D viewer…"))
        w = ViewerWorker(outdir, shape)
        w.result.connect(self._on_viewer)
        w.failed.connect(self._on_viewer_failed)
        self._worker = w
        self._thread = start_in_thread(w, self)

    def _on_viewer(self, path):
        if path:
            self.web.load(QUrl.fromLocalFile(path))
        else:
            self.web.setHtml(_LOADING.format("No snapshots were saved for this run."))

    def _on_viewer_failed(self, tb):
        print(tb)
        self.web.setHtml(_LOADING.format("Viewer failed. See console."))

    def shutdown(self):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(60000)