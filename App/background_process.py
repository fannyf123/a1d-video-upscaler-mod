import os
import sys
import json
import time
import base64
import shutil
import datetime
import threading
import requests as req
from playwright.sync_api import sync_playwright, Page, Download, TimeoutError as PWTimeout
from PySide6.QtCore import QThread, Signal

from App.firefox_relay import FirefoxRelay
from App.gmail_otp import GmailOTPReader
from App.temp_cleanup import clean_temp_files

A1D_EMAIL_ID = "#_R_4p5fiv9fkjb_-form-item"

QUALITY_TEXTS = {
    "1080p": ["1080p", "1080", "Full HD", "FHD", "1080P", "Full HD (1080p)"],
    "2k":    ["2K", "2k", "1440p", "QHD", "2K (1440p)", "1440", "2K QHD"],
    "4k":    ["4K", "4k", "2160p", "UHD", "Ultra HD", "4K (2160p)",
               "2160", "4K Ultra HD", "4K UHD"],
}

MAX_OTP_RETRIES = 3   # total percobaan OTP (1 awal + 2 retry)


class A1DProcessor(QThread):
    log_signal      = Signal(str, str)
    progress_signal = Signal(int, str)
    finished_signal = Signal(bool, str, str)

    _DEFAULT_BASE = "https://a1d.ai"

    def __init__(self, base_dir: str, video_path: str, config: dict):
        super().__init__()
        self.base_dir   = base_dir
        self.video_path = video_path
        self.config     = config
        self.page       = None
        self._pw        = None
        self._browser   = None
        self._cancelled = False

        self._relay   = None
        self._mask_id = None
        self._out_dir = ""   # set in _process(); used by _cleanup_temp_files()

        base = self.config.get("a1d_url", self._DEFAULT_BASE).rstrip("/")
        self.SIGNIN_URL = f"{base}/auth/sign-in"
        self.EDITOR_URL = f"{base}/video-upscaler/editor"

    def cancel(self):    self._cancelled = True
    def log(self, msg, level="INFO"): self.log_signal.emit(msg, level)
    def prog(self, pct, msg=""):      self.progress_signal.emit(pct, msg)

    # ══ MAIN RUN ═══════════════════════════════════════════════════════════════
    def run(self):
        try:
            out = self._process()
            if not self._cancelled:
                self.finished_signal.emit(True, "Upscale selesai!", out)
        except Exception as e:
            self.log(f"Error: {e}", "ERROR")
            self.finished_signal.emit(False, str(e), "")
        finally:
            self._cleanup_mask()
            # ✔ quit_browser FIRST (waits up to 8 s for Chromium to release
            #   all file handles), THEN clean .tmp so files are not locked.
            self._quit_browser()
            self._cleanup_temp_files()

    def _cleanup_mask(self):
        if self._relay and self._mask_id:
            try:
                self._relay.delete_mask(self._mask_id)
                self.log("Email mask dihapus", "INFO")
            except Exception:
                pass
            finally:
                self._relay   = None
                self._mask_id = None

    def _cleanup_temp_files(self):
        """Delete leftover .tmp / .crdownload from the output directory."""
        if self._out_dir:
            clean_temp_files(self._out_dir, log_fn=self.log)

    def _quit_browser(self):
        browser, pw = self._browser, self._pw
        self._browser = None
        self._pw      = None
        self.page     = None

        def _do_close():
            try:
                if browser: browser.close()
            except Exception:
                pass
            try:
                if pw: pw.stop()
            except Exception:
                pass

        t = threading.Thread(target=_do_close, daemon=True, name="pw-close")
        t.start()
        t.join(timeout=8)

    # ══ CORE PROCESS ═══════════════════════════════════════════════════════════
    def _process(self) -> str:
        self.log("Memulai proses upscale...", "INFO")
        self.prog(5, "Membuat email mask...")
        api_key = self.config.get("relay_api_key", "").strip()
        if not api_key:
            raise ValueError("Firefox Relay API Key belum diset!")

        relay     = FirefoxRelay(api_key)
        mask_data = relay.create_mask("a1d-upscale-session")
        email     = mask_data["full_address"]
        mask_id   = mask_data["id"]
        self._relay   = relay
        self._mask_id = mask_id

        self.log(f"Email mask: {email}", "SUCCESS")
        self.prog(10, "Email mask siap")

        out_dir_custom = self.config.get("output_dir", "").strip()
        raw_dir = out_dir_custom if (out_dir_custom and os.path.isdir(out_dir_custom)) \
                  else os.path.join(os.path.dirname(self.video_path), "OUTPUT")
        out_dir = os.path.normpath(os.path.abspath(raw_dir))
        os.makedirs(out_dir, exist_ok=True)
        self._out_dir = out_dir
        self.log(f"📁 Output: {out_dir}", "INFO")

        # Clean leftover temp files from any previous failed run
        prev = clean_temp_files(out_dir)
        if prev:
            self.log(f"🧹 Hapus {prev} file temp sisa dari run sebelumnya", "INFO")

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless       = self.config.get("headless", True),
            downloads_path = out_dir,
            args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--mute-audio",
                "--disable-gpu",
            ],
        )
        context = self._browser.new_context(
            viewport         = {"width": 1920, "height": 1080},
            user_agent       = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            accept_downloads = True,
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.page = context.new_page()
        self.page.set_default_timeout(30_000)
        self.log("🎮 Playwright Chromium siap", "INFO")

        self.prog(15, "Membuka halaman sign-in...")
        self.log(f"[1] Buka: {self.SIGNIN_URL}", "INFO")
        self.page.goto(self.SIGNIN_URL, wait_until="domcontentloaded")
        time.sleep(2.5)

        self.prog(20, "Input email mask...")
        self._fill_email(email)

        self.prog(25, "Submit email...")
        otp_request_time = int(time.time())
        self._click_submit()

        self.prog(30, "Menunggu form OTP...")
        self._wait_for_otp_form(timeout=30)
        self.log("✅ Form OTP terdeteksi", "SUCCESS")

        # ────────────────────────────────────────────────────────
        # OTP retry loop
        #   Percobaan 1: pakai OTP dari email pertama
        #   Percobaan 2+: klik Resend (jika ada) ATAU restart sign-in,
        #                 bersihkan kolom, tunggu OTP baru, isi ulang
        # ────────────────────────────────────────────────────────
        gmail = GmailOTPReader(self.base_dir)

        for attempt in range(1, MAX_OTP_RETRIES + 1):
            if self._cancelled:
                raise InterruptedError("Dibatalkan")

            if attempt > 1:
                self.log(
                    f"⚠️ OTP gagal/salah — percobaan {attempt}/{MAX_OTP_RETRIES}...",
                    "WARNING",
                )
                # Coba klik Resend dulu; jika tidak ada, restart full sign-in
                if self._try_resend_otp():
                    self.log("🔄 Resend OTP berhasil diklik", "INFO")
                else:
                    self.log(
                        "🔄 Tombol Resend tidak ditemukan — kembali ke halaman sign-in",
                        "INFO",
                    )
                    self._restart_signin(email)
                # Timestamp SETELAH trigger OTP baru agar Gmail reader
                # hanya ambil email yang masuk setelah ini
                otp_request_time = int(time.time())

            self.prog(
                38,
                f"Menunggu OTP dari Gmail... (percobaan {attempt}/{MAX_OTP_RETRIES})",
            )
            otp = gmail.wait_for_otp(
                sender          = "a1d.ai",
                mask_email      = email,
                after_timestamp = otp_request_time,
                timeout         = 180,
                interval        = 5,
                log_callback    = lambda m, lv="INFO": self.log(f"[Gmail] {m}", lv),
            )
            self.log(f"✅ OTP percobaan {attempt}: {otp}", "SUCCESS")

            self.prog(50, f"Memasukkan OTP (percobaan {attempt})...")
            self._clear_otp_inputs()   # ← bersihkan sisa OTP gagal sebelumnya
            self._fill_otp(otp)

            self.prog(58, "Submit OTP...")
            if self._click_otp_submit_and_verify():
                break   # ✔ login berhasil, lanjut

            if attempt >= MAX_OTP_RETRIES:
                raise RuntimeError(
                    f"❌ OTP gagal setelah {MAX_OTP_RETRIES} percobaan"
                )
        # ── end OTP retry loop ───────────────────────────────────────────────────
        time.sleep(2)

        self.prog(65, "Menunggu login berhasil...")
        self._wait_for_home(timeout=30)
        self.log(f"✅ Login: {self.page.url}", "SUCCESS")

        self.prog(72, "Membuka video editor...")
        self.log(f"[2] Buka: {self.EDITOR_URL}", "INFO")
        self.page.goto(self.EDITOR_URL, wait_until="domcontentloaded")
        time.sleep(3)

        self.prog(78, "Mengupload video...")
        self._upload_video()
        time.sleep(6)

        self.prog(82, "Memilih kualitas...")
        self._select_quality(self.config.get("output_quality", "4k").lower())

        self.prog(86, "Memulai upscale...")
        self._start_upscale()
        self.log("⚙️ Proses upscale dimulai!", "SUCCESS")

        wait_sec = max(0, int(self.config.get("initial_download_wait", 120)))
        if wait_sec > 0:
            mins  = wait_sec // 60
            secs  = wait_sec % 60
            label = f"{mins}m {secs}s" if mins else f"{secs}s"
            self.log(f"⏳ Tunggu {label} sebelum cek tombol Download...", "INFO")
            for remaining in range(wait_sec, 0, -1):
                if self._cancelled:
                    raise InterruptedError("Dibatalkan")
                if remaining % 30 == 0 or remaining <= 10:
                    self.prog(87, f"⏳ Menunggu server render... {remaining}s")
                    self.log(f"   └ sisa {remaining}s", "INFO")
                time.sleep(1)
            self.log("✅ Initial wait selesai, mulai cek tombol Download", "INFO")

        self.prog(88, "Menunggu proses selesai...")
        out_path = self._wait_and_download(out_dir)
        self.log(f"💾 Tersimpan: {out_path}", "SUCCESS")
        return out_path

    # ══ EMAIL ══════════════════════════════════════════════════════════════════════════════
    def _fill_email(self, email: str):
        EMAIL_SELS = [
            A1D_EMAIL_ID,
            'input[placeholder="your@email.com"]',
            'input[type="email"]',
            'input[autocomplete="email"]',
            'input[name="email"]',
            'input[id*="email" i]',
            'input[placeholder*="email" i]',
            'input[type="text"]',
        ]
        for sel in EMAIL_SELS:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=2_000):
                    loc.scroll_into_view_if_needed()
                    loc.fill(email)
                    if loc.input_value() == email:
                        self.log(f"✅ Email OK via: {sel}", "INFO")
                        return
            except Exception:
                continue
        filled = self.page.evaluate("""
            (email) => {
                const inp = Array.from(document.querySelectorAll('input')).find(
                    i => i.offsetParent && !i.disabled && !i.readOnly &&
                        (i.type==='email' || (i.placeholder||'').toLowerCase().includes('email'))
                );
                if (!inp) return false;
                const nv = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                nv.call(inp, email);
                ['focus','input','change'].forEach(e => inp.dispatchEvent(new Event(e,{bubbles:true})));
                return inp.value === email;
            }
        """, email)
        if filled:
            self.log("✅ Email OK via JS fallback", "INFO")
            return
        raise RuntimeError("❌ Input email tidak ditemukan")

    def _click_submit(self):
        for text in ["continue with email", "continue", "send code", "sign in"]:
            try:
                btn = self.page.get_by_role("button", name=text, exact=False)
                if btn.first.is_visible(timeout=2_000):
                    btn.first.click()
                    time.sleep(1.5)
                    return
            except Exception:
                continue
        try:
            self.page.locator("button[type='submit']").first.click()
            time.sleep(1.5)
            return
        except Exception:
            pass
        self.page.keyboard.press("Enter")
        time.sleep(1.5)

    # ══ OTP ═══════════════════════════════════════════════════════════════════════════════
    def _wait_for_otp_form(self, timeout: int = 30):
        OTP_SELS = [
            'input[autocomplete="one-time-code"]',
            'input[inputmode="numeric"]',
            'input[type="number"][maxlength="6"]',
            'input[type="text"][maxlength="6"]',
            'input[maxlength="1"]',
            'input[placeholder*="code" i]',
        ]
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._cancelled:
                raise InterruptedError("Dibatalkan")
            for sel in OTP_SELS:
                try:
                    if self.page.locator(sel).first.is_visible(timeout=500):
                        return
                except Exception:
                    continue
            time.sleep(0.8)
        raise TimeoutError("❌ Form OTP tidak muncul")

    def _clear_otp_inputs(self):
        """
        Bersihkan semua kolom input OTP sebelum mengisi OTP baru.
        Dipanggil pada percobaan ke-2 dan seterusnya.
        """
        OTP_SELS = [
            'input[autocomplete="one-time-code"]',
            'input[inputmode="numeric"]',
            'input[type="number"][maxlength="6"]',
            'input[type="text"][maxlength="6"]',
            'input[placeholder*="code" i]',
        ]
        for sel in OTP_SELS:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=500):
                    loc.fill("")
                    self.log("🧹 Input OTP dibersihkan", "INFO")
                    return
            except Exception:
                continue
        # Digit-by-digit inputs (maxlength="1")
        try:
            digits = self.page.locator('input[maxlength="1"]').all()
            for d in digits:
                try:
                    d.fill("")
                except Exception:
                    pass
            if digits:
                self.log(f"🧹 {len(digits)} kolom OTP digit dibersihkan", "INFO")
        except Exception:
            pass

    def _try_resend_otp(self) -> bool:
        """
        Coba klik tombol/link Resend OTP di halaman OTP.
        Return True jika berhasil diklik, False jika tidak ditemukan.
        """
        RESEND_TEXTS = [
            "resend", "resend otp", "resend code", "resend email",
            "send again", "send new code", "resend verification",
            "kirim ulang", "kirim ulang kode",
        ]
        for role in ["button", "link"]:
            for text in RESEND_TEXTS:
                try:
                    el = self.page.get_by_role(role, name=text, exact=False)
                    if el.first.is_visible(timeout=1_000):
                        el.first.click()
                        time.sleep(2)
                        self.log(f"🔄 Resend via {role}: '{text}'", "INFO")
                        return True
                except Exception:
                    continue
        # JS fallback: cari elemen yang teksnya mengandung 'resend'
        clicked = self.page.evaluate("""
            () => {
                const kw = ['resend','send again','kirim ulang'];
                for (const el of document.querySelectorAll('button,a,[role="button"]')) {
                    const t = el.textContent.trim().toLowerCase();
                    if (kw.some(k => t.includes(k))) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            el.click();
                            return el.textContent.trim();
                        }
                    }
                }
                return null;
            }
        """)
        if clicked:
            time.sleep(2)
            self.log(f"🔄 Resend via JS: '{clicked}'", "INFO")
            return True
        return False

    def _restart_signin(self, email: str):
        """
        Kembali ke halaman sign-in, isi ulang email,
        dan tunggu sampai form OTP muncul kembali.
        """
        self.log(f"🔄 Restart sign-in: {self.SIGNIN_URL}", "INFO")
        self.page.goto(self.SIGNIN_URL, wait_until="domcontentloaded")
        time.sleep(2.5)
        self._fill_email(email)
        self._click_submit()
        self._wait_for_otp_form(timeout=30)
        self.log("✅ Form OTP siap (setelah restart sign-in)", "SUCCESS")

    def _fill_otp(self, otp: str):
        OTP_SELS = [
            'input[autocomplete="one-time-code"]',
            'input[inputmode="numeric"]',
            'input[type="number"][maxlength="6"]',
            'input[type="text"][maxlength="6"]',
            'input[placeholder*="code" i]',
        ]
        for sel in OTP_SELS:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=1_000):
                    loc.fill(otp)
                    self.log(f"OTP via: {sel}", "INFO")
                    return
            except Exception:
                continue
        digits = self.page.locator('input[maxlength="1"]').all()
        if len(digits) >= len(otp):
            for i, ch in enumerate(otp):
                digits[i].click()
                digits[i].fill(ch)
                time.sleep(0.08)
            return
        raise RuntimeError("❌ Input OTP tidak ditemukan")

    def _click_otp_submit_and_verify(self, max_retries: int = 3) -> bool:
        for _ in range(max_retries):
            if self._cancelled:
                raise InterruptedError("Dibatalkan")
            clicked = False
            for text in ["verify", "continue", "submit"]:
                try:
                    btn = self.page.get_by_role("button", name=text, exact=False)
                    if btn.first.is_visible(timeout=1_500):
                        btn.first.click()
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                try:
                    self.page.locator("button[type='submit']").first.click()
                    clicked = True
                except Exception:
                    pass
            if not clicked:
                self.page.keyboard.press("Enter")
            time.sleep(2.5)
            url = self.page.url
            if "/home" in url or "dashboard" in url:
                return True
            otp_gone = not any(
                self.page.locator(s).first.is_visible(timeout=500)
                for s in ['input[autocomplete="one-time-code"]', 'input[inputmode="numeric"]']
            )
            if otp_gone:
                return True
            time.sleep(2)
        return "/home" in self.page.url or "dashboard" in self.page.url

    def _wait_for_home(self, timeout: int = 30):
        start = time.time()
        while time.time() - start < timeout:
            if self._cancelled:
                raise InterruptedError("Dibatalkan")
            if "/home" in self.page.url or "dashboard" in self.page.url:
                return
            time.sleep(1)
        self.log(f"⚠️ Timeout /home — {self.page.url}", "WARNING")

    # ══ UPLOAD ══════════════════════════════════════════════════════════════════════════════
    def _upload_video(self):
        abs_path = os.path.abspath(self.video_path)
        try:
            file_input = self.page.locator('input[type="file"]').first
            file_input.set_input_files(abs_path)
            self.log("✅ File diupload", "SUCCESS")
            return
        except Exception:
            pass
        for drop_sel in ['[class*="upload"]', '[class*="drop"]']:
            try:
                self.page.locator(drop_sel).first.click()
                time.sleep(1)
                self.page.locator('input[type="file"]').first.set_input_files(abs_path)
                self.log("✅ File via drop zone", "SUCCESS")
                return
            except Exception:
                continue
        raise RuntimeError("❌ Upload area tidak ditemukan")

    # ══ QUALITY SELECTION ═════════════════════════════════════════════════════════
    def _select_quality(self, quality: str):
        q     = quality.lower().strip()
        texts = QUALITY_TEXTS.get(q, QUALITY_TEXTS["4k"])
        self.log(f"📺 Pilih kualitas: {q.upper()}", "INFO")
        deadline = time.time() + 15
        while time.time() < deadline:
            found = self.page.evaluate("""
                (kw) => {
                    for (const el of document.querySelectorAll(
                        'button,[role="radio"],[role="button"],label,[class*="quality"],[class*="resolution"],[class*="option"],[class*="tab"],[class*="card"]'
                    )) {
                        const r = el.getBoundingClientRect();
                        if (r.width===0||r.height===0) continue;
                        if (kw.some(k => el.textContent.trim().toUpperCase().includes(k))) return true;
                    }
                    return false;
                }
            """, ["4K", "2K", "1080", "quality", "resolution", "UHD", "HD"])
            if found:
                break
            time.sleep(0.5)
        for text in texts:
            for role in ["radio", "button"]:
                try:
                    loc = self.page.get_by_role(role, name=text, exact=False)
                    if loc.first.is_visible(timeout=1_000):
                        loc.first.click()
                        self.log(f"✅ {q.upper()} via role={role} text='{text}'", "SUCCESS")
                        time.sleep(0.5)
                        return
                except Exception:
                    continue
        result = self.page.evaluate("""
            (targets) => {
                const SELS = ['button','[role="radio"]','[role="button"]','label',
                    '[class*="option"],[class*="quality"],[class*="resolution"],[class*="card"],[class*="tab"],[class*="pill"]'];
                for (const sel of SELS) {
                    for (const el of document.querySelectorAll(sel)) {
                        const r = el.getBoundingClientRect();
                        if (r.width===0||r.height===0) continue;
                        const txt = el.textContent.trim();
                        const val = (el.getAttribute('data-value')||el.getAttribute('aria-label')||'').toLowerCase();
                        for (const t of targets) {
                            if (txt===t||txt.toLowerCase()===t.toLowerCase()||
                                txt.toUpperCase()===t.toUpperCase()||txt.includes(t)||
                                val.includes(t.toLowerCase())) {
                                el.scrollIntoView({block:'center',behavior:'instant'});
                                el.click();
                                return 'OK|'+txt.substring(0,40);
                            }
                        }
                    }
                }
                return 'NOT_FOUND';
            }
        """, texts)
        if result and result.startswith("OK|"):
            self.log(f"✅ {q.upper()} (JS): {result}", "SUCCESS")
            time.sleep(0.8)
            return
        self.log(f"⚠️ Quality {q.upper()} tidak ditemukan — lanjut", "WARNING")
        self._debug_dump_quality()

    def _debug_dump_quality(self):
        try:
            ts        = datetime.datetime.now().strftime("%H%M%S")
            debug_dir = os.path.join(self.base_dir, "debug")
            os.makedirs(debug_dir, exist_ok=True)
            ss_path   = os.path.join(debug_dir, f"quality_{ts}.png")
            self.page.screenshot(path=ss_path, full_page=True)
            self.log(f"📸 Screenshot → {ss_path}", "WARNING")
            html_path = os.path.join(debug_dir, f"quality_{ts}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.page.content())
            self.log(f"📄 HTML dump → {html_path}", "WARNING")
        except Exception as e:
            self.log(f"_debug_dump_quality: {e}", "INFO")

    # ══ START UPSCALE ═══════════════════════════════════════════════════════════
    def _start_upscale(self):
        for text in ["Generate", "Upscale", "Enhance", "Start", "Process"]:
            try:
                btn = self.page.get_by_role("button", name=text, exact=False)
                if btn.first.is_visible(timeout=1_500) and btn.first.is_enabled():
                    btn.first.scroll_into_view_if_needed()
                    btn.first.click()
                    self.log(f"✅ Upscale via button '{text}'", "INFO")
                    time.sleep(2)
                    return
            except Exception:
                continue
        result = self.page.evaluate("""
            () => {
                for (const b of document.querySelectorAll('button')) {
                    const t = b.textContent.trim().toLowerCase();
                    if (t.includes('generate')||t.includes('upscale')||
                        t.includes('enhance')||t.includes('start')||t.includes('process')) {
                        b.scrollIntoView({block:'center'});
                        b.click();
                        return 'clicked:'+b.textContent.trim();
                    }
                }
                return 'not_found';
            }
        """)
        if result and result.startswith("clicked:"):
            self.log(f"✅ Upscale (JS): {result}", "INFO")

    # ══ WAIT & DOWNLOAD ═══════════════════════════════════════════════════════════
    def _build_output_path(self, out_dir: str, ext: str = ".mp4") -> str:
        base    = os.path.splitext(os.path.basename(self.video_path))[0]
        quality = self.config.get("output_quality", "4k")
        out     = os.path.join(out_dir, f"{base}_upscaled_{quality}{ext}")
        cnt = 1
        while os.path.exists(out):
            out = os.path.join(out_dir, f"{base}_upscaled_{quality}_{cnt}{ext}")
            cnt += 1
        return out

    def _wait_and_download(self, out_dir: str) -> str:
        timeout           = self.config.get("processing_hang_timeout", 1800)
        start             = time.time()
        last_pct          = 88
        last_disabled_log = 0

        DL_LOCATORS = [
            "//button[normalize-space(.)='Download' or contains(normalize-space(.),'Download')]",
            "//a[contains(normalize-space(.),'Download') or contains(@href,'.mp4')]",
        ]

        while time.time() - start < timeout:
            if self._cancelled:
                raise InterruptedError("Dibatalkan")

            dl_btn = None
            for xpath in DL_LOCATORS:
                try:
                    loc = self.page.locator(f"xpath={xpath}").first
                    if loc.is_visible(timeout=500):
                        dl_btn = loc
                        break
                except Exception:
                    continue

            if dl_btn:
                try:
                    enabled = dl_btn.is_enabled()
                except Exception:
                    enabled = False

                if not enabled:
                    now = time.time()
                    if now - last_disabled_log >= 30:
                        last_disabled_log = now
                        elapsed_min = int((now - start) / 60)
                        self.log(
                            f"⏳ Tombol Download terdeteksi tapi masih disabled — "
                            f"server masih render... ({elapsed_min}m)",
                            "INFO",
                        )
                    elapsed = time.time() - start
                    pct = min(91, 88 + int((elapsed / timeout) * 3))
                    if pct > last_pct:
                        last_pct = pct
                        self.prog(pct, f"Rendering di server... ({int(elapsed / 60)}m)")
                    time.sleep(6)
                    continue

                self.log("✅ Tombol Download aktif — mulai download!", "SUCCESS")
                self.prog(92, "Mendownload video...")

                # L1 — direct URL extraction
                try:
                    dl_url = self.page.evaluate("""
                        (el) => {
                            for (let i = 0; i < 8; i++) {
                                const href = el.getAttribute('href') || el.href || '';
                                if (href.startsWith('blob:')) return {type:'blob', url:href};
                                if (href.startsWith('http'))  return {type:'http', url:href};
                                for (const attr of el.attributes) {
                                    const v = attr.value || '';
                                    if (v.startsWith('blob:')) return {type:'blob', url:v};
                                    if (v.startsWith('http') && (v.includes('.mp4')||v.includes('video')))
                                        return {type:'http', url:v};
                                }
                                if (!el.parentElement) break;
                                el = el.parentElement;
                            }
                            return null;
                        }
                    """, dl_btn.element_handle())
                    if dl_url:
                        url_type = dl_url.get("type", "")
                        url      = dl_url.get("url", "")
                        self.log(f"🎯 [L1] {url_type.upper()} URL", "INFO")
                        if url_type == "http":
                            return self._download_url(url, out_dir)
                        if url_type == "blob":
                            return self._download_blob_url(url, self._build_output_path(out_dir))
                except Exception as e:
                    self.log(f"⚠️ L1 gagal: {e}", "INFO")

                # L2 — Playwright expect_download
                self.log("⏳ [L2] Playwright expect_download...", "INFO")
                dl_timeout_ms = int(self.config.get("download_timeout", 600)) * 1000
                try:
                    with self.page.expect_download(timeout=dl_timeout_ms) as dl_info:
                        dl_btn.click()
                    download: Download = dl_info.value
                    fname    = download.suggested_filename or "output.mp4"
                    ext      = os.path.splitext(fname)[1] or ".mp4"
                    out_path = self._build_output_path(out_dir, ext=ext)
                    download.save_as(out_path)
                    sz_mb = os.path.getsize(out_path) / 1_048_576
                    self.log(
                        f"✅ Download selesai: {os.path.basename(out_path)} ({sz_mb:.1f} MB)",
                        "SUCCESS",
                    )
                    return out_path
                except Exception as e:
                    self.log(f"⚠️ L2 gagal: {e}", "WARNING")

                # L3 — filesystem watch fallback
                self.log("⏳ [L3] Filesystem watch fallback...", "INFO")
                before = set(os.listdir(out_dir))
                dl_btn.click()
                for _ in range(60):
                    time.sleep(1)
                    new_files = [
                        os.path.join(out_dir, f)
                        for f in (set(os.listdir(out_dir)) - before)
                        if not f.endswith(".crdownload") and not f.endswith(".tmp")
                    ]
                    if new_files:
                        best = max(new_files, key=os.path.getmtime)
                        if os.path.getsize(best) > 500_000:
                            return best
                raise RuntimeError("❌ Download gagal setelah semua metode")

            elapsed = time.time() - start
            pct     = min(91, 88 + int((elapsed / timeout) * 3))
            if pct > last_pct:
                last_pct = pct
                self.prog(pct, f"Upscaling... ({int(elapsed / 60)} menit)")
            time.sleep(6)

        raise TimeoutError(f"Timeout setelah {timeout // 60} menit")

    def _download_blob_url(self, blob_url: str, out_path: str) -> str:
        self.log("📥 Download blob via JS fetch...", "INFO")
        data_url = self.page.evaluate("""
            async (blobUrl) => {
                const r    = await fetch(blobUrl);
                const blob = await r.blob();
                return await new Promise((resolve, reject) => {
                    const fr = new FileReader();
                    fr.onload  = () => resolve(fr.result);
                    fr.onerror = () => reject(null);
                    fr.readAsDataURL(blob);
                });
            }
        """, blob_url)
        if not data_url:
            raise RuntimeError("❌ Gagal konversi blob")
        _, b64 = data_url.split(",", 1)
        data_bytes = base64.b64decode(b64)
        with open(out_path, "wb") as f:
            f.write(data_bytes)
        self.log(
            f"✅ Blob tersimpan: {os.path.basename(out_path)} ({len(data_bytes)/1_048_576:.1f} MB)",
            "SUCCESS",
        )
        return out_path

    def _download_url(self, url: str, out_dir: str) -> str:
        out_path = self._build_output_path(out_dir)
        self.log(f"Downloading: {os.path.basename(out_path)}", "INFO")
        timeout = self.config.get("download_timeout", 600)
        with req.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(65_536):
                    if self._cancelled:
                        raise InterruptedError("Download dibatalkan")
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.prog(
                            92 + int((done / total) * 8),
                            f"Download {done//1_048_576}/{total//1_048_576} MB",
                        )
        return out_path
