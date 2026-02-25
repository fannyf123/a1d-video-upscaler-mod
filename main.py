import os
import sys
import json
import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QTextEdit, QFileDialog, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QSizePolicy, QGroupBox, QSplitter,
)
from PySide6.QtCore import Qt, QTimer, QSize, QUrl, QMimeData
from PySide6.QtGui import (
    QFont, QIcon, QColor, QDragEnterEvent, QDropEvent,
    QTextCursor, QAction, QPalette,
)
import qtawesome as qta

from App.background_process import A1DProcessor
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
APP_NAME    = "A1D Video Upscaler v2"
APP_VER     = "2.0.0"

# ══ COLOR PALETTE ════════════════════════════════════════════════════════════
C = {
    "bg":        "#0D1117",
    "surface":   "#161B22",
    "surface2":  "#21262D",
    "border":    "#30363D",
    "accent":    "#7C3AED",
    "accent2":   "#2563EB",
    "accent_h":  "#9D5CF5",
    "text":      "#E6EDF3",
    "text_dim":  "#8B949E",
    "success":   "#3FB950",
    "error":     "#F85149",
    "warning":   "#D29922",
    "info":      "#58A6FF",
}

# ══ GLOBAL QSS ══════════════════════════════════════════════════════════════════
DARK_QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: {C['text']}; }}

QMainWindow, QWidget {{ background-color: {C['bg']}; }}

QFrame#Card {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 10px;
}}
QFrame#Card2 {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    border-radius: 8px;
}}
QFrame#Divider {{ background-color: {C['border']}; max-height: 1px; }}

QLabel#Title {{
    font-size: 22px; font-weight: 700;
    color: {C['text']};
}}
QLabel#Subtitle {{
    font-size: 12px; color: {C['text_dim']};
}}
QLabel#SectionLabel {{
    font-size: 11px; font-weight: 600; letter-spacing: 1px;
    color: {C['text_dim']}; text-transform: uppercase;
}}
QLabel#Badge {{
    background-color: {C['accent']}22;
    border: 1px solid {C['accent']}55;
    border-radius: 4px; padding: 2px 8px;
    color: {C['accent_h']}; font-size: 11px; font-weight: 600;
}}

QPushButton {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    border-radius: 8px; padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {C['surface']};
    border-color: {C['accent']};
}}
QPushButton:pressed {{ background-color: {C['accent']}33; }}
QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent2']});
    border: none; border-radius: 8px;
    padding: 10px 28px; font-size: 14px; font-weight: 700;
    color: white;
}}
QPushButton#PrimaryBtn:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['accent_h']}, stop:1 #3B82F6);
}}
QPushButton#PrimaryBtn:disabled {{
    background: {C['surface2']}; color: {C['text_dim']};
    border: 1px solid {C['border']};
}}
QPushButton#DangerBtn {{
    background-color: {C['error']}22;
    border: 1px solid {C['error']}55;
    color: {C['error']}; border-radius: 8px;
    padding: 10px 20px; font-size: 14px; font-weight: 700;
}}
QPushButton#DangerBtn:hover {{ background-color: {C['error']}44; }}
QPushButton#DangerBtn:disabled {{
    background-color: transparent;
    border-color: {C['border']}; color: {C['text_dim']};
}}
QPushButton#IconBtn {{
    background: transparent; border: none;
    padding: 4px; border-radius: 4px;
}}
QPushButton#IconBtn:hover {{ background-color: {C['surface2']}; }}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    border-radius: 7px; padding: 8px 12px;
    color: {C['text']}; selection-background-color: {C['accent']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {C['accent']};
}}
QComboBox::drop-down {{
    border: none; width: 28px;
}}
QComboBox::down-arrow {{
    image: none; border: none;
    width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {C['text_dim']};
}}
QComboBox QAbstractItemView {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    selection-background-color: {C['accent']};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: transparent; border: none; width: 18px;
}}

QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 4px; border: 2px solid {C['border']};
    background: {C['surface2']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
    image: none;
}}

QListWidget {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    border-radius: 8px; outline: none;
}}
QListWidget::item {{
    padding: 8px 12px; border-radius: 6px; margin: 2px 4px;
}}
QListWidget::item:selected {{
    background-color: {C['accent']}33;
    color: {C['text']};
}}
QListWidget::item:hover {{
    background-color: {C['surface']};
}}

QTextEdit {{
    background-color: {C['bg']};
    border: 1px solid {C['border']};
    border-radius: 8px; padding: 8px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px; line-height: 1.5;
}}

QProgressBar {{
    background-color: {C['surface2']};
    border: none; border-radius: 6px; height: 10px;
    text-align: center; font-size: 11px; font-weight: 600;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent2']});
    border-radius: 6px;
}}

QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C['border']}; border-radius: 3px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 6px; }}
QScrollBar::handle:horizontal {{
    background: {C['border']}; border-radius: 3px;
}}

QToolTip {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    color: {C['text']}; padding: 6px 10px;
    border-radius: 6px;
}}
"""


# ══ DROP ZONE WIDGET ═══════════════════════════════════════════════════════════
class DropZone(QFrame):
    files_dropped = __import__('PySide6.QtCore', fromlist=['Signal']).Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self._active = False
        self._update_style(False)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(6)

        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setPixmap(
            qta.icon("fa5s.cloud-upload-alt", color=C['text_dim']).pixmap(32, 32)
        )

        self._txt = QLabel("Drop video files here  or  <b>Browse</b>")
        self._txt.setAlignment(Qt.AlignCenter)
        self._txt.setStyleSheet(f"color:{C['text_dim']}; font-size:13px;")

        self._sub = QLabel("MP4, MKV, MOV, AVI, WebM")
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setStyleSheet(f"color:{C['border']}; font-size:11px;")

        lay.addWidget(self._icon_lbl)
        lay.addWidget(self._txt)
        lay.addWidget(self._sub)

    def _update_style(self, active: bool):
        self._active = active
        bc = C['accent'] if active else C['border']
        bg = f"{C['accent']}11" if active else "transparent"
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2px dashed {bc};
                border-radius: 10px;
                background: {bg};
            }}
        """)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._update_style(True)

    def dragLeaveEvent(self, e):
        self._update_style(False)

    def dropEvent(self, e: QDropEvent):
        self._update_style(False)
        paths = [
            u.toLocalFile() for u in e.mimeData().urls()
            if u.toLocalFile().lower().endswith(
                ('.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.wmv')
            )
        ]
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, e):
        self.files_dropped.emit([])   # signal Browse


# ══ LOG WIDGET ════════════════════════════════════════════════════════════════════
LOG_COLORS = {
    "INFO":    C['text'],
    "SUCCESS": C['success'],
    "ERROR":   C['error'],
    "WARNING": C['warning'],
    "DEBUG":   C['text_dim'],
}


class LogViewer(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(1000)

    def append_log(self, msg: str, level: str = "INFO"):
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        color = LOG_COLORS.get(level, C['text'])
        dim   = C['text_dim']
        html  = (
            f'<span style="color:{dim};">[{ts}]</span> '
            f'<span style="color:{color};">{msg}</span>'
        )
        self.append(html)
        self.moveCursor(QTextCursor.End)


# ══ MAIN WINDOW ═════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config      = self._load_config()
        self.processor   = None
        self._video_paths: list[str] = []
        self._running    = False

        self.setWindowTitle(f"{APP_NAME}  v{APP_VER}")
        self.setMinimumSize(880, 680)
        self.resize(980, 760)

        self._build_ui()
        self.setAcceptDrops(True)

    # ── CONFIG ───────────────────────────────────────────────────────────────────
    def _load_config(self) -> dict:
        default = {
            "relay_api_key": "",
            "output_quality": "4k",
            "output_dir": "",
            "headless": True,
            "max_workers": DEFAULT_WORKERS,
            "batch_stagger_delay": 15,
            "processing_hang_timeout": 1800,
            "download_timeout": 600,
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    saved = json.load(f)
                default.update(saved)
            except Exception:
                pass
        return default

    def _save_config(self):
        self.config["relay_api_key"]       = self.api_key_edit.text().strip()
        self.config["output_quality"]       = self.quality_combo.currentText().lower()
        self.config["output_dir"]           = self.out_dir_edit.text().strip()
        self.config["headless"]             = self.headless_chk.isChecked()
        self.config["max_workers"]          = self.workers_spin.value()
        self.config["batch_stagger_delay"]  = self.stagger_spin.value()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.log.append_log(f"Gagal simpan config: {e}", "ERROR")

    # ── BUILD UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_lay = QVBoxLayout(root)
        main_lay.setContentsMargins(20, 16, 20, 16)
        main_lay.setSpacing(14)

        # ─ Header ───────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon("fa5s.film", color=C['accent']).pixmap(32, 32)
        )
        title_lbl = QLabel(APP_NAME)
        title_lbl.setObjectName("Title")

        ver_lbl = QLabel(f"v{APP_VER}")
        ver_lbl.setObjectName("Badge")
        ver_lbl.setFixedHeight(22)

        pw_lbl = QLabel("Playwright")
        pw_lbl.setObjectName("Badge")
        pw_lbl.setFixedHeight(22)
        pw_lbl.setStyleSheet(
            f"background:{C['success']}22; border:1px solid {C['success']}55;"
            f"border-radius:4px; padding:2px 8px; color:{C['success']};"
            f"font-size:11px; font-weight:600;"
        )

        sub_lbl = QLabel("Auto Video Upscaler via a1d.ai")
        sub_lbl.setObjectName("Subtitle")

        header.addWidget(icon_lbl)
        header.addWidget(title_lbl)
        header.addWidget(ver_lbl)
        header.addWidget(pw_lbl)
        header.addStretch()
        header.addWidget(sub_lbl)
        main_lay.addLayout(header)

        # Divider
        div = QFrame(); div.setObjectName("Divider")
        main_lay.addWidget(div)

        # ─ Splitter: top / log ────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; height: 8px; }")
        main_lay.addWidget(splitter, stretch=1)

        top_widget = QWidget()
        top_lay    = QVBoxLayout(top_widget)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(12)
        splitter.addWidget(top_widget)

        # ─ Two columns: left (input+progress) | right (settings) ─────────
        cols = QHBoxLayout()
        cols.setSpacing(14)
        top_lay.addLayout(cols)

        # LEFT COLUMN
        left = QVBoxLayout(); left.setSpacing(12)
        cols.addLayout(left, stretch=3)

        # Input card
        input_card = QFrame(); input_card.setObjectName("Card")
        input_lay  = QVBoxLayout(input_card)
        input_lay.setContentsMargins(14, 14, 14, 14)
        input_lay.setSpacing(10)

        sec_lbl = QLabel("●  INPUT FILES")
        sec_lbl.setObjectName("SectionLabel")
        input_lay.addWidget(sec_lbl)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        input_lay.addWidget(self.drop_zone)

        # File list
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(130)
        self.file_list.setToolTip("File yang akan diproses")
        input_lay.addWidget(self.file_list)

        # File list controls
        file_ctrl = QHBoxLayout(); file_ctrl.setSpacing(8)
        self.add_btn = QPushButton(
            qta.icon("fa5s.plus", color=C['accent']), "  Tambah File"
        )
        self.add_btn.setCursor(__import__('PySide6.QtCore', fromlist=['Qt']).Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self._browse_files)

        self.clear_btn = QPushButton(
            qta.icon("fa5s.trash-alt", color=C['error']), "  Clear"
        )
        self.clear_btn.clicked.connect(self._clear_files)

        self.file_count_lbl = QLabel("0 file")
        self.file_count_lbl.setStyleSheet(f"color:{C['text_dim']};")

        file_ctrl.addWidget(self.add_btn)
        file_ctrl.addWidget(self.clear_btn)
        file_ctrl.addStretch()
        file_ctrl.addWidget(self.file_count_lbl)
        input_lay.addLayout(file_ctrl)
        left.addWidget(input_card)

        # Progress card
        prog_card = QFrame(); prog_card.setObjectName("Card")
        prog_lay  = QVBoxLayout(prog_card)
        prog_lay.setContentsMargins(14, 12, 14, 12)
        prog_lay.setSpacing(8)

        prog_header = QHBoxLayout()
        prog_sec = QLabel("●  PROGRESS")
        prog_sec.setObjectName("SectionLabel")
        self.status_lbl = QLabel("Idle")
        self.status_lbl.setStyleSheet(f"color:{C['text_dim']}; font-size:12px;")
        prog_header.addWidget(prog_sec)
        prog_header.addStretch()
        prog_header.addWidget(self.status_lbl)
        prog_lay.addLayout(prog_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        prog_lay.addWidget(self.progress_bar)

        self.prog_label = QLabel("Menunggu...")
        self.prog_label.setStyleSheet(f"color:{C['text_dim']}; font-size:12px;")
        prog_lay.addWidget(self.prog_label)
        left.addWidget(prog_card)

        # RIGHT COLUMN: Settings card
        settings_card = QFrame(); settings_card.setObjectName("Card")
        set_lay = QVBoxLayout(settings_card)
        set_lay.setContentsMargins(14, 14, 14, 14)
        set_lay.setSpacing(12)
        cols.addLayout(QVBoxLayout(), stretch=0)
        cols.addWidget(settings_card, stretch=2)

        set_sec = QLabel("●  SETTINGS")
        set_sec.setObjectName("SectionLabel")
        set_lay.addWidget(set_sec)

        # Relay API Key
        set_lay.addWidget(QLabel("Firefox Relay API Key"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("fxa_...")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setText(self.config.get("relay_api_key", ""))
        show_btn = QPushButton(qta.icon("fa5s.eye", color=C['text_dim']), "")
        show_btn.setObjectName("IconBtn")
        show_btn.setFixedSize(32, 32)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda c: self.api_key_edit.setEchoMode(
                QLineEdit.Normal if c else QLineEdit.Password
            )
        )
        api_row = QHBoxLayout(); api_row.setSpacing(4)
        api_row.addWidget(self.api_key_edit)
        api_row.addWidget(show_btn)
        set_lay.addLayout(api_row)

        # Output Quality
        set_lay.addWidget(QLabel("Output Quality"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["4k", "2k", "1080p"])
        self.quality_combo.setCurrentText(self.config.get("output_quality", "4k"))
        set_lay.addWidget(self.quality_combo)

        # Output Dir
        set_lay.addWidget(QLabel("Output Folder"))
        self.out_dir_edit = QLineEdit()
        self.out_dir_edit.setPlaceholderText("Kosong = folder video/OUTPUT")
        self.out_dir_edit.setText(self.config.get("output_dir", ""))
        browse_out_btn = QPushButton(qta.icon("fa5s.folder-open", color=C['text_dim']), "")
        browse_out_btn.setObjectName("IconBtn")
        browse_out_btn.setFixedSize(32, 32)
        browse_out_btn.clicked.connect(self._browse_output)
        out_row = QHBoxLayout(); out_row.setSpacing(4)
        out_row.addWidget(self.out_dir_edit)
        out_row.addWidget(browse_out_btn)
        set_lay.addLayout(out_row)

        # Workers + Stagger
        worker_row = QHBoxLayout(); worker_row.setSpacing(12)

        w_col = QVBoxLayout(); w_col.setSpacing(4)
        w_col.addWidget(QLabel(f"Workers  (1–{MAX_PARALLEL_LIMIT})"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, MAX_PARALLEL_LIMIT)
        self.workers_spin.setValue(self.config.get("max_workers", DEFAULT_WORKERS))
        self.workers_spin.setToolTip("Jumlah video diproses paralel")
        w_col.addWidget(self.workers_spin)

        s_col = QVBoxLayout(); s_col.setSpacing(4)
        s_col.addWidget(QLabel("Stagger (detik)"))
        self.stagger_spin = QSpinBox()
        self.stagger_spin.setRange(0, 120)
        self.stagger_spin.setValue(self.config.get("batch_stagger_delay", 15))
        self.stagger_spin.setToolTip("Jeda antar worker start (0 = serentak)")
        s_col.addWidget(self.stagger_spin)

        worker_row.addLayout(w_col)
        worker_row.addLayout(s_col)
        set_lay.addLayout(worker_row)

        # Checkboxes
        self.headless_chk = QCheckBox("Headless mode")
        self.headless_chk.setChecked(self.config.get("headless", True))
        self.headless_chk.setToolTip("Browser berjalan tanpa tampilan")
        set_lay.addWidget(self.headless_chk)

        set_lay.addStretch()

        # Save config button
        save_btn = QPushButton(
            qta.icon("fa5s.save", color=C['text_dim']), "  Simpan Config"
        )
        save_btn.clicked.connect(self._save_config)
        set_lay.addWidget(save_btn)

        # ─ LOG section (bottom of splitter) ──────────────────────────────
        log_card = QFrame(); log_card.setObjectName("Card")
        log_card_lay = QVBoxLayout(log_card)
        log_card_lay.setContentsMargins(14, 12, 14, 12)
        log_card_lay.setSpacing(8)
        splitter.addWidget(log_card)
        splitter.setSizes([430, 220])

        log_header = QHBoxLayout()
        log_sec = QLabel("●  REALTIME LOG")
        log_sec.setObjectName("SectionLabel")
        clear_log_btn = QPushButton(qta.icon("fa5s.eraser", color=C['text_dim']), "  Clear Log")
        clear_log_btn.setFixedHeight(26)
        clear_log_btn.clicked.connect(lambda: self.log.clear())
        log_header.addWidget(log_sec)
        log_header.addStretch()
        log_header.addWidget(clear_log_btn)
        log_card_lay.addLayout(log_header)

        self.log = LogViewer()
        log_card_lay.addWidget(self.log)

        # ─ Bottom action bar ──────────────────────────────────────────────
        div2 = QFrame(); div2.setObjectName("Divider")
        main_lay.addWidget(div2)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(12)

        self.queue_info = QLabel("Siap memproses")
        self.queue_info.setStyleSheet(f"color:{C['text_dim']};")

        self.start_btn = QPushButton(
            qta.icon("fa5s.play", color="white"), "  MULAI PROSES"
        )
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.setMinimumWidth(180)
        self.start_btn.setFixedHeight(44)
        self.start_btn.clicked.connect(self._start)
        self.start_btn.setCursor(__import__('PySide6.QtCore', fromlist=['Qt']).Qt.PointingHandCursor)

        self.cancel_btn = QPushButton(
            qta.icon("fa5s.stop", color=C['error']), "  CANCEL"
        )
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setFixedHeight(44)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)

        action_bar.addWidget(self.queue_info)
        action_bar.addStretch()
        action_bar.addWidget(self.start_btn)
        action_bar.addWidget(self.cancel_btn)
        main_lay.addLayout(action_bar)

        # Welcome log
        self.log.append_log(f"🎥 {APP_NAME} v{APP_VER} siap", "SUCCESS")
        self.log.append_log("Drag & drop video ke area input, atur settings, lalu klik MULAI PROSES", "INFO")

    # ── FILE MANAGEMENT ───────────────────────────────────────────────────────────
    def _on_drop(self, paths: list):
        if not paths:   # Browse dipanggil dari klik drop zone
            self._browse_files()
            return
        self._add_files(paths)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Pilih Video", "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv)"
        )
        self._add_files(files)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Output")
        if d:
            self.out_dir_edit.setText(d)

    def _add_files(self, paths: list):
        added = 0
        for p in paths:
            if p not in self._video_paths:
                self._video_paths.append(p)
                item = QListWidgetItem(
                    qta.icon("fa5s.file-video", color=C['info']),
                    os.path.basename(p)
                )
                item.setToolTip(p)
                self.file_list.addItem(item)
                added += 1
        if added:
            self.log.append_log(f"Ditambahkan {added} file", "INFO")
        self._update_queue_info()

    def _clear_files(self):
        self._video_paths.clear()
        self.file_list.clear()
        self._update_queue_info()

    def _update_queue_info(self):
        n = len(self._video_paths)
        w = min(n, self.workers_spin.value())
        self.file_count_lbl.setText(f"{n} file")
        if n == 0:
            self.queue_info.setText("Siap memproses")
        elif n == 1:
            self.queue_info.setText("1 video — single mode")
        else:
            self.queue_info.setText(f"{n} video — {w} worker paralel")

    # ── START / CANCEL ───────────────────────────────────────────────────────────
    def _start(self):
        if not self._video_paths:
            self.log.append_log("⚠️ Tambahkan setidaknya 1 video terlebih dulu", "WARNING")
            return
        if not self.api_key_edit.text().strip():
            self.log.append_log("⚠️ Firefox Relay API Key belum diisi", "WARNING")
            return

        self._save_config()
        n = len(self._video_paths)
        self._set_running(True)
        self.progress_bar.setValue(0)
        self.log.append_log(f"🚀 Memulai proses {n} video...", "INFO")

        cfg = dict(self.config)

        if n == 1:
            self.processor = A1DProcessor(
                os.path.dirname(__file__), self._video_paths[0], cfg
            )
        else:
            self.processor = BatchProcessor(
                os.path.dirname(__file__), self._video_paths, cfg
            )

        self.processor.log_signal.connect(self.log.append_log)
        self.processor.progress_signal.connect(self._on_progress)
        self.processor.finished_signal.connect(self._on_finished)
        self.processor.start()

    def _cancel(self):
        if self.processor:
            self.processor.cancel()
            self.log.append_log("⚠️ Proses dibatalkan oleh user", "WARNING")
            self._set_running(False)

    def _set_running(self, running: bool):
        self._running = running
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.add_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running)
        if running:
            self.status_lbl.setText("⏳ Berjalan...")
            self.status_lbl.setStyleSheet(f"color:{C['warning']};")
        else:
            self.status_lbl.setText("Idle")
            self.status_lbl.setStyleSheet(f"color:{C['text_dim']};")

    # ── SIGNALS FROM PROCESSOR ───────────────────────────────────────────────
    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        if msg:
            self.prog_label.setText(msg)
            self.status_lbl.setText(f"{pct}%")

    def _on_finished(self, ok: bool, msg: str, *args):
        self._set_running(False)
        self.progress_bar.setValue(100 if ok else self.progress_bar.value())
        level = "SUCCESS" if ok else "ERROR"
        icon  = "✅" if ok else "❌"
        self.log.append_log(f"{icon} {msg}", level)
        self.status_lbl.setText("✅ Selesai" if ok else "❌ Gagal")
        self.status_lbl.setStyleSheet(
            f"color:{C['success']};" if ok else f"color:{C['error']};"
        )
        self.prog_label.setText(msg)

    # ── DRAG DROP on main window ──────────────────────────────────────────
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        paths = [
            u.toLocalFile() for u in e.mimeData().urls()
            if u.toLocalFile().lower().endswith(
                ('.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.wmv')
            )
        ]
        self._add_files(paths)

    def workers_spin_changed(self):
        self._update_queue_info()

    def closeEvent(self, e):
        self._save_config()
        if self.processor and self._running:
            self.processor.cancel()
        e.accept()


# ══ ENTRY POINT ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VER)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)

    # Dark palette fallback
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(C['bg']))
    pal.setColor(QPalette.WindowText,      QColor(C['text']))
    pal.setColor(QPalette.Base,            QColor(C['surface']))
    pal.setColor(QPalette.AlternateBase,   QColor(C['surface2']))
    pal.setColor(QPalette.Text,            QColor(C['text']))
    pal.setColor(QPalette.Button,          QColor(C['surface2']))
    pal.setColor(QPalette.ButtonText,      QColor(C['text']))
    pal.setColor(QPalette.Highlight,       QColor(C['accent']))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    app.setPalette(pal)

    win = MainWindow()
    win.workers_spin.valueChanged.connect(win.workers_spin_changed)
    win.show()
    sys.exit(app.exec())
