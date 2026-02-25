@echo off
chcp 65001 >nul
title A1D Upscaler — Update

echo ============================================================
echo   A1D Video Upscaler — Auto Update
echo ============================================================
echo.

:: Check git is available
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git tidak ditemukan. Install Git dulu:
    echo         https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

:: Show current version
echo [INFO] Versi saat ini:
git log -1 --format="  Commit : %%h" 2>nul
git log -1 --format="  Tanggal: %%cd" --date=format:"%%Y-%%m-%%d %%H:%%M" 2>nul
git log -1 --format="  Pesan  : %%s" 2>nul
echo.

:: ─────────────────────────────────────────────────────────────
:: STEP 1: Backup config.json agar tidak tertimpa git pull
:: ─────────────────────────────────────────────────────────────
if exist config.json (
    echo [INFO] Backup config.json...
    copy /y config.json config.json.bak >nul
    echo [OK]   config.json.bak tersimpan.
) else (
    echo [INFO] config.json tidak ada, skip backup.
)
echo.

:: ─────────────────────────────────────────────────────────────
:: STEP 2: Hentikan git dari tracking config.json
::         (hanya perlu sekali; aman dijalankan berulang)
:: ─────────────────────────────────────────────────────────────
git rm --cached config.json >nul 2>&1

:: ─────────────────────────────────────────────────────────────
:: STEP 3: Fetch + cek jumlah commit baru
:: ─────────────────────────────────────────────────────────────
echo [INFO] Mengecek update dari GitHub...
git fetch origin main >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Gagal menghubungi GitHub. Cek koneksi internet.
    goto :restore
)

for /f %%i in ('git rev-list HEAD..origin/main --count 2^>nul') do set BEHIND=%%i

if "%BEHIND%"=="0" (
    echo [OK]   Sudah versi terbaru. Tidak ada update.
    goto :restore
)

echo [INFO] Ada %BEHIND% commit baru. Mengupdate...
echo.

:: ─────────────────────────────────────────────────────────────
:: STEP 4: Stash perubahan lain (selain config.json yg sudah di-untrack)
:: ─────────────────────────────────────────────────────────────
git stash >nul 2>&1

:: ─────────────────────────────────────────────────────────────
:: STEP 5: Pull latest
:: ─────────────────────────────────────────────────────────────
git pull origin main
if errorlevel 1 (
    echo.
    echo [ERROR] Update gagal. Coba jalankan manual:
    echo         git pull origin main
    goto :restore
)

echo.
echo ============================================================
echo [OK]   Update berhasil!
echo.

:: Show new version
echo [INFO] Versi terbaru:
git log -1 --format="  Commit : %%h"
git log -1 --format="  Tanggal: %%cd" --date=format:"%%Y-%%m-%%d %%H:%%M"
git log -1 --format="  Pesan  : %%s"
echo.

:: ─────────────────────────────────────────────────────────────
:: STEP 6: Reinstall pip jika requirements.txt berubah
:: ─────────────────────────────────────────────────────────────
git diff HEAD@{1} HEAD --name-only 2>nul | findstr /i "requirements" >nul
if not errorlevel 1 (
    echo [INFO] requirements.txt berubah — install ulang dependencies...
    pip install -r requirements.txt
    echo.
)

:: ─────────────────────────────────────────────────────────────
:restore
:: STEP 7: Restore config.json dari backup
:: ─────────────────────────────────────────────────────────────
echo.
if exist config.json.bak (
    copy /y config.json.bak config.json >nul
    del /q config.json.bak >nul
    echo [OK]   Settings dipulihkan dari backup.
    echo        API key, output dir, dll tetap aman.
) else (
    echo [INFO] Tidak ada backup config — skip restore.
)

echo.
echo ============================================================
echo Tekan tombol apa saja untuk menutup...
pause >nul
