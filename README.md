<div align="center">

# 🎬 A1D Video Upscaler Batch

**Otomasi upscale video via [a1d.ai](https://a1d.ai) dengan antarmuka GUI modern**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.0%2B-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython)
[![Playwright](https://img.shields.io/badge/Playwright-1.42%2B-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

---

## ✨ Fitur

| Fitur | Keterangan |
|---|---|
| 🤖 **Full Otomasi** | Login, upload, pilih kualitas, download — semua otomatis |
| 🚀 **Batch Mode** | Proses hingga **5 video paralel** sekaligus |
| 🎨 **Dark GUI** | Antarmuka modern dark-theme, drag & drop support |
| 🦁 **Playwright** | Tidak perlu install Chrome — Playwright bundled Chromium |
| 📧 **Email Mask** | Firefox Relay untuk akun temporary sekali pakai |
| 📊 **Real-time Log** | Log berwarna dengan timestamp per worker |
| ⚙️ **Configurable** | Kualitas output, jumlah worker, stagger delay |

---

## 🖥️ Screenshot

> *Dark theme GUI dengan drag & drop, batch mode, dan real-time log*

---

## 📦 Requirements

- Python **3.10+**
- Windows 10/11 atau Linux
- Firefox Relay API Key → [relay.firefox.com](https://relay.firefox.com)
- Gmail + Google API credentials (`credentials.json`)

---

## 🚀 Instalasi

### 1. Clone repo
```bash
git clone https://github.com/fannyf123/a1d-video-upscaler-v2.git
cd a1d-video-upscaler-v2
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Playwright browser
```bash
playwright install chromium
```
> ⚡ Tidak perlu download Chrome secara manual — Playwright download Chromium sendiri (~170 MB)

### 4. Setup Google OAuth
Letakkan file `credentials.json` (Gmail API) di root folder.
Pertama kali run akan minta login Google via browser.

### 5. Jalankan
```bash
# Windows
Launcher.bat

# Linux / macOS
bash Launcher.sh

# Atau langsung
python main.py
```

---

## ⚙️ Konfigurasi (`config.json`)

```json
{
  "relay_api_key": "YOUR_FIREFOX_RELAY_API_KEY",
  "output_quality": "4k",
  "output_dir": "",
  "headless": true,
  "max_workers": 3,
  "batch_stagger_delay": 15,
  "processing_hang_timeout": 1800,
  "download_timeout": 600
}
```

| Key | Tipe | Default | Keterangan |
|---|---|---|---|
| `relay_api_key` | string | — | Firefox Relay API key |
| `output_quality` | string | `4k` | `1080p` / `2k` / `4k` |
| `output_dir` | string | `""` | Folder output (kosong = folder video/OUTPUT) |
| `headless` | bool | `true` | Jalankan browser tanpa tampilan |
| `max_workers` | int | `3` | Jumlah video paralel (1–5) |
| `batch_stagger_delay` | int | `15` | Jeda detik antar worker start |
| `processing_hang_timeout` | int | `1800` | Timeout proses render (detik) |
| `download_timeout` | int | `600` | Timeout download file (detik) |

---

## 📁 Struktur Proyek

```
a1d-video-upscaler-v2/
├── App/
│   ├── background_process.py   # Core: Playwright automation (A1DProcessor)
│   ├── batch_processor.py      # Batch: paralel multi-video (BatchProcessor)
│   ├── firefox_relay.py        # Firefox Relay API wrapper
│   └── gmail_otp.py            # Gmail OTP reader via Google API
├── main.py                     # GUI utama (PySide6 dark theme)
├── config.json                 # Konfigurasi
├── requirements.txt
├── Launcher.bat                # Launcher Windows
└── Launcher.sh                 # Launcher Linux/macOS
```

---

## 🔄 Cara Kerja

```
1. User drag & drop video ke GUI
2. BatchProcessor start N worker paralel (stagger 15s)
   └─ Tiap worker (A1DProcessor):
       ├─ Firefox Relay → buat email mask sementara
       ├─ Playwright Chromium → buka a1d.ai/auth/sign-in
       ├─ Input email → request OTP
       ├─ Gmail API → baca OTP otomatis
       ├─ Submit OTP → login berhasil
       ├─ Playwright → buka video editor, upload file
       ├─ Pilih kualitas (4K/2K/1080p)
       ├─ Klik Generate → tunggu 2 menit awal
       ├─ Polling tombol Download → expect_download()
       └─ File tersimpan ke output folder
3. Summary: ✅ N berhasil / ❌ N gagal
```

---

## 🛠️ Browser Engine

App ini menggunakan **Playwright Chromium** (bukan Selenium):

| | Selenium (lama) | Playwright (sekarang) |
|---|---|---|
| Install | Harus download ChromeDriver manual | `playwright install chromium` otomatis |
| Download file | Monitor folder manual | `expect_download()` native |
| Tunggu elemen | `WebDriverWait` manual | Auto-wait built-in |
| Click intercepted | Butuh `_safe_click()` workaround | Handled otomatis |

---

## ⚠️ Disclaimer

Tool ini dibuat untuk keperluan **pribadi/edukasi**. Penggunaan berlebihan dapat melanggar Terms of Service a1d.ai. Gunakan dengan bijak.

---

<div align="center">
Made with ❤️ by <a href="https://github.com/fannyf123">fannyf</a>
</div>
