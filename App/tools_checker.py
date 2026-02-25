import os
import sys
import platform
import zipfile
import shutil
import requests

# JSON API resmi Google - jauh lebih reliable daripada scrape HTML
_JSON_API = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"

# Fallback jika JSON API gagal
_FALLBACK_JSON = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"


def get_platform_key() -> tuple:
    system  = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return ("win64", "chromedriver.exe") if machine in ("amd64", "x86_64", "x64") else ("win32", "chromedriver.exe")
    elif system == "darwin":
        return ("mac-arm64", "chromedriver") if machine == "arm64" else ("mac-x64", "chromedriver")
    elif system == "linux":
        return ("linux64", "chromedriver")
    raise ValueError(f"Platform tidak didukung: {system} {machine}")


def _get_driver_url_from_json(platform_key: str) -> str:
    """
    Ambil URL ChromeDriver dari JSON API resmi Google.
    Endpoint: last-known-good-versions-with-downloads.json
    Struktur: { channels: { Stable: { downloads: { chromedriver: [ {platform, url} ] } } } }
    """
    print(f"[INFO] Mengambil URL ChromeDriver dari JSON API...")
    resp = requests.get(_JSON_API, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    downloads = (
        data
        .get("channels", {})
        .get("Stable", {})
        .get("downloads", {})
        .get("chromedriver", [])
    )

    if not downloads:
        raise ValueError("Data chromedriver tidak ditemukan di JSON API")

    for item in downloads:
        if item.get("platform") == platform_key:
            url = item.get("url", "")
            if url:
                print(f"[INFO] URL ditemukan: {url}")
                return url

    raise ValueError(
        f"Platform '{platform_key}' tidak ditemukan.\n"
        f"Platform tersedia: {[x.get('platform') for x in downloads]}"
    )


def _get_driver_url_fallback(platform_key: str) -> str:
    """
    Fallback: Ambil versi terbaru dari known-good-versions.
    Digunakan jika endpoint utama gagal.
    """
    print("[WARN] Endpoint utama gagal, mencoba fallback...")
    resp = requests.get(_FALLBACK_JSON, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    versions = data.get("versions", [])
    # Iterasi dari versi terbaru (akhir list)
    for ver_data in reversed(versions):
        downloads = ver_data.get("downloads", {}).get("chromedriver", [])
        for item in downloads:
            if item.get("platform") == platform_key:
                url = item.get("url", "")
                if url:
                    ver = ver_data.get("version", "unknown")
                    print(f"[INFO] Fallback: versi {ver} | URL: {url}")
                    return url

    raise ValueError(f"Fallback gagal: platform '{platform_key}' tidak ditemukan")


def _get_driver_url(platform_key: str) -> str:
    """Coba endpoint utama, jika gagal pakai fallback."""
    try:
        return _get_driver_url_from_json(platform_key)
    except Exception as e:
        print(f"[WARN] Endpoint utama error: {e}")
        return _get_driver_url_fallback(platform_key)


def download_chromedriver(base_dir: str, platform_key: str, driver_filename: str) -> str:
    driver_dir  = os.path.join(base_dir, "driver")
    driver_path = os.path.join(driver_dir, driver_filename)

    if os.path.exists(driver_path):
        print(f"[INFO] ChromeDriver sudah ada: {driver_path}")
        return driver_path

    os.makedirs(driver_dir, exist_ok=True)
    print(f"[INFO] Mendownload ChromeDriver untuk {platform_key}...")

    url      = _get_driver_url(platform_key)
    zip_path = os.path.join(driver_dir, "chromedriver.zip")

    # Download dengan progress
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        total      = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = int(downloaded / total * 100)
                    mb  = downloaded // 1048576
                    print(f"\r[INFO] Download ChromeDriver: {mb} MB ({pct}%)  ", end="", flush=True)
        print()  # newline setelah progress

    print("[INFO] Mengekstrak ChromeDriver...")
    with zipfile.ZipFile(zip_path, "r") as z:
        extracted_path = None
        for member in z.namelist():
            # Cari file chromedriver di dalam zip (bisa ada subfolder)
            if os.path.basename(member) == driver_filename and not member.endswith("/"):
                z.extract(member, driver_dir)
                extracted_path = os.path.join(driver_dir, member)
                break

        if not extracted_path or not os.path.exists(extracted_path):
            # Coba cara lain: extract semua, cari filenya
            z.extractall(driver_dir)
            for root, _, files in os.walk(driver_dir):
                for fname in files:
                    if fname == driver_filename:
                        extracted_path = os.path.join(root, fname)
                        break

    if not extracted_path or not os.path.exists(extracted_path):
        raise FileNotFoundError(f"File '{driver_filename}' tidak ditemukan setelah ekstrak")

    # Pindahkan ke driver_dir langsung
    final_path = os.path.join(driver_dir, driver_filename)
    if os.path.abspath(extracted_path) != os.path.abspath(final_path):
        shutil.move(extracted_path, final_path)

    # Hapus zip
    try:
        os.remove(zip_path)
    except Exception:
        pass

    # Hapus folder sisa ekstrak
    for item in os.listdir(driver_dir):
        item_path = os.path.join(driver_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path, ignore_errors=True)

    # Set executable permission (Linux/macOS)
    if platform.system().lower() != "windows":
        os.chmod(final_path, 0o755)

    print(f"[INFO] ChromeDriver siap: {final_path}")
    return final_path


def check_tools(base_dir: str) -> bool:
    try:
        platform_key, driver_filename = get_platform_key()
        download_chromedriver(base_dir, platform_key, driver_filename)
        return True
    except Exception as e:
        print(f"[ERROR] check_tools: {e}")
        return False
