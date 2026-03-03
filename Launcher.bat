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
set "VENV_DIR=%ROOT%.venv"
set "VENV_ACT=%VENV_DIR%\Scripts\activate.bat"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "FF_DIR=%ROOT%ffmpeg"
set "FF_EXE=%FF_DIR%\bin\ffmpeg.exe"
set "FF_ZIP=%ROOT%ffmpeg_dl.zip"
set "FF_TMP=%ROOT%ffmpeg_tmp"
set "PW_FLAG=%ROOT%.playwright_ok"
set "BASE_PY="

:: ===========================================================
:: STEP 1  —  Siapkan Python + Virtual Environment
:: ===========================================================
echo  [1/4] Python ^& Virtual Environment
echo  -----------------------------------------------------------

:: Jika .venv sudah ada dan python.exe-nya valid  →  langsung aktifkan
if exist "%VENV_PY%" (
    echo         OK  -  .venv sudah ada, langsung aktifkan.
    call "%VENV_ACT%"
    goto :install_deps
)

:: ---- Cari Python yang bisa dipakai untuk buat .venv ---------------

:: Coba 'python' (system install, Windows Store, atau PATH)
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo         System Python %%v ditemukan.
    set "BASE_PY=python"
    goto :create_venv
)

:: Coba 'py' launcher (Python Launcher for Windows)
py --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do echo         Python Launcher %%v ditemukan.
    set "BASE_PY=py"
    goto :create_venv
)

:: Coba portable Python di subfolder python/
set "PY_DIR=%ROOT%python"
set "PY_EXE=%PY_DIR%\python.exe"

if exist "%PY_EXE%" (
    echo         Portable Python ditemukan di: %PY_DIR%
    set "BASE_PY=%PY_EXE%"
    goto :patch_and_pip
)

:: Tidak ada Python sama sekali  →  download portable
echo         Python tidak ditemukan. Download Python 3.12 portable ~25 MB...
powershell -NoProfile -Command "(New-Object Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-amd64.zip', '%ROOT%py.zip')"
if errorlevel 1 (
    echo  [ERROR] Gagal download Python. Periksa koneksi internet.
    pause & exit /b 1
)
powershell -NoProfile -Command "Expand-Archive -Path '%ROOT%py.zip' -DestinationPath '%PY_DIR%' -Force"
del "%ROOT%py.zip" 2>nul
set "BASE_PY=%PY_EXE%"
echo         OK  -  Python 3.12 portable berhasil didownload.

:: ---- Patch ._pth khusus untuk portable embed ----------------------
:patch_and_pip
echo         Patch ._pth untuk aktifkan site module...
:: Gunakan /R (regex) agar TIDAK false-positive pada "#import site" (komentar bawaan)
if exist "%PY_DIR%\python312._pth" (
    findstr /R "^import site" "%PY_DIR%\python312._pth" >nul 2>&1
    if errorlevel 1 (
        echo import site>>"%PY_DIR%\python312._pth"
        echo         Patched  -  import site aktif.
    )
)

:: Install pip ke portable Python (dibutuhkan untuk buat .venv)
"%PY_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo         Install pip via get-pip.py...
    powershell -NoProfile -Command "(New-Object Net.WebClient).DownloadFile('https://bootstrap.pypa.io/get-pip.py', '%ROOT%get-pip.py')"
    if errorlevel 1 ( echo  [ERROR] Gagal download get-pip.py. & pause & exit /b 1 )
    "%PY_EXE%" "%ROOT%get-pip.py" --no-warn-script-location --quiet
    del "%ROOT%get-pip.py" 2>nul
    "%PY_EXE%" -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] pip gagal diinstall. Hapus folder 'python\' lalu coba lagi.
        pause & exit /b 1
    )
)

:: ---- Buat .venv dari BASE_PY yang sudah siap --------------------
:create_venv
echo         Membuat virtual environment (.venv)...

:: System Python: buat venv normal (pip otomatis ada)
if not "%BASE_PY%"=="%PY_EXE%" (
    %BASE_PY% -m venv "%VENV_DIR%"
    if errorlevel 1 ( echo  [ERROR] Gagal buat .venv! & pause & exit /b 1 )
    goto :activate
)

:: Portable Python: buat venv tanpa pip (ensurepip tidak ada di embed)
"%PY_EXE%" -m venv "%VENV_DIR%" --without-pip
if errorlevel 1 ( echo  [ERROR] Gagal buat .venv dari portable Python! & pause & exit /b 1 )

:: Install pip ke dalam .venv via get-pip.py
echo         Install pip ke .venv...
powershell -NoProfile -Command "(New-Object Net.WebClient).DownloadFile('https://bootstrap.pypa.io/get-pip.py', '%ROOT%get-pip.py')"
"%VENV_PY%" "%ROOT%get-pip.py" --no-warn-script-location --quiet
del "%ROOT%get-pip.py" 2>nul

:activate
call "%VENV_ACT%"
echo         OK  -  .venv aktif.

:: ===========================================================
:: STEP 2  —  Python Dependencies
:: ===========================================================
:install_deps
echo.
echo  [2/4] Python Dependencies
echo  -----------------------------------------------------------
echo         Menginstall/memperbarui dari requirements.txt...

pip install -r "%ROOT%requirements.txt" --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  [ERROR] Gagal install dependencies!
    echo         Coba hapus folder '.venv\' lalu jalankan ulang.
    pause & exit /b 1
)
echo         OK  -  PySide6, Playwright, qtawesome, dll ter-update.

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

echo         Download Chromium ~130 MB ^(pertama kali saja^)...
python -m playwright install chromium
if errorlevel 1 ( echo  [ERROR] Gagal install Chromium! & pause & exit /b 1 )
echo. > "%PW_FLAG%"
echo         OK  -  Chromium berhasil diinstall.

:: ===========================================================
:: STEP 4  —  FFmpeg
:: ===========================================================
:ffmpeg
echo.
echo  [4/4] FFmpeg Post-Processing Engine
echo  -----------------------------------------------------------

if exist "%FF_EXE%" (
    echo         OK  -  FFmpeg portable sudah ada.
    set "PATH=%FF_DIR%\bin;%PATH%"
    goto :launch
)

where ffmpeg >nul 2>&1
if not errorlevel 1 (
    echo         OK  -  FFmpeg ada di system PATH.
    goto :launch
)

echo         DOWNLOAD  -  FFmpeg ~75 MB...
if exist "%FF_TMP%" rd /s /q "%FF_TMP%" 2>nul
if exist "%FF_ZIP%"  del "%FF_ZIP%"  2>nul

powershell -NoProfile -Command "& { try { (New-Object Net.WebClient).DownloadFile('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', $env:FF_ZIP); Write-Host '         Download selesai.' } catch { Write-Host '         [WARN] gyan.dev gagal.' } }"

if not exist "%FF_ZIP%" (
    powershell -NoProfile -Command "& { try { (New-Object Net.WebClient).DownloadFile('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip', $env:FF_ZIP); Write-Host '         Download selesai.' } catch { Write-Host '         [WARN] BtbN gagal.' } }"
)

if not exist "%FF_ZIP%" (
    echo  [WARN] FFmpeg tidak bisa didownload. Post-processing dinonaktifkan.
    goto :launch
)

powershell -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::ExtractToDirectory($env:FF_ZIP, $env:FF_TMP)"
powershell -NoProfile -Command "$sub = Get-ChildItem $env:FF_TMP -Directory | Select-Object -First 1; if (-not $sub) { exit 1 }; $src = Join-Path $sub.FullName 'bin'; $dst = Join-Path $env:FF_DIR 'bin'; if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }; Copy-Item (Join-Path $src '*') -Destination $dst -Recurse -Force; Write-Host '         Ekstrak selesai.'"

if exist "%FF_TMP%" rd /s /q "%FF_TMP%" 2>nul
if exist "%FF_ZIP%" del "%FF_ZIP%" 2>nul

if exist "%FF_EXE%" (
    echo         OK  -  FFmpeg berhasil diinstall.
    set "PATH=%FF_DIR%\bin;%PATH%"
) else (
    echo  [WARN] FFmpeg gagal. Post-processing dinonaktifkan.
)

:: ===========================================================
:: LAUNCH
:: ===========================================================
:launch
echo.
echo  ===========================================================
echo   Semua siap!  Memulai A1D Video Upscaler...
echo  ===========================================================
echo.

python "%ROOT%main.py"

if errorlevel 1 (
    echo.
    echo  [ERROR] Aplikasi keluar dengan error. Periksa tab System Logs.
    echo.
    pause
)
endlocal
