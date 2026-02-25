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
APP_VER     = "2.2.0"

# ══ THEME CONFIGURATION ══════════════════════════════════════════════════════
C = {
    "bg":        "#0B0F19",  # Deep Midnight
    "sidebar":   "#111827",  # Darker Slate
    "surface":   "#1F2937",  # Slate 800
    "input":     "#030712",  # Near Black
    "border":    "#374151",  # Slate 700
    "primary":   "#C026D3",  # Fuchsia 600 (Cyberpunk vibe)
    "primary_h": "#E879F9",  # Fuchsia 400
    "accent":    "#2DD4BF",  # Teal 400
    "text":      "#F9FAFB",  # Gray 50
    "text_dim":  "#9CA3AF",  # Gray 400
    "success":   "#10B981",  # Emerald 500
    "warning":   "#F59E0B",  # Amber 500
    "error":     "#EF4444",  # Red 500
}

MODERN_STYLES = f"""
/* GLOBAL */
* {{ font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget#MainContent {{ background-color: {C['bg']}; }}
QWidget#Sidebar {{ background-color: {C['sidebar']}; border-right: 1px solid {C['border']}; }}

/* HEADERS */
QLabel#H1 {{ font-size: 28px; font-weight: 800; color: {C['text']}; letter-spacing: -0.5px; }}
QLabel#H2 {{ font-size: 16px; font-weight: 700; color: {C['text']}; margin-top: 10px; }}
QLabel#Sub {{ font-size: 12px; color: {C['text_dim']}; font-weight: 500; }}

/* CARDS & CONTAINERS */
QFrame.Card {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 16px;
}}
QFrame.Card:hover {{ border-color: {C['primary']}; }}

/* BUTTONS */
QPushButton {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QPushButton:hover {{ background-color: {C['border']}; border-color: {C['text_dim']}; }}
QPushButton:pressed {{ background-color: {C['bg']}; }}

QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['primary']}, stop:1 #7C3AED);
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
QToolButton.NavBtn {{
    background-color: transparent;
    border: none;
    border-radius: 12px;
    padding: 12px;
    font-size: 14px;
    font-weight: 600;
    text-align: left;
    color: {C['text_dim']};
    margin-bottom: 4px;
}}
QToolButton.NavBtn:hover {{ background-color: {C['surface']}CC; color: {C['text']}; }}
QToolButton.NavBtn:checked {{
    background-color: {C['primary']}22;
    color: {C['primary']};
    font-weight: 800;
}}

/* INPUTS */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 10px;
    selection-background-color: {C['primary']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {C['primary']}; }}

/* LISTS & SCROLL */
QListWidget {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 12px;
    outline: none;
}}
QListWidget::item {{ 
    padding: 12px; 
    border-bottom: 1px solid {C['surface']}; 
    border-radius: 8px;
    margin: 4px;
}}
QListWidget::item:selected {{ background-color: {C['primary']}33; color: {C['primary_h']}; }}

QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {C['primary']}88; }}

/* PROGRESS */
QProgressBar {{
    background-color: {C['input']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    height: 12px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C['primary']}, stop:1 {C['accent']});
    border-radius: 8px;
}}
"""

class ModernDropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(160)
        self.setObjectName("DropZone")
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2px dashed {C['border']};
                border-radius: 20px;
                background-color: {C['sidebar']};
            }}
            QFrame#DropZone:hover {{ border-color: {C['primary']}; background-color: {C['primary']}11; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(qta.icon("fa5s.film", color=C['primary']).pixmap(64, 64))
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        
        self.text_lbl = QLabel("Drop Videos to Upscale")
        self.text_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {C['text']};")
        self.text_lbl.setAlignment(Qt.AlignCenter)
        
        self.sub_lbl = QLabel("High-Quality AI Enhancement Engine")
        self.sub_lbl.setStyleSheet(f"color: {C['text_dim']}; font-weight: 500;")
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.text_lbl)
        layout.addWidget(self.sub_lbl)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(self.styleSheet().replace(C['border'], C['primary']))

    def dragLeaveEvent(self, e):
        self.setStyleSheet(self.styleSheet().replace(C['primary'], C['border']))

    def dropEvent(self, e):
        self.dragLeaveEvent(e)
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith(('.mp4','.mkv','.mov','.avi','.webm','.flv','.wmv'))]
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, e):
        self.files_dropped.emit([])

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VER}")
        self.resize(1200, 800)
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
            "a1d_url": "https://a1d.ai", "log_max_lines": 500,
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
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # ── SIDEBAR ──────────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(20, 40, 20, 30)
        sb_layout.setSpacing(10)

        # App Identity
        logo_container = QVBoxLayout()
        logo_container.setSpacing(5)
        
        title_top = QLabel("A1D")
        title_top.setStyleSheet(f"font-size: 32px; font-weight: 900; color: {C['primary']}; letter-spacing: 2px;")
        title_bot = QLabel("UPSCALER PRO")
        title_bot.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {C['text']}; letter-spacing: 4px; margin-bottom: 20px;")
        
        logo_container.addWidget(title_top)
        logo_container.addWidget(title_bot)
        sb_layout.addLayout(logo_container)
        sb_layout.addSpacing(20)

        # Nav
        self.btn_queue = self._create_nav_btn("Dashboard", "fa5s.th-large", 0)
        self.btn_settings = self._create_nav_btn("Configuration", "fa5s.sliders-h", 1)
        self.btn_logs = self._create_nav_btn("Activity Logs", "fa5s.terminal", 2)
        
        sb_layout.addWidget(self.btn_queue)
        sb_layout.addWidget(self.btn_settings)
        sb_layout.addWidget(self.btn_logs)
        sb_layout.addStretch()

        # Version & Status
        status_card = QFrame()
        status_card.setStyleSheet(f"background: {C['surface']}; border-radius: 12px; padding: 10px;")
        sc_layout = QVBoxLayout(status_card)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {C['text_dim']}; font-size: 18px;")
        self.status_text = QLabel("IDLE MODE")
        self.status_text.setStyleSheet(f"font-weight: 800; font-size: 10px; color: {C['text_dim']};")
        
        row = QHBoxLayout()
        row.addWidget(self.status_dot)
        row.addWidget(self.status_text)
        row.addStretch()
        sc_layout.addLayout(row)
        
        sb_layout.addWidget(status_card)
        sb_layout.addWidget(QLabel(f"v{APP_VER}", alignment=Qt.AlignCenter, objectName="Sub"))

        # ── CONTENT STACK ────────────────────────────────────────────────────
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
        btn.setIconSize(QSize(22, 22))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setProperty("class", "NavBtn")
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(index))
        btn.clicked.connect(lambda: self._update_nav_style())
        return btn

    def _update_nav_style(self):
        buttons = [(self.btn_queue, "fa5s.th-large"), 
                   (self.btn_settings, "fa5s.sliders-h"), 
                   (self.btn_logs, "fa5s.terminal")]
        for btn, icon in buttons:
            color = C['primary'] if btn.isChecked() else C['text_dim']
            btn.setIcon(qta.icon(icon, color=color))

    def _build_queue_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        # Welcome Header
        top = QHBoxLayout()
        welcome = QVBoxLayout()
        h1 = QLabel("Video Enhancement", objectName="H1")
        sub = QLabel("Select or drop your video files to begin AI upscaling process.")
        sub.setObjectName("Sub")
        welcome.addWidget(h1)
        welcome.addWidget(sub)
        top.addLayout(welcome)
        top.addStretch()
        
        self.count_badge = QLabel("0 FILES QUEUED")
        self.count_badge.setStyleSheet(f"background: {C['primary']}22; color: {C['primary']}; font-weight: 800; padding: 8px 16px; border-radius: 20px; border: 1px solid {C['primary']}44;")
        top.addWidget(self.count_badge, alignment=Qt.AlignVCenter)
        layout.addLayout(top)

        # Drop Zone
        self.drop_zone = ModernDropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        layout.addWidget(self.drop_zone)

        # File List with custom styling
        self.file_list = QListWidget()
        layout.addWidget(self.file_list, stretch=1)

        # Controls
        ctrls = QHBoxLayout()
        self.btn_add = QPushButton(" Browse Media")
        self.btn_add.setIcon(qta.icon("fa5s.plus-circle", color=C['text']))
        self.btn_add.clicked.connect(self._browse_files)
        
        self.btn_clear = QPushButton(" Clear All")
        self.btn_clear.setIcon(qta.icon("fa5s.trash-alt", color=C['error']))
        self.btn_clear.clicked.connect(self._clear_files)
        
        ctrls.addWidget(self.btn_add)
        ctrls.addWidget(self.btn_clear)
        ctrls.addStretch()
        
        self.btn_start = QPushButton("INITIALIZE UPSCALING")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setMinimumHeight(54)
        self.btn_start.setMinimumWidth(240)
        self.btn_start.setIcon(qta.icon("fa5s.bolt", color="white"))
        self.btn_start.clicked.connect(self._start)
        
        self.btn_cancel = QPushButton("ABORT")
        self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setMinimumHeight(54)
        self.btn_cancel.setMinimumWidth(120)
        self.btn_cancel.hide()
        self.btn_cancel.clicked.connect(self._cancel)

        ctrls.addWidget(self.btn_start)
        ctrls.addWidget(self.btn_cancel)
        layout.addLayout(ctrls)

        # Progress Section
        self.prog_card = QFrame()
        self.prog_card.setStyleSheet(f"background: {C['sidebar']}; border-radius: 15px; padding: 20px;")
        self.prog_card.hide()
        p_lay = QVBoxLayout(self.prog_card)
        
        self.p_label = QLabel("Waiting for initialization...")
        self.p_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        self.pbar = QProgressBar()
        
        p_lay.addWidget(self.p_label)
        p_lay.addWidget(self.pbar)
        layout.addWidget(self.prog_card)

        return page

    def _build_settings_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background: transparent;")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        layout.addWidget(QLabel("Configuration", objectName="H1"))

        def create_group(title, icon):
            group = QFrame(); group.setProperty("class", "Card"); group.setObjectName("Card")
            gl = QVBoxLayout(group)
            gl.setContentsMargins(25, 25, 25, 25)
            gl.setSpacing(15)
            header = QHBoxLayout()
            lbl = QLabel(title, objectName="H2")
            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon(icon, color=C['primary']).pixmap(20, 20))
            header.addWidget(icon_lbl); header.addWidget(lbl); header.addStretch()
            gl.addLayout(header)
            return group, gl

        # Group 1: API
        g_api, l_api = create_group("Authentication", "fa5s.key")
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setPlaceholderText("Firefox Relay API Key")
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        l_api.addWidget(QLabel("Media Cloud API Key", objectName="Sub"))
        l_api.addWidget(self.inp_api_key)
        layout.addWidget(g_api)

        # Group 2: Output
        g_out, l_out = create_group("Engine Parameters", "fa5s.cog")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["4k", "2k", "1080p"])
        
        self.inp_out_dir = QLineEdit()
        self.inp_out_dir.setPlaceholderText("Source Folder / OUTPUT")
        
        l_out.addWidget(QLabel("Target Resolution", objectName="Sub"))
        l_out.addWidget(self.combo_quality)
        l_out.addWidget(QLabel("Export Path", objectName="Sub"))
        l_out.addWidget(self.inp_out_dir)
        layout.addWidget(g_out)

        # Group 3: Performance
        g_perf, l_perf = create_group("Performance & Workers", "fa5s.microchip")
        row = QHBoxLayout()
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, MAX_PARALLEL_LIMIT)
        self.chk_headless = QCheckBox("Background Execution (Silent Mode)")
        self.chk_headless.setChecked(True)
        
        v1 = QVBoxLayout(); v1.addWidget(QLabel("Parallel Tasks", objectName="Sub")); v1.addWidget(self.spin_workers)
        row.addLayout(v1); row.addStretch()
        l_perf.addLayout(row)
        l_perf.addWidget(self.chk_headless)
        layout.addWidget(g_perf)

        btn_save = QPushButton("Apply Configurations")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setMinimumHeight(50)
        btn_save.clicked.connect(self._save_config_ui)
        layout.addWidget(btn_save)
        
        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("Engine Logs", objectName="H1"))
        header.addStretch()
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet(f"background: {C['input']}; border: 1px solid {C['border']}; border-radius: 12px; font-family: 'Consolas'; padding: 15px;")
        
        layout.addLayout(header)
        layout.addWidget(self.log_viewer)
        return page

    # ── LOGIC ────────────────────────────────────────────────────────────

    def _load_settings_to_ui(self):
        c = self.config
        self.inp_api_key.setText(c.get("relay_api_key", ""))
        self.combo_quality.setCurrentText(c.get("output_quality", "4k"))
        self.inp_out_dir.setText(c.get("output_dir", ""))
        self.spin_workers.setValue(c.get("max_workers", DEFAULT_WORKERS))
        self.chk_headless.setChecked(c.get("headless", True))

    def _save_config_ui(self):
        self.config.update({
            "relay_api_key": self.inp_api_key.text().strip(),
            "output_quality": self.combo_quality.currentText().lower(),
            "output_dir": self.inp_out_dir.text().strip(),
            "max_workers": self.spin_workers.value(),
            "headless": self.chk_headless.isChecked()
        })
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            self.log_viewer.append("✓ Settings updated.")
        except: pass

    def _on_drop(self, paths):
        if not paths: self._browse_files(); return
        self._add_files(paths)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "", "Videos (*.mp4 *.mkv *.mov *.avi *.webm)")
        self._add_files(files)

    def _add_files(self, paths):
        for p in paths:
            if p not in self._video_paths:
                self._video_paths.append(p)
                item = QListWidgetItem(f" 🎬  {os.path.basename(p)}")
                self.file_list.addItem(item)
        self.count_badge.setText(f"{len(self._video_paths)} FILES QUEUED")

    def _clear_files(self):
        self._video_paths.clear()
        self.file_list.clear()
        self.count_badge.setText("0 FILES QUEUED")

    def _start(self):
        if not self._video_paths or not self.inp_api_key.text(): return
        self._set_running(True)
        cfg = dict(self.config)
        self.processor = BatchProcessor(_PROJECT_ROOT, self._video_paths, cfg) if len(self._video_paths) > 1 else A1DProcessor(_PROJECT_ROOT, self._video_paths[0], cfg)
        self.processor.log_signal.connect(lambda m: self.log_viewer.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {m}"))
        self.processor.progress_signal.connect(self._on_progress)
        self.processor.finished_signal.connect(self._on_finished)
        self.processor.start()

    def _set_running(self, running):
        self._running = running
        self.btn_start.setVisible(not running)
        self.btn_cancel.setVisible(running)
        self.prog_card.setVisible(running)
        self.status_dot.setStyleSheet(f"color: {C['success'] if running else C['text_dim']}; font-size: 18px;")
        self.status_text.setText("PROCESSING..." if running else "IDLE MODE")

    def _on_progress(self, pct, msg):
        self.pbar.setValue(pct)
        self.p_label.setText(msg)

    def _on_finished(self, ok, msg):
        self._set_running(False)
        self.p_label.setText("Batch Completed" if ok else f"Error: {msg}")

    def _cancel(self):
        if self.processor: self.processor.cancel()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLES)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
