from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from gui.pages.setup_page import SetupPage
from gui.pages.phase_a_page import PhaseAPage
from gui.pages.simulation_page import SimulationPage
from gui.pages.dashboard_page import DashboardPage

ROOT = Path(__file__).resolve().parent.parent


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VCH Simulation")
        self.resize(1320, 880)
        self.cfg = self.mats = self.outdir = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        QApplication.setOverrideCursor(Qt.WaitCursor)  # first run builds the material cache
        try:
            self.setup = SetupPage()
        finally:
            QApplication.restoreOverrideCursor()
        self.phase_a = PhaseAPage()
        self.sim = SimulationPage()
        self.dash = DashboardPage()

        self.tabs.addTab(self.setup, "1 · Setup")
        self.tabs.addTab(self.phase_a, "2 · Phase A (coil design)")
        self.tabs.addTab(self.sim, "3 · 3D Simulation")
        self.tabs.addTab(self.dash, "4 · Dashboard")
        self._enable(0)

        self.setup.proceed.connect(self.on_setup_done)
        self.phase_a.coil_selected.connect(self.on_coil_selected)
        self.sim.finished.connect(self.on_sim_done)
        self.dash.new_run.connect(self.on_new_run)

    def _enable(self, upto):
        for i in range(1, self.tabs.count()):
            self.tabs.setTabEnabled(i, i <= upto)

    def on_setup_done(self, cfg, mats):
        self.cfg, self.mats = cfg, mats
        self.outdir = str(ROOT / "testout" / f"run_{datetime.now():%Y%m%d_%H%M%S}")
        self.phase_a.set_config(cfg, mats["tank"], self.outdir)
        self._enable(1)
        self.tabs.setCurrentIndex(1)

    def on_coil_selected(self, R_coil, n_turns):
        self.sim.prepare(self.cfg, self.mats["tank"], R_coil, n_turns, self.outdir)
        self._enable(2)
        self.tabs.setCurrentIndex(2)

    def on_sim_done(self, outdir, results):
        self.dash.show_results(outdir, results, self.cfg.get("tank_shape", "cylinder"))
        self._enable(3)
        self.tabs.setCurrentIndex(3)

    def on_new_run(self):
        self._enable(0)
        self.tabs.setCurrentIndex(0)

    def closeEvent(self, event):
        for page in (self.sim, self.phase_a, self.dash):
            page.shutdown()
        super().closeEvent(event)