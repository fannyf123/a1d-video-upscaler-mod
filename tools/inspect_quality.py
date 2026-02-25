"""
A1D Quality Button Inspector
============================
Script untuk menemukan selector TEPAT tombol kualitas (4K/2K/1080p)
di halaman a1d.ai/video-upscaler/editor tanpa menunggu proses otomatis.

Cara Pakai:
    python tools/inspect_quality.py

Langkah:
    1. Browser Chrome akan terbuka secara VISIBLE
    2. Login manual di https://a1d.ai/auth/sign-in
    3. Upload video dummy di editor
    4. Tunggu tombol kualitas muncul (1080p / 2K / 4K)
    5. Kembali ke terminal → tekan ENTER
    6. Script dump semua info ke:
       - tools/quality_report.json  (detail + saran selector)
       - tools/quality_report.png   (screenshot)
       - tools/quality_report.html  (full page source)

Setelah dapat selector:
    Tambahkan ke QUALITY_PRIORITY di App/background_process.py
    atau isi di config.json -> "quality_css_4k"
"""

import os
import sys
import json
import time

# Pastikan root project bisa di-import
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
except ImportError:
    print("\u274c selenium belum terinstall. Jalankan: pip install selenium")
    sys.exit(1)

DRV_NAME = "chromedriver.exe" if sys.platform == "win32" else "chromedriver"
DRV_PATH = os.path.join(ROOT_DIR, "driver", DRV_NAME)
OUT_JSON = os.path.join(SCRIPT_DIR, "quality_report.json")
OUT_PNG  = os.path.join(SCRIPT_DIR, "quality_report.png")
OUT_HTML = os.path.join(SCRIPT_DIR, "quality_report.html")

# JS untuk scan SEMUA elemen interaktif dan info atributnya
SCAN_JS = """
(function(){
    const SELS = [
        'button','[role="button"]','[role="radio"]','[role="tab"]',
        'label','a','input[type="radio"]','input[type="button"]',
        '[class*="option"]','[class*="quality"]','[class*="resolution"]',
        '[class*="select"]','[class*="choice"]','[class*="item"]',
        '[class*="card"]','[class*="tab"]','[class*="pill"]',
        '[class*="btn"]','[class*="radio"]','[tabindex="0"]',
    ];
    const KW = ['4k','2k','1080','quality','resolution','hd','uhd','fhd'];
    const seen = new Set();
    const all = [];
    const quality = [];

    for (const sel of SELS) {
        let els;
        try { els = document.querySelectorAll(sel); } catch(e){ continue; }
        for (const el of els) {
            if (seen.has(el)) continue;
            seen.add(el);
            const r = el.getBoundingClientRect();
            if (r.width===0||r.height===0) continue;

            const info = {
                tag:  el.tagName,
                text: el.textContent.trim().substring(0,80),
                cls:  el.className.substring(0,120),
                id:   el.id||'',
                data_value:      el.getAttribute('data-value')||'',
                data_quality:    el.getAttribute('data-quality')||'',
                data_resolution: el.getAttribute('data-resolution')||'',
                aria_label:      el.getAttribute('aria-label')||'',
                role:            el.getAttribute('role')||'',
                type:            el.getAttribute('type')||'',
                href:            el.getAttribute('href')||'',
                disabled:        el.disabled||false,
                x: Math.round(r.x),
                y: Math.round(r.y),
                w: Math.round(r.width),
                h: Math.round(r.height),
            };

            const low = [
                info.text, info.data_value,
                info.aria_label, info.cls
            ].join(' ').toLowerCase();

            if (KW.some(k => low.includes(k))) {
                quality.push(info);
            }
            if (el.tagName==='BUTTON'||
                el.getAttribute('role')==='button'||
                el.getAttribute('role')==='radio'||
                el.getAttribute('role')==='tab') {
                all.push(info);
            }
        }
    }
    return JSON.stringify({
        url:   window.location.href,
        title: document.title,
        ts:    new Date().toISOString(),
        quality_elements: quality,
        all_interactive: all.slice(0, 80),
    });
})()
"""


def _build_selector_suggestions(el: dict) -> list:
    """Hasilkan daftar selector yang bisa langsung dipakai di Python."""
    sels = []
    if el.get("id"):
        sels.append(f'#{el["id"]}')
    if el.get("data_value"):
        sels.append(f'[data-value="{el["data_value"]}"]')
    if el.get("data_quality"):
        sels.append(f'[data-quality="{el["data_quality"]}"]')
    if el.get("data_resolution"):
        sels.append(f'[data-resolution="{el["data_resolution"]}"]')
    if el.get("aria_label"):
        sels.append(f'[aria-label="{el["aria_label"]}"]')
    txt  = el.get("text", "").strip()
    tag  = el.get("tag", "*").lower()
    if txt:
        sels.append(f'//{tag}[normalize-space(.)="{txt}"]')
        sels.append(f'//{tag}[contains(.,"{txt}")]')
    return sels


def main():
    print("\n" + "=" * 65)
    print("  A1D Quality Button Inspector  |  a1d-video-upscaler-v2")
    print("=" * 65)

    if not os.path.exists(DRV_PATH):
        print(f"\u274c ChromeDriver tidak ditemukan: {DRV_PATH}")
        print("   Letakkan chromedriver di folder driver/")
        sys.exit(1)

    print("""
Langkah:
  [1] Browser Chrome akan terbuka (VISIBLE - bukan headless)
  [2] Login manual: https://a1d.ai/auth/sign-in
  [3] Upload video apa saja di editor
  [4] Tunggu sampai tombol kualitas muncul (1080p / 2K / 4K)
  [5] Kembali ke terminal ini, tekan ENTER
""")
    input(">>> Siap? Tekan ENTER untuk membuka browser <<<")

    opts = Options()
    # SENGAJA tidak --headless agar bisa manual inspect
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(DRV_PATH), options=opts)
    driver.get("https://a1d.ai/auth/sign-in")

    print("\n\u2705 Browser terbuka!")
    print("   -> Login di browser, upload video, tunggu tombol kualitas muncul")
    print("   -> Lalu kembali ke sini dan tekan ENTER")
    input("\n>>> Tombol kualitas sudah muncul? Tekan ENTER untuk scan <<<")

    print("\n\u23f3 Scanning DOM...")

    raw    = driver.execute_script(SCAN_JS)
    data   = json.loads(raw)

    # Screenshot
    driver.save_screenshot(OUT_PNG)
    print(f"\u2705 Screenshot: {OUT_PNG}")

    # HTML
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"\u2705 HTML dump : {OUT_HTML}")

    driver.quit()

    # Tambahkan saran selector ke data
    for el in data.get("quality_elements", []):
        el["selector_suggestions"] = _build_selector_suggestions(el)
    for el in data.get("all_interactive", []):
        el["selector_suggestions"] = _build_selector_suggestions(el)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\u2705 JSON report: {OUT_JSON}")

    # ── Print hasil ke terminal ────────────────────────────────────────────
    q_els = data.get("quality_elements", [])
    print("\n" + "=" * 65)
    print(f"  URL   : {data.get('url', '?')}")
    print(f"  Title : {data.get('title', '?')}")
    print("=" * 65)
    print(f"\n\u2705 QUALITY ELEMENTS DITEMUKAN: {len(q_els)}\n")

    if not q_els:
        print("  \u26a0\ufe0f  Tidak ada quality element!")
        print("  Kemungkinan tombol belum muncul saat ENTER ditekan.")
        print("  Coba ulangi setelah video ter-upload sempurna.\n")
    else:
        print("  Copy-paste selector ke QUALITY_PRIORITY di background_process.py")
        print("  atau tambahkan ke config.json -> \"quality_css_4k\"\n")
        for i, el in enumerate(q_els, 1):
            print(f"--- [{i}] {el['tag']} @ ({el['x']},{el['y']}) ---")
            print(f"  text       : '{el['text']}'")
            print(f"  class      : {el['cls'][:65]}")
            print(f"  id         : {el['id']}")
            print(f"  data-value : {el['data_value']}")
            print(f"  aria-label : {el['aria_label']}")
            print(f"  role       : {el['role']}")
            sels = el.get("selector_suggestions", [])
            if sels:
                print(f"  \u2705 SELECTOR SIAP PAKAI:")
                for s in sels:
                    print(f"       {s}")
            print()

    # Semua button visible
    all_btns = data.get("all_interactive", [])
    print(f"\u25a0 SEMUA ELEMENT INTERAKTIF ({len(all_btns)}):")
    for b in all_btns:
        sels = b.get("selector_suggestions", [])
        hint = sels[0] if sels else ""
        print(
            f"  [{b['tag']}] '{b['text'][:35]}' "
            f"dv='{b['data_value']}' "
            f"| {hint}"
        )

    print(f"\n\u25ba Tambahkan selector ke config.json:")
    print('    "quality_css_4k":  "<CSS_SELECTOR_DISINI>"')
    print('    "quality_css_2k":  "<CSS_SELECTOR_DISINI>"')
    print('    "quality_css_1080": "<CSS_SELECTOR_DISINI>"')
    print(f"\n\u25ba Atau edit langsung QUALITY_PRIORITY di:")
    print(f"    App/background_process.py -> QUALITY_PRIORITY dict")


if __name__ == "__main__":
    main()
