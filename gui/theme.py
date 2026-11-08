STYLESHEET = """
QWidget { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QTabWidget::pane { border: 1px solid #333; }
QTabBar::tab { background: #1e1e1e; padding: 10px 22px; border: 1px solid #333; border-bottom: none; }
QTabBar::tab:selected { background: #2a2a2a; color: #4CAF50; }
QTabBar::tab:disabled { color: #666; }
QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 14px; padding: 12px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #fff; font-weight: bold; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTableWidget {
    background: #1e1e1e; border: 1px solid #333; border-radius: 4px; padding: 3px 6px; }
QPushButton { background: #2a2a2a; border: 1px solid #444; border-radius: 4px; padding: 8px 16px; }
QPushButton:hover { background: #333; }
QPushButton:disabled { color: #666; }
QPushButton#primary { background: #2e7d32; border-color: #4CAF50; color: white; font-weight: bold; }
QPushButton#primary:disabled { background: #1e1e1e; border-color: #333; color: #666; }
QProgressBar { border: 1px solid #333; border-radius: 4px; text-align: center; background: #1e1e1e; }
QProgressBar::chunk { background: #4CAF50; }
QFrame#kpi { background: #1e1e1e; border-top: 4px solid #4CAF50; border-radius: 8px; }
QLabel#kpiValue { color: #4CAF50; font-size: 22px; font-weight: bold; }
QLabel#warn { color: #ff7043; }
QHeaderView::section { background: #1e1e1e; color: #bbb; padding: 6px; border: none; border-bottom: 1px solid #333; }
"""