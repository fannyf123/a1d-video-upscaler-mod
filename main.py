import sys
import os
import json
import datetime
from pathlib import Path

# ══ FIX: Ensure project root is in sys.path ══════════════════════════════════
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
# ────────────────────────────────────────────────────────────────────────────────

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QTextEdit, QFileDialog, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QToolButton,
    QFormLayout, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import (
    QFont, QColor, QDragEnterEvent, QDropEvent,
    QTextCursor, QPalette, QIcon, QLinearGradient, QBrush
)
import qtawesome as qta

from App.background_process import A1DProcessor
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS

CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
APP_NAME    = "A1D Video Upscaler"
APP_VER     = "2.3.0"

# ══ THEME CONFIGURATION ══════════════════════════════════════════════════════
C = {
    "bg":        "#0B0F19",
    "sidebar":   "#111827",
    "surface":   "#1F2937",
    "input":     "#030712",
    "border":    "#374151",
    "primary":   "#8B5CF6",  # Violet 500
    "primary_h": "#A855F7",  # Purple 500
    "accent":    "#3B82F6",  # Blue 500
    "text":      "#F9FAFB",
    "text_dim":  "#9CA3AF",
    "success":   "#10B981",
    "warning":   "#F59E0B",
    "error":     "#EF4444",
}

MODERN_STYLES = f"""
/* GLOBAL */
* {{ font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget#MainContent {{ background-color: {C['bg']}; }}
QWidget#Sidebar {{ background-color: {C['sidebar']}; border-right: 1px solid {C['border']}; }}

/* HEADERS */
QLabel#H1 {{ font-size: 26px; font-weight: 800; color: {C['text']}; }}
QLabel#H2 {{ font-size: 16px; font-weight: 700; color: {C['text']}; }}
QLabel#Sub {{ font-size: 12px; color: {C['text_dim']}; font-weight: 500; }}

/* CARDS & CONTAINERS */
QFrame#Card {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QFrame#Card:hover {{ border-color: {C['primary']}88; }}

/* BUTTONS */
QPushButton {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 700;
}}
QPushButton:hover {{ background-color: {C['border']}; border-color: {C['text_dim']}; }}
QPushButton:pressed {{ background-color: {C['bg']}; }}

QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['primary']}, stop:1 #6D28D9);
    border: none;
    color: white;
}}
QPushButton#PrimaryBtn:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['primary_h']}, stop:1 {C['primary']}); }}

QPushButton#DangerBtn {{
    background-color: transparent;
    border: 2px solid {C['error']};
    color: {C['error']};
}}
QPushButton#DangerBtn:hover {{ background-color: {C['error']}; color: white; }}

/* SIDEBAR NAV BUTTONS */
QToolButton#NavBtn {{
    background-color: transparent;
    border: none;
    border-radius: 10px;
    padding: 12px;
    font-size: 14px;
    font-weight: 600;
    text-align: left;
    color: {C['text_dim']};
}}
QToolButton#NavBtn:hover {{ background-color: {C['surface']}; color: {C['text']}; }}
QToolButton#NavBtn:checked {{ background-color: {C['primary']}22; color: {C['primary']}; font-weight: 800; }}

/* INPUTS */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 20px;
    selection-background-color: {C['primary']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {C['primary']}; background-color: {C['bg']}; }}

/* LISTS & SCROLL */
QListWidget {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    outline: none;
}}
QListWidget::item {{ padding: 12px; border-bottom: 1px solid {C['surface']}; }}
QListWidget::item:selected {{ background-color: {C['primary']}33; color: {C['primary_h']}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 4px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {C['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* PROGRESS */
QProgressBar {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    min-height: 14px;
    max-height: 14px;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C['primary']}, stop:1 {C['accent']});
    border-radius: 6px;
}}
"""

class ModernDropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setObjectName("DropZone")
        self._default_style = f"""
            QFrame#DropZone {{ border: 2px dashed {C['border']}; border-radius: 16px; background-color: {C['sidebar']}; }}
        """
        self._hover_style = f"""
            QFrame#DropZone {{ border: 2px dashed {C['primary']}; border-radius: 16px; background-color: {C['primary']}11; }}
        """
        self.setStyleSheet(self._default_style)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary']).pixmap(48, 48))
        self.icon_lbl.setAlignment(Qt.AlignCenter)

        self.text_lbl = QLabel("Drag & Drop Videos Here")
        self.text_lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {C['text']};")
        self.text_lbl.setAlignment(Qt.AlignCenter)

        self.sub_lbl = QLabel("Supported formats: MP4, MKV, MOV, AVI, WEBM")
        self.sub_lbl.setStyleSheet(f"font-size: 12px; color: {C['text_dim']};")
        self.sub_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.text_lbl)
        layout.addWidget(self.sub_lbl)

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
            if u.toLocalFile().lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.wmv'))
        ]
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, e):
        self.files_dropped.emit([])


class LogViewer(QTextEdit):
    def __init__(self, max_lines=1500):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C['input']};
                border: 1px solid {C['border']};
                border-radius: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 15px;
                color: {C['text']};
            }}
        """)

    def append_log(self, msg, level="INFO"):
        if isinstance(msg, tuple): 
            msg = str(msg[0])
            
        color = C['text']
        msg_lower = msg.lower()
        
        # Smart color parsing to highlight worker events nicely
        if "error" in msg_lower or "failed" in msg_lower or "exception" in msg_lower:
            color = C['error']
        elif "success" in msg_lower or "completed" in msg_lower or "finished" in msg_lower:
            color = C['success']
        elif "warning" in msg_lower or "timeout" in msg_lower:
            color = C['warning']
        elif "worker" in msg_lower or "thread" in msg_lower or "batch" in msg_lower:
            color = C['accent']  # Make worker messages stand out
        elif level == "SUCCESS": color = C['success']
        elif level == "ERROR": color = C['error']
        elif level == "WARNING": color = C['warning']

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:{C["text_dim"]}">[{ts}]</span> <span style="color:{color}">{msg}</span>'
        self.append(html)
        self.moveCursor(QTextCursor.End)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VER}")
        self.resize(1150, 780)
        self.config = self._load_config()
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
            "a1d_url": "https://a1d.ai", "log_max_lines": 1000,
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    default.update(json.load(f))
            except: pass
        return default

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

        # App Identity
        title_top = QLabel("A1D")
        title_top.setStyleSheet(f"font-size: 32px; font-weight: 900; color: {C['primary']};")
        title_bot = QLabel("UPSCALER PRO")
        title_bot.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {C['text']}; letter-spacing: 2px;")

        sb_layout.addWidget(title_top)
        sb_layout.addWidget(title_bot)
        sb_layout.addSpacing(30)

        # Nav
        self.btn_queue = self._create_nav_btn("Dashboard", "fa5s.home", 0)
        self.btn_settings = self._create_nav_btn("Settings", "fa5s.cogs", 1)
        self.btn_logs = self._create_nav_btn("Worker Logs", "fa5s.terminal", 2)

        sb_layout.addWidget(self.btn_queue)
        sb_layout.addWidget(self.btn_settings)
        sb_layout.addWidget(self.btn_logs)
        sb_layout.addStretch()

        # Status card
        status_card = QFrame()
        status_card.setStyleSheet(f"QFrame {{ background: {C['surface']}; border-radius: 12px; }}")
        sc_layout = QVBoxLayout(status_card)
        sc_layout.setContentsMargins(15, 12, 15, 12)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {C['text_dim']}; font-size: 16px;")
        self.status_text = QLabel("IDLE MODE")
        self.status_text.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {C['text_dim']};")

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

        # ── CONTENT STACK ───────────────────────────────────────────────
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

    def _create_nav_btn(self, text, icon_name, index):
        btn = QToolButton()
        btn.setText(f"  {text}")
        btn.setIcon(qta.icon(icon_name, color=C['text_dim']))
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

        # Header
        top = QHBoxLayout()
        welcome = QVBoxLayout()
        welcome.setSpacing(4)
        h1 = QLabel("Video Processing Queue")
        h1.setObjectName("H1")
        sub = QLabel("Select or drop video files to begin AI upscaling via SotongHD.")
        sub.setObjectName("Sub")
        welcome.addWidget(h1)
        welcome.addWidget(sub)
        top.addLayout(welcome)
        top.addStretch()

        self.count_badge = QLabel("0 QUEUED")
        self.count_badge.setStyleSheet(
            f"background: {C['primary']}22; color: {C['primary']};"
            f" font-weight: 800; font-size: 11px;"
            f" padding: 6px 14px; border-radius: 15px; border: 1px solid {C['primary']}44;"
        )
        top.addWidget(self.count_badge, alignment=Qt.AlignVCenter)
        layout.addLayout(top)

        # Drop Zone
        self.drop_zone = ModernDropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        layout.addWidget(self.drop_zone)

        # File List
        self.file_list = QListWidget()
        layout.addWidget(self.file_list, stretch=1)

        # Controls
        ctrls = QHBoxLayout()
        self.btn_add = QPushButton(" Browse Media")
        self.btn_add.setIcon(qta.icon("fa5s.folder-plus", color=C['text']))
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

        # Progress Card
        self.prog_card = QFrame()
        self.prog_card.setStyleSheet(f"QFrame {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 12px; padding: 15px; }}")
        self.prog_card.hide()
        p_lay = QVBoxLayout(self.prog_card)
        p_lay.setSpacing(10)

        self.p_label = QLabel("Waiting for initialization...")
        self.p_label.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {C['text']};")
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)

        p_lay.addWidget(self.p_label)
        p_lay.addWidget(self.pbar)
        layout.addWidget(self.prog_card)

        return page

    def _build_settings_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

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
            gl.setContentsMargins(20, 20, 20, 20)
            gl.setSpacing(15)
            
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
            form.setSpacing(12)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            gl.addLayout(form)
            return group, form

        # Group 1: API & Network (Full Settings Restored)
        g_api, f_api = create_group("Authentication & Network", "fa5s.globe")
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setPlaceholderText("fxa_...")
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        
        self.inp_url = QLineEdit()
        self.inp_url.setPlaceholderText("https://a1d.ai")
        
        f_api.addRow("Firefox Relay API Key:", self.inp_api_key)
        f_api.addRow("Target Service URL:", self.inp_url)
        layout.addWidget(g_api)

        # Group 2: Output Options
        g_out, f_out = create_group("Output Engine", "fa5s.video")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["4k", "2k", "1080p"])
        
        self.inp_out_dir = QLineEdit()
        self.inp_out_dir.setPlaceholderText("Leave empty to use Source Folder / OUTPUT")
        btn_browse = QToolButton()
        btn_browse.setIcon(qta.icon("fa5s.folder-open", color=C['text']))
        btn_browse.clicked.connect(self._browse_output)
        
        h_dir = QHBoxLayout()
        h_dir.addWidget(self.inp_out_dir)
        h_dir.addWidget(btn_browse)
        
        f_out.addRow("Target Resolution:", self.combo_quality)
        f_out.addRow("Export Path:", h_dir)
        layout.addWidget(g_out)

        # Group 3: Performance & Advanced (Full Settings Restored)
        g_perf, f_perf = create_group("Workers & Advanced Performance", "fa5s.microchip")
        
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, MAX_PARALLEL_LIMIT)
        
        self.spin_stagger = QSpinBox()
        self.spin_stagger.setRange(0, 120)
        self.spin_stagger.setSuffix(" sec")
        
        self.spin_dl_timeout = QSpinBox()
        self.spin_dl_timeout.setRange(60, 3600)
        self.spin_dl_timeout.setSuffix(" sec")
        
        self.spin_render_timeout = QSpinBox()
        self.spin_render_timeout.setRange(300, 7200)
        self.spin_render_timeout.setSuffix(" sec")
        
        self.chk_headless = QCheckBox("Enable Background Execution (Silent Browser)")
        self.chk_headless.setChecked(True)
        
        f_perf.addRow("Parallel Tasks (Max Workers):", self.spin_workers)
        f_perf.addRow("Batch Stagger Delay:", self.spin_stagger)
        f_perf.addRow("Download Timeout:", self.spin_dl_timeout)
        f_perf.addRow("Processing Timeout:", self.spin_render_timeout)
        f_perf.addRow("", self.chk_headless)
        layout.addWidget(g_perf)

        # Save Button
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

        btn_clear_log = QPushButton(" Clear Logs")
        btn_clear_log.setIcon(qta.icon("fa5s.eraser", color=C['text']))
        btn_clear_log.setMaximumWidth(120)
        header.addWidget(btn_clear_log)

        self.log_viewer = LogViewer(max_lines=2000)
        btn_clear_log.clicked.connect(self.log_viewer.clear)

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
            "processing_hang_timeout": self.spin_render_timeout.value()
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
    app.setStyleSheet(MODERN_STYLES)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
