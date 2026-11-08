# main.py -- starts the VCH Simulation desktop application
# (the old terminal wizard is kept in main_cli.py)
import os
import sys

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow  # imports QtWebEngine before QApplication exists
from gui.theme import STYLESHEET


def main():
    # pythonw / frozen builds have no stdout; the physics code prints
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())