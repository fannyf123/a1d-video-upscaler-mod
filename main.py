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
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS, DEFAULT_MAX_RETRIES
from App.ffmpeg_postprocessor import PRESET_LABELS, PRESET_KEYS

CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
APP_NAME    = "A1D Video Upscaler"
APP_VER     = "2.7.0"

# ══════════════════════════════════════════════════════════════════════════════
#  COLOUR SYSTEM  —  GitHub-style palette
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        "bg":         "#0d1117",
        "sidebar":    "#161b22",
        "surface":    "#161b22",
        "surface2":   "#21262d",
        "input":      "#0d1117",
        "border":     "#30363d",
        "primary":    "#1f6feb",
        "primary_h":  "#58a6ff",
        "accent":     "#58a6ff",
        "accent2":    "#3fb950",
        "text":       "#e6edf3",
        "text_dim":   "#c9d1d9",
        "text_muted": "#8b949e",
        "success":    "#3fb950",
        "warning":    "#e3b341",
        "error":      "#f85149",
        "log_bg":     "#010409",
    },
    "light": {
        "bg":         "#ffffff",
        "sidebar":    "#f6f8fa",
        "surface":    "#ffffff",
        "surface2":   "#f6f8fa",
        "input":      "#f6f8fa",
        "border":     "#d0d7de",
        "primary":    "#0969da",
        "primary_h":  "#0550ae",
        "accent":     "#0969da",
        "accent2":    "#1a7f37",
        "text":       "#1f2328",
        "text_dim":   "#24292f",
        "text_muted": "#636c76",
        "success":    "#1a7f37",
        "warning":    "#9a6700",
        "error":      "#cf222e",
        "log_bg":     "#f6f8fa",
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

QLabel {{ color: {c['text_dim']}; font-size: 10pt; font-weight: 600; }}
QLabel#PageTitle {{
    color: {c['text']}; font-size: 21pt; font-weight: 900; letter-spacing: -0.5px;
}}
QLabel#SectionTitle {{
    color: {c['text']}; font-size: 12pt; font-weight: 800;
}}
QLabel#SubLabel {{
    color: {c['text_muted']}; font-size: 9pt; font-weight: 600;
}}
QLabel#HintLabel {{
    color: {c['text_muted']}; font-size: 8pt; font-style: italic; font-weight: 500;
}}
QLabel#BadgeLabel {{
    background: {c['primary']}30;
    color: {c['primary_h']};
    font-size: 9pt; font-weight: 900;
    padding: 5px 14px; border-radius: 20px;
    border: 1px solid {c['primary']}50;
}}

QFrame#Card {{
    background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px;
}}
QFrame#AccentCard {{
    background: {c['surface']}; border: 1px solid {c['border']};
    border-left: 4px solid {c['primary']}; border-radius: 6px;
}}
QFrame#SuccessCard {{
    background: {c['surface']}; border: 1px solid {c['border']};
    border-left: 4px solid {c['success']}; border-radius: 6px;
}}
QFrame#WarnCard {{
    background: {c['surface']}; border: 1px solid {c['border']};
    border-left: 4px solid {c['warning']}; border-radius: 6px;
}}

QPushButton {{
    background: {c['surface2']}; border: 1px solid {c['border']};
    border-radius: 6px; padding: 8px 18px;
    font-weight: 700; font-size: 10pt; color: {c['text']};
}}
QPushButton:hover  {{ background: {c['border']}; border-color: {c['primary']}; color: {c['text']}; }}
QPushButton:pressed{{ background: {c['bg']}; }}
QPushButton#PrimaryBtn {{
    background: {c['primary']};
    border: 1px solid {c['primary']};
    color: #ffffff; font-size: 11pt; font-weight: 700; padding: 12px 28px;
    border-radius: 6px;
}}
QPushButton#PrimaryBtn:hover {{
    background: {c['primary_h']};
    border-color: {c['primary_h']};
}}
QPushButton#DangerBtn {{
    background: {c['error']}18; border: 1px solid {c['error']}80;
    color: {c['error']}; font-weight: 700; border-radius: 6px;
}}
QPushButton#DangerBtn:hover {{ background: {c['error']}; color: #ffffff; }}
QPushButton#WarnBtn {{
    background: {c['warning']}18; border: 1px solid {c['warning']}80;
    color: {c['warning']}; font-weight: 700; border-radius: 6px;
}}
QPushButton#WarnBtn:hover {{ background: {c['warning']}; color: #0d1117; }}
QPushButton#GhostBtn {{
    background: transparent; border: 1px solid {c['border']};
    color: {c['text_dim']}; font-weight: 600; border-radius: 6px;
}}
QPushButton#GhostBtn:hover {{ border-color: {c['primary']}; color: {c['primary_h']}; background: {c['primary']}10; }}

QToolButton#NavBtn {{
    background: transparent; border: none; border-radius: 6px;
    padding: 12px 16px; font-size: 10pt; font-weight: 600;
    text-align: left; color: {c['text_muted']};
}}
QToolButton#NavBtn:hover {{ background: {c['surface2']}; color: {c['text']}; }}
QToolButton#NavBtn:checked {{
    background: {c['primary']}1A;
    color: {c['primary_h']}; font-weight: 700;
    border-left: 3px solid {c['primary']};
}}

QLineEdit, QComboBox, QSpinBox {{
    background: {c['input']}; border: 1px solid {c['border']};
    border-radius: 6px; padding: 9px 14px; min-height: 22px;
    color: {c['text']}; font-weight: 600; font-size: 10pt;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {c['primary']}; outline: 2px solid {c['primary']}40;
    background: {c['surface']};
}}
QLineEdit::placeholder {{ color: {c['text_muted']}; font-weight: 400; }}
QComboBox QAbstractItemView {{
    background: {c['surface2']}; border: 1px solid {c['border']};
    color: {c['text']}; selection-background-color: {c['primary']}40;
}}

QCheckBox {{ color: {c['text_dim']}; spacing: 10px; font-weight: 600; font-size: 10pt; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border: 1px solid {c['border']};
    border-radius: 4px; background: {c['input']};
}}
QCheckBox::indicator:hover {{ border-color: {c['primary']}; }}
QCheckBox::indicator:checked {{
    background: {c['primary']};
    border-color: {c['primary']};
}}

QListWidget {{
    background: {c['input']}; border: 1px solid {c['border']};
    border-radius: 6px; outline: none; color: {c['text_dim']}; font-weight: 600;
}}
QListWidget::item {{
    padding: 12px 16px; border-bottom: 1px solid {c['border']}; color: {c['text_dim']};
}}
QListWidget::item:hover {{ background: {c['surface2']}; color: {c['text']}; }}
QListWidget::item:selected {{
    background: {c['primary']}18; color: {c['primary_h']};
    border-left: 3px solid {c['primary']};
}}

QProgressBar {{
    background: {c['surface2']}; border: 1px solid {c['border']};
    border-radius: 6px; min-height: 10px; color: transparent;
}}
QProgressBar::chunk {{
    background: {c['primary']};
    border-radius: 5px;
}}

QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{
    background: {c['border']}; border-radius: 4px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
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
                border: 2px dashed {C['border']};
                border-radius: 6px;
                background: {C['surface']};
            }}
        """)
        self.ico.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary']).pixmap(52, 52))
        self.txt.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {C['text']}; background: transparent;")
        self.sub.setStyleSheet(f"font-size: 9pt; font-weight: 400; color: {C['text_muted']}; background: transparent;")

    def _apply_hover(self):
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2px dashed {C['primary']};
                border-radius: 6px;
                background: {C['primary']}0D;
            }}
        """)
        self.ico.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary_h']).pixmap(56, 56))
        self.txt.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {C['primary_h']}; background: transparent;")

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
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(8000)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C['log_bg']};
                border: 1px solid {C['border']};
                border-radius: 6px;
                font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
                font-size: 10pt;
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

        colours = {
            "ERROR":   (C['error'],   f"{C['error']}12"),
            "WARNING": (C['warning'], f"{C['warning']}10"),
            "SUCCESS": (C['success'], f"{C['success']}10"),
            "INFO":    (C['text'],    None),
        }
        text_color, bg_color = colours.get(lvl, (C['text'], None))

        ts      = datetime.datetime.now().strftime("%H:%M:%S")
        ts_html = f'<span style="color:{C["text_muted"]};font-weight:600;">[{ts}]</span>'

        badge_styles = {
            "ERROR":   f'background:{C["error"]}35;color:{C["error"]};',
            "WARNING": f'background:{C["warning"]}35;color:{C["warning"]};',
            "SUCCESS": f'background:{C["success"]}35;color:{C["success"]};',
            "INFO":    f'background:{C["accent"]}30;color:{C["accent"]};',
        }
        badge_labels = {"ERROR":" ERR ","WARNING":" WRN ","SUCCESS":" OK ","INFO":" INF "}
        bs  = badge_styles.get(lvl, badge_styles["INFO"])
        bl  = badge_labels.get(lvl, " INF ")
        badge = f'<span style="{bs}padding:1px 7px;border-radius:4px;font-size:8pt;font-weight:700;">{bl}</span>'

        row_style = f"background:{bg_color};border-radius:4px;padding:2px 6px;" if bg_color else "padding:2px 6px;"
        html = (f'<div style="{row_style}margin-bottom:2px;">'
                f'{ts_html} {badge} '
                f'<span style="color:{text_color};font-weight:500;">{msg}</span>'
                f'</div>')
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
        self.config   = self._load_config()
        self._theme   = self.config.get("theme", "dark")
        self._apply_theme(self._theme)
        self._paths   = []
        self.processor= None
        self._running = False
        self._setup_ui()
        self._load_settings_to_ui()

    # ── Config ───────────────────────────────────────────────────────────────────────
    def _load_config(self):
        # ─ Defaults ────────────────────────────────────────────────────────────
        d = {
            "output_quality":          "4k",
            "output_dir":              "",
            "headless":                True,
            "max_workers":             DEFAULT_WORKERS,
            "batch_stagger_delay":     15,
            "initial_download_wait":   120,
            "processing_hang_timeout": 1800,
            "download_timeout":        600,
            "a1d_url":                 "https://a1d.ai",
            "theme":                   "dark",
            "max_retries":             DEFAULT_MAX_RETRIES,
            "ffmpeg": {
                "enabled":          True,
                "preset_name":      "adobe_stock_4k_h264",
                "mute_audio":       True,
                "replace_original": True,
                "crf":              18,
                "encode_preset":    "slow",
                "timeout":          7200,
                "video_codec":      "libx264",
                "pix_fmt":          "yuv420p",
                "scale":            "3840:2160",
                "audio_codec":      "aac",
                "audio_rate":       "48000",
                "audio_bitrate":    "320k",
                "extra_args":       "-movflags +faststart",
            },
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    loaded = json.load(f)
                # Merge ffmpeg sub-dict agar tidak tertimpa seluruhnya
                if "ffmpeg" in loaded:
                    d["ffmpeg"].update(loaded.pop("ffmpeg"))
                d.update(loaded)
            except Exception:
                pass
        return d

    def _apply_theme(self, name):
        global C
        C.update(THEMES.get(name, THEMES["dark"]))
        self._theme = name; self.config["theme"] = name

    # ── UI Scaffold ───────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        hl = QHBoxLayout(root); hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
        hl.addWidget(self._build_sidebar())
        self.stack = QStackedWidget(); self.stack.setObjectName("MainContent")
        self.stack.addWidget(self._build_dashboard())   # 0
        self.stack.addWidget(self._build_settings())    # 1
        self.stack.addWidget(self._build_logs())        # 2
        hl.addWidget(self.stack)
        self.nav_queue.setChecked(True)
        self._refresh_all()

    # ── Sidebar ──────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = QWidget(); sb.setObjectName("Sidebar"); sb.setFixedWidth(260)
        ly = QVBoxLayout(sb); ly.setContentsMargins(16, 32, 16, 24); ly.setSpacing(4)

        brand = QFrame(); brand.setObjectName("Card")
        brand.setStyleSheet(f"""QFrame#Card {{
            background: {C['surface2']};
            border: 1px solid {C['border']}; border-radius: 6px;
        }}""")
        bly = QVBoxLayout(brand); bly.setContentsMargins(16, 12, 16, 12)
        self.lbl_app = QLabel("A1D")
        self.lbl_ver = QLabel(f"Video Upscaler · v{APP_VER}"); self.lbl_ver.setObjectName("SubLabel")
        bly.addWidget(self.lbl_app); bly.addWidget(self.lbl_ver)
        ly.addWidget(brand); ly.addSpacing(20)

        self.nav_queue    = self._nav_btn("Dashboard",   "fa5s.layer-group", 0)
        self.nav_settings = self._nav_btn("Settings",    "fa5s.sliders-h",  1)
        self.nav_logs     = self._nav_btn("System Logs", "fa5s.terminal",   2)
        for b in [self.nav_queue, self.nav_settings, self.nav_logs]: ly.addWidget(b)
        ly.addStretch()

        self.btn_theme = QPushButton(); self.btn_theme.setObjectName("GhostBtn")
        self.btn_theme.setMinimumHeight(38); self.btn_theme.clicked.connect(self._toggle_theme)
        ly.addWidget(self.btn_theme); ly.addSpacing(12)

        sr = QHBoxLayout(); sr.setSpacing(8)
        self.dot_status = QLabel("●")
        self.lbl_status = QLabel("SYSTEM IDLE"); self.lbl_status.setObjectName("SubLabel")
        sr.addWidget(self.dot_status); sr.addWidget(self.lbl_status); sr.addStretch()
        ly.addLayout(sr)
        return sb

    def _nav_btn(self, text, icon, page):
        b = QToolButton(); b.setText(f"  {text}")
        b.setIconSize(QSize(18, 18)); b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setCheckable(True); b.setAutoExclusive(True)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setObjectName("NavBtn"); b.setMinimumHeight(44)
        b.clicked.connect(lambda _, i=page: self.stack.setCurrentIndex(i))
        b.clicked.connect(self._refresh_nav_icons)
        return b

    # ── Dashboard ────────────────────────────────────────────────────────────────
    def _build_dashboard(self):
        page = QWidget(); ly = QVBoxLayout(page)
        ly.setContentsMargins(40, 40, 40, 40); ly.setSpacing(20)

        hdr = QHBoxLayout()
        vb  = QVBoxLayout()
        t = QLabel("Upscale Manager"); t.setObjectName("PageTitle")
        s = QLabel("Queue your videos then launch the batch AI engine."); s.setObjectName("SubLabel")
        vb.addWidget(t); vb.addWidget(s); hdr.addLayout(vb); hdr.addStretch()
        self.badge_count = QLabel("0 FILES QUEUED"); self.badge_count.setObjectName("BadgeLabel")
        hdr.addWidget(self.badge_count, alignment=Qt.AlignVCenter)
        ly.addLayout(hdr)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        ly.addWidget(self.drop_zone)

        self.file_list = QListWidget(); self.file_list.setMinimumHeight(140)
        ly.addWidget(self.file_list, stretch=1)

        ctrl = QHBoxLayout(); ctrl.setSpacing(10)
        b_add = QPushButton("  Add Videos"); b_add.setObjectName("GhostBtn")
        b_add.setIcon(qta.icon("fa5s.plus", color=C['accent'])); b_add.setMinimumHeight(40)
        b_add.clicked.connect(self._browse_files)
        b_del = QPushButton("  Remove Selected"); b_del.setObjectName("GhostBtn")
        b_del.setIcon(qta.icon("fa5s.minus", color=C['error'])); b_del.setMinimumHeight(40)
        b_del.clicked.connect(self._remove_selected)
        b_clr = QPushButton("  Clear All"); b_clr.setObjectName("DangerBtn")
        b_clr.setIcon(qta.icon("fa5s.trash", color=C['error'])); b_clr.setMinimumHeight(40)
        b_clr.clicked.connect(self._clear_files)
        ctrl.addWidget(b_add); ctrl.addWidget(b_del); ctrl.addWidget(b_clr); ctrl.addStretch()

        self.btn_start = QPushButton("  RUN UPSCALER"); self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setIcon(qta.icon("fa5s.rocket", color="#FFF")); self.btn_start.setMinimumSize(220, 48)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel = QPushButton("  FORCE STOP"); self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setIcon(qta.icon("fa5s.stop", color=C['error'])); self.btn_cancel.setMinimumSize(150, 48)
        self.btn_cancel.hide(); self.btn_cancel.clicked.connect(self._cancel)
        ctrl.addWidget(self.btn_start); ctrl.addWidget(self.btn_cancel)
        ly.addLayout(ctrl)

        self.prog_card = QFrame(); self.prog_card.setObjectName("AccentCard"); self.prog_card.hide()
        pl = QVBoxLayout(self.prog_card); pl.setContentsMargins(20, 16, 20, 16); pl.setSpacing(8)
        ph = QHBoxLayout()
        self.prog_lbl = QLabel("Initializing engine...")
        self.prog_lbl.setStyleSheet(f"color:{C['text']}; font-weight:600; font-size:11pt;")
        ph.addWidget(self.prog_lbl); ph.addStretch()
        self.prog_pct = QLabel("0%")
        self.prog_pct.setStyleSheet(f"color:{C['primary_h']}; font-weight:700; font-size:12pt;")
        ph.addWidget(self.prog_pct); pl.addLayout(ph)
        self.pbar = QProgressBar(); pl.addWidget(self.pbar)
        ly.addWidget(self.prog_card)
        return page

    # ── Settings ───────────────────────────────────────────────────────────────────
    def _build_settings(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); ly = QVBoxLayout(content)
        ly.setContentsMargins(40, 40, 40, 40); ly.setSpacing(24)

        t = QLabel("Advanced Configuration"); t.setObjectName("PageTitle"); ly.addWidget(t)
        s = QLabel("All settings persist to config.json on disk"); s.setObjectName("SubLabel"); ly.addWidget(s)

        def section(label, icon_name, card_type="AccentCard"):
            f = QFrame(); f.setObjectName(card_type)
            fl = QVBoxLayout(f); fl.setContentsMargins(24, 20, 24, 20); fl.setSpacing(16)
            hh = QHBoxLayout(); hh.setSpacing(10)
            ic = QLabel(); ic.setPixmap(qta.icon(icon_name, color=C['primary']).pixmap(20, 20))
            tl = QLabel(label); tl.setObjectName("SectionTitle")
            hh.addWidget(ic); hh.addWidget(tl); hh.addStretch(); fl.addLayout(hh)
            sep = QFrame(); sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"background:{C['border']}; max-height:1px;")
            fl.addWidget(sep)
            form = QFormLayout(); form.setSpacing(14); form.setLabelAlignment(Qt.AlignRight)
            fl.addLayout(form)
            return f, form

        def row_label(text, hint=""):
            w = QWidget(); ly2 = QVBoxLayout(w); ly2.setContentsMargins(0, 0, 12, 0); ly2.setSpacing(2)
            l = QLabel(text); l.setStyleSheet(f"color:{C['text']};font-weight:600;font-size:10pt;")
            ly2.addWidget(l)
            if hint:
                h = QLabel(hint); h.setObjectName("HintLabel"); ly2.addWidget(h)
            return w

        # ─────────────────────────────────────────────────────────────────────
        # 1. A1D Service
        # ─────────────────────────────────────────────────────────────────────
        g1, f1 = section("A1D Service", "fa5s.cog")
        self.i_url = QLineEdit(); self.i_url.setPlaceholderText("https://a1d.ai")
        mail_note = QLabel("✉️  Temporary email otomatis via Mailticking — tidak perlu API key.")
        mail_note.setObjectName("HintLabel")
        f1.addRow(row_label("Service URL", "Override jika A1D ganti domain"), self.i_url)
        f1.addRow("", mail_note)
        ly.addWidget(g1)

        # ─────────────────────────────────────────────────────────────────────
        # 2. Output & Quality
        # ─────────────────────────────────────────────────────────────────────
        g2, f2 = section("Output & Quality", "fa5s.film", "SuccessCard")
        self.c_qual = QComboBox(); self.c_qual.addItems(["4k", "2k", "1080p"]); self.c_qual.setMinimumHeight(40)
        self.i_out = QLineEdit(); self.i_out.setPlaceholderText("Leave empty to save next to source file")
        b_brw = QPushButton(); b_brw.setObjectName("GhostBtn")
        b_brw.setIcon(qta.icon("fa5s.folder-open", color=C['accent'])); b_brw.setFixedSize(40, 40)
        b_brw.clicked.connect(self._browse_output)
        out_row = QHBoxLayout(); out_row.addWidget(self.i_out); out_row.addWidget(b_brw)
        self.s_wait = QSpinBox(); self.s_wait.setRange(0, 600); self.s_wait.setSuffix(" sec"); self.s_wait.setMinimumHeight(40)
        f2.addRow(row_label("Target Resolution", "Upscale target: 4K / 2K / 1080p"), self.c_qual)
        f2.addRow(row_label("Output Directory",  "Folder penyimpanan video hasil"), out_row)
        f2.addRow(row_label("Initial Render Wait","Tunggu sebelum cek tombol Download"), self.s_wait)
        ly.addWidget(g2)

        # ─────────────────────────────────────────────────────────────────────
        # 3. Performance & Reliability
        # ─────────────────────────────────────────────────────────────────────
        g3, f3 = section("Performance & Reliability", "fa5s.microchip", "WarnCard")
        self.s_work    = QSpinBox(); self.s_work.setRange(1, MAX_PARALLEL_LIMIT); self.s_work.setMinimumHeight(40)
        self.s_stagger = QSpinBox(); self.s_stagger.setRange(0, 120); self.s_stagger.setSuffix(" sec"); self.s_stagger.setMinimumHeight(40)
        self.s_retries = QSpinBox(); self.s_retries.setRange(0, 10); self.s_retries.setMinimumHeight(40)
        self.s_dl_to   = QSpinBox(); self.s_dl_to.setRange(60, 3600); self.s_dl_to.setSuffix(" sec"); self.s_dl_to.setMinimumHeight(40)
        self.s_hang    = QSpinBox(); self.s_hang.setRange(300, 7200); self.s_hang.setSuffix(" sec"); self.s_hang.setMinimumHeight(40)
        self.chk_h     = QCheckBox("Headless Browser  (run Chromium silently in background)")
        self.btn_rst   = QPushButton("  Force Reset — Kill Workers & Clear Temp Files")
        self.btn_rst.setObjectName("WarnBtn")
        self.btn_rst.setIcon(qta.icon("fa5s.sync-alt", color=C['warning'])); self.btn_rst.setMinimumHeight(44)
        self.btn_rst.clicked.connect(self._force_reset)
        f3.addRow(row_label("Max Parallel Workers",  f"Max: {MAX_PARALLEL_LIMIT} simultaneous"), self.s_work)
        f3.addRow(row_label("Stagger Delay",         "Detik jeda antar worker start"), self.s_stagger)
        f3.addRow(row_label("Max Retries",           "Retry otomatis jika video gagal upscale"), self.s_retries)
        f3.addRow(row_label("Download Timeout",      "Max tunggu download mulai"), self.s_dl_to)
        f3.addRow(row_label("Process Hang Timeout",  "Kill worker jika total waktu melebihi ini"), self.s_hang)
        f3.addRow("", self.chk_h); f3.addRow("", self.btn_rst)
        ly.addWidget(g3)

        # ─────────────────────────────────────────────────────────────────────
        # 4. FFmpeg Post-Processing  (Adobe Stock 4K Microstock)
        # ─────────────────────────────────────────────────────────────────────
        g4, f4 = section("FFmpeg Post-Processing", "fa5s.photo-video", "SuccessCard")

        self.chk_ff_en = QCheckBox(
            "🎬 Aktifkan FFmpeg setelah A1D selesai upscale"
        )

        self.c_ff_preset = QComboBox(); self.c_ff_preset.setMinimumHeight(40)
        for key in PRESET_KEYS:
            self.c_ff_preset.addItem(PRESET_LABELS[key], userData=key)

        self.chk_ff_mute = QCheckBox(
            "🔇 Mute Audio (-an)  — wajib untuk stock video Adobe tanpa musik"
        )
        self.chk_ff_replace = QCheckBox(
            "♻️ Replace Original  — ganti file A1D dengan hasil FFmpeg (hemat storage)"
        )

        self.s_ff_crf = QSpinBox()
        self.s_ff_crf.setRange(0, 51)
        self.s_ff_crf.setToolTip("0 = lossless, 18 = sangat bagus, 28 = medium")
        self.s_ff_crf.setMinimumHeight(40)

        self.c_ff_speed = QComboBox(); self.c_ff_speed.setMinimumHeight(40)
        self.c_ff_speed.addItems([
            "ultrafast", "superfast", "veryfast", "faster",
            "fast", "medium", "slow", "slower", "veryslow",
        ])

        ff_note = QLabel(
            "📌 Preset adobe_stock_4k_h264: H.264 High 5.2 │ 3840×2160 │ "
            "yuv420p │ CRF 18 │ slow │ -movflags +faststart"
        )
        ff_note.setObjectName("HintLabel")
        ff_note.setWordWrap(True)

        f4.addRow("",                                                          self.chk_ff_en)
        f4.addRow(row_label("Preset",       "Resolusi & codec output"),        self.c_ff_preset)
        f4.addRow("",                                                          self.chk_ff_mute)
        f4.addRow("",                                                          self.chk_ff_replace)
        f4.addRow(row_label("CRF",          "0=lossless  18=sangat bagus"),    self.s_ff_crf)
        f4.addRow(row_label("Encode Speed", "slow=kualitas terbaik"),          self.c_ff_speed)
        f4.addRow("",                                                          ff_note)
        ly.addWidget(g4)

        # ─ Save button ─────────────────────────────────────────────────────────────
        btn_sv = QPushButton("  SAVE ALL SETTINGS"); btn_sv.setObjectName("PrimaryBtn")
        btn_sv.setIcon(qta.icon("fa5s.save", color="#FFF")); btn_sv.setMinimumHeight(52)
        btn_sv.clicked.connect(self._save_config); ly.addWidget(btn_sv)
        ly.addStretch()
        scroll.setWidget(content); return scroll

    # ── Logs ─────────────────────────────────────────────────────────────────────────
    def _build_logs(self):
        page = QWidget(); ly = QVBoxLayout(page)
        ly.setContentsMargins(40, 40, 40, 40); ly.setSpacing(20)

        self.log_viewer = LogViewer()

        hdr = QHBoxLayout()
        t   = QLabel("System Logs"); t.setObjectName("PageTitle")
        hdr.addWidget(t); hdr.addStretch()
        b_exp = QPushButton("  Export Logs"); b_exp.setObjectName("GhostBtn")
        b_exp.setIcon(qta.icon("fa5s.download", color=C['accent']))
        b_exp.clicked.connect(self._export_logs)
        b_clr = QPushButton("  Clear"); b_clr.setObjectName("DangerBtn")
        b_clr.setIcon(qta.icon("fa5s.eraser", color=C['error']))
        b_clr.clicked.connect(lambda: self.log_viewer.clear())
        hdr.addWidget(b_exp); hdr.addWidget(b_clr); ly.addLayout(hdr)

        leg = QHBoxLayout(); leg.setSpacing(20)
        for label, col in [("INFO", C['accent']), ("SUCCESS", C['success']),
                            ("WARNING", C['warning']), ("ERROR", C['error'])]:
            d = QLabel(f"●  {label}")
            d.setStyleSheet(f"color:{col}; font-size:9pt; font-weight:700;")
            leg.addWidget(d)
        leg.addStretch(); ly.addLayout(leg)
        ly.addWidget(self.log_viewer)
        return page

    # ── Theme ────────────────────────────────────────────────────────────────────────
    def _toggle_theme(self):
        new = "light" if self._theme == "dark" else "dark"
        self._apply_theme(new)
        QApplication.instance().setStyleSheet(build_stylesheet(C))
        self._refresh_all()
        self._save_config(silent=True)

    def _refresh_all(self):
        self.lbl_app.setStyleSheet(f"font-size:22pt; font-weight:700; color:{C['primary_h']};")
        self.lbl_ver.setStyleSheet(f"font-size:8pt; font-weight:400; color:{C['text_muted']};")
        ico = "fa5s.sun" if self._theme == "dark" else "fa5s.moon"
        lbl = "  Light Mode" if self._theme == "dark" else "  Dark Mode"
        self.btn_theme.setIcon(qta.icon(ico, color=C['accent'])); self.btn_theme.setText(lbl)
        self.badge_count.setStyleSheet(
            f"background:{C['primary']}20; color:{C['primary_h']}; font-weight:700; "
            f"font-size:9pt; padding:4px 14px; border-radius:20px; border:1px solid {C['primary']}40;"
        )
        self.drop_zone.refresh_theme()
        if hasattr(self, "log_viewer"): self.log_viewer.refresh_theme()
        self._refresh_nav_icons()
        self._set_running(self._running)

    def _refresh_nav_icons(self):
        for btn, icon in [(self.nav_queue,"fa5s.layer-group"),
                          (self.nav_settings,"fa5s.sliders-h"),
                          (self.nav_logs,"fa5s.terminal")]:
            btn.setIcon(qta.icon(icon, color=C['primary_h'] if btn.isChecked() else C['text_muted']))

    # ── Business Logic ────────────────────────────────────────────────────────────
    def _load_settings_to_ui(self):
        c  = self.config
        ff = c.get("ffmpeg", {})

        # A1D Service
        self.i_url.setText(c.get("a1d_url", "https://a1d.ai"))

        # Output & Quality
        self.c_qual.setCurrentText(c.get("output_quality", "4k"))
        self.i_out.setText(c.get("output_dir", ""))
        self.s_wait.setValue(c.get("initial_download_wait", 120))

        # Performance
        self.s_work.setValue(c.get("max_workers",             DEFAULT_WORKERS))
        self.s_stagger.setValue(c.get("batch_stagger_delay",  15))
        self.s_retries.setValue(c.get("max_retries",          DEFAULT_MAX_RETRIES))
        self.s_dl_to.setValue(c.get("download_timeout",       600))
        self.s_hang.setValue(c.get("processing_hang_timeout", 1800))
        self.chk_h.setChecked(c.get("headless", True))

        # FFmpeg
        self.chk_ff_en.setChecked(ff.get("enabled",          True))
        preset_key = ff.get("preset_name", "adobe_stock_4k_h264")
        idx = self.c_ff_preset.findData(preset_key)
        if idx >= 0: self.c_ff_preset.setCurrentIndex(idx)
        self.chk_ff_mute.setChecked(ff.get("mute_audio",       True))
        self.chk_ff_replace.setChecked(ff.get("replace_original", True))
        self.s_ff_crf.setValue(ff.get("crf",                   18))
        sp_idx = self.c_ff_speed.findText(ff.get("encode_preset", "slow"))
        if sp_idx >= 0: self.c_ff_speed.setCurrentIndex(sp_idx)

    def _save_config(self, silent=False):
        ff = dict(self.config.get("ffmpeg", {}))
        ff.update({
            "enabled":          self.chk_ff_en.isChecked(),
            "preset_name":      self.c_ff_preset.currentData(),
            "mute_audio":       self.chk_ff_mute.isChecked(),
            "replace_original": self.chk_ff_replace.isChecked(),
            "crf":              self.s_ff_crf.value(),
            "encode_preset":    self.c_ff_speed.currentText(),
        })
        self.config.update({
            "a1d_url":                 self.i_url.text().strip() or "https://a1d.ai",
            "output_quality":          self.c_qual.currentText(),
            "output_dir":              self.i_out.text().strip(),
            "initial_download_wait":   self.s_wait.value(),
            "max_workers":             self.s_work.value(),
            "batch_stagger_delay":     self.s_stagger.value(),
            "max_retries":             self.s_retries.value(),
            "download_timeout":        self.s_dl_to.value(),
            "processing_hang_timeout": self.s_hang.value(),
            "headless":                self.chk_h.isChecked(),
            "theme":                   self._theme,
            "ffmpeg":                  ff,
        })
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            if not silent: self._log("All settings saved to config.json", "SUCCESS")
        except Exception as e:
            self._log(f"Cannot save config: {e}", "ERROR")

    def _force_reset(self):
        if QMessageBox.question(self, "Force Reset",
                                "Stop all workers and clear temp folder?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._cancel()
        for folder in ["temp", "debug"]:
            p = os.path.join(_PROJECT_ROOT, folder)
            if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)
        self._log("Force reset complete — workers terminated, temp & debug cleared.", "WARNING")

    def _export_logs(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Logs",
            os.path.join(os.path.expanduser("~"), f"a1d_log_{ts}.txt"),
            "Text (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_viewer.toPlainText())
                self._log(f"Logs exported → {path}", "SUCCESS")
            except Exception as e:
                self._log(f"Export failed: {e}", "ERROR")

    def _log(self, m, l="INFO"):
        if hasattr(self, "log_viewer"): self.log_viewer.append_log(m, l)

    def _on_drop(self, ps):
        if not ps: self._browse_files()
        else: self._add_files(ps)

    def _browse_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "",
                "Videos (*.mp4 *.mkv *.mov *.avi *.webm *.flv)")
        self._add_files(fs)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Output Folder")
        if d: self.i_out.setText(d)

    def _add_files(self, ps):
        for p in ps:
            if p and p not in self._paths:
                self._paths.append(p)
                it = QListWidgetItem(f"  {os.path.basename(p)}")
                it.setIcon(qta.icon("fa5s.film", color=C['primary']))
                it.setToolTip(p); self.file_list.addItem(it)
        self._update_badge()

    def _remove_selected(self):
        for it in reversed(self.file_list.selectedItems()):
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
            return self._log("Queue is empty. Please add video files.", "WARNING")
        self._save_config(silent=True)
        self._set_running(True)
        cfg = dict(self.config)
        self._log("-" * 52)
        self._log(
            f"BATCH ENGINE STARTING  —  {len(self._paths)} file(s)  |  "
            f"{cfg['output_quality'].upper()} mode  |  "
            f"FFmpeg: {'ON' if cfg.get('ffmpeg', {}).get('enabled', True) else 'OFF'}",
            "SUCCESS",
        )
        self._log(
            f"Workers: {cfg['max_workers']}  |  Stagger: {cfg['batch_stagger_delay']}s  "
            f"|  Headless: {cfg['headless']}"
        )
        ff = cfg.get("ffmpeg", {})
        self._log(
            f"FFmpeg preset: {ff.get('preset_name','adobe_stock_4k_h264')}  "
            f"|  CRF: {ff.get('crf', 18)}  "
            f"|  Audio: {'MUTED' if ff.get('mute_audio', True) else 'KEEP'}  "
            f"|  Replace: {ff.get('replace_original', True)}"
        )
        self._log("-" * 52)
        # Always use BatchProcessor for consistent retry logic
        self.processor = BatchProcessor(_PROJECT_ROOT, self._paths, cfg)
        self.processor.log_signal.connect(self._log)
        self.processor.progress_signal.connect(self._on_progress)
        self.processor.finished_signal.connect(lambda ok, m, _: self._on_finished(ok, m))
        self.processor.video_status_signal.connect(self._update_video_status)
        self.processor.start()

    def _set_running(self, r):
        self._running = r
        self.btn_start.setVisible(not r); self.btn_cancel.setVisible(r)
        self.prog_card.setVisible(r)
        color = C['success'] if r else C['text_muted']
        self.dot_status.setStyleSheet(f"color:{color}; font-size:14pt;")
        self.lbl_status.setText("PROCESSING" if r else "SYSTEM IDLE")
        self.lbl_status.setStyleSheet(f"color:{color}; font-size:8pt; font-weight:700; letter-spacing:1px;")

    def _on_progress(self, pct, msg):
        self.pbar.setValue(pct)
        self.prog_lbl.setText(msg)
        self.prog_pct.setText(f"{pct}%")

    def _on_finished(self, ok, msg):
        self._set_running(False)
        self.prog_lbl.setText("Batch completed successfully." if ok else "Process failed or cancelled.")
        self.prog_pct.setText("100%" if ok else "--")
        self._log(f"{'DONE: ' if ok else 'FAILED: '}{msg}", "SUCCESS" if ok else "ERROR")

    def _cancel(self):
        if self.processor: self.processor.cancel()
        self._log("Force stop requested — terminating all workers.", "ERROR")

    def _update_video_status(self, job_idx: int, status: str):
        """Update the icon of a video item in the file list based on its processing status."""
        if job_idx < 0 or job_idx >= self.file_list.count():
            return
        item = self.file_list.item(job_idx)
        if item is None:
            return
        status_icons = {
            "pending":    ("fa5s.clock",        C['text_muted']),
            "processing": ("fa5s.sync-alt",     C['primary']),
            "success":    ("fa5s.check-circle", C['success']),
            "failed":     ("fa5s.times-circle", C['error']),
        }
        icon_name, color = status_icons.get(status, ("fa5s.clock", C['text_muted']))
        item.setIcon(qta.icon(icon_name, color=color))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    font = QFont("Segoe UI", 10); font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    app.setStyleSheet(build_stylesheet(C))
    w = MainWindow(); w.show()
    sys.exit(app.exec())
