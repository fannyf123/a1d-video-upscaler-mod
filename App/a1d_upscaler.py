import os
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QProgressBar, QFrame,
    QFileDialog, QDialog, QLineEdit, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QIcon, QFont, QColor
import qtawesome as qta

from App.config_manager import load_config, save_config
from App.file_processor import is_valid_video
from App.firefox_relay import FirefoxRelay
from App.background_process import A1DProcessor

# ── Color Palette ─────────────────────────────────────────────────────────────
BG      = "#0f172a"
CARD    = "#1e293b"
ACCENT  = "#7c3aed"
SUCCESS = "#22c55e"
WARN    = "#f59e0b"
ERR     = "#ef4444"
TEXT    = "#f1f5f9"
MUTED   = "#64748b"


STYLESHEET = f"""
QMainWindow, QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI', sans-serif; }}
QPushButton {{
    background: {ACCENT}; color: white; border-radius: 8px;
    padding: 8px 18px; font-size: 13px; font-weight: 600;
}}
QPushButton:hover {{ background: #6d28d9; }}
QPushButton:disabled {{ background: {MUTED}; color: #334155; }}
QPushButton#btn_cancel {{ background: {ERR}; }}
QPushButton#btn_cancel:hover {{ background: #dc2626; }}
QPushButton#btn_settings {{ background: transparent; border: 1px solid {MUTED}; }}
QPushButton#btn_settings:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QComboBox {{
    background: {CARD}; color: {TEXT}; border: 1px solid {MUTED};
    border-radius: 6px; padding: 6px 12px; font-size: 13px;
}}
QComboBox::drop-down {{ border: none; }}
QProgressBar {{
    background: {CARD}; border-radius: 5px; height: 10px; text-align: center;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}
QTextEdit {{
    background: #0b1120; color: {TEXT}; border: 1px solid #1e293b;
    border-radius: 8px; font-family: 'Consolas', monospace; font-size: 12px;
    padding: 8px;
}}
QLabel {{ color: {TEXT}; }}
QLineEdit {{
    background: {CARD}; color: {TEXT}; border: 1px solid {MUTED};
    border-radius: 6px; padding: 6px 12px; font-size: 13px;
}}
QCheckBox {{ color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {MUTED}; background: {CARD};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
"""


class DropFrame(QFrame):
    from PySide6.QtCore import Signal
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)
        self._default_style = f"QFrame {{ border: 2px dashed {MUTED}; border-radius: 12px; background: {CARD}; }}"
        self._hover_style   = f"QFrame {{ border: 2px dashed {ACCENT}; border-radius: 12px; background: #1a1332; }}"
        self.setStyleSheet(self._default_style)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)

        self._icon_lbl = QLabel("🎬")
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setStyleSheet("font-size: 36px; border: none;")

        self._text_lbl = QLabel("Drag & Drop video ke sini\natau klik untuk pilih file")
        self._text_lbl.setAlignment(Qt.AlignCenter)
        self._text_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; border: none;")

        lay.addWidget(self._icon_lbl)
        lay.addWidget(self._text_lbl)
        self.setCursor(Qt.PointingHandCursor)

    def set_video(self, path: str):
        name = os.path.basename(path)
        self._icon_lbl.setText("📹")
        self._text_lbl.setText(f"{name}\n(klik untuk ganti)")
        self._text_lbl.setStyleSheet(f"color: #a78bfa; font-size: 13px; border: none; font-weight: bold;")

    def reset(self):
        self._icon_lbl.setText("🎬")
        self._text_lbl.setText("Drag & Drop video ke sini\natau klik untuk pilih file")
        self._text_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; border: none;")

    def mousePressEvent(self, _):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Pilih Video",
            filter="Video (*.mp4 *.mov *.avi *.mkv *.webm *.m4v *.wmv);;All (*)"
        )
        if files:
            self.files_dropped.emit(files)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(self._hover_style)

    def dragLeaveEvent(self, _):
        self.setStyleSheet(self._default_style)

    def dropEvent(self, e):
        self.setStyleSheet(self._default_style)
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
        if paths:
            self.files_dropped.emit(paths)


class SettingsDialog(QDialog):
    def __init__(self, base_dir: str, config: dict, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.config   = config
        self.setWindowTitle("Pengaturan")
        self.setMinimumWidth(460)
        self.setStyleSheet(STYLESHEET)

        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 20)

        # ── Firefox Relay API Key ────────────────────────────────────────────
        lay.addWidget(QLabel("🦊  Firefox Relay API Key"))
        self.inp_key = QLineEdit(config.get("relay_api_key", ""))
        self.inp_key.setPlaceholderText("Paste API Key dari relay.firefox.com/accounts/profile/")
        self.inp_key.setEchoMode(QLineEdit.Password)
        lay.addWidget(self.inp_key)

        btn_show = QPushButton("👁  Tampilkan / Sembunyikan Key")
        btn_show.setObjectName("btn_settings")
        btn_show.clicked.connect(self._toggle_echo)
        lay.addWidget(btn_show)

        btn_test = QPushButton("🔌  Test Koneksi API Key")
        btn_test.setObjectName("btn_settings")
        btn_test.clicked.connect(self._test_relay)
        lay.addWidget(btn_test)

        # ── Headless ─────────────────────────────────────────────────────────
        self.chk_headless = QCheckBox("Headless Mode (browser di background)")
        self.chk_headless.setChecked(config.get("headless", True))
        lay.addWidget(self.chk_headless)

        # ── Timeout ──────────────────────────────────────────────────────────
        lay.addWidget(QLabel("Timeout Proses (detik) — default 1800 = 30 menit"))
        self.inp_timeout = QLineEdit(str(config.get("processing_hang_timeout", 1800)))
        lay.addWidget(self.inp_timeout)

        # ── Save ─────────────────────────────────────────────────────────────
        lay.addWidget(QLabel(""))  # spacer
        btn_save = QPushButton("💾  Simpan Pengaturan")
        btn_save.clicked.connect(self._save)
        lay.addWidget(btn_save)

    def _toggle_echo(self):
        if self.inp_key.echoMode() == QLineEdit.Password:
            self.inp_key.setEchoMode(QLineEdit.Normal)
        else:
            self.inp_key.setEchoMode(QLineEdit.Password)

    def _test_relay(self):
        key = self.inp_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Error", "Masukkan API Key terlebih dahulu!")
            return
        relay = FirefoxRelay(key)
        if relay.test_connection():
            QMessageBox.information(self, "Sukses", "Koneksi Firefox Relay berhasil! ✅")
        else:
            QMessageBox.critical(self, "Gagal", "API Key tidak valid atau koneksi gagal. ❌")

    def _save(self):
        self.config["relay_api_key"] = self.inp_key.text().strip()
        self.config["headless"]      = self.chk_headless.isChecked()
        try:
            self.config["processing_hang_timeout"] = int(self.inp_timeout.text())
        except ValueError:
            pass
        save_config(self.base_dir, self.config)
        FirefoxRelay.save_key(self.base_dir, self.config["relay_api_key"])
        QMessageBox.information(self, "Tersimpan", "Pengaturan berhasil disimpan! ✅")
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, base_dir: str, icon_path):
        super().__init__()
        self.base_dir    = base_dir
        self.config      = load_config(base_dir)
        self.video_path  = ""
        self.processor   = None

        self.setWindowTitle("A1D Video Upscaler v2")
        self.setMinimumSize(700, 620)
        self.setStyleSheet(STYLESHEET)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # ── Header ───────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("🎬  A1D Video Upscaler")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: #a78bfa;")
        hdr.addWidget(title)
        hdr.addStretch()
        btn_settings = QPushButton(" ⚙  Settings")
        btn_settings.setObjectName("btn_settings")
        btn_settings.setFixedWidth(110)
        btn_settings.clicked.connect(self._open_settings)
        hdr.addWidget(btn_settings)
        root.addLayout(hdr)

        sub = QLabel("Upscale otomatis via a1d.ai menggunakan Firefox Relay")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        root.addWidget(sub)

        # ── Drop area ─────────────────────────────────────────────────────────
        self.drop_frame = DropFrame()
        self.drop_frame.files_dropped.connect(self._on_files)
        root.addWidget(self.drop_frame)

        # ── Quality selector ─────────────────────────────────────────────────
        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Kualitas Output:"))
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["1080p", "2K", "4K"])
        current_q = self.config.get("output_quality", "4k").upper()
        idx = self.combo_quality.findText(current_q, Qt.MatchFixedString)
        self.combo_quality.setCurrentIndex(max(0, idx))
        self.combo_quality.currentTextChanged.connect(self._on_quality_changed)
        q_row.addWidget(self.combo_quality)
        q_row.addStretch()
        root.addLayout(q_row)

        # ── Progress bar ─────────────────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        root.addWidget(self.progress)

        self.lbl_status = QLabel("Siap — pilih video dan klik Start")
        self.lbl_status.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        root.addWidget(self.lbl_status)

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton(" ▶  Start Upscale")
        self.btn_start.setFixedHeight(42)
        self.btn_start.clicked.connect(self._start)
        btn_row.addWidget(self.btn_start)

        self.btn_cancel = QPushButton(" ✕  Cancel")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setFixedHeight(42)
        self.btn_cancel.setFixedWidth(110)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        btn_row.addWidget(self.btn_cancel)
        root.addLayout(btn_row)

        # ── Log terminal ─────────────────────────────────────────────────────
        log_lbl = QLabel("📋  Log")
        log_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        root.addWidget(log_lbl)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(160)
        root.addWidget(self.log_box)

        # Footer
        footer = QLabel("Made with ❤️  by fannyf123 — Inspired by SotongHD")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        root.addWidget(footer)

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_files(self, paths: list):
        valid = [p for p in paths if is_valid_video(p)]
        if not valid:
            QMessageBox.warning(self, "File Tidak Valid",
                "File yang dipilih bukan video yang didukung.\n"
                "Format: MP4, MOV, AVI, MKV, WEBM, M4V, WMV")
            return
        self.video_path = valid[0]
        self.drop_frame.set_video(self.video_path)
        self._log(f"Video dipilih: {os.path.basename(self.video_path)}", "INFO")

    def _on_quality_changed(self, text: str):
        self.config["output_quality"] = text.lower()

    def _open_settings(self):
        dlg = SettingsDialog(self.base_dir, self.config, self)
        dlg.exec()
        self.config = load_config(self.base_dir)

    def _start(self):
        if not self.video_path:
            QMessageBox.warning(self, "Pilih Video", "Belum ada video yang dipilih!")
            return
        if not self.config.get("relay_api_key", "").strip():
            QMessageBox.warning(self, "API Key",
                "Firefox Relay API Key belum diset!\nBuka Settings ⚙ terlebih dahulu.")
            return

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setValue(0)
        self._log("=" * 50, "INFO")
        self._log(f"Memulai: {os.path.basename(self.video_path)}", "INFO")
        self._log(f"Kualitas: {self.config.get('output_quality', '4k').upper()}", "INFO")

        self.processor = A1DProcessor(self.base_dir, self.video_path, self.config)
        self.processor.log_signal.connect(self._log)
        self.processor.progress_signal.connect(self._update_progress)
        self.processor.finished_signal.connect(self._on_finished)
        self.processor.start()

    def _cancel(self):
        if self.processor:
            self.processor.cancel()
            self._log("Proses dibatalkan oleh user.", "WARNING")
        self.btn_cancel.setEnabled(False)
        self.btn_start.setEnabled(True)

    def _update_progress(self, pct: int, msg: str):
        self.progress.setValue(pct)
        if msg:
            self.lbl_status.setText(msg)

    def _on_finished(self, success: bool, message: str, output_path: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setValue(100 if success else self.progress.value())

        if success:
            self.lbl_status.setText(f"Selesai! Output: {output_path}")
            self._log(f"SELESAI: {output_path}", "SUCCESS")
            QMessageBox.information(self, "Selesai!",
                f"Video berhasil di-upscale!\n\nOutput:\n{output_path}")
            self.video_path = ""
            self.drop_frame.reset()
        else:
            self.lbl_status.setText(f"Error: {message}")
            self._log(f"GAGAL: {message}", "ERROR")
            QMessageBox.critical(self, "Error", f"Proses gagal:\n{message}")

    def _log(self, msg: str, level: str = "INFO"):
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO":    TEXT,
            "SUCCESS": SUCCESS,
            "WARNING": WARN,
            "ERROR":   ERR,
        }
        color = colors.get(level.upper(), TEXT)
        html  = f'<span style="color:{MUTED}">[{ts}]</span> <span style="color:{color}">{msg}</span>'
        self.log_box.append(html)
        # Auto scroll ke bawah
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())


def run_app(base_dir: str, icon_path):
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(base_dir, icon_path)
    win.show()
    sys.exit(app.exec())
