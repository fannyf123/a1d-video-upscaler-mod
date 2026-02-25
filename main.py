import sys
import os

# ══ FIX: pastikan project root selalu ada di sys.path ════════════════════════════
# Diperlukan saat dijalankan via Launcher.bat / Python portable
# yang working directory-nya bisa berbeda dengan lokasi main.py
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
# ────────────────────────────────────────────────────────────────────────────────

import json
import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QTextEdit, QFileDialog, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QSizePolicy, QSplitter,
)
from PySide6.QtCore import Qt, QTimer, QMimeData
from PySide6.QtGui import (
    QFont, QColor, QDragEnterEvent, QDropEvent,
    QTextCursor, QPalette,
)
import qtawesome as qta

from App.background_process import A1DProcessor
from App.batch_processor import BatchProcessor, MAX_PARALLEL_LIMIT, DEFAULT_WORKERS

CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
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

DARK_QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget {{ background-color: {C['bg']}; }}
QFrame#Card {{
    background-color: {C['surface']};
    border: 1px solid {C['border']}; border-radius: 10px;
}}
QFrame#Card2 {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']}; border-radius: 8px;
}}
QFrame#Divider {{ background-color: {C['border']}; max-height: 1px; }}
QLabel#Title {{ font-size: 22px; font-weight: 700; color: {C['text']}; }}
QLabel#Subtitle {{ font-size: 12px; color: {C['text_dim']}; }}
QLabel#SectionLabel {{
    font-size: 10px; font-weight: 700; letter-spacing: 1.5px;
    color: {C['text_dim']};
}}
QLabel#FieldLabel {{ font-size: 12px; color: {C['text_dim']}; margin-bottom: 1px; }}
QLabel#Badge {{
    background: {C['accent']}22; border: 1px solid {C['accent']}55;
    border-radius: 4px; padding: 2px 8px;
    color: {C['accent_h']}; font-size: 11px; font-weight: 600;
}}
QPushButton {{
    background-color: {C['surface2']}; border: 1px solid {C['border']};
    border-radius: 8px; padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background-color: {C['surface']}; border-color: {C['accent']}; }}
QPushButton:pressed {{ background-color: {C['accent']}33; }}
QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent2']});
    border: none; border-radius: 8px;
    padding: 10px 28px; font-size: 14px; font-weight: 700; color: white;
}}
QPushButton#PrimaryBtn:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['accent_h']}, stop:1 #3B82F6);
}}
QPushButton#PrimaryBtn:disabled {{
    background: {C['surface2']}; color: {C['text_dim']}; border: 1px solid {C['border']};
}}
QPushButton#DangerBtn {{
    background: {C['error']}22; border: 1px solid {C['error']}55;
    color: {C['error']}; border-radius: 8px; padding: 10px 20px;
    font-size: 14px; font-weight: 700;
}}
QPushButton#DangerBtn:hover {{ background: {C['error']}44; }}
QPushButton#DangerBtn:disabled {{
    background: transparent; border-color: {C['border']}; color: {C['text_dim']};
}}
QPushButton#IconBtn {{ background: transparent; border: none; padding: 4px; border-radius: 4px; }}
QPushButton#IconBtn:hover {{ background: {C['surface2']}; }}
QLineEdit, QComboBox, QSpinBox {{
    background: {C['surface2']}; border: 1px solid {C['border']};
    border-radius: 7px; padding: 7px 11px; color: {C['text']};
    selection-background-color: {C['accent']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {C['accent']}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 5px solid {C['text_dim']};
}}
QComboBox QAbstractItemView {{
    background: {C['surface2']}; border: 1px solid {C['border']};
    selection-background-color: {C['accent']}; outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{ background: transparent; border: none; width: 18px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 2px solid {C['border']}; background: {C['surface2']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent']}; border-color: {C['accent']};
}}
QListWidget {{
    background: {C['surface2']}; border: 1px solid {C['border']};
    border-radius: 8px; outline: none;
}}
QListWidget::item {{ padding: 7px 12px; border-radius: 6px; margin: 2px 4px; }}
QListWidget::item:selected {{ background: {C['accent']}33; }}
QListWidget::item:hover {{ background: {C['surface']}; }}
QTextEdit {{
    background: {C['bg']}; border: 1px solid {C['border']};
    border-radius: 8px; padding: 8px;
    font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;
}}
QProgressBar {{
    background: {C['surface2']}; border: none; border-radius: 6px;
    height: 10px; text-align: center; font-size: 11px; font-weight: 600;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent2']});
    border-radius: 6px;
}}
QScrollBar:vertical {{ background: transparent; width: 6px; }}
QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 6px; }}
QScrollBar::handle:horizontal {{ background: {C['border']}; border-radius: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QToolTip {{
    background: {C['surface2']}; border: 1px solid {C['border']};
    color: {C['text']}; padding: 6px 10px; border-radius: 6px;
}}
"""

LOG_COLORS = {
    "INFO":    C['text'],
    "SUCCESS": C['success'],
    "ERROR":   C['error'],
    "WARNING": C['warning'],
    "DEBUG":   C['text_dim'],
}


# ══ HELPERS ════════════════════════════════════════════════════════════════════
def _field(label: str, widget, tooltip: str = "") -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(4)
    lbl = QLabel(label)
    lbl.setObjectName("FieldLabel")
    if tooltip:
        lbl.setToolTip(tooltip)
        widget.setToolTip(tooltip)
    lay.addWidget(lbl)
    lay.addWidget(widget)
    return lay


# ══ DROP ZONE ═══════════════════════════════════════════════════════════════════
class DropZone(QFrame):
    files_dropped = __import__('PySide6.QtCore', fromlist=['Signal']).Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self._update_style(False)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(5)
        ico = QLabel()
        ico.setAlignment(Qt.AlignCenter)
        ico.setPixmap(qta.icon("fa5s.cloud-upload-alt", color=C['text_dim']).pixmap(28, 28))
        txt = QLabel("Drop video here  ·  <b>atau klik Browse</b>")
        txt.setAlignment(Qt.AlignCenter)
        txt.setStyleSheet(f"color:{C['text_dim']};")
        sub = QLabel("MP4 · MKV · MOV · AVI · WebM")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color:{C['border']}; font-size:11px;")
        lay.addWidget(ico); lay.addWidget(txt); lay.addWidget(sub)

    def _update_style(self, active: bool):
        bc = C['accent'] if active else C['border']
        bg = f"{C['accent']}11" if active else "transparent"
        self.setStyleSheet(
            f"QFrame#DropZone{{border:2px dashed {bc};border-radius:10px;background:{bg};}}"
        )

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction(); self._update_style(True)
    def dragLeaveEvent(self, e):  self._update_style(False)
    def dropEvent(self, e):
        self._update_style(False)
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith(
                     ('.mp4','.mkv','.mov','.avi','.webm','.flv','.wmv'))]
        if paths: self.files_dropped.emit(paths)
    def mousePressEvent(self, e): self.files_dropped.emit([])


# ══ LOG VIEWER ══════════════════════════════════════════════════════════════════
class LogViewer(QTextEdit):
    def __init__(self, max_lines: int = 500, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)

    def set_max_lines(self, n: int):
        self.document().setMaximumBlockCount(n)

    def append_log(self, msg: str, level: str = "INFO"):
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        color = LOG_COLORS.get(level, C['text'])
        dim   = C['text_dim']
        self.append(
            f'<span style="color:{dim};">[{ts}]</span> '
            f'<span style="color:{color};">{msg}</span>'
        )
        self.moveCursor(QTextCursor.End)


# ══ SECTION HEADER ═══════════════════════════════════════════════════════════
def _sec_header(text: str, icon: str = "") -> QWidget:
    w   = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 4); lay.setSpacing(6)
    if icon:
        ico = QLabel()
        ico.setPixmap(qta.icon(icon, color=C['accent']).pixmap(14, 14))
        lay.addWidget(ico)
    lbl = QLabel(text.upper()); lbl.setObjectName("SectionLabel")
    div = QFrame(); div.setFrameShape(QFrame.HLine)
    div.setStyleSheet(f"color:{C['border']};")
    lay.addWidget(lbl); lay.addWidget(div, stretch=1)
    return w


# ══ MAIN WINDOW ═════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config      = self._load_config()
        self.processor   = None
        self._video_paths: list[str] = []
        self._running    = False
        self.setWindowTitle(f"{APP_NAME}  v{APP_VER}")
        self.setMinimumSize(960, 700)
        self.resize(1080, 800)
        self._build_ui()
        self.setAcceptDrops(True)

    # ── CONFIG ───────────────────────────────────────────────────────────────────
    def _load_config(self) -> dict:
        default = {
            "relay_api_key":          "",
            "output_quality":          "4k",
            "output_dir":              "",
            "headless":                True,
            "max_workers":             DEFAULT_WORKERS,
            "batch_stagger_delay":     15,
            "initial_download_wait":   120,
            "processing_hang_timeout": 1800,
            "download_timeout":        600,
            "a1d_url":                 "https://a1d.ai",
            "log_max_lines":           500,
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    default.update(json.load(f))
            except Exception:
                pass
        return default

    def _save_config(self):
        self.config.update({
            "relay_api_key":          self.api_key_edit.text().strip(),
            "output_quality":          self.quality_combo.currentText().lower(),
            "output_dir":              self.out_dir_edit.text().strip(),
            "headless":                self.headless_chk.isChecked(),
            "max_workers":             self.workers_spin.value(),
            "batch_stagger_delay":     self.stagger_spin.value(),
            "initial_download_wait":   self.init_wait_spin.value(),
            "processing_hang_timeout": self.render_timeout_spin.value(),
            "download_timeout":        self.dl_timeout_spin.value(),
            "a1d_url":                 self.a1d_url_edit.text().strip() or "https://a1d.ai",
            "log_max_lines":           self.log_lines_spin.value(),
        })
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.log.set_max_lines(self.config["log_max_lines"])
            self.log.append_log("✅ Config tersimpan", "SUCCESS")
        except Exception as e:
            self.log.append_log(f"❌ Gagal simpan config: {e}", "ERROR")

    # ── BUILD UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_lay = QVBoxLayout(root)
        main_lay.setContentsMargins(20, 16, 20, 16)
        main_lay.setSpacing(12)

        # Header
        hdr = QHBoxLayout(); hdr.setSpacing(10)
        ico_lbl = QLabel()
        ico_lbl.setPixmap(qta.icon("fa5s.film", color=C['accent']).pixmap(30, 30))
        title_lbl = QLabel(APP_NAME); title_lbl.setObjectName("Title")
        ver_lbl = QLabel(f"v{APP_VER}"); ver_lbl.setObjectName("Badge")
        pw_lbl = QLabel("Playwright")
        pw_lbl.setStyleSheet(
            f"background:{C['success']}22;border:1px solid {C['success']}55;"
            f"border-radius:4px;padding:2px 8px;color:{C['success']};"
            f"font-size:11px;font-weight:600;")
        sub_lbl = QLabel("Auto Video Upscaler via a1d.ai")
        sub_lbl.setObjectName("Subtitle")
        for w in [ico_lbl, title_lbl, ver_lbl, pw_lbl]: hdr.addWidget(w)
        hdr.addStretch(); hdr.addWidget(sub_lbl)
        main_lay.addLayout(hdr)
        div = QFrame(); div.setObjectName("Divider"); main_lay.addWidget(div)

        # Splitter
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle{background:transparent;height:8px;}")
        main_lay.addWidget(splitter, stretch=1)
        top_w = QWidget()
        top_l = QHBoxLayout(top_w)
        top_l.setContentsMargins(0, 0, 0, 0); top_l.setSpacing(14)
        splitter.addWidget(top_w)

        # LEFT column
        left = QVBoxLayout(); left.setSpacing(12)
        top_l.addLayout(left, stretch=3)

        in_card = QFrame(); in_card.setObjectName("Card")
        in_lay  = QVBoxLayout(in_card)
        in_lay.setContentsMargins(14,12,14,12); in_lay.setSpacing(8)
        in_lay.addWidget(_sec_header("Input Files", "fa5s.file-video"))
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        in_lay.addWidget(self.drop_zone)
        self.file_list = QListWidget(); self.file_list.setMaximumHeight(120)
        in_lay.addWidget(self.file_list)
        fc = QHBoxLayout(); fc.setSpacing(8)
        self.add_btn   = QPushButton(qta.icon("fa5s.plus", color=C['accent']), "  Tambah")
        self.add_btn.clicked.connect(self._browse_files)
        self.clear_btn = QPushButton(qta.icon("fa5s.trash-alt", color=C['error']), "  Clear")
        self.clear_btn.clicked.connect(self._clear_files)
        self.file_count_lbl = QLabel("0 file")
        self.file_count_lbl.setStyleSheet(f"color:{C['text_dim']};")
        for w in [self.add_btn, self.clear_btn]: fc.addWidget(w)
        fc.addStretch(); fc.addWidget(self.file_count_lbl)
        in_lay.addLayout(fc)
        left.addWidget(in_card)

        pr_card = QFrame(); pr_card.setObjectName("Card")
        pr_lay  = QVBoxLayout(pr_card)
        pr_lay.setContentsMargins(14,12,14,12); pr_lay.setSpacing(8)
        ph = QHBoxLayout()
        ph.addWidget(_sec_header("Progress", "fa5s.tasks"))
        self.status_lbl = QLabel("Idle")
        self.status_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:12px;")
        ph.addStretch(); ph.addWidget(self.status_lbl)
        pr_lay.addLayout(ph)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100); self.progress_bar.setFormat("%p%")
        pr_lay.addWidget(self.progress_bar)
        self.prog_label = QLabel("Menunggu...")
        self.prog_label.setStyleSheet(f"color:{C['text_dim']};font-size:12px;")
        pr_lay.addWidget(self.prog_label)
        left.addWidget(pr_card)
        left.addStretch()

        # RIGHT column: Settings scrollable
        set_card  = QFrame(); set_card.setObjectName("Card")
        set_outer = QVBoxLayout(set_card)
        set_outer.setContentsMargins(14,12,14,12); set_outer.setSpacing(6)
        set_outer.addWidget(_sec_header("Settings", "fa5s.sliders-h"))
        top_l.addWidget(set_card, stretch=2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        set_outer.addWidget(scroll, stretch=1)
        sc_w = QWidget(); sc_l = QVBoxLayout(sc_w)
        sc_l.setContentsMargins(2,0,8,4); sc_l.setSpacing(2)
        scroll.setWidget(sc_w)

        # ─ Authentication
        sc_l.addWidget(_sec_header("Authentication", "fa5s.key"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("fxa_...")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setText(self.config.get("relay_api_key", ""))
        show_btn = QPushButton(qta.icon("fa5s.eye", color=C['text_dim']), "")
        show_btn.setObjectName("IconBtn"); show_btn.setFixedSize(32,32)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda c: self.api_key_edit.setEchoMode(
                QLineEdit.Normal if c else QLineEdit.Password))
        api_row = QHBoxLayout(); api_row.setSpacing(4)
        api_row.addWidget(self.api_key_edit); api_row.addWidget(show_btn)
        sc_l.addWidget(QLabel("Firefox Relay API Key")); sc_l.addLayout(api_row)

        # ─ Output
        sc_l.addWidget(_sec_header("Output", "fa5s.folder-open"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["4k", "2k", "1080p"])
        self.quality_combo.setCurrentText(self.config.get("output_quality", "4k"))
        sc_l.addLayout(_field("Kualitas Output", self.quality_combo,
                               "Resolusi output: 4K / 2K / 1080p"))
        self.out_dir_edit = QLineEdit()
        self.out_dir_edit.setPlaceholderText("Kosong = folder video/OUTPUT")
        self.out_dir_edit.setText(self.config.get("output_dir", ""))
        browse_out = QPushButton(qta.icon("fa5s.folder-open", color=C['text_dim']), "")
        browse_out.setObjectName("IconBtn"); browse_out.setFixedSize(32,32)
        browse_out.clicked.connect(self._browse_output)
        out_row = QHBoxLayout(); out_row.setSpacing(4)
        out_row.addWidget(self.out_dir_edit); out_row.addWidget(browse_out)
        sc_l.addWidget(QLabel("Folder Output")); sc_l.addLayout(out_row)

        # ─ Timing
        sc_l.addWidget(_sec_header("Timing", "fa5s.clock"))
        self.init_wait_spin = QSpinBox()
        self.init_wait_spin.setRange(0, 600); self.init_wait_spin.setSingleStep(10)
        self.init_wait_spin.setSuffix(" detik")
        self.init_wait_spin.setValue(self.config.get("initial_download_wait", 120))
        sc_l.addLayout(_field("Wait Setelah Upscale Start", self.init_wait_spin,
                               "Jeda sebelum mulai polling tombol Download"))
        self.render_timeout_spin = QSpinBox()
        self.render_timeout_spin.setRange(300, 7200); self.render_timeout_spin.setSingleStep(60)
        self.render_timeout_spin.setSuffix(" detik")
        self.render_timeout_spin.setValue(self.config.get("processing_hang_timeout", 1800))
        sc_l.addLayout(_field("Timeout Render", self.render_timeout_spin,
                               "Timeout maks menunggu server selesai render"))
        self.dl_timeout_spin = QSpinBox()
        self.dl_timeout_spin.setRange(60, 3600); self.dl_timeout_spin.setSingleStep(30)
        self.dl_timeout_spin.setSuffix(" detik")
        self.dl_timeout_spin.setValue(self.config.get("download_timeout", 600))
        sc_l.addLayout(_field("Timeout Download", self.dl_timeout_spin,
                               "Timeout maks menunggu file selesai didownload"))

        # ─ Batch
        sc_l.addWidget(_sec_header("Batch", "fa5s.layer-group"))
        row2 = QHBoxLayout(); row2.setSpacing(10)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, MAX_PARALLEL_LIMIT)
        self.workers_spin.setValue(self.config.get("max_workers", DEFAULT_WORKERS))
        self.workers_spin.valueChanged.connect(self._update_queue_info)
        self.stagger_spin = QSpinBox()
        self.stagger_spin.setRange(0, 120); self.stagger_spin.setSuffix(" detik")
        self.stagger_spin.setValue(self.config.get("batch_stagger_delay", 15))
        wl = QVBoxLayout(); wl.addLayout(
            _field(f"Workers (1–{MAX_PARALLEL_LIMIT})", self.workers_spin,
                   "Jumlah video paralel"))
        sl = QVBoxLayout(); sl.addLayout(
            _field("Stagger Delay", self.stagger_spin, "Jeda antar worker start"))
        row2.addLayout(wl); row2.addLayout(sl)
        sc_l.addLayout(row2)

        # ─ Browser
        sc_l.addWidget(_sec_header("Browser", "fa5s.globe"))
        self.headless_chk = QCheckBox("Headless mode")
        self.headless_chk.setChecked(self.config.get("headless", True))
        self.headless_chk.setToolTip("Browser tanpa tampilan (lebih hemat resource)")
        sc_l.addWidget(self.headless_chk)

        # ─ Advanced
        sc_l.addWidget(_sec_header("Advanced", "fa5s.cog"))
        self.a1d_url_edit = QLineEdit()
        self.a1d_url_edit.setPlaceholderText("https://a1d.ai")
        self.a1d_url_edit.setText(self.config.get("a1d_url", "https://a1d.ai"))
        sc_l.addLayout(_field("a1d.ai URL", self.a1d_url_edit,
                               "URL base a1d.ai (ubah jika domain pindah)"))
        self.log_lines_spin = QSpinBox()
        self.log_lines_spin.setRange(100, 5000); self.log_lines_spin.setSingleStep(100)
        self.log_lines_spin.setValue(self.config.get("log_max_lines", 500))
        sc_l.addLayout(_field("Maks Baris Log", self.log_lines_spin,
                               "Jumlah maks baris log yang ditampilkan"))
        sc_l.addStretch()

        save_btn = QPushButton(qta.icon("fa5s.save", color=C['success']), "  Simpan Semua Setting")
        save_btn.clicked.connect(self._save_config)
        set_outer.addWidget(save_btn)

        # LOG
        log_card = QFrame(); log_card.setObjectName("Card")
        log_lay  = QVBoxLayout(log_card)
        log_lay.setContentsMargins(14,12,14,12); log_lay.setSpacing(8)
        splitter.addWidget(log_card)
        splitter.setSizes([460, 220])
        lh = QHBoxLayout()
        lh.addWidget(_sec_header("Realtime Log", "fa5s.terminal"))
        clr_btn = QPushButton(qta.icon("fa5s.eraser", color=C['text_dim']), "  Clear Log")
        clr_btn.setFixedHeight(26)
        clr_btn.clicked.connect(lambda: self.log.clear())
        lh.addStretch(); lh.addWidget(clr_btn)
        log_lay.addLayout(lh)
        self.log = LogViewer(max_lines=self.config.get("log_max_lines", 500))
        log_lay.addWidget(self.log)

        # Action bar
        div2 = QFrame(); div2.setObjectName("Divider"); main_lay.addWidget(div2)
        ab = QHBoxLayout(); ab.setSpacing(12)
        self.queue_info = QLabel("Siap memproses")
        self.queue_info.setStyleSheet(f"color:{C['text_dim']};")
        self.start_btn = QPushButton(qta.icon("fa5s.play", color="white"), "  MULAI PROSES")
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.setMinimumWidth(180); self.start_btn.setFixedHeight(44)
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton(qta.icon("fa5s.stop", color=C['error']), "  CANCEL")
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setFixedHeight(44); self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        ab.addWidget(self.queue_info); ab.addStretch()
        ab.addWidget(self.start_btn); ab.addWidget(self.cancel_btn)
        main_lay.addLayout(ab)

        self.log.append_log(f"🎥 {APP_NAME} v{APP_VER} siap", "SUCCESS")
        self.log.append_log(
            f"Project root: {_PROJECT_ROOT}", "DEBUG")
        self.log.append_log(
            "Semua setting bisa diubah dari panel Settings", "INFO")

    # ── FILE MANAGEMENT ───────────────────────────────────────────────────────────
    def _on_drop(self, paths):
        if not paths: self._browse_files(); return
        self._add_files(paths)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Pilih Video", "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv)")
        self._add_files(files)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Output")
        if d: self.out_dir_edit.setText(d)

    def _add_files(self, paths):
        added = 0
        for p in paths:
            if p and p not in self._video_paths:
                self._video_paths.append(p)
                item = QListWidgetItem(
                    qta.icon("fa5s.file-video", color=C['info']), os.path.basename(p))
                item.setToolTip(p)
                self.file_list.addItem(item)
                added += 1
        if added: self.log.append_log(f"Ditambahkan {added} file", "INFO")
        self._update_queue_info()

    def _clear_files(self):
        self._video_paths.clear()
        self.file_list.clear()
        self._update_queue_info()

    def _update_queue_info(self):
        n = len(self._video_paths)
        w = min(n, self.workers_spin.value())
        self.file_count_lbl.setText(f"{n} file")
        if n == 0:   self.queue_info.setText("Siap memproses")
        elif n == 1: self.queue_info.setText("1 video — single mode")
        else:        self.queue_info.setText(f"{n} video — {w} worker paralel")

    # ── START / CANCEL ───────────────────────────────────────────────────────────
    def _start(self):
        if not self._video_paths:
            self.log.append_log("⚠️ Tambahkan setidaknya 1 video", "WARNING"); return
        if not self.api_key_edit.text().strip():
            self.log.append_log("⚠️ Firefox Relay API Key belum diisi", "WARNING"); return
        self._save_config()
        n   = len(self._video_paths)
        cfg = dict(self.config)
        self._set_running(True)
        self.progress_bar.setValue(0)
        self.log.append_log(f"🚀 Memulai proses {n} video...", "INFO")
        self.processor = (
            A1DProcessor(_PROJECT_ROOT, self._video_paths[0], cfg)
            if n == 1 else
            BatchProcessor(_PROJECT_ROOT, self._video_paths, cfg)
        )
        self.processor.log_signal.connect(self.log.append_log)
        self.processor.progress_signal.connect(self._on_progress)
        self.processor.finished_signal.connect(self._on_finished)
        self.processor.start()

    def _cancel(self):
        if self.processor:
            self.processor.cancel()
            self.log.append_log("⚠️ Proses dibatalkan", "WARNING")
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

    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        if msg: self.prog_label.setText(msg); self.status_lbl.setText(f"{pct}%")

    def _on_finished(self, ok: bool, msg: str, *args):
        self._set_running(False)
        if ok: self.progress_bar.setValue(100)
        self.log.append_log(f"{'\u2705' if ok else '\u274c'} {msg}", "SUCCESS" if ok else "ERROR")
        self.status_lbl.setText("✅ Selesai" if ok else "❌ Gagal")
        self.status_lbl.setStyleSheet(
            f"color:{C['success']};" if ok else f"color:{C['error']};")
        self.prog_label.setText(msg)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith(
                     ('.mp4','.mkv','.mov','.avi','.webm','.flv','.wmv'))]
        self._add_files(paths)

    def closeEvent(self, e):
        self._save_config()
        if self.processor and self._running: self.processor.cancel()
        e.accept()


# ══ ENTRY POINT ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VER)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
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
    win.show()
    sys.exit(app.exec())
