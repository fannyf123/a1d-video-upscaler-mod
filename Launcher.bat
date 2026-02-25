@echo off
title A1D Video Upscaler v2 Launcher
chcp 65001 > nul
color 0A

echo.
echo  =============================================
echo    A1D VIDEO UPSCALER v2
echo    Powered by SotongHD Architecture
echo  =============================================
echo.

set PYTHON_DIR=%~dp0python
set PYTHON_EXE=%PYTHON_DIR%\python.exe

if exist "%PYTHON_EXE%" (
    echo [OK] Python portable ditemukan.
    goto :run_app
)

echo [INFO] Python portable tidak ditemukan. Mendownload...
echo.

set PYTHON_URL=https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-amd64.zip
set PYTHON_ZIP=%~dp0python_embed.zip

powershell -Command "(New-Object Net.WebClient).DownloadFile('%PYTHON_URL%', '%PYTHON_ZIP%')" 2>nul
if errorlevel 1 (
    echo [ERROR] Gagal download Python. Periksa koneksi internet.
    pause
    exit /b 1
)

echo [INFO] Mengekstrak Python...
powershell -Command "Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force" 2>nul
del "%PYTHON_ZIP%"

echo [INFO] Setup pip...
powershell -Command "(New-Object Net.WebClient).DownloadFile('https://bootstrap.pypa.io/get-pip.py', '%~dp0get-pip.py')" 2>nul

for %%f in ("%PYTHON_DIR%\python312._pth") do (
    echo import site >> "%%f"
)

"%PYTHON_EXE%" get-pip.py --quiet
del get-pip.py

:run_app
echo [INFO] Menginstall/memperbarui dependencies...
"%PYTHON_EXE%" -m pip install -r "%~dp0requirements.txt" --quiet --disable-pip-version-check

if errorlevel 1 (
    echo [ERROR] Gagal install dependencies!
    pause
    exit /b 1
)

echo [INFO] Memulai aplikasi...
echo.

"%PYTHON_EXE%" "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Aplikasi berhenti dengan error.
    pause
)
