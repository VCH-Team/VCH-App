import math

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

import materials
from physics import config
from gui import options
from gui.widgets import Combo, DSpin, ISpin, PortBox, subform


class SetupPage(QWidget):
    proceed = Signal(object, object)  # cfg, mats

    def __init__(self):
        super().__init__()
        self._mat_cache = {}
        self.max_mass = 0.0

        avail = materials.list_available()
        fluids = [n for n in options.FLUIDS if n in avail] or avail
        metals = [n for n in options.METALS if n in avail] or avail
        insul = [n for n in options.INSULATORS if n in avail] or avail

        # ---------------- materials
        g_mat = QGroupBox("Materials")
        f = QFormLayout(g_mat)
        self.cb_tank = Combo(fluids, "RBD Palm Oil")
        self.cb_coil = Combo(fluids, "Water")
        self.cb_tube = Combo(metals, "Copper")
        self.cb_wall = Combo(metals, "Stailness Steel")
        f.addRow("Tank fluid", self.cb_tank)
        f.addRow("Coil fluid", self.cb_coil)
        f.addRow("Coil tube metal", self.cb_tube)
        f.addRow("Tank wall metal", self.cb_wall)

        # ---------------- geometry
        g_geo = QGroupBox("Tank geometry & walls")
        f = QFormLayout(g_geo)
        self.cb_shape = Combo(["cylinder", "cuboid"], "cylinder")
        self.radius = DSpin(0.5, 0.05, 20, 3, 0.05, " m")
        self.length = DSpin(1.0, 0.1, 20, 3, 0.1, " m")
        self.width = DSpin(1.0, 0.1, 20, 3, 0.1, " m")
        self.shape_stack = QStackedWidget()
        self.shape_stack.addWidget(subform(("Radius", self.radius)))
        self.shape_stack.addWidget(subform(("Length", self.length), ("Width", self.width)))
        self.height = DSpin(1.0, 0.1, 50, 3, 0.1, " m")
        self.res = ISpin(20, 10, 60)
        self.t_wall = DSpin(0.005, 0.0005, 0.2, 4, 0.001, " m")
        self.h_air = DSpin(10.0, 0.0, 200, 1, 1, " W/m²K")
        self.chk_ins = QCheckBox("Add insulation")
        self.t_ins = DSpin(0.05, 0.001, 1.0, 3, 0.01, " m")
        self.cb_ins = Combo(insul)
        self.ins_box = subform(("Thickness", self.t_ins), ("Material", self.cb_ins))
        self.ins_box.setEnabled(False)
        f.addRow("Shape", self.cb_shape)
        f.addRow(self.shape_stack)
        f.addRow("Height", self.height)
        f.addRow("Grid resolution (10–60)", self.res)
        f.addRow("Wall thickness", self.t_wall)
        f.addRow("Ambient air convection", self.h_air)
        f.addRow(self.chk_ins)
        f.addRow(self.ins_box)

        # ---------------- operating
        g_op = QGroupBox("Operating conditions")
        f = QFormLayout(g_op)
        self.t_amb_low = DSpin(5.0, -50, 60, 1, 1, " °C")
        self.t_start = DSpin(20.0, -50, 200, 1, 1, " °C")
        self.t_target = DSpin(60.0, -50, 200, 1, 1, " °C")
        self.t_amb_mid = DSpin(25.0, -50, 60, 1, 1, " °C")
        self.t_water_in = DSpin(80.0, 0, 200, 1, 1, " °C")
        self.flow = DSpin(1.0, 0.001, 1000, 3, 0.1, " m³/h")
        f.addRow("Lowest site temp / solid start", self.t_amb_low)
        f.addRow("Tank starting temp", self.t_start)
        f.addRow("Target liquid temp", self.t_target)
        f.addRow("Ambient temp", self.t_amb_mid)
        f.addRow("Coil inlet temp", self.t_water_in)
        f.addRow("Coil flow rate", self.flow)

        # ---------------- fluid mass
        g_mass = QGroupBox("Tank fluid mass")
        f = QFormLayout(g_mass)
        self.chk_full = QCheckBox("Fill to capacity")
        self.chk_full.setChecked(True)
        self.mass = DSpin(100.0, 0.1, 1e7, 1, 10, " kg")
        self.lbl_cap = QLabel("")
        f.addRow(self.chk_full)
        f.addRow("Mass", self.mass)
        f.addRow(self.lbl_cap)

        # ---------------- coil
        g_coil = QGroupBox("Coil dimensions & placement")
        f = QFormLayout(g_coil)
        self.d_in = DSpin(0.0409, 0.002, 0.5, 5, 0.001, " m")
        self.d_out = DSpin(0.04826, 0.003, 0.5, 5, 0.001, " m")
        self.clr_bot = DSpin(0.05, 0.0, 10, 3, 0.01, " m")
        self.clr_top = DSpin(0.05, 0.0, 10, 3, 0.01, " m")
        self.lbl_coil = QLabel("")
        f.addRow("Inner diameter", self.d_in)
        f.addRow("Outer diameter", self.d_out)
        f.addRow("Clearance from bottom", self.clr_bot)
        f.addRow("Clearance from top", self.clr_top)
        f.addRow(self.lbl_coil)

        # ---------------- schedule
        g_sch = QGroupBox("Simulation schedule")
        f = QFormLayout(g_sch)
        self.t_heat = DSpin(12.0, 0.01, 1000, 2, 1, " h")
        self.t_cool = DSpin(12.0, 0.0, 1000, 2, 1, " h")
        self.cycles = ISpin(1, 1, 20)
        self.dt = DSpin(1.0, 0.1, 60, 2, 0.5, " s")
        self.snap = DSpin(0.1, 0.01, 10, 2, 0.05, " h")
        f.addRow("Heating phase", self.t_heat)
        f.addRow("Cooling phase", self.t_cool)
        f.addRow("Cycles (heating + cooling)", self.cycles)
        f.addRow("Time step", self.dt)
        f.addRow("Snapshot interval", self.snap)

        self.drain = PortBox("drain")
        self.fill = PortBox("fill")

        # ---------------- layout
        left, right = QVBoxLayout(), QVBoxLayout()
        for g in (g_mat, g_geo, g_mass, g_coil):
            left.addWidget(g)
        left.addStretch()
        for g in (g_op, g_sch, self.drain, self.fill):
            right.addWidget(g)
        right.addStretch()
        cols = QHBoxLayout()
        cols.addLayout(left)
        cols.addLayout(right)
        inner = QWidget()
        inner.setLayout(cols)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)

        self.btn_next = QPushButton("Next: Phase A coil design  →")
        self.btn_next.setObjectName("primary")
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(self.btn_next)
        root = QVBoxLayout(self)
        root.addWidget(scroll)
        root.addLayout(bottom)

        # ---------------- signals (after all widgets exist)
        self.cb_shape.currentTextChanged.connect(self._on_shape)
        self.chk_ins.toggled.connect(self.ins_box.setEnabled)
        self.chk_full.toggled.connect(self._refresh)
        self.cb_tank.currentIndexChanged.connect(self._refresh)
        for w in (self.radius, self.length, self.width, self.height, self.t_start,
                  self.d_out, self.clr_bot, self.clr_top):
            w.valueChanged.connect(self._refresh)
        self.btn_next.clicked.connect(self._on_next)
        self._on_shape("cylinder")
        self._refresh()

    # ------------------------------------------------------------ helpers
    def _mat(self, name):
        if name not in self._mat_cache:
            self._mat_cache[name] = materials.load(name)
        return self._mat_cache[name]

    def _on_shape(self, shape):
        self.shape_stack.setCurrentIndex(0 if shape == "cylinder" else 1)
        self.drain.set_shape(shape)
        self.fill.set_shape(shape)
        self._refresh()

    def _tank_volume(self):
        h = self.height.value()
        if self.cb_shape.currentText() == "cylinder":
            return math.pi * self.radius.value() ** 2 * h
        return self.length.value() * self.width.value() * h

    def _refresh(self, *_):
        try:
            mat = self._mat(self.cb_tank.currentText())
            rho = float(np.interp(self.t_start.value(), mat["T_grid"], mat["rho_grid"]))
            self.max_mass = self._tank_volume() * rho
            self.lbl_cap.setText(f"Capacity at {self.t_start.value():.0f} °C ≈ {self.max_mass:.1f} kg")
            self.mass.setRange(0.1, max(self.max_mass, 0.2))
            if self.chk_full.isChecked():
                self.mass.setValue(self.max_mass)
            self.mass.setEnabled(not self.chk_full.isChecked())
        except Exception as e:
            self.lbl_cap.setText(f"Could not compute capacity: {e}")
        L_avail = self.height.value() - self.clr_bot.value() - self.clr_top.value()
        max_turns = int(L_avail / self.d_out.value()) if L_avail > 0 else 0
        self.lbl_coil.setText(f"Axial length for coil: {L_avail:.3f} m  ·  max turns ≈ {max_turns}")

    # ------------------------------------------------------------ build config
    def build_config(self):
        shape = self.cb_shape.currentText()
        h = self.height.value()
        if shape == "cylinder":
            L = W = 0.0
            r_inner = self.radius.value()
        else:
            L, W = self.length.value(), self.width.value()
            # physics.coil validates the coil against r_inner, which would be 0 for a cuboid;
            # use half of the shorter side so the coil check works.
            r_inner = min(L, W) / 2.0

        d_in, d_out = self.d_in.value(), self.d_out.value()
        if d_in >= d_out:
            raise ValueError("Coil inner diameter must be smaller than the outer diameter.")
        L_avail = h - self.clr_bot.value() - self.clr_top.value()
        if L_avail < d_out:
            raise ValueError("Coil clearances leave no room for even one turn. Reduce the clearances.")

        t_ins, k_ins = 0.0, 0.04
        if self.chk_ins.isChecked():
            t_ins = self.t_ins.value()
            k_ins = float(self._mat(self.cb_ins.currentText())["k_grid"][0])

        mats = {
            "tank": self._mat(self.cb_tank.currentText()),
            "coil": self._mat(self.cb_coil.currentText()),
            "tube": self._mat(self.cb_tube.currentText()),
            "wall": self._mat(self.cb_wall.currentText()),
        }
        cfg = config.with_defaults({
            "tank_shape": shape, "r_inner": r_inner, "tank_height": h, "res": self.res.value(),
            "tank_length": L, "tank_width": W,
            "d_in": d_in, "d_out": d_out, "t_wall": self.t_wall.value(),
            "t_ins": t_ins, "k_ins": k_ins, "h_air": self.h_air.value(),
            "M_fluid": self.mass.value(), "T_start": self.t_start.value(),
            "T_amb_low": self.t_amb_low.value(), "T_target": self.t_target.value(),
            "T_amb_mid": self.t_amb_mid.value(), "T_water_in": self.t_water_in.value(),
            "flow_m3h": self.flow.value(), "dt_sec": self.dt.value(),
            "t_window_hr": self.t_heat.value(), "t_cooldown_hr": self.t_cool.value(),
            "N_cycles": self.cycles.value(), "snapshot_interval_hr": self.snap.value(),
            "coil_clearance_bottom": self.clr_bot.value(), "L_avail": L_avail,
            **self.drain.to_cfg(), **self.fill.to_cfg(),
        })
        cfg["T_water_arr"] = mats["coil"]["T_grid"]
        cfg["rho_water_arr"] = mats["coil"]["rho_grid"]
        cfg["cp_water_arr"] = mats["coil"]["cp_sens_grid"]
        cfg["mu_water_arr"] = mats["coil"]["mu_grid"]
        cfg["k_water_arr"] = mats["coil"]["k_grid"]
        cfg["T_tube_arr"] = mats["tube"]["T_grid"]
        cfg["k_tube_arr"] = mats["tube"]["k_grid"]
        cfg["T_wall_arr"] = mats["wall"]["T_grid"]
        cfg["k_wall_arr"] = mats["wall"]["k_grid"]
        cfg["rho_wall_arr"] = mats["wall"]["rho_grid"]
        cfg["cp_wall_arr"] = mats["wall"]["cp_sens_grid"]
        return cfg, mats

    def _on_next(self):
        try:
            cfg, mats = self.build_config()
        except Exception as e:
            QMessageBox.warning(self, "Check your inputs", str(e))
            return
        self.proceed.emit(cfg, mats)