"""Centralized dark theme; replaceable without changing the shell."""

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

BACKGROUND = "#191b20"
PANEL = "#14161a"
TEXT = "#eef0f5"
MUTED = "#a2a8b5"
ACCENT = "#b8a1ff"

STYLE = """
QWidget { color: #eef0f5; font-size: 14px; }
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget { background: #191b20; }
QFrame#topbar { background: #191b20; border-bottom: 1px solid #2b2e36; }
QFrame#rail, QFrame#catalog { background: #14161a; border-right: 1px solid #2b2e36; }
QLabel { background: transparent; }
QLabel[kind="muted"] { color: #a2a8b5; }
QLabel[kind="eyebrow"] { color: #b8a1ff; font-size: 12px; font-weight: 600; }
QLabel[kind="title"] { font-size: 36px; font-weight: 600; }
QLabel[kind="heading"] { font-size: 18px; font-weight: 600; }
QLabel#brand { font-size: 16px; font-weight: 600; }
QLabel#badge { background: #272332; color: #cdbaff; border-radius: 10px;
    padding: 5px 12px; font-size: 12px; }
QPushButton { background: transparent; border: 1px solid transparent;
    border-radius: 9px; padding: 10px 14px; text-align: left; }
QPushButton:hover { background: #282b33; }
QPushButton:checked { background: #30283f; color: #dccfff; border: 1px solid #514266; }
QPushButton:focus { border: 1px solid #b8a1ff; }
QPushButton:disabled { color: #818794; }
QPushButton#primary { background: #c4afff; color: #19151f; font-weight: 600;
    padding: 13px 22px; }
QPushButton#primary:hover { background: #d5c5ff; }
QPushButton#newScenario { background: #23262d; border: 1px solid #363a44; }
QLineEdit { background: #1e2127; border: 1px solid #363a44;
    border-radius: 8px; padding: 10px; color: #a2a8b5; }
QFrame#card { background: #20232a; border: 1px solid #343843; border-radius: 14px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #191b20; width: 8px; }
QScrollBar::handle:vertical { background: #494d59; border-radius: 4px;
    min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QListWidget::item:selected:active { background: #b8a1ff; color: #19151f; }
QListWidget::item:selected:!active { background: #30343e; color: #eef0f5; }
QComboBox QAbstractItemView { background: #20232a; color: #eef0f5;
    selection-background-color: #b8a1ff; selection-color: #19151f; }
QToolTip { color: #eef0f5; background: #30343e; border: 1px solid #515766; }
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BACKGROUND),
        (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.Base, PANEL),
        (QPalette.ColorRole.Text, TEXT),
        (QPalette.ColorRole.Button, PANEL),
        (QPalette.ColorRole.ButtonText, TEXT),
        (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, BACKGROUND),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
