import os
import sys
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QProgressBar, QFrame,
    QFileDialog, QDialog, QLineEdit, QMessageBox, QCheckBox,
    QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from App.config_manager import load_config, save_config, get_user_data_dir, get_gmail_token_paths
from App.file_processor import is_valid_video
from App.firefox_relay import FirefoxRelay
from App.background_process import A1DProcessor

# ── Color Palette ────────────────────────────────────────────────────────────────
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
QPushButton#btn_secondary {{
    background: {CARD}; color: {TEXT}; border: 1px solid {MUTED}; padding: 6px 12px;
}}
QPushButton#btn_secondary:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
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
QSplitter::handle:vertical {{
    background: {CARD}; height: 6px; margin: 2px 0;
    border-top: 1px solid {MUTED};
}}
QSplitter::handle:vertical:hover {{ background: {ACCENT}; }}
"""


class DropFrame(QFrame):
    from PySide6.QtCore import Signal
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self._default_style = f"QFrame {{ border: 2px dashed {MUTED}; border-radius: 12px; background: {CARD}; }}"
        self._hover_style   = f"QFrame {{ border: 2px dashed {ACCENT}; border-radius: 12px; background: #1a1332; }}"
        self.setStyleSheet(self._default_style)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(4)

        self._icon_lbl = QLabel("🎥")
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setStyleSheet("font-size: 28px; border: none;")

        self._text_lbl = QLabel("Drag & Drop video ke sini\natau klik untuk pilih file")
        self._text_lbl.setAlignment(Qt.AlignCenter)
        self._text_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; border: none;")

        lay.addWidget(self._icon_lbl)
        lay.addWidget(self._text_lbl)
        self.setCursor(Qt.PointingHandCursor)

    def set_video(self, path: str):
        self._icon_lbl.setText("📹")
        self._text_lbl.setText(f"{os.path.basename(path)}\n(klik untuk ganti)")
        self._text_lbl.setStyleSheet("color: #a78bfa; font-size: 13px; border: none; font-weight: bold;")

    def reset(self):
        self._icon_lbl.setText("🎥")
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


# ══════════════════════════════════════════════════════════════════════════
#  SETTINGS DIALOG
# ══════════════════════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    def __init__(self, base_dir: str, config: dict, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.config   = config
        self.setWindowTitle("Pengaturan")
        self.setMinimumWidth(500)
        self.setSizeGripEnabled(True)   # ← dialog bisa di-resize
        self.setStyleSheet(STYLESHEET)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 20, 20, 20)

        # ─ Info lokasi config (tidak terhapus saat update) ─
        udd = get_user_data_dir()
        info_lbl = QLabel(f"📁  Config tersimpan di (aman dari update):\n{udd}")
        info_lbl.setStyleSheet(
            f"color: {SUCCESS}; font-size: 10px; padding: 6px 10px;"
            f"background: #0d2d1a; border-radius: 6px; border: 1px solid #1a4a2a;"
        )
        info_lbl.setWordWrap(True)
        lay.addWidget(info_lbl)

        # ─ Firefox Relay ─
        lay.addWidget(self._section("Firefox Relay"))
        lay.addWidget(QLabel("🦊  Firefox Relay API Key"))
        self.inp_key = QLineEdit(config.get("relay_api_key", ""))
        self.inp_key.setPlaceholderText("Paste API Key dari relay.firefox.com/accounts/profile/")
        self.inp_key.setEchoMode(QLineEdit.Password)
        lay.addWidget(self.inp_key)

        row_key = QHBoxLayout()
        btn_show = QPushButton("👁  Tampilkan Key")
        btn_show.setObjectName("btn_secondary")
        btn_show.clicked.connect(self._toggle_echo)
        row_key.addWidget(btn_show)
        btn_test = QPushButton("🔌  Test Koneksi")
        btn_test.setObjectName("btn_secondary")
        btn_test.clicked.connect(self._test_relay)
        row_key.addWidget(btn_test)
        lay.addLayout(row_key)

        # ─ Headless + Timeout ─
        lay.addWidget(self._section("Proses"))
        self.chk_headless = QCheckBox("Headless Mode (browser di background)")
        self.chk_headless.setChecked(config.get("headless", True))
        lay.addWidget(self.chk_headless)

        lay.addWidget(QLabel("Timeout Proses (detik) — default 1800 = 30 menit"))
        self.inp_timeout = QLineEdit(str(config.get("processing_hang_timeout", 1800)))
        lay.addWidget(self.inp_timeout)

        # ─ Gmail Token ─
        lay.addWidget(self._section("Gmail Token"))

        lbl_gmail_info = QLabel(
            "📧  Hapus token jika terjadi error autentikasi Gmail "
            "atau ingin mengganti akun Google."
        )
        lbl_gmail_info.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        lbl_gmail_info.setWordWrap(True)
        lay.addWidget(lbl_gmail_info)

        btn_reset_token = QPushButton("🗑  Reset Gmail Token")
        btn_reset_token.setObjectName("btn_secondary")
        btn_reset_token.clicked.connect(self._reset_gmail_token)
        lay.addWidget(btn_reset_token)

        # ─ Save ─
        lay.addStretch()
        btn_save = QPushButton("💾  Simpan Pengaturan")
        btn_save.clicked.connect(self._save)
        lay.addWidget(btn_save)

    # ─ Helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _section(label: str) -> QLabel:
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; font-weight: bold;"
            f"border-bottom: 1px solid {MUTED}; padding-bottom: 2px; margin-top: 6px;"
        )
        return lbl

    def _toggle_echo(self):
        self.inp_key.setEchoMode(
            QLineEdit.Normal if self.inp_key.echoMode() == QLineEdit.Password
            else QLineEdit.Password
        )

    def _test_relay(self):
        key = self.inp_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Error", "Masukkan API Key terlebih dahulu!"); return
        relay = FirefoxRelay(key)
        if relay.test_connection():
            QMessageBox.information(self, "Sukses", "Koneksi Firefox Relay berhasil! ✅")
        else:
            QMessageBox.critical(self, "Gagal", "API Key tidak valid atau koneksi gagal. ❌")

    def _reset_gmail_token(self):
        token_paths = get_gmail_token_paths(self.base_dir)
        deleted = []
        failed  = []
        for p in token_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    deleted.append(p)
                except Exception as e:
                    failed.append(f"{p} — {e}")

        if deleted:
            msg = "Token berhasil dihapus:"
            for p in deleted:
                msg += f"\n  • {p}"
            msg += "\n\nLogin Gmail akan diminta ulang pada proses berikutnya."
            if failed:
                msg += "\n\n⚠️ Gagal hapus:"
                for p in failed:
                    msg += f"\n  • {p}"
            QMessageBox.information(self, "Token Dihapus", msg)
        else:
            QMessageBox.information(
                self, "Tidak Ada Token",
                "Tidak ada token Gmail yang ditemukan.\n"
                "Login ulang akan diminta secara otomatis jika diperlukan."
            )

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


# ══════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self, base_dir: str, icon_path):
        super().__init__()
        self.base_dir   = base_dir
        self.config     = load_config(base_dir)
        self.video_path = ""
        self.processor  = None

        self.setWindowTitle("A1D Video Upscaler v2")
        self.setMinimumSize(580, 460)   # minimum size agar semua elemen muat
        self.resize(740, 760)           # ukuran awal
        self.setStyleSheet(STYLESHEET)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(0)

        # ====================================================================
        #  TOP PANE — semua kontrol (tidak scroll)
        # ====================================================================
        top_w   = QWidget()
        top_lay = QVBoxLayout(top_w)
        top_lay.setContentsMargins(0, 0, 0, 8)
        top_lay.setSpacing(8)

        # ─ Header ─
        hdr = QHBoxLayout()
        title = QLabel("🎥  A1D Video Upscaler")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #a78bfa;")
        hdr.addWidget(title)
        hdr.addStretch()
        btn_settings = QPushButton(" ⚙  Settings")
        btn_settings.setObjectName("btn_secondary")
        btn_settings.setFixedWidth(110)
        btn_settings.clicked.connect(self._open_settings)
        hdr.addWidget(btn_settings)
        top_lay.addLayout(hdr)

        sub = QLabel("Upscale otomatis via a1d.ai menggunakan Firefox Relay")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        top_lay.addWidget(sub)

        # ─ Input Video ─
        inp_lbl = QLabel("📂  Input Video")
        inp_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: bold;")
        top_lay.addWidget(inp_lbl)

        self.drop_frame = DropFrame()
        self.drop_frame.files_dropped.connect(self._on_files)
        top_lay.addWidget(self.drop_frame)

        inp_path_row = QHBoxLayout()
        self.inp_video_path = QLineEdit()
        self.inp_video_path.setPlaceholderText("Path video input...")
        self.inp_video_path.setReadOnly(True)
        self.inp_video_path.setStyleSheet(
            f"background: {CARD}; color: {MUTED}; border: 1px solid {MUTED};"
            "border-radius: 6px; padding: 5px 10px; font-size: 11px;"
        )
        inp_path_row.addWidget(self.inp_video_path)
        btn_browse_file = QPushButton("📄 Pilih File")
        btn_browse_file.setObjectName("btn_secondary")
        btn_browse_file.setFixedWidth(100)
        btn_browse_file.clicked.connect(self._browse_input_file)
        inp_path_row.addWidget(btn_browse_file)
        top_lay.addLayout(inp_path_row)

        # ─ Output Folder ─
        out_lbl = QLabel("📂  Output Folder")
        out_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: bold;")
        top_lay.addWidget(out_lbl)

        out_row = QHBoxLayout()
        self.inp_out_dir = QLineEdit(self.config.get("output_dir", ""))
        self.inp_out_dir.setPlaceholderText(
            "Default: folder video + /OUTPUT  (kosongkan untuk default)"
        )
        self.inp_out_dir.setReadOnly(True)
        out_row.addWidget(self.inp_out_dir)
        btn_browse_out = QPushButton("📁 Browse")
        btn_browse_out.setObjectName("btn_secondary")
        btn_browse_out.setFixedWidth(90)
        btn_browse_out.clicked.connect(self._browse_output)
        out_row.addWidget(btn_browse_out)
        btn_clear_out = QPushButton("✕")
        btn_clear_out.setObjectName("btn_secondary")
        btn_clear_out.setFixedWidth(34)
        btn_clear_out.setToolTip("Reset ke default (folder video + /OUTPUT)")
        btn_clear_out.clicked.connect(self._clear_output)
        out_row.addWidget(btn_clear_out)
        top_lay.addLayout(out_row)

        # ─ Quality + Progress ─
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
        top_lay.addLayout(q_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        top_lay.addWidget(self.progress)

        self.lbl_status = QLabel("Siap — pilih video dan klik Start")
        self.lbl_status.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        top_lay.addWidget(self.lbl_status)

        # ─ Buttons ─
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
        top_lay.addLayout(btn_row)

        # ====================================================================
        #  BOTTOM PANE — log (bisa di-resize dengan splitter)
        # ====================================================================
        bot_w   = QWidget()
        bot_lay = QVBoxLayout(bot_w)
        bot_lay.setContentsMargins(0, 4, 0, 0)
        bot_lay.setSpacing(4)

        log_hdr = QHBoxLayout()
        log_lbl = QLabel("📋  Log")
        log_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        log_hdr.addWidget(log_lbl)
        log_hdr.addStretch()
        btn_clear_log = QPushButton("🗑 Clear")
        btn_clear_log.setObjectName("btn_secondary")
        btn_clear_log.setFixedWidth(70)
        btn_clear_log.setFixedHeight(22)
        btn_clear_log.clicked.connect(lambda: self.log_box.clear())
        log_hdr.addWidget(btn_clear_log)
        bot_lay.addLayout(log_hdr)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bot_lay.addWidget(self.log_box, 1)  # stretch=1 agar isi ruang

        footer = QLabel("Made with ❤️  by fannyf123 — Inspired by SotongHD")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        bot_lay.addWidget(footer)

        # ====================================================================
        #  QSplitter — atas/bawah bisa di-drag untuk resize
        # ====================================================================
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top_w)
        splitter.addWidget(bot_w)
        splitter.setSizes([490, 220])        # proporsi awal
        splitter.setChildrenCollapsible(False)  # tidak bisa di-collapse sampai hilang
        root.addWidget(splitter)

    # ====================================================================
    #  EVENT HANDLERS
    # ====================================================================
    def _on_files(self, paths: list):
        valid = [p for p in paths if is_valid_video(p)]
        if not valid:
            QMessageBox.warning(
                self, "File Tidak Valid",
                "File bukan video yang didukung.\nFormat: MP4 MOV AVI MKV WEBM M4V WMV"
            )
            return
        self.video_path = valid[0]
        self.drop_frame.set_video(self.video_path)
        self.inp_video_path.setText(self.video_path)
        if not self.inp_out_dir.text().strip():
            default_out = os.path.join(os.path.dirname(self.video_path), "OUTPUT")
            self.inp_out_dir.setPlaceholderText(f"Default: {default_out}")
        self._log(f"Video: {os.path.basename(self.video_path)}", "INFO")

    def _browse_input_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Pilih Video",
            filter="Video (*.mp4 *.mov *.avi *.mkv *.webm *.m4v *.wmv);;All (*)"
        )
        if files:
            self._on_files(files)

    def _browse_output(self):
        start  = self.inp_out_dir.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Output", start)
        if folder:
            self.inp_out_dir.setText(folder)
            self.config["output_dir"] = folder
            save_config(self.base_dir, self.config)
            self._log(f"📁 Output folder: {folder}", "INFO")

    def _clear_output(self):
        self.inp_out_dir.clear()
        self.config["output_dir"] = ""
        save_config(self.base_dir, self.config)
        if self.video_path:
            default_out = os.path.join(os.path.dirname(self.video_path), "OUTPUT")
            self.inp_out_dir.setPlaceholderText(f"Default: {default_out}")
        else:
            self.inp_out_dir.setPlaceholderText(
                "Default: folder video + /OUTPUT  (kosongkan untuk default)"
            )
        self._log("📁 Output folder direset ke default", "INFO")

    def _on_quality_changed(self, text: str):
        self.config["output_quality"] = text.lower()

    def _open_settings(self):
        dlg = SettingsDialog(self.base_dir, self.config, self)
        dlg.exec()
        self.config = load_config(self.base_dir)

    def _start(self):
        if not self.video_path:
            QMessageBox.warning(self, "Pilih Video", "Belum ada video yang dipilih!"); return
        if not self.config.get("relay_api_key", "").strip():
            QMessageBox.warning(
                self, "API Key",
                "Firefox Relay API Key belum diset!\nBuka Settings ⚙ terlebih dahulu."
            ); return

        out_dir_custom = self.inp_out_dir.text().strip()
        self.config["output_dir"] = out_dir_custom

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setValue(0)
        self._log("=" * 50, "INFO")
        self._log(f"Input : {self.video_path}", "INFO")
        if out_dir_custom:
            self._log(f"Output: {out_dir_custom}", "INFO")
        else:
            self._log(
                f"Output: {os.path.join(os.path.dirname(self.video_path), 'OUTPUT')} (default)",
                "INFO"
            )
        self._log(f"Kualitas: {self.config.get('output_quality','4k').upper()}", "INFO")

        self.processor = A1DProcessor(self.base_dir, self.video_path, self.config)
        self.processor.log_signal.connect(self._log)
        self.processor.progress_signal.connect(self._update_progress)
        self.processor.finished_signal.connect(self._on_finished)
        self.processor.start()

    def _cancel(self):
        if self.processor:
            self.processor.cancel()
            self._log("Proses dibatalkan.", "WARNING")
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
            self.lbl_status.setText(f"Selesai! → {output_path}")
            self._log(f"🏁 SELESAI: {output_path}", "SUCCESS")
            QMessageBox.information(
                self, "Selesai!",
                f"Video berhasil di-upscale!✅\n\nOutput:\n{output_path}"
            )
            self.video_path = ""
            self.drop_frame.reset()
            self.inp_video_path.clear()
        else:
            self.lbl_status.setText(f"Error: {message}")
            self._log(f"❌ GAGAL: {message}", "ERROR")
            QMessageBox.critical(self, "Error", f"Proses gagal:\n{message}")

    def _log(self, msg: str, level: str = "INFO"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": TEXT, "SUCCESS": SUCCESS, "WARNING": WARN, "ERROR": ERR}
        color  = colors.get(level.upper(), TEXT)
        self.log_box.append(
            f'<span style="color:{MUTED}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())


def run_app(base_dir: str, icon_path):
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(base_dir, icon_path)
    win.show()
    sys.exit(app.exec())
