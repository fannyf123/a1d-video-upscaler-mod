import os
import sys
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def main():
    from App.tools_checker import check_tools
    from App.temp_cleanup import clean_temp

    clean_temp(BASE_DIR)

    try:
        tools_ok = check_tools(BASE_DIR)
    except Exception as e:
        print(f"[ERROR] Tools check failed: {e}")
        return 1
    if not tools_ok:
        print("[ERROR] Tools check failed. Aborting.")
        return 1

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "fannyf123.A1DVideoUpscaler"
            )
        except Exception:
            pass

    icon_path = os.path.join(BASE_DIR, "App", "a1d_icon.ico")
    icon_path = icon_path if os.path.exists(icon_path) else None

    try:
        from App.a1d_upscaler import run_app
        print("[INFO] Starting A1D Video Upscaler...")
        run_app(BASE_DIR, icon_path)
    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
