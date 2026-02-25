import json
import os

DEFAULT_CONFIG = {
    "app_version": "2.0.0",
    "output_quality": "4k",
    "headless": True,
    "processing_hang_timeout": 1800,
    "download_timeout": 600,
    "relay_api_key": "",
    "a1d_url": "https://a1d.ai",
    "log_max_lines": 500,
    "batch_size": 1,
    "chromedriver_size_mb": 171
}


def load_config(base_dir: str) -> dict:
    path = os.path.join(base_dir, "config.json")
    if not os.path.exists(path):
        save_config(base_dir, DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Merge default keys jika ada yang kurang
    for k, v in DEFAULT_CONFIG.items():
        data.setdefault(k, v)
    return data


def save_config(base_dir: str, config: dict):
    path = os.path.join(base_dir, "config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
