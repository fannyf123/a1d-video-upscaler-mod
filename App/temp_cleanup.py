import os
import shutil

# Extensions that are considered incomplete/temp download artifacts
_TEMP_EXTS = {".tmp", ".crdownload", ".part", ".download"}


def clean_temp(base_dir: str):
    """Remove and recreate the app's temp/ folder."""
    temp_dir = os.path.join(base_dir, "temp")
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"[WARN] clean_temp: {e}")
    os.makedirs(temp_dir, exist_ok=True)


def clean_temp_files(directory: str, log_fn=None) -> int:
    """
    Delete incomplete download artifacts (.tmp, .crdownload, .part, .download)
    from *directory*.  Only the top level is scanned (non-recursive).

    Returns the number of files removed.
    log_fn(msg, level) is called when files are removed (optional).
    """
    if not directory or not os.path.isdir(directory):
        return 0

    removed = []
    try:
        for fname in os.listdir(directory):
            _, ext = os.path.splitext(fname.lower())
            if ext in _TEMP_EXTS:
                fpath = os.path.join(directory, fname)
                try:
                    os.remove(fpath)
                    removed.append(fname)
                except Exception:
                    pass
    except Exception:
        pass

    if removed and log_fn:
        log_fn(
            f"🧹 Hapus {len(removed)} file temp: {', '.join(removed[:5])}"
            + (f" ... (+{len(removed)-5} lainnya)" if len(removed) > 5 else ""),
            "INFO",
        )
    return len(removed)
