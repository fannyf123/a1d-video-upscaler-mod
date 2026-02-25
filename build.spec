# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
#  A1D Video Upscaler - PyInstaller Build Spec
#  Used by GitHub Actions build.yml AND local build_local.bat
# =============================================================================
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# ── Collect data files from packages ──────────────────────────────
datas = []
datas += collect_data_files('PySide6')
datas += collect_data_files('qtawesome')
datas += collect_data_files('playwright')
datas += [('config.json', '.')]

# ── Hidden imports ────────────────────────────────────────────────
hiddenimports  = collect_submodules('PySide6')
hiddenimports += collect_submodules('qtawesome')
hiddenimports += collect_submodules('playwright')
hiddenimports += collect_submodules('google')
hiddenimports += [
    'App', 'App.background_process', 'App.batch_processor',
    'App.a1d_upscaler', 'App.gmail_otp', 'App.firefox_relay',
    'App.config_manager', 'App.file_processor', 'App.logger',
    'App.progress_handler', 'App.temp_cleanup', 'App.tools_checker',
    'requests', 'bs4', 'lxml', 'PIL',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'notebook', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='A1D-Upscaler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # <-- No black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'python3*.dll'],
    name='A1D-Upscaler',
)
