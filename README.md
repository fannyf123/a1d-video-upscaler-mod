<div align="center">

# 🎬 A1D Video Upscaler Mod

**Otomasi batch upscale video via [a1d.ai](https://a1d.ai) — GUI modern, FFmpeg post-processing, zero API key**

[![Version](https://img.shields.io/badge/Version-2.7.0-blue?style=for-the-badge)](https://github.com/fannyf123/a1d-video-upscaler-mod/releases)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.0%2B-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython)
[![Playwright](https://img.shields.io/badge/Playwright-1.42%2B-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Auto_Install-orange?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

*Fork dari [SotongHD](https://github.com/SotongHD) — dimodifikasi untuk batch processing, Mailticking, dan FFmpeg post-processing*

</div>

---

## ✨ Fitur Utama

| Fitur | Keterangan |
|---|---|
| 🤖 **Full Otomasi** | Login, upload, pilih kualitas, download — semua otomatis via Playwright |
| 🚀 **Batch Paralel** | Proses hingga **5 video sekaligus** dengan antrian cerdas |
| 📧 **Mailticking** | Email temporary otomatis — **tanpa API key, tanpa setup** |
| 🎥 **FFmpeg Post-Processing** | Encode ulang hasil A1D: H.264/H.265, CRF, preset Adobe Stock 4K |
| 🔇 **Adobe Stock Ready** | Preset mute audio + faststart — siap upload ke Adobe Stock langsung |
| 🎨 **Dark / Light Theme** | GUI GitHub-style, drag & drop, real-time log berwarna |
| ⚙️ **Settings Lengkap** | Worker, timeout, FFmpeg preset, CRF, encode speed — semua dari GUI |
| 💻 **Auto Setup** | `Launcher.bat` install Python, Playwright, dan **FFmpeg otomatis** |

---

## 💻 Requirements

| Komponen | Versi | Keterangan |
|---|---|---|
| Windows | 10 / 11 | Launcher.bat otomatis setup semua |
| Python | 3.12 (portable) | Di-download otomatis oleh Launcher |
| Chromium | via Playwright | Di-install otomatis |
| FFmpeg | release-essentials | Di-download otomatis dari gyan.dev |

> ✅ **Tidak perlu install apapun secara manual** — cukup jalankan `Launcher.bat`

---

## 🚀 Quick Start (Windows)

```bat
:: 1. Clone repo
git clone https://github.com/fannyf123/a1d-video-upscaler-mod.git
cd a1d-video-upscaler-mod

:: 2. Jalankan launcher (install semua otomatis)
Launcher.bat
```

Launcher akan otomatis:
1. **[1/4]** Download & setup Python 3.12 portable
2. **[2/4]** Install semua Python dependencies (`requirements.txt`)
3. **[3/4]** Install Playwright Chromium (~130 MB, sekali saja)
4. **[4/4]** Download & install FFmpeg portable (~75 MB, sekali saja)
5. 🚀 Jalankan `main.py`

### Linux / macOS

```bash
bash Launcher.sh
```

> ⚠️ FFmpeg di Linux/macOS perlu install manual: `sudo apt install ffmpeg` atau `brew install ffmpeg`

### Manual (tanpa Launcher)

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

---

## ⚙️ Konfigurasi (`config.json`)

File ini di-generate otomatis saat pertama kali dijalankan. Semua setting bisa diubah langsung dari tab **Settings** di GUI.

```json
{
  "output_quality": "4k",
  "output_dir": "",
  "headless": true,
  "max_workers": 3,
  "batch_stagger_delay": 15,
  "initial_download_wait": 120,
  "processing_hang_timeout": 1800,
  "download_timeout": 600,
  "a1d_url": "https://a1d.ai",
  "theme": "dark",
  "ffmpeg": {
    "enabled": true,
    "preset_name": "adobe_stock_4k_h264",
    "mute_audio": true,
    "replace_original": true,
    "crf": 18,
    "encode_preset": "slow",
    "timeout": 7200,
    "video_codec": "libx264",
    "pix_fmt": "yuv420p",
    "scale": "3840:2160",
    "audio_codec": "aac",
    "audio_bitrate": "320k",
    "extra_args": "-movflags +faststart"
  }
}
```

### Parameter Utama

| Key | Default | Keterangan |
|---|---|---|
| `output_quality` | `4k` | Target upscale: `1080p` / `2k` / `4k` |
| `output_dir` | `""` | Folder output (kosong = folder video/OUTPUT) |
| `headless` | `true` | Browser berjalan di background (tanpa tampilan) |
| `max_workers` | `3` | Jumlah video paralel (1–5) |
| `batch_stagger_delay` | `15` | Jeda detik antar worker mulai |
| `initial_download_wait` | `120` | Tunggu sebelum cek tombol Download (detik) |
| `processing_hang_timeout` | `1800` | Timeout total render per video (detik) |
| `download_timeout` | `600` | Timeout download file (detik) |
| `a1d_url` | `https://a1d.ai` | URL service (ubah jika domain berganti) |

### FFmpeg Settings

| Key | Default | Keterangan |
|---|---|---|
| `ffmpeg.enabled` | `true` | Aktifkan FFmpeg setelah A1D selesai |
| `ffmpeg.preset_name` | `adobe_stock_4k_h264` | Profil encode output |
| `ffmpeg.mute_audio` | `true` | Hapus audio (`-an`) — wajib untuk Adobe Stock |
| `ffmpeg.replace_original` | `true` | Ganti file A1D dengan hasil FFmpeg |
| `ffmpeg.crf` | `18` | Kualitas: `0`=lossless, `18`=sangat bagus, `28`=medium |
| `ffmpeg.encode_preset` | `slow` | Kecepatan encode: `ultrafast` → `veryslow` |

---

## 📁 Struktur Proyek

```
a1d-video-upscaler-mod/
├── App/
│   ├── background_process.py    # Core: Playwright automation (A1DProcessor)
│   ├── batch_processor.py       # Batch: antrian multi-video (BatchProcessor)
│   ├── ffmpeg_postprocessor.py  # FFmpeg post-processing engine + preset defs
│   ├── mailticking_pw.py        # Mailticking temp email (tanpa API key)
│   ├── temp_cleanup.py          # Bersihkan file temp / .crdownload
│   ├── progress_handler.py      # Progress tracking per worker
│   ├── logger.py                # Logging utilities
│   └── __init__.py
├── main.py                      # GUI utama (PySide6 dark/light, v2.7.0)
├── config.default.json          # Template konfigurasi default
├── requirements.txt             # Python dependencies
├── Launcher.bat                 # Auto-setup + launcher (Windows)
├── Launcher.sh                  # Launcher (Linux/macOS)
├── build.spec                   # PyInstaller config
├── build_local.bat              # Build .exe lokal
└── update.bat                   # Auto-update dari GitHub
```

---

## 🔄 Cara Kerja

```
1. User drag & drop video ke GUI  →  klik RUN UPSCALER
2. BatchProcessor start N worker paralel (stagger delay antar start)
   └─ Tiap worker (A1DProcessor):
       ├─ Mailticking   →  buat email temporary sekali pakai (otomatis)
       ├─ Playwright    →  buka a1d.ai, sign-in dengan email temp
       ├─ OTP           →  baca kode dari Mailticking inbox, isi otomatis
       ├─ Upload        →  upload file video ke a1d.ai
       ├─ Generate      →  pilih kualitas (4K/2K/1080p), klik Generate
       ├─ Download      →  polling tombol Download, simpan ke output folder
       └─ FFmpeg        →  [jika enabled] encode ulang:
             ├─ Preset: H.264/H.265, resolusi, bitrate
             ├─ Mute audio → Adobe Stock compliant
             └─ Replace original atau simpan terpisah
3. Summary: ✅ N berhasil  ❌ N gagal  (total N video)
```

---

## 🎬 FFmpeg Post-Processing

Setelah A1D selesai, file di-encode ulang oleh FFmpeg untuk memastikan kompatibilitas maksimal:

| Preset | Resolusi | Codec | Keterangan |
|---|---|---|---|
| `adobe_stock_4k_h264` | 3840×2160 | H.264 High 5.2 | Default — Adobe Stock 4K |
| `adobe_stock_4k_h265` | 3840×2160 | H.265 Main | Lebih kecil, kualitas sama |
| `adobe_stock_2k_h264` | 2560×1440 | H.264 | Adobe Stock 2K |
| `adobe_stock_1080p_h264` | 1920×1080 | H.264 | Adobe Stock 1080p |

Semua preset:
- `-pix_fmt yuv420p` — kompatibel maksimal
- `-movflags +faststart` — web streaming ready
- Mute audio opsional (`-an`) — wajib untuk stock video

---

## 🔧 Troubleshooting

| Error | Solusi |
|---|---|
| `[ERROR] Gagal download Python` | Cek koneksi internet, coba lagi |
| `[ERROR] Gagal install Chromium` | Jalankan ulang Launcher.bat |
| FFmpeg tidak terinstall | Cek log di step [4/4], atau install manual dari [ffmpeg.org](https://ffmpeg.org/download.html) dan tambahkan ke PATH |
| OTP timeout | Naikkan `initial_download_wait` di Settings |
| Worker hang | Naikkan `processing_hang_timeout`, atau klik **Force Reset** di Settings |
| Video gagal di-upscale | Cek tab System Logs untuk detail error per worker |

---

## 📊 Changelog

### v2.7.0
- ➕ FFmpeg Post-Processing UI di Settings (preset, CRF, encode speed, mute, replace)
- ➕ Launcher.bat auto-install FFmpeg portable (gyan.dev + BtbN fallback)
- 🔄 Migrasi email: Firefox Relay → **Mailticking** (tanpa API key)
- 🔊 Hapus field Firefox Relay Key dari Settings UI
- 📁 Cleanup file legacy (a1d_upscaler.py, config_manager.py, file_processor.py, firefox_relay.py)
- 🐛 Fix Launcher.bat: ganti `!()` → `-not ()` untuk kompatibilitas `EnableDelayedExpansion`

### v2.6.x
- Batch processor dengan queue cerdas (N worker, stagger delay)
- Dark/Light theme GitHub-style
- Real-time log dengan badge INFO/SUCCESS/WARNING/ERROR

---

## ⚠️ Disclaimer

Tool ini dibuat untuk keperluan **pribadi / edukasi**. Penggunaan berlebihan dapat melanggar Terms of Service [a1d.ai](https://a1d.ai). Gunakan dengan bijak dan bertanggung jawab.

---

<div align="center">

Made with ❤️ by <a href="https://github.com/fannyf123">fannyf123</a> &nbsp;·&nbsp; Inspired by <a href="https://github.com/SotongHD">SotongHD</a>

</div>
