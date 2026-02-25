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

:: Fetch latest info
echo [INFO] Mengecek update dari GitHub...
git fetch origin main >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Gagal menghubungi GitHub. Cek koneksi internet.
    echo.
    pause
    exit /b 1
)

:: Count commits behind
for /f %%i in ('git rev-list HEAD..origin/main --count 2^>nul') do set BEHIND=%%i

if "%BEHIND%"=="0" (
    echo [OK]   Sudah versi terbaru. Tidak ada update.
    echo.
    pause
    exit /b 0
)

echo [INFO] Ada %BEHIND% commit baru. Mengupdate...
echo.

:: Stash any local changes so pull won't fail
git stash >nul 2>&1

:: Pull latest
git pull origin main
if errorlevel 1 (
    echo.
    echo [ERROR] Update gagal. Coba jalankan manual:
    echo         git pull origin main
    echo.
    pause
    exit /b 1
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
echo ============================================================
echo.

:: Optional: reinstall dependencies if requirements.txt changed
git diff HEAD@{1} HEAD --name-only 2>nul | findstr /i "requirements" >nul
if not errorlevel 1 (
    echo [INFO] requirements.txt berubah — install ulang dependencies...
    echo.
    pip install -r requirements.txt
    echo.
)

echo Tekan tombol apa saja untuk menutup...
pause >nul
