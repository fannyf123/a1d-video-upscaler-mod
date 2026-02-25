<div align="center">

<br>

# 🎬 A1D Video Upscaler v2

**Upscale video ke 4K secara otomatis via a1d.ai — tidak perlu buka browser sendiri!**

![Version](https://img.shields.io/badge/version-2.0.0-7c3aed?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Mac-0078d4?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)

<br>

</div>

---

## 🤔 Apa Itu Aplikasi Ini?

Aplikasi ini **secara otomatis** mengupscale video kamu ke resolusi yang lebih tinggi (1080p / 2K / 4K) menggunakan layanan gratis [a1d.ai](https://a1d.ai).

Biasanya untuk pakai a1d.ai kamu harus:
1. Buka browser secara manual
2. Daftar akun pakai email
3. Verifikasi OTP dari Gmail
4. Upload video
5. Tunggu proses selesai
6. Download hasilnya

**Aplikasi ini mengerjakan semua langkah di atas secara otomatis** — kamu hanya perlu drag & drop video, lalu tunggu hasilnya.

---

## ✨ Fitur Utama

| Fitur | Keterangan |
|---|---|
| 🎬 **Drag & Drop** | Seret video langsung ke aplikasi |
| 🤖 **Full Otomasi** | Register → OTP → Upload → Upscale → Download — semua otomatis |
| 📺 **Pilih Kualitas** | Support **1080p**, **2K**, **4K** |
| 🦊 **Firefox Relay** | Email sekali pakai otomatis (tidak perlu email asli) |
| 🗬 **Headless Mode** | Browser jalan di background, tidak mengganggu layar |
| 📂 **Folder Bebas** | Pilih sendiri folder penyimpanan hasil video |
| 📊 **Log Real-Time** | Pantau progress langsung di panel bawah |
| 🛡️ **Config Aman** | Setting tersimpan di folder user — **tidak terhapus saat update app** |
| 🗑️ **Reset Token** | Tombol reset Gmail token langsung dari Settings |

---

## 📋 Persyaratan Sebelum Mulai

Pastikan semua ini sudah terpasang sebelum lanjut:

| Kebutuhan | Link Download | Keterangan |
|---|---|---|
| **Python 3.10+** | [python.org/downloads](https://www.python.org/downloads/) | Pilih versi terbaru, centang **"Add to PATH"** saat install |
| **Google Chrome** | [google.com/chrome](https://www.google.com/chrome/) | Untuk proses otomasi browser |
| **Akun Gmail** | [gmail.com](https://gmail.com) | Untuk baca kode OTP secara otomatis |
| **Akun Firefox Relay** | [relay.firefox.com](https://relay.firefox.com) | Gratis, untuk buat email sekali pakai |
| **Akun Google Cloud** | [console.cloud.google.com](https://console.cloud.google.com) | Gratis, untuk Gmail API |

---

## 🚀 Panduan Instalasi (Langkah demi Langkah)

### ① Download Aplikasi

**Cara 1 — Dengan Git:**
```bash
git clone https://github.com/fannyf123/a1d-video-upscaler-v2.git
cd a1d-video-upscaler-v2
```

**Cara 2 — Download ZIP (lebih mudah):**
1. Klik tombol hijau **`< > Code`** di halaman ini
2. Pilih **`Download ZIP`**
3. Ekstrak ZIP ke folder pilihan kamu

---

### ② Setup Gmail API *(hanya sekali, sekitar 5 menit)*

Ini diperlukan agar aplikasi bisa membaca kode OTP dari Gmail kamu.

**Langkah-langkahnya:**

1. Buka [console.cloud.google.com](https://console.cloud.google.com/) dan login dengan akun Google
2. Klik **"Select a Project"** → **"New Project"** → beri nama bebas → klik **Create**
3. Di menu kiri, klik **"APIs & Services"** → **"Library"**
4. Cari **"Gmail API"** → klik → klik tombol **"Enable"**
5. Kembali ke **"APIs & Services"** → klik **"OAuth consent screen"**
   - Pilih **External** → klik **Create**
   - Isi **App name** (bebas, contoh: `A1D Upscaler`)
   - Isi **User support email** dengan email kamu → scroll bawah → **Save and Continue**
   - Klik **Save and Continue** dua kali lagi (lewati Scopes & Test Users)
   - Klik **Back to Dashboard**
6. Klik **"Credentials"** → **"+ Create Credentials"** → **"OAuth client ID"**
   - Application type: pilih **Desktop app**
   - Name: bebas → klik **Create**
7. Klik tombol **⬇ Download JSON** di kolom paling kanan
8. **Rename** file yang didownload menjadi tepat: **`credentials.json`**
9. **Pindahkan** file `credentials.json` ke **folder utama aplikasi** (sejajar dengan `main.py`)

> ⚠️ **Penting:** Saat pertama kali menjalankan aplikasi, akan muncul jendela browser untuk login Gmail. Ini **hanya terjadi sekali** — setelah itu otomatis.

---

### ③ Dapatkan Firefox Relay API Key *(hanya sekali)*

Ini diperlukan agar aplikasi bisa membuat email sekali pakai untuk mendaftar di a1d.ai.

1. Buka [relay.firefox.com](https://relay.firefox.com) → login atau daftar (gratis)
2. Klik foto profil / nama kamu di pojok kanan atas
3. Pilih **"Settings"** atau **"Account"**
4. Scroll ke bawah sampai menemukan bagian **"API Key"**
5. **Copy** API Key tersebut

> 💡 API Key terlihat seperti kode panjang acak, contoh: `abc123def456...`

---

### ④ Jalankan Aplikasi

**Windows** — double-click file:
```
Launcher.bat
```

**Linux / macOS** — buka terminal di folder aplikasi:
```bash
bash Launcher.sh
```

> Saat pertama kali, launcher akan otomatis menginstall semua library yang dibutuhkan. Tunggu hingga selesai.

---

### ⑤ Konfigurasi Pertama

1. Aplikasi terbuka → klik tombol **⚙ Settings** di kanan atas
2. Paste **Firefox Relay API Key** yang sudah di-copy tadi
3. Klik **🔌 Test Koneksi** untuk memastikan API Key valid
4. Klik **💾 Simpan Pengaturan**

---

### ⑥ Cara Pakai (Setiap Kali)

1. **Drag & Drop** file video ke area tengah — atau klik **📄 Pilih File**
2. (Opsional) Klik **📁 Browse** untuk memilih folder output sendiri
3. Pilih kualitas: **1080p**, **2K**, atau **4K**
4. Klik **▶ Start Upscale**
5. Tunggu hingga selesai (biasanya 5–30 menit tergantung panjang video)
6. Hasil tersimpan otomatis di folder yang dipilih (default: `OUTPUT/` di lokasi video)

---

## 🛡️ Cara Update Aplikasi Tanpa Kehilangan Settingan

Sejak versi 2.0, **config dan token Gmail disimpan di luar folder aplikasi**:

| Sistem Operasi | Lokasi Penyimpanan |
|---|---|
| **Windows** | `C:\Users\NamaKamu\AppData\Roaming\A1DUpscaler\` |
| **macOS** | `~/Library/Application Support/A1DUpscaler/` |
| **Linux** | `~/.config/A1DUpscaler/` |

Jadi kamu bisa **replace seluruh folder aplikasi** saat update tanpa khawatir settingan terhapus.

---

## 📁 Struktur Proyek

```
a1d-video-upscaler-v2/
├── main.py                    ← Jalankan ini (via Launcher)
├── requirements.txt           ← Daftar library Python
├── Launcher.bat               ← Windows: double-click untuk jalan
├── Launcher.sh                ← Linux/macOS: bash Launcher.sh
├── credentials.json           ← ⚠️ Kamu yang taruh (dari Google Cloud)
├── driver/                    ← ChromeDriver (auto-download)
└── App/
    ├── a1d_upscaler.py        ← Tampilan GUI (PySide6)
    ├── background_process.py  ← Otomasi browser (Selenium)
    ├── firefox_relay.py       ← Buat email sekali pakai
    ├── gmail_otp.py           ← Baca kode OTP dari Gmail
    ├── config_manager.py      ← Simpan/baca pengaturan
    ├── tools_checker.py       ← Cek dan download ChromeDriver
    └── ... (file pendukung)

📦 Config tersimpan DI LUAR folder ini (aman dari update):
   Windows : %APPDATA%\A1DUpscaler\config.json
   macOS   : ~/Library/Application Support/A1DUpscaler/config.json
   Linux   : ~/.config/A1DUpscaler/config.json
```

---

## ❓ Pertanyaan Umum (FAQ)

<details>
<summary><b>Q: Apakah aplikasi ini gratis?</b></summary>

Ya. Aplikasi ini gratis dan open-source. Layanan a1d.ai juga memiliki tier gratis. Firefox Relay tersedia gratis dengan batas tertentu.
</details>

<details>
<summary><b>Q: Apakah aman? Apakah akun Gmail saya bisa diakses orang lain?</b></summary>

Aman. Token OAuth Gmail tersimpan lokal di komputer kamu (`%APPDATA%\A1DUpscaler\token.json`). Aplikasi hanya membaca email masuk untuk mengambil kode OTP — tidak bisa kirim email, hapus email, atau akses hal lain.
</details>

<details>
<summary><b>Q: Kenapa proses lama sekali?</b></summary>

Proses upscale dilakukan oleh server a1d.ai, bukan komputer kamu. Durasi tergantung:
- Panjang dan resolusi video asli
- Beban server a1d.ai saat itu
- Kualitas output yang dipilih (4K lebih lama dari 1080p)

Normal antara 5 menit hingga 30 menit.
</details>

<details>
<summary><b>Q: Muncul dialog "Save As" saat download. Bagaimana cara menghilangkannya?</b></summary>

Ini sudah diperbaiki di versi terbaru. Pastikan kamu menggunakan kode terbaru dari repo ini.
</details>

<details>
<summary><b>Q: Error "Gmail token expired" atau gagal baca OTP.</b></summary>

Buka **⚙ Settings** → bagian **Gmail Token** → klik **🗑 Reset Gmail Token**. Pada proses berikutnya, browser akan meminta login Gmail ulang (hanya sekali).
</details>

<details>
<summary><b>Q: Bagaimana cara update aplikasi?</b></summary>

1. Download/clone versi terbaru
2. Replace seluruh isi folder aplikasi lama
3. Jalankan lagi — **settingan tidak akan terhapus** karena tersimpan di folder user
</details>

<details>
<summary><b>Q: ChromeDriver versi saya tidak cocok.</b></summary>

Launcher otomatis mendownload ChromeDriver yang sesuai dengan versi Chrome kamu. Pastikan Google Chrome sudah terinstall dan update ke versi terbaru.
</details>

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---|---|
| `ModuleNotFoundError` | Jalankan via Launcher (bukan `python main.py` langsung) |
| `credentials.json not found` | Pastikan file `credentials.json` ada di folder utama app |
| Login Gmail tidak muncul | Hapus `token.json` via Settings → Reset Gmail Token |
| Browser terbuka tapi macet | Pastikan Chrome versi terbaru terinstall |
| `API Key tidak valid` | Buka relay.firefox.com dan copy ulang API Key |
| Proses timeout | Naikkan nilai Timeout di Settings (default 1800 detik) |
| Dialog Save As muncul | Update ke kode terbaru (sudah diperbaiki) |
| Kualitas 4K tidak terpilih | Jalankan `python tools/inspect_quality.py` untuk cek selector |

---

## 📋 Syarat Minimum Sistem

- **OS:** Windows 10/11, macOS 12+, Ubuntu 20.04+
- **Python:** 3.10 atau lebih baru
- **RAM:** minimal 4 GB
- **Browser:** Google Chrome (versi terbaru)
- **Internet:** koneksi stabil

---

<div align="center">

Made with ❤️ by [fannyf123](https://github.com/fannyf123) — Architecture inspired by [SotongHD](https://github.com/mudrikam/SotongHD)

</div>
