import os
import re
import shutil

# Extensions that are incomplete / temp download artifacts
_TEMP_EXTS = {".tmp", ".crdownload", ".part", ".download"}

# Playwright/Chromium sometimes drops UUID-named temp files without an extension
_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE,
)


def clean_temp(base_dir: str):
    """Remove and recreate the app’s temp/ folder."""
    temp_dir = os.path.join(base_dir, "temp")
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"[WARN] clean_temp: {e}")
    os.makedirs(temp_dir, exist_ok=True)


def clean_temp_files(directory: str, log_fn=None) -> int:
    """
    Delete incomplete download artifacts from *directory* (top-level only).

    Targets:
      • Files whose extension is in _TEMP_EXTS (.tmp .crdownload .part .download)
      • UUID-named files with no extension (Playwright Chromium temp downloads)

    Returns the number of files removed.
    log_fn(msg, level) is called when files are removed (optional).
    """
    if not directory or not os.path.isdir(directory):
        return 0

    removed = []
    try:
        for fname in os.listdir(directory):
            fpath = os.path.join(directory, fname)
            if not os.path.isfile(fpath):
                continue

            name, ext = os.path.splitext(fname)
            ext_lower  = ext.lower()

            is_temp = (
                ext_lower in _TEMP_EXTS                          # known bad ext
                or (ext_lower == "" and _UUID_RE.match(fname))  # UUID no-ext
            )

            if is_temp:
                try:
                    os.remove(fpath)
                    removed.append(fname)
                except Exception:
                    pass   # file still locked — skip silently
    except Exception:
        pass

    if removed and log_fn:
        shown = ', '.join(removed[:5])
        extra = f" ... (+{len(removed)-5} lainnya)" if len(removed) > 5 else ""
        log_fn(f"🧹 Hapus {len(removed)} file temp: {shown}{extra}", "INFO")

    return len(removed)
