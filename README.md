<div align="center">

<br>

# 🎬 A1D Video Upscaler v2

**Otomasi upscale video ke 4K via a1d.ai — Firefox Relay + Gmail OTP + PySide6 GUI**

![Version](https://img.shields.io/badge/version-2.0.0-7c3aed?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Mac-0078d4?style=flat-square)
![Python](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)

<br>

</div>

---

## ✨ Fitur Utama

| Fitur | Keterangan |
|---|---|
| 🎬 **Drag & Drop** | Seret video langsung ke aplikasi |
| 🤖 **Full Otomasi** | Register, OTP Gmail, Upload, Upscale, Download — semua otomatis |
| 📺 **Pilih Kualitas** | Support **1080p**, **2K**, **4K** |
| 🦊 **Firefox Relay** | Email mask otomatis lewat API (tidak perlu buka browser manual) |
| 🖥️ **Headless Mode** | Proses di background tanpa jendela browser |
| 📂 **Auto Simpan** | Hasil masuk folder `OUTPUT/` di lokasi video |
| 📊 **Log Terminal** | Progress real-time berwarna di panel bawah |
| 🏗️ **SotongHD Arch** | Modular, clean code, PySide6 GUI |

---

## 🚀 Cara Pakai

### Langkah 1 — Clone / Download
```bash
git clone https://github.com/fannyf123/a1d-video-upscaler-v2.git
cd a1d-video-upscaler-v2
```
Atau download ZIP langsung di tombol hijau **Code** di atas.

---

### Langkah 2 — Setup Gmail API *(sekali saja)*

1. Buka [console.cloud.google.com](https://console.cloud.google.com/)
2. Buat project baru → aktifkan **Gmail API**
3. Buat credentials **OAuth 2.0 Desktop App**
4. Download JSON → rename jadi `credentials.json`
5. Letakkan di folder yang sama dengan `main.py`

---

### Langkah 3 — Dapatkan Firefox Relay API Key *(sekali saja)*

1. Buka [relay.firefox.com](https://relay.firefox.com) → login
2. Klik profil → **Settings**
3. Scroll ke bawah → **API Key** → copy

---

### Langkah 4 — Jalankan

**Windows:**
```
Double-click Launcher.bat
```

**Linux / macOS:**
```bash
bash Launcher.sh
```

---

### Langkah 5 — Konfigurasi & Pakai

1. Klik **⚙ Settings** di kanan atas
2. Paste **Firefox Relay API Key**
3. Pilih kualitas output: **1080p / 2K / 4K**
4. Drag & drop video ke area tengah
5. Klik **▶ Start Upscale** — selesai!

---

## 📁 Struktur Proyek

```
a1d-video-upscaler-v2/
├── main.py                    ← Entry point
├── config.json                ← Konfigurasi global
├── requirements.txt           ← Dependencies
├── Launcher.bat               ← Windows launcher
├── Launcher.sh                ← Linux / macOS launcher
├── credentials.json           ← ⚠️ Kamu yang taruh (Google Cloud)
└── App/
    ├── a1d_upscaler.py        ← GUI PySide6
    ├── background_process.py  ← Core Selenium automation
    ├── firefox_relay.py       ← Firefox Relay API wrapper
    ├── gmail_otp.py           ← Gmail OTP reader
    ├── tools_checker.py       ← Auto-download ChromeDriver
    ├── config_manager.py      ← Baca/tulis config
    ├── logger.py              ← Sistem logging
    ├── progress_handler.py    ← Progress tracking
    ├── temp_cleanup.py        ← Bersihkan temp files
    └── file_processor.py      ← Validasi video
```

---

## 📌 Syarat Sistem

- Python 3.10+
- Google Chrome (untuk Selenium ChromeDriver)
- Akun Gmail (untuk baca OTP otomatis)
- Akun Firefox Relay (gratis di relay.firefox.com)
- Internet aktif

---

<div align="center">

Made with ❤️ by [fannyf123](https://github.com/fannyf123) — Architecture inspired by [SotongHD](https://github.com/mudrikam/SotongHD)

</div>
