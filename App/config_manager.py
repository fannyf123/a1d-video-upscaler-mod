import json
import os
import sys

APP_NAME = "A1DUpscaler"

DEFAULT_CONFIG = {
    "app_version": "2.0.0",
    "output_quality": "4k",
    "headless": True,
    "processing_hang_timeout": 1800,
    "download_timeout": 600,
    "a1d_url": "https://a1d.ai",
    "log_max_lines": 500,
    "batch_size": 1,
    "chromedriver_size_mb": 171
}


def get_user_data_dir() -> str:
    """
    Folder yang TIDAK ikut terhapus saat update / replace file app.
    Windows : %APPDATA%\\A1DUpscaler\\
    macOS   : ~/Library/Application Support/A1DUpscaler/
    Linux   : ~/.config/A1DUpscaler/
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _config_path() -> str:
    return os.path.join(get_user_data_dir(), "config.json")


def load_config(base_dir: str) -> dict:
    path = _config_path()

    # ─ Migrasi: jika ada config lama di base_dir, pindahkan ke user_data_dir ─
    old_path = os.path.join(base_dir, "config.json")
    if not os.path.exists(path) and os.path.exists(old_path):
        try:
            import shutil
            shutil.copy2(old_path, path)
        except Exception:
            pass

    if not os.path.exists(path):
        save_config(base_dir, DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Merge default keys jika ada yang kurang (update app tambah key baru)
    for k, v in DEFAULT_CONFIG.items():
        data.setdefault(k, v)
    return data


def save_config(base_dir: str, config: dict):
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
