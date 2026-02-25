@echo off
title A1D Upscaler - Local Build Tool
echo ============================================================
echo   A1D VIDEO UPSCALER - ENCRYPTED EXE BUILD SCRIPT
echo   Uses PyArmor (encrypt) + PyInstaller (bundle)
echo ============================================================
echo.

:: ── Prerequisites Check ───────────────────────────────────────────────
where python >nul 2>&1 || (
    echo [ERROR] Python not found. Please install Python 3.10+ first.
    pause & exit /b 1
)

:: ── Step 1: Install build tools ───────────────────────────────────────
echo [STEP 1] Installing build tools...
pip install pyinstaller pyarmor --quiet
if %ERRORLEVEL% neq 0 ( echo [ERROR] Failed to install build tools. & pause & exit /b 1 )

:: ── Step 2: Clean previous builds ────────────────────────────────────
echo [STEP 2] Cleaning previous builds...
if exist build_obf  rmdir /s /q build_obf
if exist dist       rmdir /s /q dist
if exist build      rmdir /s /q build

:: ── Step 3: Encrypt source with PyArmor ─────────────────────────────
echo [STEP 3] Encrypting source with PyArmor...
pyarmor gen --output build_obf -r main.py App/
if %ERRORLEVEL% neq 0 ( echo [ERROR] PyArmor encryption failed. & pause & exit /b 1 )
echo [OK] Source encrypted successfully.

:: ── Step 4: Copy assets ───────────────────────────────────────────────
echo [STEP 4] Copying required assets...
copy config.json build_obf\ >nul

:: ── Step 5: Detect PyArmor runtime package name ──────────────────────
for /d %%D in (build_obf\pyarmor_runtime*) do set RUNTIME=%%~nxD
echo [INFO] PyArmor runtime: %RUNTIME%

:: ── Step 6: Build EXE with PyInstaller ─────────────────────────────
echo [STEP 5] Building EXE with PyInstaller...
cd build_obf
pyinstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "A1D-Upscaler" ^
    --add-data "config.json;." ^
    --collect-all PySide6 ^
    --collect-all qtawesome ^
    --collect-all playwright ^
    --collect-all google ^
    --collect-all bs4 ^
    --collect-all lxml ^
    --hidden-import App.background_process ^
    --hidden-import App.batch_processor ^
    --hidden-import App.a1d_upscaler ^
    --hidden-import App.gmail_otp ^
    --hidden-import App.firefox_relay ^
    --hidden-import App.config_manager ^
    --hidden-import App.file_processor ^
    --hidden-import App.logger ^
    --hidden-import App.progress_handler ^
    --hidden-import App.temp_cleanup ^
    --hidden-import App.tools_checker ^
    --hidden-import %RUNTIME% ^
    --exclude-module tkinter ^
    --exclude-module matplotlib ^
    main.py
cd ..

if %ERRORLEVEL% neq 0 ( echo [ERROR] PyInstaller build failed. & pause & exit /b 1 )

:: ── Step 7: Done ───────────────────────────────────────────────────
echo.
echo ============================================================
echo   BUILD SUCCESS!
echo   Output: build_obf\dist\A1D-Upscaler\
echo   Main EXE: build_obf\dist\A1D-Upscaler\A1D-Upscaler.exe
echo ============================================================
pause
