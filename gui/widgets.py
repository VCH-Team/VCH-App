from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QSpinBox, QStackedWidget, QWidget)


class _NoWheel:
    """Ignore the mouse wheel unless the widget has focus (so scrolling the form is safe)."""
    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class DSpin(_NoWheel, QDoubleSpinBox):
    def __init__(self, value=0.0, lo=0.0, hi=1e6, dec=3, step=0.1, suffix=""):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setKeyboardTracking(False)
        self.setDecimals(dec)
        self.setRange(lo, hi)
        self.setSingleStep(step)
        self.setValue(value)
        if suffix:
            self.setSuffix(suffix)


class ISpin(_NoWheel, QSpinBox):
    def __init__(self, value=0, lo=0, hi=1000000, suffix=""):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setKeyboardTracking(False)
        self.setRange(lo, hi)
        self.setValue(value)
        if suffix:
            self.setSuffix(suffix)


class Combo(_NoWheel, QComboBox):
    def __init__(self, items, default=None):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.addItems(list(items))
        if default in items:
            self.setCurrentText(default)


def subform(*rows):
    w = QWidget()
    f = QFormLayout(w)
    f.setContentsMargins(0, 0, 0, 0)
    for label, widget in rows:
        f.addRow(label, widget)
    return w


class PortBox(QGroupBox):
    """Drain or fill configuration. Checkable group box = enable/disable."""

    def __init__(self, kind):
        super().__init__(f"Enable {kind}")
        self.kind = kind
        self.setCheckable(True)
        self.setChecked(False)
        form = QFormLayout(self)

        self.r = DSpin(0.0, 0, 50, 3, 0.05, " m")
        self.theta = DSpin(0.0, 0, 360, 1, 5, " °")
        self.x = DSpin(0.0, -50, 50, 3, 0.05, " m")
        self.y = DSpin(0.0, -50, 50, 3, 0.05, " m")
        self.stack = QStackedWidget()
        self.stack.addWidget(subform(("Radius", self.r), ("Angle", self.theta)))
        self.stack.addWidget(subform(("X (centre = 0)", self.x), ("Y (centre = 0)", self.y)))
        form.addRow(self.stack)

        self.z = DSpin(0.01 if kind == "drain" else 0.99, 0, 50, 3, 0.05, " m")
        self.d = DSpin(0.05, 0.001, 1.0, 4, 0.005, " m")
        form.addRow("Height", self.z)
        form.addRow("Diameter", self.d)

        if kind == "drain":
            self.pressure = DSpin(0.0, 0, 1e7, 1, 100, " Pa")
            self.max_flow = DSpin(0.0, 0, 1e4, 2, 0.5, " m³/h")
            form.addRow("Controlled pressure (0 = none)", self.pressure)
            form.addRow("Max flow (0 = unlimited)", self.max_flow)
        else:
            self.flow = DSpin(0.5, 0.01, 100, 2, 0.1, " m³/h")
            self.temp = DSpin(20.0, -50, 200, 1, 1, " °C")
            self.max_flow = DSpin(0.0, 0, 1e4, 2, 0.5, " m³/h")
            self.spread = QCheckBox("Positive pressure (spread beyond fill cell)")
            self.spread.setChecked(True)
            form.addRow("Flow rate", self.flow)
            form.addRow("Fluid temperature", self.temp)
            form.addRow("Max flow cap (0 = unlimited)", self.max_flow)
            form.addRow(self.spread)

    def set_shape(self, shape):
        self.stack.setCurrentIndex(0 if shape == "cylinder" else 1)

    def to_cfg(self):
        k = self.kind
        out = {
            f"simulate_{k}": self.isChecked(),
            f"{k}_r": self.r.value(), f"{k}_theta": self.theta.value(),
            f"{k}_x": self.x.value(), f"{k}_y": self.y.value(),
            f"{k}_z": self.z.value(), f"{k}_diameter": self.d.value(),
            f"{k}_max_flow_m3h": self.max_flow.value(),
        }
        if k == "drain":
            out["drain_pressure_pa"] = self.pressure.value()
        else:
            out["fill_flow_m3h"] = self.flow.value()
            out["fill_T"] = self.temp.value()
            out["fill_spread"] = self.spread.isChecked()
        return out