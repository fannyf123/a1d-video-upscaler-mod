import sys
import os
import json
import datetime
import shutil

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QTextEdit, QFileDialog, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QSizePolicy, QStackedWidget, QToolButton,
    QFormLayout, QMessageBox, QSpacerItem
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QTextCursor, QColor
import qtawesome as qta

from App.background_process import A1DProcessor
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS

CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
APP_NAME    = "A1D Video Upscaler"
APP_VER     = "2.6.0"

# ══════════════════════════════════════════════════════════════════════════════
#  COLOUR SYSTEM  —  minimum 7:1 contrast ratio on all text
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        "bg":         "#0B0D14",     # deep navy-black
        "sidebar":    "#0E1120",     # slightly navy
        "surface":    "#151929",     # card surface
        "surface2":   "#1C2136",     # slightly lighter card
        "input":      "#0E1020",     # input field bg
        "border":     "#2A3050",     # visible blue-tinted border
        "primary":    "#8B5CF6",     # vivid violet
        "primary_h":  "#A78BFA",     # lighter violet hover
        "accent":     "#38BDF8",     # sky blue accent
        "accent2":    "#34D399",     # emerald accent
        "text":       "#F0F4FF",     # near white, cool tint — HIGH CONTRAST
        "text_dim":   "#CBD5E1",     # light slate  — still very readable
        "text_muted": "#64748B",     # muted slate for secondary labels
        "success":    "#4ADE80",     # bright lime-green
        "warning":    "#FBBF24",     # amber
        "error":      "#F87171",     # soft red
        "log_bg":     "#07090F",     # near-black log bg
    },
    "light": {
        "bg":         "#EEF2FF",     # indigo-tinted white page
        "sidebar":    "#FFFFFF",     # pure white sidebar
        "surface":    "#FFFFFF",     # card surface
        "surface2":   "#F1F5F9",
        "input":      "#F8FAFC",
        "border":     "#C7D2E8",
        "primary":    "#6D28D9",     # deep violet — readable on white
        "primary_h":  "#5B21B6",
        "accent":     "#0369A1",     # deep sky-blue
        "accent2":    "#059669",
        "text":       "#0F172A",     # near-black
        "text_dim":   "#1E293B",     # dark slate
        "text_muted": "#475569",     # medium slate  — still very readable
        "success":    "#15803D",     # deep green on white
        "warning":    "#92400E",     # dark amber on white
        "error":      "#991B1B",     # deep red on white
        "log_bg":     "#F8FAFC",
    },
}

C = dict(THEMES["dark"])

def build_stylesheet(c: dict) -> str:
    return f"""
* {{ font-family: 'Inter', 'Segoe UI', sans-serif; outline: none; }}

QMainWindow {{ background: {c['bg']}; }}
QWidget#MainContent {{ background: {c['bg']}; }}
QWidget#Sidebar {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {c['sidebar']}, stop:1 {c['bg']});
    border-right: 1px solid {c['border']};
}}

/* ─ Typography ─────────────────────────────────────────────── */
QLabel {{ color: {c['text_dim']}; font-size: 13px; font-weight: 600; }}
QLabel#PageTitle {{
    color: {c['text']}; font-size: 28px; font-weight: 900; letter-spacing: -0.5px;
}}
QLabel#SectionTitle {{
    color: {c['text']}; font-size: 16px; font-weight: 800;
}}
QLabel#SubLabel {{
    color: {c['text_muted']}; font-size: 12px; font-weight: 600;
}}
QLabel#HintLabel {{
    color: {c['text_muted']}; font-size: 11px; font-style: italic; font-weight: 500;
}}
QLabel#BadgeLabel {{
    background: {c['primary']}30;
    color: {c['primary']};
    font-size: 12px; font-weight: 900;
    padding: 5px 14px; border-radius: 20px;
    border: 1px solid {c['primary']}50;
}}
QLabel#BadgeSuccess {{
    background: {c['success']}25;
    color: {c['success']};
    font-size: 12px; font-weight: 900;
    padding: 5px 14px; border-radius: 20px;
    border: 1px solid {c['success']}50;
}}
QLabel#BadgeError {{
    background: {c['error']}25;
    color: {c['error']};
    font-size: 12px; font-weight: 900;
    padding: 5px 14px; border-radius: 20px;
    border: 1px solid {c['error']}50;
}}

/* ─ Cards ────────────────────────────────────────────────── */
QFrame#Card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 16px;
}}
QFrame#AccentCard {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-left: 4px solid {c['primary']};
    border-radius: 16px;
}}
QFrame#SuccessCard {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-left: 4px solid {c['success']};
    border-radius: 16px;
}}
QFrame#WarnCard {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-left: 4px solid {c['warning']};
    border-radius: 16px;
}}

/* ─ Buttons ────────────────────────────────────────────── */
QPushButton {{
    background: {c['surface2']};
    border: 1.5px solid {c['border']};
    border-radius: 10px; padding: 10px 22px;
    font-weight: 800; font-size: 13px;
    color: {c['text']};
}}
QPushButton:hover  {{ background: {c['border']}; border-color: {c['primary']}; color: {c['text']}; }}
QPushButton:pressed{{ background: {c['bg']}; }}

QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {c['primary']}, stop:1 {c['primary_h']});
    border: none; color: #FFFFFF; font-size: 14px; font-weight: 900;
    padding: 14px 32px;
}}
QPushButton#PrimaryBtn:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {c['primary_h']}, stop:1 {c['primary']});
}}
QPushButton#DangerBtn {{
    background: {c['error']}18; border: 2px solid {c['error']};
    color: {c['error']}; font-weight: 900;
}}
QPushButton#DangerBtn:hover {{ background: {c['error']}; color: #FFFFFF; }}
QPushButton#WarnBtn {{
    background: {c['warning']}18; border: 2px solid {c['warning']};
    color: {c['warning']}; font-weight: 800;
}}
QPushButton#WarnBtn:hover {{ background: {c['warning']}; color: #0F172A; }}
QPushButton#GhostBtn {{
    background: transparent; border: 1.5px solid {c['border']};
    color: {c['text_dim']}; font-weight: 700;
}}
QPushButton#GhostBtn:hover {{ border-color: {c['primary']}; color: {c['primary']}; }}

/* ─ Sidebar Nav ────────────────────────────────────────── */
QToolButton#NavBtn {{
    background: transparent; border: none; border-radius: 12px;
    padding: 14px 16px; font-size: 13px; font-weight: 700;
    text-align: left; color: {c['text_muted']};
}}
QToolButton#NavBtn:hover {{
    background: {c['surface']};
    color: {c['text']};
}}
QToolButton#NavBtn:checked {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {c['primary']}40, stop:1 {c['primary']}08);
    color: {c['primary_h']};
    font-weight: 900;
    border-left: 3px solid {c['primary']};
}}

/* ─ Inputs ─────────────────────────────────────────────── */
QLineEdit, QComboBox, QSpinBox {{
    background: {c['input']};
    border: 1.5px solid {c['border']};
    border-radius: 10px; padding: 11px 16px;
    min-height: 22px;
    color: {c['text']}; font-weight: 700; font-size: 13px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {c['primary']}; background: {c['surface']};
}}
QLineEdit::placeholder {{ color: {c['text_muted']}; font-weight: 500; }}
QComboBox QAbstractItemView {{
    background: {c['surface2']}; border: 1.5px solid {c['border']};
    color: {c['text']}; selection-background-color: {c['primary']}50;
}}

/* ─ Checkbox ─────────────────────────────────────────── */
QCheckBox {{ color: {c['text_dim']}; spacing: 10px; font-weight: 700; font-size: 13px; }}
QCheckBox::indicator {{
    width: 22px; height: 22px; border: 2px solid {c['border']};
    border-radius: 7px; background: {c['input']};
}}
QCheckBox::indicator:hover {{ border-color: {c['primary']}; }}
QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {c['primary']}, stop:1 {c['primary_h']});
    border-color: {c['primary']};
}}

/* ─ List ───────────────────────────────────────────────── */
QListWidget {{
    background: {c['input']}; border: 1.5px solid {c['border']};
    border-radius: 14px; outline: none;
    color: {c['text_dim']}; font-weight: 700;
}}
QListWidget::item {{
    padding: 14px 18px; border-bottom: 1px solid {c['border']};
    color: {c['text_dim']};
}}
QListWidget::item:hover {{ background: {c['surface2']}; color: {c['text']}; }}
QListWidget::item:selected {{
    background: {c['primary']}20;
    color: {c['primary_h']};
    border-left: 3px solid {c['primary']};
}}

/* ─ Progress Bar ────────────────────────────────────────── */
QProgressBar {{
    background: {c['surface2']}; border: 1.5px solid {c['border']};
    border-radius: 12px; min-height: 22px; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {c['primary']}, stop:0.5 {c['accent']}, stop:1 {c['accent2']});
    border-radius: 10px;
}}

/* ─ Scrollbar ──────────────═════════════════════════ */
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{
    background: {c['border']}; border-radius: 4px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['primary']}80; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

# ══════════════════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════════════════
class DropZone(QFrame):
    files_dropped = Signal(list)
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True); self.setMinimumHeight(170); self.setObjectName("DropZone")
        ly = QVBoxLayout(self); ly.setAlignment(Qt.AlignCenter); ly.setSpacing(8)
        self.ico = QLabel(); self.ico.setAlignment(Qt.AlignCenter)
        self.txt = QLabel("Drag & Drop Video Files Here"); self.txt.setAlignment(Qt.AlignCenter)
        self.sub = QLabel("MP4 · MKV · MOV · AVI · WEBM · FLV  —  or click to browse")
        self.sub.setAlignment(Qt.AlignCenter)
        for w in [self.ico, self.txt, self.sub]: ly.addWidget(w)
        self._apply_idle()

    def _apply_idle(self):
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2.5px dashed {C['border']};
                border-radius: 20px;
                background: {C['surface']};
            }}
        """)
        self.ico.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary']).pixmap(52, 52))
        self.txt.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {C['text']}; background: transparent;")
        self.sub.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {C['text_muted']}; background: transparent;")

    def _apply_hover(self):
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2.5px dashed {C['primary']};
                border-radius: 20px;
                background: {C['primary']}0D;
            }}
        """)
        self.ico.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary_h']).pixmap(56, 56))
        self.txt.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {C['primary_h']}; background: transparent;")

    def refresh_theme(self): self._apply_idle()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction(); self._apply_hover()
    def dragLeaveEvent(self, e): self._apply_idle()
    def dropEvent(self, e):
        self._apply_idle()
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith(('.mp4','.mkv','.mov','.avi','.webm','.flv'))]
        if paths: self.files_dropped.emit(paths)
    def mousePressEvent(self, e): self.files_dropped.emit([])


class LogViewer(QTextEdit):
    LEVEL_STYLES = {
        "ERROR":   ("#F87171", "#F8717112"),
        "WARNING": ("#FBBF24", "#FBBF2410"),
        "SUCCESS": ("#4ADE80", "#4ADE8010"),
        "INFO":    ("#F0F4FF", None),
    }

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(8000)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C['log_bg']};
                border: 1.5px solid {C['border']};
                border-radius: 16px;
                font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
                font-size: 13px;
                padding: 20px;
                color: {C['text']};
                line-height: 1.6;
            }}
        """)

    def append_log(self, msg, level="INFO"):
        if isinstance(msg, tuple): msg = str(msg[0])
        ml = msg.lower()
        if   "error" in ml or "failed" in ml or "gagal" in ml: lvl = "ERROR"
        elif "warning" in ml or "timeout" in ml or "warn" in ml: lvl = "WARNING"
        elif ("success" in ml or "selesai" in ml or "berhasil" in ml
              or "✅" in msg or "completed" in ml): lvl = "SUCCESS"
        else: lvl = level

        text_color, bg_color = self.LEVEL_STYLES.get(lvl, (C['text'], None))

        # Override bg to match current theme in light mode
        if C['log_bg'] != "#07090F":
            lvl_bg = {
                "ERROR":   "#991B1B18",
                "WARNING": "#92400E15",
                "SUCCESS": "#15803D15",
            }.get(lvl, None)
            bg_color = lvl_bg

        ts      = datetime.datetime.now().strftime("%H:%M:%S")
        ts_html = f'<span style="color:{C["text_muted"]};font-weight:700;">[{ts}]</span>'

        badge_map = {
            "ERROR":   f'<span style="background:{C["error"]}30;color:{C["error"]};padding:1px 7px;border-radius:4px;font-size:11px;font-weight:900;"> ERR </span>',
            "WARNING": f'<span style="background:{C["warning"]}30;color:{C["warning"]};padding:1px 7px;border-radius:4px;font-size:11px;font-weight:900;"> WRN </span>',
            "SUCCESS": f'<span style="background:{C["success"]}30;color:{C["success"]};padding:1px 7px;border-radius:4px;font-size:11px;font-weight:900;"> OK </span>',
            "INFO":    f'<span style="background:{C["accent"]}25;color:{C["accent"]};padding:1px 7px;border-radius:4px;font-size:11px;font-weight:900;"> INF </span>',
        }
        badge = badge_map.get(lvl, badge_map["INFO"])

        row_bg = f'background:{bg_color};border-radius:6px;padding:2px 6px;' if bg_color else 'padding:2px 6px;'
        html = f'<div style="{row_bg}margin-bottom:2px;">{ts_html} {badge} <span style="color:{text_color};font-weight:600;">{msg}</span></div>'
        self.append(html)
        self.moveCursor(QTextCursor.End)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VER}")
        self.resize(1260, 880)
        self.config = self._load_config()
        self._theme = self.config.get("theme", "dark")
        self._apply_theme(self._theme)
        self._paths   = []
        self.processor= None
        self._running = False
        self._setup_ui()
        self._load_settings_to_ui()

    # ── Config ──────────────────────────────────────────────────
    def _load_config(self):
        d = {"relay_api_key":"","output_quality":"4k","output_dir":"",
             "headless":True,"max_workers":DEFAULT_WORKERS,
             "batch_stagger_delay":15,"initial_download_wait":120,
             "processing_hang_timeout":1800,"download_timeout":600,
             "a1d_url":"https://a1d.ai","theme":"dark"}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f: d.update(json.load(f))
            except: pass
        return d

    def _apply_theme(self, name):
        global C
        C.update(THEMES.get(name, THEMES["dark"]))
        self._theme = name; self.config["theme"] = name

    # ── UI Setup ──────────────────────────────────────────────
    def _setup_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        hl = QHBoxLayout(root); hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
        hl.addWidget(self._build_sidebar())
        self.stack = QStackedWidget(); self.stack.setObjectName("MainContent")
        self.stack.addWidget(self._build_dashboard())
        self.stack.addWidget(self._build_settings())
        self.stack.addWidget(self._build_logs())
        hl.addWidget(self.stack)
        self.nav_queue.setChecked(True)
        self._refresh_all()

    def _build_sidebar(self):
        sb = QWidget(); sb.setObjectName("Sidebar"); sb.setFixedWidth(270)
        ly = QVBoxLayout(sb); ly.setContentsMargins(22, 42, 22, 28); ly.setSpacing(6)

        # Brand block
        brand = QFrame(); brand.setObjectName("Card")
        brand.setStyleSheet(f"""QFrame#Card {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {C['primary']}30, stop:1 {C['accent']}18);
            border: 1px solid {C['primary']}40;
            border-radius: 16px; padding: 4px;
        }}""")
        bly = QVBoxLayout(brand); bly.setContentsMargins(18, 14, 18, 14)
        self.lbl_app = QLabel("A1D")
        self.lbl_ver = QLabel(f"Video Upscaler · v{APP_VER}")
        self.lbl_ver.setObjectName("SubLabel")
        ly.addWidget(brand); bly.addWidget(self.lbl_app); bly.addWidget(self.lbl_ver)

        ly.addSpacing(28)

        # Nav buttons
        self.nav_queue    = self._nav_btn("Dashboard",    "fa5s.layer-group", 0)
        self.nav_settings = self._nav_btn("Settings",     "fa5s.sliders-h",  1)
        self.nav_logs     = self._nav_btn("System Logs",  "fa5s.terminal",   2)
        for b in [self.nav_queue, self.nav_settings, self.nav_logs]: ly.addWidget(b)

        ly.addStretch()

        # Theme toggle
        self.btn_theme = QPushButton(); self.btn_theme.setObjectName("GhostBtn")
        self.btn_theme.setMinimumHeight(42); self.btn_theme.clicked.connect(self._toggle_theme)
        ly.addWidget(self.btn_theme)
        ly.addSpacing(14)

        # Status pill
        status_row = QHBoxLayout(); status_row.setSpacing(10)
        self.dot_status = QLabel("●")
        self.lbl_status = QLabel("SYSTEM IDLE")
        self.lbl_status.setObjectName("SubLabel")
        status_row.addWidget(self.dot_status); status_row.addWidget(self.lbl_status)
        status_row.addStretch(); ly.addLayout(status_row)
        return sb

    def _nav_btn(self, text, icon, page):
        b = QToolButton(); b.setText(f"  {text}")
        b.setIconSize(QSize(20, 20)); b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setCheckable(True); b.setAutoExclusive(True)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setObjectName("NavBtn"); b.setMinimumHeight(50)
        b.clicked.connect(lambda _, i=page: self.stack.setCurrentIndex(i))
        b.clicked.connect(self._refresh_nav_icons)
        return b

    def _build_dashboard(self):
        page = QWidget(); ly = QVBoxLayout(page)
        ly.setContentsMargins(48, 48, 48, 48); ly.setSpacing(24)

        # Header row
        hdr = QHBoxLayout()
        vb  = QVBoxLayout()
        t = QLabel("Upscale Manager"); t.setObjectName("PageTitle")
        s = QLabel("Add video files, configure quality, then launch the batch engine.")
        s.setObjectName("SubLabel")
        vb.addWidget(t); vb.addWidget(s); hdr.addLayout(vb); hdr.addStretch()
        self.badge_count = QLabel("0 FILES QUEUED")
        self.badge_count.setObjectName("BadgeLabel")
        hdr.addWidget(self.badge_count, alignment=Qt.AlignVCenter)
        ly.addLayout(hdr)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        ly.addWidget(self.drop_zone)

        # File list
        self.file_list = QListWidget(); self.file_list.setMinimumHeight(140)
        ly.addWidget(self.file_list, stretch=1)

        # Bottom controls
        ctrl = QHBoxLayout(); ctrl.setSpacing(12)
        b_add = QPushButton("  Add Videos"); b_add.setObjectName("GhostBtn")
        b_add.setIcon(qta.icon("fa5s.plus", color=C['accent'])); b_add.setMinimumHeight(44)
        b_add.clicked.connect(self._browse_files)
        b_del = QPushButton("  Remove Selected"); b_del.setObjectName("GhostBtn")
        b_del.setIcon(qta.icon("fa5s.minus", color=C['error'])); b_del.setMinimumHeight(44)
        b_del.clicked.connect(self._remove_selected)
        b_clr = QPushButton("  Clear All"); b_clr.setObjectName("DangerBtn")
        b_clr.setIcon(qta.icon("fa5s.trash", color=C['error'])); b_clr.setMinimumHeight(44)
        b_clr.clicked.connect(self._clear_files)
        ctrl.addWidget(b_add); ctrl.addWidget(b_del); ctrl.addWidget(b_clr); ctrl.addStretch()
        self.btn_start = QPushButton("  RUN UPSCALER"); self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setIcon(qta.icon("fa5s.rocket", color="#FFF")); self.btn_start.setMinimumSize(240, 54)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel = QPushButton("  FORCE STOP"); self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setIcon(qta.icon("fa5s.stop", color=C['error'])); self.btn_cancel.setMinimumSize(160, 54)
        self.btn_cancel.hide(); self.btn_cancel.clicked.connect(self._cancel)
        ctrl.addWidget(self.btn_start); ctrl.addWidget(self.btn_cancel)
        ly.addLayout(ctrl)

        # Progress card
        self.prog_card = QFrame(); self.prog_card.setObjectName("AccentCard")
        self.prog_card.hide()
        pl = QVBoxLayout(self.prog_card); pl.setContentsMargins(22, 18, 22, 18); pl.setSpacing(10)
        ph = QHBoxLayout()
        self.prog_icon = QLabel(); self.prog_icon.setPixmap(qta.icon("fa5s.cog", color=C['primary']).pixmap(20,20))
        self.prog_lbl  = QLabel("Initializing engine...")
        self.prog_lbl.setStyleSheet(f"color: {C['text']}; font-weight: 700; font-size: 14px;")
        ph.addWidget(self.prog_icon); ph.addWidget(self.prog_lbl); ph.addStretch()
        self.prog_pct = QLabel("0%")
        self.prog_pct.setStyleSheet(f"color: {C['primary']}; font-weight: 900; font-size: 16px;")
        ph.addWidget(self.prog_pct); pl.addLayout(ph)
        self.pbar = QProgressBar(); pl.addWidget(self.pbar)
        ly.addWidget(self.prog_card)
        return page

    def _build_settings(self):
        page = QWidget(); scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); ly = QVBoxLayout(content)
        ly.setContentsMargins(48, 48, 48, 48); ly.setSpacing(28)

        t = QLabel("Advanced Configuration"); t.setObjectName("PageTitle"); ly.addWidget(t)
        s = QLabel("All settings are persisted automatically to config.json")
        s.setObjectName("SubLabel"); ly.addWidget(s)

        def section(label, icon_name, card_type="AccentCard"):
            f = QFrame(); f.setObjectName(card_type)
            fl = QVBoxLayout(f); fl.setContentsMargins(26, 22, 26, 22); fl.setSpacing(18)
            hh = QHBoxLayout(); hh.setSpacing(12)
            ic = QLabel(); ic.setPixmap(qta.icon(icon_name, color=C['primary']).pixmap(22,22))
            tl = QLabel(label); tl.setObjectName("SectionTitle")
            hh.addWidget(ic); hh.addWidget(tl); hh.addStretch(); fl.addLayout(hh)
            sep = QFrame(); sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"background: {C['border']}; max-height: 1px; margin: 0px 0px 4px 0px;")
            fl.addWidget(sep)
            form = QFormLayout(); form.setSpacing(16); form.setLabelAlignment(Qt.AlignRight)
            fl.addLayout(form)
            return f, form

        def row_label(text, hint=""):
            w = QWidget(); ly2 = QVBoxLayout(w); ly2.setContentsMargins(0,0,12,0); ly2.setSpacing(2)
            l = QLabel(text); l.setStyleSheet(f"color: {C['text']}; font-weight: 700; font-size: 13px;")
            ly2.addWidget(l)
            if hint:
                h = QLabel(hint); h.setObjectName("HintLabel"); ly2.addWidget(h)
            return w

        # Section 1 — Auth
        g1, f1 = section("Authentication & API", "fa5s.key")
        self.i_api = QLineEdit(); self.i_api.setEchoMode(QLineEdit.Password)
        self.i_api.setPlaceholderText("Paste your Firefox Relay API key here")
        self.i_url = QLineEdit(); self.i_url.setPlaceholderText("https://a1d.ai")
        # Show/hide key button
        key_row = QHBoxLayout(); self.btn_show = QPushButton()
        self.btn_show.setObjectName("GhostBtn")
        self.btn_show.setIcon(qta.icon("fa5s.eye", color=C['text_muted']))
        self.btn_show.setFixedSize(44, 44)
        self.btn_show.setCheckable(True)
        self.btn_show.toggled.connect(lambda on: (
            self.i_api.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password),
            self.btn_show.setIcon(qta.icon("fa5s.eye-slash" if on else "fa5s.eye", color=C['accent']))
        ))
        key_row.addWidget(self.i_api); key_row.addWidget(self.btn_show)
        f1.addRow(row_label("Firefox Relay Key", "Required for temporary email masking"), key_row)
        f1.addRow(row_label("Service URL", "Override if A1D changes their domain"), self.i_url)
        ly.addWidget(g1)

        # Section 2 — Output
        g2, f2 = section("Output & Quality", "fa5s.film", "SuccessCard")
        self.c_qual = QComboBox(); self.c_qual.addItems(["4k", "2k", "1080p"])
        self.c_qual.setMinimumHeight(44)
        self.i_out = QLineEdit(); self.i_out.setPlaceholderText("Leave empty to save next to source file")
        b_brw = QPushButton(); b_brw.setObjectName("GhostBtn")
        b_brw.setIcon(qta.icon("fa5s.folder-open", color=C['accent']))
        b_brw.setFixedSize(44, 44); b_brw.clicked.connect(self._browse_output)
        out_row = QHBoxLayout(); out_row.addWidget(self.i_out); out_row.addWidget(b_brw)
        self.s_wait = QSpinBox(); self.s_wait.setRange(0, 600); self.s_wait.setSuffix(" sec")
        self.s_wait.setMinimumHeight(44)
        f2.addRow(row_label("Target Resolution", "Upscale target: 4K / 2K / 1080p"), self.c_qual)
        f2.addRow(row_label("Output Directory", "Where to save finished videos"), out_row)
        f2.addRow(row_label("Initial Render Wait", "Wait before checking download button (longer = safer)"), self.s_wait)
        ly.addWidget(g2)

        # Section 3 — Performance
        g3, f3 = section("Performance & Reliability", "fa5s.microchip", "WarnCard")
        self.s_work = QSpinBox(); self.s_work.setRange(1, MAX_PARALLEL_LIMIT); self.s_work.setMinimumHeight(44)
        self.s_stagger = QSpinBox(); self.s_stagger.setRange(0, 120); self.s_stagger.setSuffix(" sec"); self.s_stagger.setMinimumHeight(44)
        self.s_dl_to = QSpinBox(); self.s_dl_to.setRange(60, 3600); self.s_dl_to.setSuffix(" sec"); self.s_dl_to.setMinimumHeight(44)
        self.s_hang = QSpinBox(); self.s_hang.setRange(300, 7200); self.s_hang.setSuffix(" sec"); self.s_hang.setMinimumHeight(44)
        self.chk_h = QCheckBox("Headless Browser  (run Chromium silently in background)")
        self.btn_rst = QPushButton("  Force Reset — Kill Workers & Clear Temp Files")
        self.btn_rst.setObjectName("WarnBtn")
        self.btn_rst.setIcon(qta.icon("fa5s.sync-alt", color=C['warning']))
        self.btn_rst.setMinimumHeight(48); self.btn_rst.clicked.connect(self._force_reset)
        f3.addRow(row_label("Max Parallel Workers", f"Maximum: {MAX_PARALLEL_LIMIT} simultaneous workers"), self.s_work)
        f3.addRow(row_label("Stagger Delay", "Seconds between launching each worker"), self.s_stagger)
        f3.addRow(row_label("Download Timeout", "Max wait for download to start"), self.s_dl_to)
        f3.addRow(row_label("Process Hang Timeout", "Kill worker if total time exceeds this"), self.s_hang)
        f3.addRow("", self.chk_h); f3.addRow("", self.btn_rst)
        ly.addWidget(g3)

        btn_sv = QPushButton("  SAVE ALL SETTINGS"); btn_sv.setObjectName("PrimaryBtn")
        btn_sv.setIcon(qta.icon("fa5s.save", color="#FFF")); btn_sv.setMinimumHeight(58)
        btn_sv.clicked.connect(self._save_config); ly.addWidget(btn_sv)
        ly.addStretch()
        scroll.setWidget(content); return scroll

    def _build_logs(self):
        page = QWidget(); ly = QVBoxLayout(page)
        ly.setContentsMargins(48, 48, 48, 48); ly.setSpacing(24)
        hdr = QHBoxLayout()
        t = QLabel("System Logs"); t.setObjectName("PageTitle"); hdr.addWidget(t); hdr.addStretch()
        b_exp = QPushButton("  Export Logs"); b_exp.setObjectName("GhostBtn")
        b_exp.setIcon(qta.icon("fa5s.download", color=C['accent'])); b_exp.clicked.connect(self._export_logs)
        b_clr = QPushButton("  Clear"); b_clr.setObjectName("DangerBtn")
        b_clr.setIcon(qta.icon("fa5s.eraser", color=C['error'])); b_clr.clicked.connect(self.log_viewer.clear)
        hdr.addWidget(b_exp); hdr.addWidget(b_clr); ly.addLayout(hdr)
        # Legend bar
        leg = QHBoxLayout(); leg.setSpacing(16)
        for label, col in [("INFO", C['accent']), ("SUCCESS", C['success']), ("WARNING", C['warning']), ("ERROR", C['error'])]:
            dot = QLabel(f"●  {label}")
            dot.setStyleSheet(f"color: {col}; font-size: 12px; font-weight: 800;")
            leg.addWidget(dot)
        leg.addStretch(); ly.addLayout(leg)
        self.log_viewer = LogViewer()
        ly.addWidget(self.log_viewer); return page

    # ── Theme ──────────────────────────────────────────────
    def _toggle_theme(self):
        new = "light" if self._theme == "dark" else "dark"
        self._apply_theme(new)
        QApplication.instance().setStyleSheet(build_stylesheet(C))
        self._refresh_all()
        self._save_config(silent=True)

    def _refresh_all(self):
        self.lbl_app.setStyleSheet(f"font-size: 32px; font-weight: 1000; color: {C['primary_h']};")
        self.lbl_ver.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {C['text_muted']};")
        ico = "fa5s.sun" if self._theme == "dark" else "fa5s.moon"
        lbl = "  Light Mode" if self._theme == "dark" else "  Dark Mode"
        self.btn_theme.setIcon(qta.icon(ico, color=C['accent'])); self.btn_theme.setText(lbl)
        self.badge_count.setStyleSheet(
            f"background: {C['primary']}28; color: {C['primary_h']}; font-weight: 900; "
            f"font-size: 12px; padding: 6px 16px; border-radius: 20px; border: 1px solid {C['primary']}50;"
        )
        self.drop_zone.refresh_theme()
        if hasattr(self, 'log_viewer'): self.log_viewer.refresh_theme()
        self._refresh_nav_icons()
        self._set_running(self._running)

    def _refresh_nav_icons(self):
        for btn, icon in [(self.nav_queue,"fa5s.layer-group"),(self.nav_settings,"fa5s.sliders-h"),(self.nav_logs,"fa5s.terminal")]:
            btn.setIcon(qta.icon(icon, color=C['primary_h'] if btn.isChecked() else C['text_muted']))

    # ── Business Logic ───────────────────────────────────────
    def _load_settings_to_ui(self):
        c = self.config
        self.i_api.setText(c.get("relay_api_key",""))
        self.i_url.setText(c.get("a1d_url","https://a1d.ai"))
        self.c_qual.setCurrentText(c.get("output_quality","4k"))
        self.i_out.setText(c.get("output_dir",""))
        self.s_work.setValue(c.get("max_workers",DEFAULT_WORKERS))
        self.s_stagger.setValue(c.get("batch_stagger_delay",15))
        self.s_wait.setValue(c.get("initial_download_wait",120))
        self.s_dl_to.setValue(c.get("download_timeout",600))
        self.s_hang.setValue(c.get("processing_hang_timeout",1800))
        self.chk_h.setChecked(c.get("headless",True))

    def _save_config(self, silent=False):
        self.config.update({
            "relay_api_key":          self.i_api.text().strip(),
            "a1d_url":                self.i_url.text().strip(),
            "output_quality":         self.c_qual.currentText(),
            "output_dir":             self.i_out.text().strip(),
            "max_workers":            self.s_work.value(),
            "batch_stagger_delay":    self.s_stagger.value(),
            "initial_download_wait":  self.s_wait.value(),
            "download_timeout":       self.s_dl_to.value(),
            "processing_hang_timeout":self.s_hang.value(),
            "headless":               self.chk_h.isChecked(),
            "theme":                  self._theme,
        })
        try:
            with open(CONFIG_PATH,"w",encoding="utf-8") as f: json.dump(self.config,f,indent=2)
            if not silent: self._log("All settings saved to config.json","SUCCESS")
        except Exception as e: self._log(f"Cannot save config: {e}","ERROR")

    def _force_reset(self):
        if QMessageBox.question(self,"Force Reset","Stop all workers and clear temp folder?",
                                QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes: return
        self._cancel()
        tmp = os.path.join(_PROJECT_ROOT,"temp")
        if os.path.exists(tmp): shutil.rmtree(tmp, ignore_errors=True)
        dbg = os.path.join(_PROJECT_ROOT,"debug")
        if os.path.exists(dbg): shutil.rmtree(dbg, ignore_errors=True)
        self._log("Force reset complete — workers terminated, temp files cleared.","WARNING")

    def _export_logs(self):
        path, _ = QFileDialog.getSaveFileName(self,"Export Logs",
                  os.path.join(os.path.expanduser("~"),f"a1d_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"),
                  "Text (*.txt)")
        if path:
            try:
                with open(path,"w",encoding="utf-8") as f: f.write(self.log_viewer.toPlainText())
                self._log(f"Logs exported → {path}","SUCCESS")
            except Exception as e: self._log(f"Export failed: {e}","ERROR")

    def _log(self, m, l="INFO"):
        if hasattr(self,"log_viewer"): self.log_viewer.append_log(m, l)

    def _on_drop(self, ps):
        if not ps: self._browse_files()
        else: self._add_files(ps)

    def _browse_files(self):
        fs,_ = QFileDialog.getOpenFileNames(self,"Select Videos","",
               "Videos (*.mp4 *.mkv *.mov *.avi *.webm *.flv)")
        self._add_files(fs)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self,"Output Folder")
        if d: self.i_out.setText(d)

    def _add_files(self, ps):
        added = 0
        for p in ps:
            if p and p not in self._paths:
                self._paths.append(p); added += 1
                it = QListWidgetItem(f"  {os.path.basename(p)}")
                it.setIcon(qta.icon("fa5s.film", color=C['primary']))
                it.setToolTip(p); self.file_list.addItem(it)
        if added: self._update_badge()

    def _remove_selected(self):
        for it in self.file_list.selectedItems():
            row = self.file_list.row(it)
            self.file_list.takeItem(row)
            if row < len(self._paths): self._paths.pop(row)
        self._update_badge()

    def _clear_files(self):
        self._paths.clear(); self.file_list.clear(); self._update_badge()

    def _update_badge(self):
        n = len(self._paths)
        self.badge_count.setText(f"{n} FILE{'S' if n != 1 else ''} QUEUED")

    def _start(self):
        if not self._paths:
            return self._log("Queue is empty. Please add video files.","WARNING")
        if not self.i_api.text().strip():
            self._log("Firefox Relay API Key is required. Go to Settings.","ERROR")
            return self.nav_settings.click()
        self._save_config(silent=True); self._set_running(True); cfg = dict(self.config)
        self._log("-" * 50)
        self._log(f"BATCH ENGINE STARTING  —  {len(self._paths)} file(s), {cfg['output_quality'].upper()} mode","SUCCESS")
        self._log(f"Workers: {cfg['max_workers']}  |  Stagger: {cfg['batch_stagger_delay']}s  |  Headless: {cfg['headless']}")
        self._log("-" * 50)
        if len(self._paths) == 1:
            self.processor = A1DProcessor(_PROJECT_ROOT, self._paths[0], cfg)
        else:
            self.processor = BatchProcessor(_PROJECT_ROOT, self._paths, cfg)
        self.processor.log_signal.connect(self._log)
        self.processor.progress_signal.connect(self._on_progress)
        self.processor.finished_signal.connect(lambda ok, m, _: self._on_finished(ok, m))
        self.processor.start()

    def _set_running(self, r):
        self._running = r
        self.btn_start.setVisible(not r); self.btn_cancel.setVisible(r)
        self.prog_card.setVisible(r)
        color = C['success'] if r else C['text_muted']
        self.dot_status.setStyleSheet(f"color: {color}; font-size: 20px;")
        self.lbl_status.setText("PROCESSING" if r else "SYSTEM IDLE")
        self.lbl_status.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 800; letter-spacing: 1px;")

    def _on_progress(self, pct, msg):
        self.pbar.setValue(pct)
        self.prog_lbl.setText(msg)
        self.prog_pct.setText(f"{pct}%")

    def _on_finished(self, ok, msg):
        self._set_running(False)
        self.prog_lbl.setText("Batch completed." if ok else "Process failed or cancelled.")
        self.prog_pct.setText("100%" if ok else "--")
        self._log(f"{'DONE: ' if ok else 'FAILED: '}{msg}", "SUCCESS" if ok else "ERROR")

    def _cancel(self):
        if self.processor: self.processor.cancel()
        self._log("Force stop requested — terminating all workers.","ERROR")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    font = QFont("Inter", 10); font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    app.setStyleSheet(build_stylesheet(C))
    w = MainWindow(); w.show()
    sys.exit(app.exec())
