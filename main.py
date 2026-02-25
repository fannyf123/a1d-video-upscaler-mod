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
from PySide6.QtGui import QFont, QTextCursor
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
        "text_dim":  "#E2E8F0",   # very visible light grey
        "text_muted":"#9CA3AF",   # secondary text
        "success":   "#3FB950",
        "warning":   "#D29922",
        "error":     "#F85149",
        "log_bg":    "#010409",
    },
    "light": {
        "bg":        "#F3F4F6",   # light grey bg
        "sidebar":   "#FFFFFF",
        "surface":   "#FFFFFF",
        "input":     "#F9FAFB",
        "border":    "#D1D5DB",
        "primary":   "#7C3AED",   # deep violet
        "primary_h": "#6D28D9",
        "accent":    "#2563EB",   # blue
        "text":      "#111827",   # near-black
        "text_dim":  "#374151",   # dark grey
        "text_muted":"#6B7280",
        "success":   "#10B981",
        "warning":   "#D97706",
        "error":     "#EF4444",
        "log_bg":    "#FFFFFF",
    },
}

# ── Dynamic Pointer to Active Palette ──
C = dict(THEMES["dark"])


def build_stylesheet(c: dict) -> str:
    return f"""
QWidget {{ color: {c['text']}; outline: none; }}
QMainWindow, QWidget#MainContent {{ background-color: {c['bg']}; }}
QWidget#Sidebar {{ background-color: {c['sidebar']}; border-right: 1px solid {c['border']}; }}

QLabel#H1  {{ font-size: 24px; font-weight: 800; color: {c['text']}; }}
QLabel#H2  {{ font-size: 15px; font-weight: 700; color: {c['text']}; }}
QLabel#Sub {{ font-size: 12px; color: {c['text_muted']}; font-weight: 500; }}
QLabel     {{ color: {c['text']}; }}

QFrame#Card {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#Card:hover {{ border-color: {c['primary']}; }}

QPushButton {{
    background-color: {c['surface']}; border: 1px solid {c['border']};
    border-radius: 8px; padding: 9px 18px; font-weight: 700; color: {c['text']};
}}
QPushButton:hover  {{ background-color: {c['border']}; border-color: {c['text_muted']}; }}
QPushButton:pressed{{ background-color: {c['bg']}; }}

QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['primary']}, stop:1 {c['primary_h']});
    border: none; color: #FFFFFF;
}}
QPushButton#PrimaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['primary_h']}, stop:1 {c['primary']});
}}

QPushButton#DangerBtn {{ background-color: transparent; border: 2px solid {c['error']}; color: {c['error']}; }}
QPushButton#DangerBtn:hover {{ background-color: {c['error']}; color: #FFFFFF; }}

QPushButton#ThemeBtn {{
    background-color: transparent; border: 1px solid {c['border']}; border-radius: 20px;
    padding: 6px 14px; font-size: 12px; font-weight: 700; color: {c['text_dim']};
}}
QPushButton#ThemeBtn:hover {{ background-color: {c['primary']}22; border-color: {c['primary']}; color: {c['primary']}; }}

QToolButton#NavBtn {{
    background-color: transparent; border: none; border-radius: 10px; padding: 11px;
    font-size: 13px; font-weight: 600; text-align: left; color: {c['text_dim']};
}}
QToolButton#NavBtn:hover   {{ background-color: {c['surface']}; color: {c['text']}; }}
QToolButton#NavBtn:checked {{ background-color: {c['primary']}33; color: {c['primary']}; font-weight: 800; }}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px;
    padding: 8px 12px; min-height: 22px; color: {c['text']}; selection-background-color: {c['primary']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1.5px solid {c['primary']}; }}
QLineEdit::placeholder {{ color: {c['text_muted']}; }}
QComboBox::drop-down {{ border: none; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; border: none; }}

QCheckBox {{ color: {c['text']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1.5px solid {c['border']};
    border-radius: 4px; background: {c['input']};
}}
QCheckBox::indicator:checked {{ background: {c['primary']}; border-color: {c['primary']}; }}

QListWidget {{
    background-color: {c['input']}; border: 1px solid {c['border']};
    border-radius: 10px; outline: none; color: {c['text']};
}}
QListWidget::item {{ padding: 11px; border-bottom: 1px solid {c['border']}; color: {c['text']}; }}
QListWidget::item:selected {{ background-color: {c['primary']}33; color: {c['primary']}; }}

QScrollBar:vertical {{ background: transparent; width: 7px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QProgressBar {{
    background-color: {c['input']}; border: 1px solid {c['border']};
    border-radius: 8px; min-height: 14px; max-height: 14px; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['primary']}, stop:1 {c['accent']});
    border-radius: 6px;
}}
"""

# ══════════════════════════════════════════════════════════════════════════════
#  CUSTOM WIDGETS
# ══════════════════════════════════════════════════════════════════════════════
class ModernDropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setObjectName("DropZone")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.text_lbl = QLabel("Drag & Drop Videos Here")
        self.text_lbl.setAlignment(Qt.AlignCenter)
        self.sub_lbl = QLabel("Supported: MP4 · MKV · MOV · AVI · WEBM")
        self.sub_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.text_lbl)
        layout.addWidget(self.sub_lbl)
        self.refresh_theme()

    def refresh_theme(self):
        self._default_style = f"QFrame#DropZone {{ border: 2px dashed {C['border']}; border-radius: 16px; background-color: {C['surface']}; }}"
        self._hover_style   = f"QFrame#DropZone {{ border: 2px dashed {C['primary']}; border-radius: 16px; background-color: {C['primary']}18; }}"
        self.setStyleSheet(self._default_style)
        self.icon_lbl.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary']).pixmap(44, 44))
        self.text_lbl.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {C['text']};")
        self.sub_lbl.setStyleSheet(f"font-size: 12px; color: {C['text_muted']};")

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


class LogViewer(QTextEdit):
    def __init__(self, max_lines=2000):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C['log_bg']}; border: 1px solid {C['border']};
                border-radius: 12px; font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px; padding: 14px; color: {C['text']};
            }}
        """)

    def append_log(self, msg, level="INFO"):
        if isinstance(msg, tuple): msg = str(msg[0])
        ml = msg.lower()
        if   "error" in ml or "failed" in ml:    color = C['error']
        elif "success" in ml or "completed" in ml: color = C['success']
        elif "warning" in ml or "timeout" in ml:   color = C['warning']
        elif "worker" in ml or "batch" in ml:      color = C['accent']
        elif level == "SUCCESS":                   color = C['success']
        elif level == "ERROR":                     color = C['error']
        elif level == "WARNING":                   color = C['warning']
        else:                                      color = C['text']

        ts   = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:{C["text_muted"]}">[{ts}]</span> <span style="color:{color}">{msg}</span>'
        self.append(html)
        self.moveCursor(QTextCursor.End)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VER}")
        self.resize(1150, 780)
        self.config = self._load_config()
        
        # Determine startup theme
        self._current_theme_name = self.config.get("theme", "dark")
        self._apply_theme_colors(self._current_theme_name)
        
        self._video_paths = []
        self.processor = None
        self._running = False

        self._setup_ui()
        self._load_settings_to_ui()

    def _load_config(self) -> dict:
        default = {
            "relay_api_key": "", "output_quality": "4k", "output_dir": "",
            "headless": True, "max_workers": DEFAULT_WORKERS,
            "batch_stagger_delay": 15, "initial_download_wait": 120,
            "processing_hang_timeout": 1800, "download_timeout": 600,
            "a1d_url": "https://a1d.ai", "theme": "dark"
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    default.update(json.load(f))
            except: pass
        return default

    def _apply_theme_colors(self, theme_name: str):
        global C
        if theme_name not in THEMES: theme_name = "dark"
        C.update(THEMES[theme_name])
        self._current_theme_name = theme_name
        self.config["theme"] = theme_name

    def _toggle_theme(self):
        new_theme = "light" if self._current_theme_name == "dark" else "dark"
        self._apply_theme_colors(new_theme)
        
        # Apply new stylesheet entirely
        app = QApplication.instance()
        app.setStyleSheet(build_stylesheet(C))
        
        # Manually refresh custom styled widgets
        self._refresh_static_labels()
        self.drop_zone.refresh_theme()
        self.log_viewer.refresh_theme()
        self._update_nav_style()
        self._set_running(self._running) # Refresh dot color

        # Update button text
        ico = "fa5s.sun" if new_theme == "dark" else "fa5s.moon"
        lbl = "Light Mode" if new_theme == "dark" else "Dark Mode"
        self.btn_theme.setIcon(qta.icon(ico, color=C['text_dim']))
        self.btn_theme.setText(f" {lbl}")
        
        # Save change
        try:
            with open(CONFIG_PATH, "w") as f: json.dump(self.config, f, indent=2)
        except: pass

    def _refresh_static_labels(self):
        self.title_top.setStyleSheet(f"font-size: 32px; font-weight: 900; color: {C['primary']};")
        self.title_bot.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {C['text']}; letter-spacing: 2px;")
        
        self.count_badge.setStyleSheet(
            f"background: {C['primary']}22; color: {C['primary']};"
            f" font-weight: 800; font-size: 11px; padding: 6px 14px; border-radius: 15px;"
        )
        
        # Refresh dynamic list icons
        for i in range(self.file_list.count()):
            self.file_list.item(i).setIcon(qta.icon("fa5s.film", color=C['primary']))
            
        self.btn_add.setIcon(qta.icon("fa5s.folder-plus", color=C['text']))
        self.btn_clear_log.setIcon(qta.icon("fa5s.eraser", color=C['text']))
        self.btn_browse.setIcon(qta.icon("fa5s.folder-open", color=C['text']))

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── SIDEBAR ─────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(20, 35, 20, 25)
        sb_layout.setSpacing(8)

        self.title_top = QLabel("A1D")
        self.title_bot = QLabel("UPSCALER PRO")
        sb_layout.addWidget(self.title_top)
        sb_layout.addWidget(self.title_bot)
        sb_layout.addSpacing(30)

        self.btn_queue = self._create_nav_btn("Dashboard", "fa5s.home", 0)
        self.btn_settings = self._create_nav_btn("Settings", "fa5s.cogs", 1)
        self.btn_logs = self._create_nav_btn("Worker Logs", "fa5s.terminal", 2)
        sb_layout.addWidget(self.btn_queue)
        sb_layout.addWidget(self.btn_settings)
        sb_layout.addWidget(self.btn_logs)
        sb_layout.addStretch()

        # Theme Switcher
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("ThemeBtn")
        self.btn_theme.clicked.connect(self._toggle_theme)
        sb_layout.addWidget(self.btn_theme)
        sb_layout.addSpacing(10)

        # Status
        status_card = QFrame()
        status_card.setObjectName("Card")
        sc_layout = QVBoxLayout(status_card)
        sc_layout.setContentsMargins(15, 12, 15, 12)
        self.status_dot = QLabel("●")
        self.status_text = QLabel("IDLE MODE")
        self.status_text.setObjectName("Sub")
        row = QHBoxLayout()
        row.addWidget(self.status_dot)
        row.addWidget(self.status_text)
        row.addStretch()
        sc_layout.addLayout(row)
        sb_layout.addWidget(status_card)
        
        ver_lbl = QLabel(f"v{APP_VER}")
        ver_lbl.setObjectName("Sub")
        ver_lbl.setAlignment(Qt.AlignCenter)
        sb_layout.addWidget(ver_lbl)

        # ── STACK ───────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setObjectName("MainContent")

        self.page_queue = self._build_queue_page()
        self.page_settings = self._build_settings_page()
        self.page_logs = self._build_logs_page()

        self.stack.addWidget(self.page_queue)
        self.stack.addWidget(self.page_settings)
        self.stack.addWidget(self.page_logs)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)
        self.btn_queue.setChecked(True)
        
        # Init static labels styles
        self._refresh_static_labels()
        
        # Init Theme Button State
        ico = "fa5s.sun" if self._current_theme_name == "dark" else "fa5s.moon"
        lbl = "Light Mode" if self._current_theme_name == "dark" else "Dark Mode"
        self.btn_theme.setIcon(qta.icon(ico, color=C['text_dim']))
        self.btn_theme.setText(f" {lbl}")

    def _create_nav_btn(self, text, icon_name, index):
        btn = QToolButton()
        btn.setText(f"  {text}")
        btn.setIconSize(QSize(20, 20))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setObjectName("NavBtn")
        btn.clicked.connect(lambda checked, i=index: self.stack.setCurrentIndex(i))
        btn.clicked.connect(self._update_nav_style)
        return btn

    def _update_nav_style(self):
        buttons = [
            (self.btn_queue, "fa5s.home"),
            (self.btn_settings, "fa5s.cogs"),
            (self.btn_logs, "fa5s.terminal"),
        ]
        for btn, icon in buttons:
            color = C['primary'] if btn.isChecked() else C['text_dim']
            btn.setIcon(qta.icon(icon, color=color))

    def _build_queue_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.setSpacing(20)

        top = QHBoxLayout()
        welcome = QVBoxLayout()
        h1 = QLabel("Video Processing Queue")
        h1.setObjectName("H1")
        sub = QLabel("Select or drop video files to begin AI upscaling via SotongHD.")
        sub.setObjectName("Sub")
        welcome.addWidget(h1)
        welcome.addWidget(sub)
        top.addLayout(welcome)
        top.addStretch()

        self.count_badge = QLabel("0 QUEUED")
        top.addWidget(self.count_badge, alignment=Qt.AlignVCenter)
        layout.addLayout(top)

        self.drop_zone = ModernDropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        layout.addWidget(self.drop_zone)

        self.file_list = QListWidget()
        layout.addWidget(self.file_list, stretch=1)

        ctrls = QHBoxLayout()
        self.btn_add = QPushButton(" Browse Media")
        self.btn_add.clicked.connect(self._browse_files)
        self.btn_clear = QPushButton(" Clear Queue")
        self.btn_clear.setIcon(qta.icon("fa5s.trash", color=C['error']))
        self.btn_clear.clicked.connect(self._clear_files)

        ctrls.addWidget(self.btn_add)
        ctrls.addWidget(self.btn_clear)
        ctrls.addStretch()

        self.btn_start = QPushButton("START BATCH PROCESS")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setMinimumHeight(48)
        self.btn_start.setMinimumWidth(220)
        self.btn_start.setIcon(qta.icon("fa5s.play", color="white"))
        self.btn_start.clicked.connect(self._start)

        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setMinimumHeight(48)
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.hide()
        self.btn_cancel.clicked.connect(self._cancel)

        ctrls.addWidget(self.btn_start)
        ctrls.addWidget(self.btn_cancel)
        layout.addLayout(ctrls)

        self.prog_card = QFrame()
        self.prog_card.setObjectName("Card")
        self.prog_card.hide()
        p_lay = QVBoxLayout(self.prog_card)
        self.p_label = QLabel("Waiting for initialization...")
        self.pbar = QProgressBar()
        p_lay.addWidget(self.p_label)
        p_lay.addWidget(self.pbar)
        layout.addWidget(self.prog_card)

        return page

    def _build_settings_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.setSpacing(25)

        lbl_h1 = QLabel("System Configuration")
        lbl_h1.setObjectName("H1")
        layout.addWidget(lbl_h1)

        def create_group(title, icon_name):
            group = QFrame()
            group.setObjectName("Card")
            gl = QVBoxLayout(group)
            header = QHBoxLayout()
            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon(icon_name, color=C['primary']).pixmap(20, 20))
            lbl = QLabel(title)
            lbl.setObjectName("H2")
            header.addWidget(icon_lbl)
            header.addWidget(lbl)
            header.addStretch()
            gl.addLayout(header)
            form = QFormLayout()
            gl.addLayout(form)
            return group, form

        g_api, f_api = create_group("Authentication & Network", "fa5s.globe")
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        self.inp_url = QLineEdit()
        f_api.addRow("Firefox Relay API Key:", self.inp_api_key)
        f_api.addRow("Target Service URL:", self.inp_url)
        layout.addWidget(g_api)

        g_out, f_out = create_group("Output Engine", "fa5s.video")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["4k", "2k", "1080p"])
        self.inp_out_dir = QLineEdit()
        self.btn_browse = QToolButton()
        self.btn_browse.clicked.connect(self._browse_output)
        h_dir = QHBoxLayout()
        h_dir.addWidget(self.inp_out_dir)
        h_dir.addWidget(self.btn_browse)
        f_out.addRow("Target Resolution:", self.combo_quality)
        f_out.addRow("Export Path:", h_dir)
        layout.addWidget(g_out)

        g_perf, f_perf = create_group("Workers & Advanced Performance", "fa5s.microchip")
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, MAX_PARALLEL_LIMIT)
        self.spin_stagger = QSpinBox()
        self.spin_stagger.setSuffix(" sec")
        self.spin_dl_timeout = QSpinBox()
        self.spin_dl_timeout.setRange(60, 3600)
        self.spin_dl_timeout.setSuffix(" sec")
        self.spin_render_timeout = QSpinBox()
        self.spin_render_timeout.setRange(300, 7200)
        self.spin_render_timeout.setSuffix(" sec")
        self.chk_headless = QCheckBox("Enable Background Execution (Silent Browser)")
        
        f_perf.addRow("Parallel Tasks (Max Workers):", self.spin_workers)
        f_perf.addRow("Batch Stagger Delay:", self.spin_stagger)
        f_perf.addRow("Download Timeout:", self.spin_dl_timeout)
        f_perf.addRow("Processing Timeout:", self.spin_render_timeout)
        f_perf.addRow("", self.chk_headless)
        layout.addWidget(g_perf)

        btn_save = QPushButton("Save Configurations")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setMinimumHeight(45)
        btn_save.clicked.connect(self._save_config_ui)
        layout.addWidget(btn_save)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    def _build_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.setSpacing(20)

        header = QHBoxLayout()
        lbl_h1 = QLabel("System & Worker Logs")
        lbl_h1.setObjectName("H1")
        header.addWidget(lbl_h1)
        header.addStretch()

        self.btn_clear_log = QPushButton(" Clear Logs")
        self.btn_clear_log.setMaximumWidth(120)
        header.addWidget(self.btn_clear_log)

        self.log_viewer = LogViewer()
        self.btn_clear_log.clicked.connect(self.log_viewer.clear)

        layout.addLayout(header)
        layout.addWidget(self.log_viewer)
        return page

    # ── LOGIC ────────────────────────────────────────────────────────────

    def _load_settings_to_ui(self):
        c = self.config
        self.inp_api_key.setText(c.get("relay_api_key", ""))
        self.inp_url.setText(c.get("a1d_url", "https://a1d.ai"))
        self.combo_quality.setCurrentText(c.get("output_quality", "4k"))
        self.inp_out_dir.setText(c.get("output_dir", ""))
        self.spin_workers.setValue(c.get("max_workers", DEFAULT_WORKERS))
        self.spin_stagger.setValue(c.get("batch_stagger_delay", 15))
        self.chk_headless.setChecked(c.get("headless", True))
        self.spin_dl_timeout.setValue(c.get("download_timeout", 600))
        self.spin_render_timeout.setValue(c.get("processing_hang_timeout", 1800))

    def _save_config_ui(self):
        self.config.update({
            "relay_api_key": self.inp_api_key.text().strip(),
            "a1d_url": self.inp_url.text().strip(),
            "output_quality": self.combo_quality.currentText().lower(),
            "output_dir": self.inp_out_dir.text().strip(),
            "max_workers": self.spin_workers.value(),
            "batch_stagger_delay": self.spin_stagger.value(),
            "headless": self.chk_headless.isChecked(),
            "download_timeout": self.spin_dl_timeout.value(),
            "processing_hang_timeout": self.spin_render_timeout.value(),
            "theme": self._current_theme_name
        })
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            self._log("Settings configuration saved successfully.", "SUCCESS")
        except Exception as e:
            self._log(f"Failed to save settings: {e}", "ERROR")

    def _log(self, msg, level="INFO"):
        self.log_viewer.append_log(msg, level)

    def _on_drop(self, paths):
        if not paths:
            self._browse_files()
            return
        self._add_files(paths)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Videos", "",
            "Videos (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv)"
        )
        self._add_files(files)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            self.inp_out_dir.setText(d)

    def _add_files(self, paths):
        for p in paths:
            if p not in self._video_paths:
                self._video_paths.append(p)
                item = QListWidgetItem(f"  {os.path.basename(p)}")
                item.setIcon(qta.icon("fa5s.film", color=C['primary']))
                item.setToolTip(p)
                self.file_list.addItem(item)
        self.count_badge.setText(f"{len(self._video_paths)} QUEUED")
        self._log(f"Added {len(paths)} file(s) to processing queue.")

    def _clear_files(self):
        self._video_paths.clear()
        self.file_list.clear()
        self.count_badge.setText("0 QUEUED")

    def _start(self):
        if not self._video_paths:
            self._log("Queue is empty! Please add video files first.", "WARNING")
            return
        if not self.inp_api_key.text().strip():
            self._log("Missing Firefox Relay API Key. Please update Configuration.", "ERROR")
            self.btn_settings.click()
            return
            
        self._save_config_ui()
        self._set_running(True)
        cfg = dict(self.config)
        
        self._log("=========================================")
        self._log(f"Initializing SotongHD Engine - {len(self._video_paths)} files")
        self._log(f"Workers: {cfg.get('max_workers', 1)} | Target: {cfg.get('output_quality', '4k').upper()}")
        self._log("=========================================")
        
        if len(self._video_paths) == 1:
            self.processor = A1DProcessor(_PROJECT_ROOT, self._video_paths[0], cfg)
        else:
            self.processor = BatchProcessor(_PROJECT_ROOT, self._video_paths, cfg)
            
        self.processor.log_signal.connect(self._log)
        self.processor.progress_signal.connect(self._on_progress)
        self.processor.finished_signal.connect(self._on_finished)
        self.processor.start()

    def _set_running(self, running):
        self._running = running
        self.btn_start.setVisible(not running)
        self.btn_cancel.setVisible(running)
        self.prog_card.setVisible(running)
        dot_color = C['success'] if running else C['text_dim']
        self.status_dot.setStyleSheet(f"color: {dot_color}; font-size: 16px;")
        self.status_text.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {C['text']};")
        self.status_text.setText("PROCESSING..." if running else "IDLE MODE")

    def _on_progress(self, pct, msg):
        self.pbar.setValue(pct)
        self.p_label.setText(msg)

    def _on_finished(self, ok, msg):
        self._set_running(False)
        self.p_label.setText("Batch processing completed!" if ok else f"Process aborted or failed.")
        self._log(f"Final Status: {msg}", "SUCCESS" if ok else "ERROR")

    def _cancel(self):
        if self.processor:
            self.processor.cancel()
            self._log("User requested process cancellation. Terminating workers...", "WARNING")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VER)
    
    font = QFont("Inter", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    
    # Init Default Style
    app.setStyleSheet(build_stylesheet(C))
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
