import os
import shutil


def clean_temp(base_dir: str):
    temp_dir = os.path.join(base_dir, "temp")
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"[WARN] clean_temp: {e}")
    os.makedirs(temp_dir, exist_ok=True)
