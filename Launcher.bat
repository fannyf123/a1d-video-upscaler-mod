@echo off
setlocal EnableDelayedExpansion
title A1D Video Upscaler v2.7.0  —  Launcher
chcp 65001 > nul
cls

color 0A
echo.
echo  ===========================================================
echo    A1D VIDEO UPSCALER  v2.7.0
echo    Auto Setup  ^&  Launcher
echo    github.com/fannyf123/a1d-video-upscaler-mod
echo  ===========================================================
echo.

set "ROOT=%~dp0"
set "PY_DIR=%ROOT%python"
set "PY_EXE=%PY_DIR%\python.exe"
set "FF_DIR=%ROOT%ffmpeg"
set "FF_EXE=%FF_DIR%\bin\ffmpeg.exe"
set "FF_ZIP=%ROOT%ffmpeg_dl.zip"
set "FF_TMP=%ROOT%ffmpeg_tmp"
set "PW_FLAG=%ROOT%.playwright_ok"

:: ===========================================================
:: STEP 1  —  Python 3.12 Portable
:: ===========================================================
echo  [1/4] Python Portable
echo  -----------------------------------------------------------

if exist "%PY_EXE%" (
    echo         OK  -  Python portable sudah ada.
    goto :pip_setup
)

echo         Download  -  Python 3.12 embed ^(amd64^) ~25 MB...
powershell -NoProfile -Command "(New-Object Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-amd64.zip', '%ROOT%py.zip')"
if errorlevel 1 (
    echo  [ERROR] Gagal download Python. Periksa koneksi internet.
    pause & exit /b 1
)

echo         Mengekstrak...
powershell -NoProfile -Command "Expand-Archive -Path '%ROOT%py.zip' -DestinationPath '%PY_DIR%' -Force"
del "%ROOT%py.zip" 2>nul
echo         OK  -  Python 3.12 berhasil diinstall.

:: ===========================================================
:: Patch ._pth + Install pip
:: ===========================================================
:pip_setup

:: Patch semua python3*._pth (wildcard agar jalan di versi manapun)
:: WAJIB dilakukan SEBELUM pip diinstall agar site-packages aktif
echo         Patch ._pth untuk aktifkan site-packages...
for %%f in ("%PY_DIR%\python3*._pth") do (
    findstr /C:"import site" "%%f" >nul 2>&1
    if errorlevel 1 (
        echo import site>>"%%f"
        echo         Patched: %%~nxf
    )
)

:: Cek apakah pip sudah tersedia
"%PY_EXE%" -m pip --version >nul 2>&1
if not errorlevel 1 (
    echo         OK  -  pip sudah tersedia.
    goto :install_deps
)

:: Coba ensurepip dulu (bundled dalam Python, tidak perlu download)
echo         Setup pip via ensurepip ^(bundled^)...
"%PY_EXE%" -m ensurepip --upgrade

:: Verifikasi setelah ensurepip
"%PY_EXE%" -m pip --version >nul 2>&1
if not errorlevel 1 (
    echo         OK  -  pip berhasil diinstall via ensurepip.
    goto :upgrade_pip
)

:: Fallback: download get-pip.py jika ensurepip gagal
echo         ensurepip gagal  -  fallback ke get-pip.py...
powershell -NoProfile -Command "(New-Object Net.WebClient).DownloadFile('https://bootstrap.pypa.io/get-pip.py', '%ROOT%get-pip.py')"
if errorlevel 1 (
    echo  [ERROR] Gagal download get-pip.py. Periksa koneksi.
    pause & exit /b 1
)
"%PY_EXE%" "%ROOT%get-pip.py"
del "%ROOT%get-pip.py" 2>nul

:: Verifikasi akhir
"%PY_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] pip tidak bisa diinstall setelah dua percobaan.
    echo         Coba hapus folder 'python\' lalu jalankan ulang Launcher.bat
    pause & exit /b 1
)
echo         OK  -  pip berhasil diinstall via get-pip.py.

:upgrade_pip
echo         Upgrade pip ke versi terbaru...
"%PY_EXE%" -m pip install --upgrade pip --quiet --disable-pip-version-check

:: ===========================================================
:: STEP 2  —  Python Dependencies
:: ===========================================================
:install_deps
echo.
echo  [2/4] Python Dependencies
echo  -----------------------------------------------------------
echo         Menginstall/memperbarui dari requirements.txt...

"%PY_EXE%" -m pip install -r "%ROOT%requirements.txt" --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  [ERROR] Gagal install Python dependencies!
    echo         Coba jalankan ulang Launcher.bat, atau periksa koneksi internet.
    pause & exit /b 1
)
echo         OK  -  PySide6, Playwright, qtawesome, dll sudah ter-update.

:: ===========================================================
:: STEP 3  —  Playwright Chromium
:: ===========================================================
echo.
echo  [3/4] Playwright Chromium Browser
echo  -----------------------------------------------------------

if exist "%PW_FLAG%" (
    echo         OK  -  Chromium sudah terinstall ^(skip^).
    goto :ffmpeg
)

echo         Install pertama kali, download Chromium ~130 MB...
"%PY_EXE%" -m playwright install chromium
if errorlevel 1 (
    echo  [ERROR] Gagal install Playwright Chromium!
    pause & exit /b 1
)
echo. > "%PW_FLAG%"
echo         OK  -  Chromium berhasil diinstall.

:: ===========================================================
:: STEP 4  —  FFmpeg (Post-Processing Engine)
:: ===========================================================
:ffmpeg
echo.
echo  [4/4] FFmpeg Post-Processing Engine
echo  -----------------------------------------------------------

:: Prioritas 1: portable lokal di folder ffmpeg/
if exist "%FF_EXE%" (
    echo         OK  -  FFmpeg portable ditemukan.
    set "PATH=%FF_DIR%\bin;%PATH%"
    goto :launch
)

:: Prioritas 2: FFmpeg sudah di system PATH
where ffmpeg >nul 2>&1
if not errorlevel 1 (
    echo         OK  -  FFmpeg ditemukan di system PATH.
    goto :launch
)

:: FFmpeg tidak ada  →  Download otomatis
echo         DOWNLOAD  -  FFmpeg belum ada, mendownload...
echo         Sumber 1: gyan.dev ^(ffmpeg-release-essentials ~75 MB^)

:: Bersihkan sisa gagal sebelumnya
if exist "%FF_TMP%" rd /s /q "%FF_TMP%" 2>nul
if exist "%FF_ZIP%"  del "%FF_ZIP%"  2>nul

:: --- Download: gyan.dev (primary) ----------------------------------
powershell -NoProfile -Command "& { try { $wc = New-Object Net.WebClient; $wc.DownloadFile('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', $env:FF_ZIP); Write-Host '         Download selesai.' } catch { Write-Host ('         [WARN] gyan.dev gagal: ' + $_.Exception.Message) } }"

:: Jika gagal, coba BtbN GitHub Releases (fallback)
if not exist "%FF_ZIP%" (
    echo         Sumber 2: github.com/BtbN/FFmpeg-Builds ^(win64-gpl ~80 MB^)
    powershell -NoProfile -Command "& { try { $wc = New-Object Net.WebClient; $wc.DownloadFile('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip', $env:FF_ZIP); Write-Host '         Download selesai.' } catch { Write-Host ('         [WARN] BtbN gagal: ' + $_.Exception.Message) } }"
)

if not exist "%FF_ZIP%" (
    echo  [WARN] Kedua sumber download gagal.
    echo         FFmpeg tidak terinstall  -  fitur post-processing dinonaktifkan.
    echo         Pasang FFmpeg manual ^(https://ffmpeg.org/download.html^) lalu jalankan ulang.
    goto :launch
)

:: --- Ekstrak zip ke folder sementara --------------------------------
echo         Mengekstrak arsip...
powershell -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::ExtractToDirectory($env:FF_ZIP, $env:FF_TMP)"

:: --- Salin bin\ ke ffmpeg\bin\ ----------------------------------------
powershell -NoProfile -Command "$sub = Get-ChildItem $env:FF_TMP -Directory | Select-Object -First 1; if (-not $sub) { Write-Host '[ERROR] Struktur zip tidak dikenali'; exit 1 }; $src = Join-Path $sub.FullName 'bin'; $dst = Join-Path $env:FF_DIR 'bin'; if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }; Copy-Item (Join-Path $src '*') -Destination $dst -Recurse -Force; Write-Host '         Salin selesai.'"

:: --- Bersihkan temp ------------------------------------------------
if exist "%FF_TMP%" rd /s /q "%FF_TMP%" 2>nul
if exist "%FF_ZIP%" del "%FF_ZIP%" 2>nul

if exist "%FF_EXE%" (
    echo         OK  -  FFmpeg portable berhasil diinstall.
    echo         Path aktif: %FF_DIR%\bin
    set "PATH=%FF_DIR%\bin;%PATH%"
) else (
    echo  [WARN] FFmpeg gagal diinstall  -  post-processing dinonaktifkan.
)

:: ===========================================================
:: LAUNCH APP
:: ===========================================================
:launch
echo.
echo  ===========================================================
echo   Semua komponen siap!  Memulai A1D Video Upscaler...
echo  ===========================================================
echo.

"%PY_EXE%" "%ROOT%main.py"

if errorlevel 1 (
    echo.
    echo  [ERROR] Aplikasi keluar dengan kode error.
    echo         Periksa tab System Logs untuk detail.
    echo.
    pause
)
endlocal
