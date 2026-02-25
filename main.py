import sys
import os
import json
import datetime
import shutil
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
    QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QTextCursor
import qtawesome as qta

from App.background_process import A1DProcessor
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS

CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
APP_NAME    = "A1D Video Upscaler"
APP_VER     = "2.5.0"

# ══════════════════════════════════════════════════════════════════════════════
#  MODERN PALETTES — HIGH CONTRAST
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        "bg":        "#0A0C10",
        "sidebar":   "#12151C",
        "surface":   "#1C212B",
        "input":     "#0A0C10",
        "border":    "#2D333B",
        "primary":   "#A78BFA",
        "primary_h": "#C4B5FD",
        "accent":    "#60A5FA",
        "text":      "#FFFFFF",   # Pure white for high visibility
        "text_dim":  "#F1F5F9",   # Very bright grey
        "text_muted":"#94A3B8",   # Legible muted text
        "success":   "#34D399",
        "warning":   "#FBBF24",
        "error":     "#F87171",
        "log_bg":    "#05070A",
    },
    "light": {
        "bg":        "#F8FAFC",
        "sidebar":   "#FFFFFF",
        "surface":   "#FFFFFF",
        "input":     "#F1F5F9",
        "border":    "#E2E8F0",
        "primary":   "#7C3AED",
        "primary_h": "#6D28D9",
        "accent":    "#2563EB",
        "text":      "#0F172A",   # Deep black
        "text_dim":  "#1E293B",
        "text_muted":"#64748B",
        "success":   "#059669",
        "warning":   "#D97706",
        "error":     "#DC2626",
        "log_bg":    "#FFFFFF",
    },
}

C = dict(THEMES["dark"])

def build_stylesheet(c: dict) -> str:
    return f"""
QWidget {{ color: {c['text']}; outline: none; font-family: 'Inter', 'Segoe UI', sans-serif; }}
QMainWindow, QWidget#MainContent {{ background-color: {c['bg']}; }}
QWidget#Sidebar {{ background-color: {c['sidebar']}; border-right: 1px solid {c['border']}; }}

QLabel#H1  {{ font-size: 26px; font-weight: 900; color: {c['text']}; }}
QLabel#H2  {{ font-size: 16px; font-weight: 800; color: {c['text']}; }}
QLabel#Sub {{ font-size: 13px; color: {c['text_muted']}; font-weight: 600; }}
QLabel     {{ color: {c['text_dim']}; font-weight: 500; }}

QFrame#Card {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#Card:hover {{ border-color: {c['primary']}; }}

QPushButton {{
    background-color: {c['surface']}; border: 1px solid {c['border']};
    border-radius: 10px; padding: 10px 20px; font-weight: 800; color: {c['text']};
}}
QPushButton:hover  {{ background-color: {c['border']}; border-color: {c['primary']}; }}
QPushButton:pressed{{ background-color: {c['bg']}; }}

QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['primary']}, stop:1 {c['primary_h']});
    border: none; color: #FFFFFF; font-size: 14px;
}}
QPushButton#DangerBtn {{ background-color: transparent; border: 2px solid {c['error']}; color: {c['error']}; font-weight: 900; }}
QPushButton#DangerBtn:hover {{ background-color: {c['error']}; color: #FFFFFF; }}

QPushButton#ThemeBtn {{
    background-color: transparent; border: 1.5px solid {c['border']}; border-radius: 20px;
    padding: 8px 16px; font-size: 12px; font-weight: 800; color: {c['text_dim']};
}}

QToolButton#NavBtn {{
    background-color: transparent; border: none; border-radius: 12px; padding: 14px;
    font-size: 14px; font-weight: 700; text-align: left; color: {c['text_muted']};
}}
QToolButton#NavBtn:hover   {{ background-color: {c['surface']}; color: {c['text']}; }}
QToolButton#NavBtn:checked {{ background-color: {c['primary']}22; color: {c['primary']}; font-weight: 900; }}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {c['input']}; border: 1.5px solid {c['border']}; border-radius: 8px;
    padding: 10px 14px; min-height: 24px; color: {c['text']}; font-weight: 600;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {c['primary']}; }}

QCheckBox {{ color: {c['text_dim']}; spacing: 10px; font-weight: 600; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border: 2px solid {c['border']}; border-radius: 6px; }}
QCheckBox::indicator:checked {{ background: {c['primary']}; border-color: {c['primary']}; }}

QListWidget {{
    background-color: {c['input']}; border: 1.5px solid {c['border']};
    border-radius: 12px; outline: none; color: {c['text_dim']}; font-weight: 600;
}}
QListWidget::item {{ padding: 14px; border-bottom: 1px solid {c['border']}; }}
QListWidget::item:selected {{ background-color: {c['primary']}15; color: {c['primary']}; }}

QProgressBar {{
    background-color: {c['input']}; border: 1.5px solid {c['border']};
    border-radius: 10px; min-height: 18px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['primary']}, stop:1 {c['accent']});
    border-radius: 8px;
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
        self.setMinimumHeight(160)
        self.setObjectName("DropZone")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.icon_lbl = QLabel()
        self.text_lbl = QLabel("Drag & Drop Video Files")
        self.sub_lbl  = QLabel("MP4, MKV, MOV, AVI, WEBM, FLV")
        for w in [self.icon_lbl, self.text_lbl, self.sub_lbl]:
            w.setAlignment(Qt.AlignCenter)
            layout.addWidget(w)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(f"QFrame#DropZone {{ border: 2.5px dashed {C['border']}; border-radius: 20px; background-color: {C['surface']}; }}")
        self.icon_lbl.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['primary']).pixmap(50, 50))
        self.text_lbl.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {C['text']}; margin-top: 10px;")
        self.sub_lbl.setStyleSheet(f"font-size: 13px; color: {C['text_muted']}; font-weight: 600;")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(f"QFrame#DropZone {{ border: 2.5px dashed {C['primary']}; border-radius: 20px; background-color: {C['primary']}10; }}")
    def dragLeaveEvent(self, e): self.refresh_theme()
    def dropEvent(self, e):
        self.refresh_theme()
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile().lower().endswith(('.mp4','.mkv','.mov','.avi','.webm','.flv'))]
        if paths: self.files_dropped.emit(paths)

class LogViewer(QTextEdit):
    def __init__(self, max_lines=5000):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C['log_bg']}; border: 2px solid {C['border']};
                border-radius: 14px; font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 13px; padding: 18px; color: {C['text_dim']}; line-height: 1.5;
            }}
        """)

    def append_log(self, msg, level="INFO"):
        if isinstance(msg, tuple): msg = str(msg[0])
        ml = msg.lower()
        if   "error" in ml or "failed" in ml:      color = C['error']
        elif "success" in ml or "completed" in ml: color = C['success']
        elif "warning" in ml or "timeout" in ml:   color = C['warning']
        elif "worker" in ml or "batch" in ml:      color = C['accent']
        else:                                      color = C['text']

        ts   = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:{C["text_muted"]}; font-weight:bold;">[{ts}]</span> <span style="color:{color}; font-weight:600;">{msg}</span>'
        self.append(html)
        self.moveCursor(QTextCursor.End)

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VER}")
        self.resize(1200, 850)
        self.config = self._load_config()
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
                with open(CONFIG_PATH, 'r') as f: default.update(json.load(f))
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
        QApplication.instance().setStyleSheet(build_stylesheet(C))
        self._refresh_ui_elements()
        ico = "fa5s.sun" if new_theme == "dark" else "fa5s.moon"
        lbl = "Light Mode" if new_theme == "dark" else "Dark Mode"
        self.btn_theme.setIcon(qta.icon(ico, color=C['text_dim']))
        self.btn_theme.setText(f" {lbl}")
        self._save_config_ui(silent=True)

    def _refresh_ui_elements(self):
        self.title_top.setStyleSheet(f"font-size: 36px; font-weight: 1000; color: {C['primary']};")
        self.title_bot.setStyleSheet(f"font-size: 14px; font-weight: 900; color: {C['text']}; letter-spacing: 3px;")
        self.count_badge.setStyleSheet(f"background: {C['primary']}25; color: {C['primary']}; font-weight: 900; font-size: 12px; padding: 7px 16px; border-radius: 18px;")
        self.drop_zone.refresh_theme()
        self.log_viewer.refresh_theme()
        self._update_nav_style()
        self._set_running(self._running)

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── SIDEBAR ───────────────────────────────────────────────────
        sidebar = QWidget(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(260)
        sb_layout = QVBoxLayout(sidebar); sb_layout.setContentsMargins(25, 45, 25, 30); sb_layout.setSpacing(12)

        self.title_top = QLabel("A1D")
        self.title_bot = QLabel("UPSCALER ULTRA")
        sb_layout.addWidget(self.title_top); sb_layout.addWidget(self.title_bot)
        sb_layout.addSpacing(40)

        self.btn_queue    = self._create_nav_btn("DASHBOARD", "fa5s.layer-group", 0)
        self.btn_settings = self._create_nav_btn("SETTINGS",  "fa5s.sliders-h",  1)
        self.btn_logs     = self._create_nav_btn("SYSTEM LOG", "fa5s.terminal",   2)
        sb_layout.addWidget(self.btn_queue); sb_layout.addWidget(self.btn_settings); sb_layout.addWidget(self.btn_logs)
        sb_layout.addStretch()

        self.btn_theme = QPushButton(); self.btn_theme.setObjectName("ThemeBtn")
        self.btn_theme.clicked.connect(self._toggle_theme); sb_layout.addWidget(self.btn_theme)
        sb_layout.addSpacing(15)

        status_card = QFrame(); status_card.setObjectName("Card")
        sc_layout = QVBoxLayout(status_card); sc_layout.setContentsMargins(18, 15, 18, 15)
        self.status_dot = QLabel("●"); self.status_text = QLabel("SYSTEM IDLE"); self.status_text.setObjectName("Sub")
        row = QHBoxLayout(); row.addWidget(self.status_dot); row.addWidget(self.status_text); row.addStretch()
        sc_layout.addLayout(row); sb_layout.addWidget(status_card)
        
        ver_lbl = QLabel(f"Version {APP_VER}"); ver_lbl.setObjectName("Sub"); ver_lbl.setAlignment(Qt.AlignCenter)
        sb_layout.addWidget(ver_lbl)

        # ── MAIN STACK ────────────────────────────────────────────────
        self.stack = QStackedWidget(); self.stack.setObjectName("MainContent")
        self.stack.addWidget(self._build_queue_page())
        self.stack.addWidget(self._build_settings_page())
        self.stack.addWidget(self._build_logs_page())

        main_layout.addWidget(sidebar); main_layout.addWidget(self.stack)
        self.btn_queue.setChecked(True); self._refresh_ui_elements()

    def _create_nav_btn(self, text, icon, index):
        btn = QToolButton(); btn.setText(f"  {text}"); btn.setIconSize(QSize(22, 22))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setCheckable(True)
        btn.setAutoExclusive(True); btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setObjectName("NavBtn")
        btn.clicked.connect(lambda ch, i=index: self.stack.setCurrentIndex(i))
        btn.clicked.connect(self._update_nav_style)
        return btn

    def _update_nav_style(self):
        for btn, icon in [(self.btn_queue, "fa5s.layer-group"), (self.btn_settings, "fa5s.sliders-h"), (self.btn_logs, "fa5s.terminal")]:
            btn.setIcon(qta.icon(icon, color=C['primary'] if btn.isChecked() else C['text_muted']))

    def _build_queue_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(45, 45, 45, 45); layout.setSpacing(25)
        header = QHBoxLayout()
        vbox = QVBoxLayout(); h1 = QLabel("Upscale Manager"); h1.setObjectName("H1")
        sub = QLabel("Queue your videos for high-performance AI enhancement."); sub.setObjectName("Sub")
        vbox.addWidget(h1); vbox.addWidget(sub); header.addLayout(vbox); header.addStretch()
        self.count_badge = QLabel("0 QUEUED"); header.addWidget(self.count_badge, alignment=Qt.AlignVCenter)
        layout.addLayout(header)

        self.drop_zone = ModernDropZone(); self.drop_zone.files_dropped.connect(self._on_drop); layout.addWidget(self.drop_zone)
        self.file_list = QListWidget(); layout.addWidget(self.file_list, stretch=1)

        ctrls = QHBoxLayout()
        btn_add = QPushButton(" ADD VIDEO"); btn_add.setIcon(qta.icon("fa5s.plus-circle", color=C['text']))
        btn_add.clicked.connect(self._browse_files)
        btn_clr = QPushButton(" CLEAR ALL"); btn_clr.setIcon(qta.icon("fa5s.trash-alt", color=C['error']))
        btn_clr.clicked.connect(self._clear_files)
        ctrls.addWidget(btn_add); ctrls.addWidget(btn_clr); ctrls.addStretch()

        self.btn_start = QPushButton(" RUN BATCH UPSCALER"); self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setMinimumSize(260, 55); self.btn_start.setIcon(qta.icon("fa5s.rocket", color="white"))
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel = QPushButton(" FORCE STOP"); self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setMinimumSize(140, 55); self.btn_cancel.hide(); self.btn_cancel.clicked.connect(self._cancel)
        ctrls.addWidget(self.btn_start); ctrls.addWidget(self.btn_cancel); layout.addLayout(ctrls)

        self.prog_card = QFrame(); self.prog_card.setObjectName("Card"); self.prog_card.hide()
        p_lay = QVBoxLayout(self.prog_card); self.p_label = QLabel("Initializing..."); self.pbar = QProgressBar()
        p_lay.addWidget(self.p_label); p_lay.addWidget(self.pbar); layout.addWidget(self.prog_card)
        return page

    def _build_settings_page(self):
        page = QWidget(); scroll = QScrollArea(); scroll.setWidgetResizable(True); content = QWidget()
        layout = QVBoxLayout(content); layout.setContentsMargins(45, 45, 45, 45); layout.setSpacing(30)
        h1 = QLabel("Advanced Configuration"); h1.setObjectName("H1"); layout.addWidget(h1)

        def group(title, icon):
            f = QFrame(); f.setObjectName("Card"); fl = QVBoxLayout(f)
            h = QHBoxLayout(); i_lbl = QLabel(); i_lbl.setPixmap(qta.icon(icon, color=C['primary']).pixmap(24,24))
            l = QLabel(title); l.setObjectName("H2"); h.addWidget(i_lbl); h.addWidget(l); h.addStretch()
            fl.addLayout(h); form = QFormLayout(); form.setSpacing(15); fl.addLayout(form); return f, form

        g1, f1 = group("SotongHD API & Auth", "fa5s.key")
        self.i_api = QLineEdit(); self.i_api.setEchoMode(QLineEdit.Password); self.i_url = QLineEdit()
        f1.addRow("Firefox Relay Key:", self.i_api); f1.addRow("Service URL:", self.i_url); layout.addWidget(g1)

        g2, f2 = group("Processing Engine", "fa5s.cog")
        self.c_qual = QComboBox(); self.c_qual.addItems(["4k", "2k", "1080p"])
        self.i_out = QLineEdit(); self.b_brw = QToolButton(); self.b_brw.setIcon(qta.icon("fa5s.folder-open", color=C['text']))
        self.b_brw.clicked.connect(self._browse_output); h_out = QHBoxLayout(); h_out.addWidget(self.i_out); h_out.addWidget(self.b_brw)
        self.s_wait = QSpinBox(); self.s_wait.setRange(0, 600); self.s_wait.setSuffix(" sec")
        f2.addRow("Upscale Resolution:", self.c_qual); f2.addRow("Output Directory:", h_out); f2.addRow("Initial Render Wait:", self.s_wait); layout.addWidget(g2)

        g3, f3 = group("Performance & Reliability", "fa5s.microchip")
        self.s_work = QSpinBox(); self.s_work.setRange(1, 5); self.s_stagger = QSpinBox(); self.s_stagger.setSuffix(" sec")
        self.s_h_to = QSpinBox(); self.s_h_to.setRange(300, 7200); self.s_h_to.setSuffix(" sec")
        self.chk_h = QCheckBox("Background Execution (Headless)"); self.btn_rst = QPushButton(" Force Reset Browser/Temp")
        self.btn_rst.setIcon(qta.icon("fa5s.sync-alt", color=C['warning'])); self.btn_rst.clicked.connect(self._reset_browser)
        f3.addRow("Max Parallel Workers:", self.s_work); f3.addRow("Worker Stagger Delay:", self.s_stagger); f3.addRow("Process Hang Timeout:", self.s_h_to)
        f3.addRow("", self.chk_h); f3.addRow("", self.btn_rst); layout.addWidget(g3)

        btn_sv = QPushButton(" SAVE ALL CONFIGURATIONS"); btn_sv.setObjectName("PrimaryBtn")
        btn_sv.setMinimumHeight(55); btn_sv.clicked.connect(self._save_config_ui); layout.addWidget(btn_sv); layout.addStretch()
        scroll.setWidget(content); return scroll

    def _build_logs_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(45, 45, 45, 45); layout.setSpacing(25)
        header = QHBoxLayout(); h1 = QLabel("Real-time Logs"); h1.setObjectName("H1"); header.addWidget(h1); header.addStretch()
        btn_clr = QPushButton(" CLEAR LOGS"); btn_clr.setIcon(qta.icon("fa5s.eraser", color=C['text']))
        btn_clr.clicked.connect(lambda: self.log_viewer.clear()); header.addWidget(btn_clr)
        self.log_viewer = LogViewer(); layout.addLayout(header); layout.addWidget(self.log_viewer); return page

    # ── LOGIC ─────────────────────────────────────────────────────────
    def _load_settings_to_ui(self):
        c = self.config
        self.i_api.setText(c.get("relay_api_key", ""))
        self.i_url.setText(c.get("a1d_url", "https://a1d.ai"))
        self.c_qual.setCurrentText(c.get("output_quality", "4k"))
        self.i_out.setText(c.get("output_dir", ""))
        self.s_work.setValue(c.get("max_workers", 3))
        self.s_stagger.setValue(c.get("batch_stagger_delay", 15))
        self.s_wait.setValue(c.get("initial_download_wait", 120))
        self.s_h_to.setValue(c.get("processing_hang_timeout", 1800))
        self.chk_h.setChecked(c.get("headless", True))

    def _save_config_ui(self, silent=False):
        self.config.update({
            "relay_api_key": self.i_api.text().strip(), "a1d_url": self.i_url.text().strip(),
            "output_quality": self.c_qual.currentText(), "output_dir": self.i_out.text().strip(),
            "max_workers": self.s_work.value(), "batch_stagger_delay": self.s_stagger.value(),
            "initial_download_wait": self.s_wait.value(), "processing_hang_timeout": self.s_h_to.value(),
            "headless": self.chk_h.isChecked(), "theme": self._current_theme_name
        })
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(self.config, f, indent=2)
            if not silent: self._log("Configuration successfully synchronized to disk.", "SUCCESS")
        except Exception as e: self._log(f"Config write failure: {e}", "ERROR")

    def _reset_browser(self):
        if QMessageBox.question(self, "Force Reset", "This will terminate all workers and clear temp folders. Proceed?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self._cancel(); temp = os.path.join(_PROJECT_ROOT, "temp")
            if os.path.exists(temp): shutil.rmtree(temp, ignore_errors=True)
            self._log("Browser engine and temporary files have been reset.", "WARNING")

    def _log(self, m, l="INFO"): self.log_viewer.append_log(m, l)
    def _on_drop(self, ps): self._add_files(ps)
    def _browse_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Media Selection", "", "Videos (*.mp4 *.mkv *.mov *.avi *.webm *.flv)")
        self._add_files(fs)
    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Export Destination")
        if d: self.i_out.setText(d)
    def _add_files(self, ps):
        for p in ps:
            if p not in self._video_paths:
                self._video_paths.append(p); item = QListWidgetItem(f"  {os.path.basename(p)}")
                item.setIcon(qta.icon("fa5s.film", color=C['primary'])); item.setToolTip(p); self.file_list.addItem(item)
        self.count_badge.setText(f"{len(self._video_paths)} QUEUED")
    def _clear_files(self): self._video_paths.clear(); self.file_list.clear(); self.count_badge.setText("0 QUEUED")

    def _start(self):
        if not self._video_paths: return self._log("Selection empty. Please add media files.", "WARNING")
        if not self.i_api.text().strip(): return (self._log("Authentication required: Missing API Key.", "ERROR") or self.btn_settings.click())
        self._save_config_ui(silent=True); self._set_running(True); cfg = dict(self.config)
        self._log("-" * 40); self._log("INITIATING BATCH PROCESS ENGINE", "SUCCESS")
        self._log(f"├ Total Files: {len(self._video_paths)} | Mode: {cfg['output_quality'].upper()}")
        self._log(f"└ Parallel Workers: {cfg['max_workers']} | Headless: {cfg['headless']}")
        self._log("-" * 40)
        
        if len(self._video_paths) == 1:
            self.processor = A1DProcessor(_PROJECT_ROOT, self._video_paths[0], cfg)
            self.processor.log_signal.connect(self._log); self.processor.progress_signal.connect(self._on_progress)
            self.processor.finished_signal.connect(lambda ok, m, _: self._on_finished(ok, m))
        else:
            self.processor = BatchProcessor(_PROJECT_ROOT, self._video_paths, cfg)
            self.processor.log_signal.connect(self._log); self.processor.progress_signal.connect(self._on_progress)
            self.processor.finished_signal.connect(lambda ok, m, _: self._on_finished(ok, m))
        self.processor.start()

    def _set_running(self, r):
        self._running = r; self.btn_start.setVisible(not r); self.btn_cancel.setVisible(r); self.prog_card.setVisible(r)
        self.status_dot.setStyleSheet(f"color: {C['success'] if r else C['text_muted']}; font-size: 18px;")
        self.status_text.setText("SYSTEM ACTIVE" if r else "SYSTEM IDLE")
    def _on_progress(self, p, m): self.pbar.setValue(p); self.p_label.setText(m)
    def _on_finished(self, ok, m): self._set_running(False); self.p_label.setText("Batch complete." if ok else "Failed."); self._log(f"Engine Shutdown: {m}", "SUCCESS" if ok else "ERROR")
    def _cancel(self):
        if self.processor: self.processor.cancel(); self._log("Force Termination requested by user.", "ERROR")

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setApplicationName(APP_NAME)
    font = QFont("Inter", 10); font.setStyleHint(QFont.SansSerif); app.setFont(font)
    app.setStyleSheet(build_stylesheet(C))
    win = MainWindow(); win.show(); sys.exit(app.exec())
