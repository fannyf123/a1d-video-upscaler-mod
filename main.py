import sys
import os
import json
import datetime
from pathlib import Path

# ══ FIX: Ensure project root is in sys.path ════════════════════════════════
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QTextEdit, QFileDialog, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QSizePolicy, QStackedWidget, QToolButton,
    QFormLayout
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QColor, QDragEnterEvent, QDropEvent, QTextCursor
import qtawesome as qta

from App.background_process import A1DProcessor
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS

CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
APP_NAME    = "A1D Video Upscaler"
APP_VER     = "2.4.0"

# ══════════════════════════════════════════════════════════════════════════════
#  THEME PALETTES  —  Dark (default) & Light
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        "bg":        "#0D1117",
        "sidebar":   "#161B22",
        "surface":   "#21262D",
        "input":     "#0D1117",
        "border":    "#30363D",
        "primary":   "#A78BFA",   # bright violet
        "primary_h": "#C4B5FD",   # lighter violet
        "accent":    "#60A5FA",   # blue
        "text":      "#FFFFFF",   # crisp white
        "text_dim":  "#C9D1D9",   # light grey — much brighter than before
        "text_muted":"#8B949E",
        "success":   "#3FB950",
        "warning":   "#D29922",
        "error":     "#F85149",
        "log_bg":    "#010409",
    },
    "light": {
        "bg":        "#F6F8FA",
        "sidebar":   "#FFFFFF",
        "surface":   "#FFFFFF",
        "input":     "#F6F8FA",
        "border":    "#D0D7DE",
        "primary":   "#7C3AED",   # deep violet
        "primary_h": "#6D28D9",
        "accent":    "#2563EB",   # blue
        "text":      "#1C2128",   # near-black
        "text_dim":  "#24292F",   # dark — clearly visible
        "text_muted":"#57606A",
        "success":   "#1A7F37",
        "warning":   "#9A6700",
        "error":     "#CF222E",
        "log_bg":    "#FFFFFF",
    },
}

# Active theme starts as dark
C = dict(THEMES["dark"])
_CURRENT_THEME = "dark"


def build_stylesheet(c: dict) -> str:
    """
    Generate the full QSS from a given color palette dict `c`.
    No wildcard `*` selector — font is set at app level to avoid
    QFont::setPointSize <= 0 warnings.
    """
    return f"""
/* ── GLOBAL ── */
QWidget {{ color: {c['text']}; outline: none; }}
QMainWindow, QWidget#MainContent {{ background-color: {c['bg']}; }}
QWidget#Sidebar {{ background-color: {c['sidebar']}; border-right: 1px solid {c['border']}; }}

/* ── TYPOGRAPHY ── */
QLabel#H1  {{ font-size: 24px; font-weight: 800; color: {c['text']}; }}
QLabel#H2  {{ font-size: 15px; font-weight: 700; color: {c['text']}; }}
QLabel#Sub {{ font-size: 12px; color: {c['text_muted']}; font-weight: 500; }}
QLabel     {{ color: {c['text']}; }}

/* ── CARDS ── */
QFrame#Card {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}
QFrame#Card:hover {{ border-color: {c['primary']}; }}

/* ── STANDARD BUTTONS ── */
QPushButton {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 700;
    color: {c['text']};
}}
QPushButton:hover  {{ background-color: {c['border']}; border-color: {c['text_muted']}; }}
QPushButton:pressed{{ background-color: {c['bg']}; }}

/* ── PRIMARY GRADIENT BUTTON ── */
QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c['primary']}, stop:1 {c['primary_h']});
    border: none;
    color: #FFFFFF;
}}
QPushButton#PrimaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c['primary_h']}, stop:1 {c['primary']});
}}

/* ── DANGER BUTTON ── */
QPushButton#DangerBtn {{
    background-color: transparent;
    border: 2px solid {c['error']};
    color: {c['error']};
}}
QPushButton#DangerBtn:hover {{ background-color: {c['error']}; color: #FFFFFF; }}

/* ── THEME TOGGLE BUTTON ── */
QPushButton#ThemeBtn {{
    background-color: transparent;
    border: 1px solid {c['border']};
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 700;
    color: {c['text_dim']};
}}
QPushButton#ThemeBtn:hover {{
    background-color: {c['primary']}22;
    border-color: {c['primary']};
    color: {c['primary']};
}}

/* ── SIDEBAR NAV BUTTONS ── */
QToolButton#NavBtn {{
    background-color: transparent;
    border: none;
    border-radius: 10px;
    padding: 11px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
    color: {c['text_dim']};
}}
QToolButton#NavBtn:hover   {{ background-color: {c['surface']}; color: {c['text']}; }}
QToolButton#NavBtn:checked {{ background-color: {c['primary']}33; color: {c['primary']}; font-weight: 800; }}

/* ── INPUTS ── */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {c['input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 22px;
    color: {c['text']};
    selection-background-color: {c['primary']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1.5px solid {c['primary']};
}}
QLineEdit::placeholder {{ color: {c['text_muted']}; }}

QComboBox::drop-down {{ border: none; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; border: none; }}

/* ── CHECKBOX ── */
QCheckBox {{ color: {c['text']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1.5px solid {c['border']};
    border-radius: 4px;
    background: {c['input']};
}}
QCheckBox::indicator:checked {{
    background: {c['primary']};
    border-color: {c['primary']};
}}

/* ── LIST WIDGET ── */
QListWidget {{
    background-color: {c['input']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    outline: none;
    color: {c['text']};
}}
QListWidget::item {{ padding: 11px; border-bottom: 1px solid {c['border']}; color: {c['text']}; }}
QListWidget::item:selected {{ background-color: {c['primary']}33; color: {c['primary']}; }}

/* ── SCROLL BAR ── */
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 3px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── PROGRESS BAR ── */
QProgressBar {{
    background-color: {c['input']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    min-height: 14px;
    max-height: 14px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['primary']}, stop:1 {c['accent']});
    border-radius: 6px;
}}

/* ── SCROLL AREA ── */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
"""


# ══════════════════════════════════════════════════════════════════════════════
#  DROP ZONE
# ══════════════════════════════════════════════════════════════════════════════
class ModernDropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setObjectName("DropZone")
        self._refresh_styles()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)

        self.text_lbl = QLabel("Drag & Drop Videos Here")
        self.text_lbl.setAlignment(Qt.AlignCenter)

        self.sub_lbl = QLabel("Supported: MP4 · MKV · MOV · AVI · WEBM · FLV")
        self.sub_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.text_lbl)
        layout.addWidget(self.sub_lbl)
        self._refresh_content_styles()

    def _refresh_styles(self):
        self._default_style = f"QFrame#DropZone {{ border: 2px dashed {C['border']}; border-radius: 16px; background-color: {C['surface']}; }}"
        self._hover_style   = f"QFrame#DropZone {{ border: 2px dashed {C['primary']}; border-radius: 16px; background-color: {C['primary']}18; }}"
        self.setStyleSheet(self._default_style)

    def _refresh_content_styles(self):
        self.icon_lbl.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary']).pixmap(44, 44))
        self.text_lbl.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {C['text']};")
        self.sub_lbl.setStyleSheet(f"font-size: 12px; color: {C['text_muted']};")

    def refresh_theme(self):
        self._refresh_styles()
        self._refresh_content_styles()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(self._hover_style)

    def dragLeaveEvent(self, e):
        self.setStyleSheet(self._default_style)

    def dropEvent(self, e):
        self.setStyleSheet(self._default_style)
        paths = [
            u.toLocalFile() for u in e.mimeData().urls()
            if u.toLocalFile().lower().endswith(('.mp4','.mkv','.mov','.avi','.webm','.flv','.wmv'))
        ]
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, e):
        self.files_dropped.emit([])


# ══════════════════════════════════════════════════════════════════════════════
#  LOG VIEWER
# ══════════════════════════════════════════════════════════════════════════════
class LogViewer(QTextEdit):
    def __init__(self, max_lines: int = 2000):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C['log_bg']};
                border: 1px solid {C['border']};
                border-radius: 12px;
                font-family: 'Consolas', 'Monaco', 'Lucida Console', monospace;
                font-size: 12px;
                padding: 14px;
                color: {C['text']};
            }}
        """)

    def append_log(self, msg, level: str = "INFO"):
        if isinstance(msg, tuple):
            msg = str(msg[0])

        ml = msg.lower()
        if   "error"     in ml or "failed"    in ml or "exception" in ml: color = C['error']
        elif "success"   in ml or "completed" in ml or "finished"  in ml: color = C['success']
        elif "warning"   in ml or "timeout"   in ml:                      color = C['warning']
        elif "worker"    in ml or "thread"    in ml or "batch"     in ml: color = C['accent']
        elif level == "SUCCESS":  color = C['success']
        elif level == "ERROR":    color = C['error']
        elif level == "WARNING":  color = C['warning']
        else:                     color = C['text']

        ts   = datetime.datetime.now().strftime("%H:%M:%S")
        html = (f'<span style="color:{C["text_muted"]}": 