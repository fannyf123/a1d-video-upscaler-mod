import os
import re
import sys
import platform
import zipfile
import shutil
import requests


def get_platform_key() -> tuple:
    system  = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return ("win64", "chromedriver.exe") if machine in ("amd64", "x86_64", "x64") else ("win32", "chromedriver.exe")
    elif system == "darwin":
        return ("mac-arm64", "chromedriver") if machine == "arm64" else ("mac-x64", "chromedriver")
    elif system == "linux":
        return ("linux64", "chromedriver")
    raise ValueError(f"Unsupported platform: {system} {machine}")


def _get_driver_url(platform_key: str) -> str:
    PAGE = "https://googlechromelabs.github.io/chrome-for-testing/"
    resp = requests.get(PAGE, timeout=15)
    resp.raise_for_status()
    html = resp.text
    stable_start = html.find('id="stable"')
    if stable_start == -1:
        raise ValueError("Stable section not found")
    sec_open  = html.rfind("<section", 0, stable_start)
    sec_close = html.find("</section>", stable_start)
    stable_html = html[sec_open:sec_close]
    pattern = re.compile(
        rf"https://storage\.googleapis\.com/[A-Za-z0-9_\-./]*/[0-9\.]+/"
        rf"{re.escape(platform_key)}/chromedriver-{re.escape(platform_key)}\.zip"
    )
    m = pattern.search(stable_html)
    if not m:
        raise ValueError(f"ChromeDriver URL not found for {platform_key}")
    return m.group(0)


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

    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            if member.endswith(driver_filename):
                z.extract(member, driver_dir)
                extracted = os.path.join(driver_dir, member)
                shutil.move(extracted, driver_path)
                break

    os.remove(zip_path)

    for item in os.listdir(driver_dir):
        item_path = os.path.join(driver_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path, ignore_errors=True)

    if platform.system().lower() != "windows":
        os.chmod(driver_path, 0o755)

    print(f"[INFO] ChromeDriver siap: {driver_path}")
    return driver_path


def check_tools(base_dir: str) -> bool:
    try:
        platform_key, driver_filename = get_platform_key()
        download_chromedriver(base_dir, platform_key, driver_filename)
        return True
    except Exception as e:
        print(f"[ERROR] check_tools: {e}")
        return False
