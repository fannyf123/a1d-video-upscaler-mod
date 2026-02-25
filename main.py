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
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QFont, QColor, QDragEnterEvent, QDropEvent,
    QTextCursor, QPalette, QIcon
)
import qtawesome as qta

from App.background_process import A1DProcessor
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS

CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
APP_NAME    = "A1D Video Upscaler"
APP_VER     = "2.1.0"

# ══ THEME CONFIGURATION ══════════════════════════════════════════════════════
C = {
    "bg":        "#0F172A",  # Slate 900
    "sidebar":   "#1E293B",  # Slate 800
    "surface":   "#334155",  # Slate 700
    "input":     "#0F172A",  # Darker for inputs
    "border":    "#475569",  # Slate 600
    "primary":   "#8B5CF6",  # Violet 500
    "primary_h": "#7C3AED",  # Violet 600
    "secondary": "#3B82F6",  # Blue 500
    "text":      "#F1F5F9",  # Slate 100
    "text_dim":  "#94A3B8",  # Slate 400
    "success":   "#10B981",  # Emerald 500
    "warning":   "#F59E0B",  # Amber 500
    "error":     "#EF4444",  # Red 500
}

MODERN_STYLES = f"""
/* GLOBAL */
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget#MainContent {{ background-color: {C['bg']}; }}
QWidget#Sidebar {{ background-color: {C['sidebar']}; border-right: 1px solid {C['border']}; }}

/* HEADERS */
QLabel#H1 {{ font-size: 24px; font-weight: 800; color: {C['text']}; margin-bottom: 4px; }}
QLabel#H2 {{ font-size: 16px; font-weight: 700; color: {C['text']}; margin-bottom: 8px; }}
QLabel#Sub {{ font-size: 13px; color: {C['text_dim']}; }}

/* CARDS & CONTAINERS */
QFrame.Card {{
    background-color: {C['sidebar']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QFrame.Card:hover {{ border-color: {C['primary']}; }}

/* BUTTONS */
QPushButton {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {C['border']}; border-color: {C['text_dim']}; }}
QPushButton:pressed {{ background-color: {C['bg']}; }}

QPushButton#PrimaryBtn {{
    background-color: {C['primary']};
    border: 1px solid {C['primary_h']};
    color: white;
}}
QPushButton#PrimaryBtn:hover {{ background-color: {C['primary_h']}; }}

QPushButton#DangerBtn {{
    background-color: transparent;
    border: 1px solid {C['error']};
    color: {C['error']};
}}
QPushButton#DangerBtn:hover {{ background-color: {C['error']}; color: white; }}

/* SIDEBAR NAV BUTTONS */
QToolButton.NavBtn {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
    font-weight: 600;
    text-align: left;
    color: {C['text_dim']};
}}
QToolButton.NavBtn:hover {{ background-color: {C['surface']}; color: {C['text']}; }}
QToolButton.NavBtn:checked {{
    background-color: {C['primary']}33;
    color: {C['primary']};
    border-left: 3px solid {C['primary']};
}}

/* INPUTS */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {C['primary']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {C['primary']}; }}

/* LISTS & SCROLL */
QListWidget {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    outline: none;
}}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid {C['surface']}; }}
QListWidget::item:selected {{ background-color: {C['primary']}22; border-left: 2px solid {C['primary']}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['surface']}; border-radius: 4px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {C['border']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* PROGRESS */
QProgressBar {{
    background-color: {C['input']};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {C['primary']};
    border-radius: 4px;
}}
"""

# ══ COMPONENTS ═══════════════════════════════════════════════════════════════

class ModernDropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setObjectName("DropZone")
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2px dashed {C['border']};
                border-radius: 12px;
                background-color: {C['bg']};
            }}
            QFrame#DropZone:hover {{ border-color: {C['primary']}; background-color: {C['primary']}11; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['text_dim']).pixmap(48, 48))
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        
        self.text_lbl = QLabel("Drag & Drop Video Files Here")
        self.text_lbl.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {C['text']};")
        self.text_lbl.setAlignment(Qt.AlignCenter)
        
        self.sub_lbl = QLabel("MP4, MKV, MOV, AVI, WEBM supported")
        self.sub_lbl.setStyleSheet(f"color: {C['text_dim']};")
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.text_lbl)
        layout.addWidget(self.sub_lbl)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(f"""
                QFrame#DropZone {{
                    border: 2px dashed {C['primary']};
                    border-radius: 12px;
                    background-color: {C['primary']}22;
                }}
            """)

    def dragLeaveEvent(self, e):
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2px dashed {C['border']};
                border-radius: 12px;
                background-color: {C['bg']};
            }}
        """)

    def dropEvent(self, e):
        self.dragLeaveEvent(e)
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith(('.mp4','.mkv','.mov','.avi','.webm','.flv','.wmv'))]
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, e):
        self.files_dropped.emit([])

class LogViewer(QTextEdit):
    def __init__(self, max_lines=500):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C['input']};
                border: 1px solid {C['border']};
                border-radius: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                padding: 8px;
            }}
        """)

    def append_log(self, msg, level="INFO"):
        color = C['text']
        if level == "SUCCESS": color = C['success']
        elif level == "WARNING": color = C['warning']
        elif level == "ERROR": color = C['error']
        elif level == "DEBUG": color = C['text_dim']
        
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:{C["text_dim"]}">[{ts}]</span> <span style="color:{color}">{msg}</span>'
        self.append(html)

# ══ MAIN WINDOW ══════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VER}")
        self.resize(1100, 750)
        self.config = self._load_config()
        self._video_paths = []
        self.processor = None
        self._running = False
        
        # UI Setup
        self._setup_ui()
        self._load_settings_to_ui()

    def _load_config(self) -> dict:
        default = {
            "relay_api_key": "", "output_quality": "4k", "output_dir": "",
            "headless": True, "max_workers": DEFAULT_WORKERS,
            "batch_stagger_delay": 15, "initial_download_wait": 120,
            "processing_hang_timeout": 1800, "download_timeout": 600,
            "a1d_url": "https://a1d.ai", "log_max_lines": 500,
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    default.update(json.load(f))
            except: pass
        return default

    def _setup_ui(self):
        # Main Container
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # ── SIDEBAR ──────────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(16, 24, 16, 24)
        sb_layout.setSpacing(8)

        # App Logo/Title
        app_title = QLabel(APP_NAME)
        app_title.setObjectName("H2")
        app_title.setWordWrap(True)
        sb_layout.addWidget(app_title)
        sb_layout.addWidget(QLabel(f"v{APP_VER} • Playwright", objectName="Sub"))
        sb_layout.addSpacing(24)

        # Nav Buttons
        self.btn_queue = self._create_nav_btn("Queue", "fa5s.list-ul", 0)
        self.btn_settings = self._create_nav_btn("Settings", "fa5s.cog", 1)
        self.btn_logs = self._create_nav_btn("Logs", "fa5s.terminal", 2)
        
        sb_layout.addWidget(self.btn_queue)
        sb_layout.addWidget(self.btn_settings)
        sb_layout.addWidget(self.btn_logs)
        sb_layout.addStretch()

        # Status Footer in Sidebar
        self.status_indicator = QLabel("● Idle")
        self.status_indicator.setStyleSheet(f"color: {C['text_dim']}; font-weight: 600;")
        sb_layout.addWidget(self.status_indicator)

        # ── CONTENT STACK ────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setObjectName("MainContent")
        
        # Page 1: Queue
        self.page_queue = self._build_queue_page()
        self.stack.addWidget(self.page_queue)
        
        # Page 2: Settings
        self.page_settings = self._build_settings_page()
        self.stack.addWidget(self.page_settings)
        
        # Page 3: Logs
        self.page_logs = self._build_logs_page()
        self.stack.addWidget(self.page_logs)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        # Default Page
        self.btn_queue.click()

    def _create_nav_btn(self, text, icon_name, index):
        btn = QToolButton()
        btn.setText(f"  {text}")
        btn.setIcon(qta.icon(icon_name, color=C['text_dim']))
        btn.setIconSize(QSize(20, 20))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setClass("NavBtn") # Requires patched PySide or just use objectName/setProperty
        btn.setProperty("class", "NavBtn") # For QSS
        
        # Hack for QSS class selector since it's not standard in Qt5/6 QSS completely
        btn.setObjectName("NavBtn") 
        
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(index))
        btn.clicked.connect(lambda: self._update_nav_style(btn))
        return btn

    def _update_nav_style(self, active_btn):
        # Reset icons to dim
        for b in [self.btn_queue, self.btn_settings, self.btn_logs]:
            icon_name = "fa5s.list-ul" if b == self.btn_queue else "fa5s.cog" if b == self.btn_settings else "fa5s.terminal"
            color = C['primary'] if b.isChecked() else C['text_dim']
            b.setIcon(qta.icon(icon_name, color=color))

    def _build_queue_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("Video Queue", objectName="H1"))
        header.addStretch()
        
        self.file_count_lbl = QLabel("0 files")
        self.file_count_lbl.setStyleSheet(f"color: {C['text_dim']}; font-weight: bold; background: {C['surface']}; padding: 4px 12px; border-radius: 12px;")
        header.addWidget(self.file_count_lbl)
        layout.addLayout(header)

        # Drop Zone
        self.drop_zone = ModernDropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        layout.addWidget(self.drop_zone)

        # List
        self.file_list = QListWidget()
        layout.addWidget(self.file_list, stretch=1)

        # Action Bar
        actions = QHBoxLayout()
        
        self.btn_add = QPushButton(" Add Files")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color=C['text']))
        self.btn_add.clicked.connect(self._browse_files)
        
        self.btn_clear = QPushButton(" Clear")
        self.btn_clear.setIcon(qta.icon("fa5s.trash", color=C['error']))
        self.btn_clear.clicked.connect(self._clear_files)
        
        actions.addWidget(self.btn_add)
        actions.addWidget(self.btn_clear)
        actions.addStretch()
        
        self.btn_start = QPushButton("START PROCESSING")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setMinimumHeight(44)
        self.btn_start.setMinimumWidth(180)
        self.btn_start.setIcon(qta.icon("fa5s.play", color="white"))
        self.btn_start.clicked.connect(self._start)
        
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setMinimumHeight(44)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)

        actions.addWidget(self.btn_start)
        actions.addWidget(self.btn_cancel)
        layout.addLayout(actions)

        # Global Progress
        self.progress_container = QWidget()
        pc_layout = QVBoxLayout(self.progress_container)
        pc_layout.setContentsMargins(0,0,0,0)
        self.lbl_progress = QLabel("Ready")
        self.pbar = QProgressBar()
        pc_layout.addWidget(self.lbl_progress)
        pc_layout.addWidget(self.pbar)
        layout.addWidget(self.progress_container)

        return page

    def _build_settings_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        layout.addWidget(QLabel("Settings", objectName="H1"))

        # Auth Section
        card_auth = QFrame(); card_auth.setProperty("class", "Card"); card_auth.setObjectName("Card")
        l_auth = QVBoxLayout(card_auth)
        l_auth.addWidget(QLabel("Authentication", objectName="H2"))
        
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setPlaceholderText("Firefox Relay API Key (fxa_...)")
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        
        btn_show = QToolButton()
        btn_show.setIcon(qta.icon("fa5s.eye", color=C['text']))
        btn_show.setAutoRaise(True)
        btn_show.pressed.connect(lambda: self.inp_api_key.setEchoMode(QLineEdit.Normal))
        btn_show.released.connect(lambda: self.inp_api_key.setEchoMode(QLineEdit.Password))
        
        h_api = QHBoxLayout()
        h_api.addWidget(self.inp_api_key)
        h_api.addWidget(btn_show)
        
        l_auth.addLayout(h_api)
        layout.addWidget(card_auth)

        # Output Section
        card_out = QFrame(); card_out.setProperty("class", "Card"); card_out.setObjectName("Card")
        l_out = QVBoxLayout(card_out)
        l_out.addWidget(QLabel("Output", objectName="H2"))
        
        grid = QVBoxLayout()
        
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["4k", "2k", "1080p"])
        grid.addWidget(QLabel("Target Resolution"))
        grid.addWidget(self.combo_quality)
        
        self.inp_out_dir = QLineEdit()
        self.inp_out_dir.setPlaceholderText("Default: Source Folder / OUTPUT")
        btn_browse = QToolButton()
        btn_browse.setIcon(qta.icon("fa5s.folder-open", color=C['text']))
        btn_browse.clicked.connect(self._browse_output)
        
        h_dir = QHBoxLayout()
        h_dir.addWidget(self.inp_out_dir)
        h_dir.addWidget(btn_browse)
        
        grid.addWidget(QLabel("Output Directory"))
        grid.addLayout(h_dir)
        
        l_out.addLayout(grid)
        layout.addWidget(card_out)

        # Performance Section
        card_perf = QFrame(); card_perf.setProperty("class", "Card"); card_perf.setObjectName("Card")
        l_perf = QVBoxLayout(card_perf)
        l_perf.addWidget(QLabel("Performance", objectName="H2"))
        
        h_perf = QHBoxLayout()
        
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, MAX_PARALLEL_LIMIT)
        
        self.spin_stagger = QSpinBox()
        self.spin_stagger.setRange(0, 120)
        self.spin_stagger.setSuffix("s")
        
        self.chk_headless = QCheckBox("Headless Mode (No Browser UI)")
        
        v1 = QVBoxLayout(); v1.addWidget(QLabel("Max Workers")); v1.addWidget(self.spin_workers)
        v2 = QVBoxLayout(); v2.addWidget(QLabel("Stagger Delay")); v2.addWidget(self.spin_stagger)
        
        h_perf.addLayout(v1)
        h_perf.addLayout(v2)
        l_perf.addLayout(h_perf)
        l_perf.addWidget(self.chk_headless)
        
        layout.addWidget(card_perf)

        # Advanced
        with_label = lambda w, t: (QVBoxLayout(), w, QLabel(t))
        
        card_adv = QFrame(); card_adv.setProperty("class", "Card"); card_adv.setObjectName("Card")
        l_adv = QVBoxLayout(card_adv)
        l_adv.addWidget(QLabel("Advanced", objectName="H2"))
        
        self.inp_url = QLineEdit()
        self.spin_dl_timeout = QSpinBox()
        self.spin_dl_timeout.setRange(60, 3600)
        self.spin_render_timeout = QSpinBox()
        self.spin_render_timeout.setRange(300, 7200)
        
        l_adv.addWidget(QLabel("Service URL"))
        l_adv.addWidget(self.inp_url)
        
        h_time = QHBoxLayout()
        v_dl = QVBoxLayout(); v_dl.addWidget(QLabel("Download Timeout")); v_dl.addWidget(self.spin_dl_timeout)
        v_rn = QVBoxLayout(); v_rn.addWidget(QLabel("Render Timeout")); v_rn.addWidget(self.spin_render_timeout)
        h_time.addLayout(v_dl); h_time.addLayout(v_rn)
        l_adv.addLayout(h_time)
        
        layout.addWidget(card_adv)

        # Save Button
        btn_save = QPushButton("Save Settings")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self._save_config_ui)
        layout.addWidget(btn_save)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        return scroll

    def _build_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("System Logs", objectName="H1"))
        
        btn_copy = QPushButton("Copy")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.log_viewer.toPlainText()))
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(lambda: self.log_viewer.clear())
        
        header.addStretch()
        header.addWidget(btn_copy)
        header.addWidget(btn_clear)
        layout.addLayout(header)
        
        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer)
        return page

    # ── LOGIC ────────────────────────────────────────────────────────────

    def _load_settings_to_ui(self):
        c = self.config
        self.inp_api_key.setText(c.get("relay_api_key", ""))
        self.combo_quality.setCurrentText(c.get("output_quality", "4k"))
        self.inp_out_dir.setText(c.get("output_dir", ""))
        self.spin_workers.setValue(c.get("max_workers", DEFAULT_WORKERS))
        self.spin_stagger.setValue(c.get("batch_stagger_delay", 15))
        self.chk_headless.setChecked(c.get("headless", True))
        self.inp_url.setText(c.get("a1d_url", "https://a1d.ai"))
        self.spin_dl_timeout.setValue(c.get("download_timeout", 600))
        self.spin_render_timeout.setValue(c.get("processing_hang_timeout", 1800))

    def _save_config_ui(self):
        self.config.update({
            "relay_api_key": self.inp_api_key.text().strip(),
            "output_quality": self.combo_quality.currentText().lower(),
            "output_dir": self.inp_out_dir.text().strip(),
            "max_workers": self.spin_workers.value(),
            "batch_stagger_delay": self.spin_stagger.value(),
            "headless": self.chk_headless.isChecked(),
            "a1d_url": self.inp_url.text().strip(),
            "download_timeout": self.spin_dl_timeout.value(),
            "processing_hang_timeout": self.spin_render_timeout.value()
        })
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            self.log_viewer.append_log("Settings saved successfully", "SUCCESS")
        except Exception as e:
            self.log_viewer.append_log(f"Failed to save settings: {e}", "ERROR")

    def _on_drop(self, paths):
        if not paths: self._browse_files(); return
        self._add_files(paths)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files", "", 
            "Videos (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv)")
        self._add_files(files)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d: self.inp_out_dir.setText(d)

    def _add_files(self, paths):
        for p in paths:
            if p not in self._video_paths:
                self._video_paths.append(p)
                item = QListWidgetItem(os.path.basename(p))
                item.setToolTip(p)
                item.setIcon(qta.icon("fa5s.file-video", color=C['primary']))
                self.file_list.addItem(item)
        self.file_count_lbl.setText(f"{len(self._video_paths)} files")
        self.log_viewer.append_log(f"Added {len(paths)} files to queue")

    def _clear_files(self):
        self._video_paths.clear()
        self.file_list.clear()
        self.file_count_lbl.setText("0 files")

    def _start(self):
        if not self._video_paths:
            self.log_viewer.append_log("Queue is empty!", "WARNING")
            return
        if not self.inp_api_key.text().strip():
            self.log_viewer.append_log("API Key is missing!", "ERROR")
            self.btn_settings.click()
            self.inp_api_key.setFocus()
            return
            
        self._save_config_ui()
        self._set_running(True)
        self.log_viewer.append_log("Starting batch process...", "INFO")
        
        cfg = dict(self.config)
        if len(self._video_paths) == 1:
            self.processor = A1DProcessor(_PROJECT_ROOT, self._video_paths[0], cfg)
        else:
            self.processor = BatchProcessor(_PROJECT_ROOT, self._video_paths, cfg)
            
        self.processor.log_signal.connect(self.log_viewer.append_log)
        self.processor.progress_signal.connect(self._on_progress)
        self.processor.finished_signal.connect(self._on_finished)
        self.processor.start()

    def _cancel(self):
        if self.processor:
            self.processor.cancel()
            self.log_viewer.append_log("Cancelling process...", "WARNING")

    def _set_running(self, running):
        self._running = running
        self.btn_start.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        self.btn_add.setEnabled(not running)
        self.btn_clear.setEnabled(not running)
        self.drop_zone.setVisible(not running)
        
        status = "● Running..." if running else "● Idle"
        color = C['success'] if running else C['text_dim']
        self.status_indicator.setText(status)
        self.status_indicator.setStyleSheet(f"color: {color}; font-weight: 600;")

    def _on_progress(self, pct, msg):
        self.pbar.setValue(pct)
        self.lbl_progress.setText(msg)

    def _on_finished(self, ok, msg):
        self._set_running(False)
        level = "SUCCESS" if ok else "ERROR"
        self.log_viewer.append_log(msg, level)
        if ok: self.pbar.setValue(100)
        self.lbl_progress.setText("Completed" if ok else "Failed")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VER)
    app.setStyle("Fusion")
    
    # Apply stylesheet
    app.setStyleSheet(MODERN_STYLES)
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
