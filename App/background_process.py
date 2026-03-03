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

from App.mailticking_pw import MailtickingClient
from App.temp_cleanup import clean_temp_files
from App.ffmpeg_postprocessor import FFmpegPostProcessor

A1D_EMAIL_ID = "#_R_4p5fiv9fkjb_-form-item"
A1D_OTP_ID = "#_r_0_-form-item"

QUALITY_TEXTS = {
    "1080p": ["1080p", "1080", "Full HD", "FHD", "1080P", "Full HD (1080p)"],
    "2k":    ["2K", "2k", "1440p", "QHD", "2K (1440p)", "1440", "2K QHD"],
    "4k":    ["4K", "4k", "2160p", "UHD", "Ultra HD", "4K (2160p)",
               "2160", "4K Ultra HD", "4K UHD"],
}

MAX_OTP_RETRIES = 3   # total percobaan OTP (1 awal + 2 retry)

# Semua selector yang mungkin berisi input OTP
_OTP_INPUT_SELS = [
    A1D_OTP_ID,
    "#_r_0_-form-item",
    'input[autocomplete="one-time-code"]',
    'input[inputmode="numeric"]',
    'input[type="number"][maxlength="6"]',
    'input[type="text"][maxlength="6"]',
    'input[placeholder*="code" i]',
]


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

        self._out_dir = ""

        base = self.config.get("a1d_url", self._DEFAULT_BASE).rstrip("/")
        self.SIGNIN_URL = f"{base}/auth/sign-in"
        self.EDITOR_URL = f"{base}/video-upscaler/editor"

    def cancel(self):    self._cancelled = True
    def log(self, msg, level="INFO"): self.log_signal.emit(msg, level)
    def prog(self, pct, msg=""):      self.progress_signal.emit(pct, msg)

    # ══ MAIN RUN ══════════════════════════════════════
    def run(self):
        try:
            out = self._process()
            if not self._cancelled:
                self.finished_signal.emit(True, "Upscale selesai!", out)
        except Exception as e:
            self.log(f"Error: {e}", "ERROR")
            self.finished_signal.emit(False, str(e), "")
        finally:
            self._quit_browser()
            self._cleanup_temp_files()

    def _cleanup_temp_files(self):
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

    # ══ CORE PROCESS ═══════════════════════════════════════
    def _process(self) -> str:
        self.log("Memulai proses upscale...", "INFO")

        out_dir_custom = self.config.get("output_dir", "").strip()
        raw_dir = out_dir_custom if (out_dir_custom and os.path.isdir(out_dir_custom)) \
                  else os.path.join(os.path.dirname(self.video_path), "OUTPUT")
        out_dir = os.path.normpath(os.path.abspath(raw_dir))
        os.makedirs(out_dir, exist_ok=True)
        self._out_dir = out_dir
        self.log(f"📁 Output: {out_dir}", "INFO")

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

        self.prog(5, "Membuka mailticking untuk temp email...")
        self.mail_page = context.new_page()
        mail_client = MailtickingClient(self.mail_page, log_callback=self.log)
        email = mail_client.open_mailticking()
        self.log(f"Temp email: {email}", "SUCCESS")
        self.prog(10, "Email siap")

        self.prog(15, "Membuka halaman sign-in...")
        self.page.bring_to_front()
        self.log(f"[1] Buka: {self.SIGNIN_URL}", "INFO")
        self.page.goto(self.SIGNIN_URL, wait_until="domcontentloaded")
        time.sleep(2.5)

        self.prog(20, "Input email temp...")
        self._fill_email(email)

        self.prog(25, "Submit email...")
        self._click_submit()

        # ────────────────────────────────────────────────
        # Tunggu form OTP: dengan internal retry + reload sign-in
        # jika form tidak muncul dalam timeout.
        # ────────────────────────────────────────────────
        self.prog(30, "Menunggu form OTP...")
        self._wait_for_otp_form(timeout=30, email=email)

        # ────────────────────────────────────────────────
        # OTP retry loop:
        #  - Percobaan 1 : OTP dari email pertama
        #  - Percobaan 2+: resend / restart sign-in,
        #                  lalu KONFIRMASI form OTP muncul lagi
        #                  sebelum isi OTP baru
        # ────────────────────────────────────────────────
        for attempt in range(1, MAX_OTP_RETRIES + 1):
            if self._cancelled:
                raise InterruptedError("Dibatalkan")

            if attempt > 1:
                self.log(
                    f"⚠️ OTP gagal/salah — percobaan {attempt}/{MAX_OTP_RETRIES}...",
                    "WARNING",
                )
                self.page.bring_to_front()
                if self._try_resend_otp():
                    self.log("🔄 Resend OTP berhasil diklik", "INFO")
                else:
                    self.log(
                        "🔄 Tombol Resend tidak ditemukan — kembali ke halaman sign-in",
                        "INFO",
                    )
                    self._restart_signin(email)

                # Setelah resend/restart: konfirmasi form OTP terlihat lagi
                # sebelum menunggu email OTP baru.
                self.log("⏳ Konfirmasi form OTP kembali terlihat...", "INFO")
                self._wait_for_otp_form(timeout=30, email=email)

            self.prog(
                38,
                f"Menunggu OTP dari Mailticking... (percobaan {attempt}/{MAX_OTP_RETRIES})",
            )

            found = mail_client.wait_for_verification_email(timeout=180)
            if not found:
                raise TimeoutError("❌ Timeout — OTP email tidak diterima di mailticking.")

            otp = mail_client.extract_verification_code()
            if not otp:
                raise ValueError("❌ Gagal mengekstrak OTP dari email mailticking.")

            self.log(f"✅ OTP percobaan {attempt}: {otp}", "SUCCESS")

            self.prog(50, f"Memasukkan OTP (percobaan {attempt})...")
            self.page.bring_to_front()

            # Bersihkan input lama, lalu isi dan VALIDASI nilai OTP.
            # _fill_and_validate_otp() akan retry hingga 3x jika nilai
            # yang ter-input tidak sesuai sebelum raise.
            self._clear_otp_inputs()
            self._fill_and_validate_otp(otp)

            self.prog(58, "Submit OTP...")
            if self._click_otp_submit_and_verify():
                break

            if attempt >= MAX_OTP_RETRIES:
                raise RuntimeError(
                    f"❌ OTP gagal setelah {MAX_OTP_RETRIES} percobaan"
                )
        # ── end OTP loop ─────────────────────────────────────────────────────
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

        ff_cfg = self.config.get("ffmpeg", {})
        if ff_cfg.get("enabled", True):
            self.prog(93, "🎬 FFMPEG: Adobe Stock 4K H.264 + Muted...")
            self.log(
                "🎬 FFMPEG Post-Processing — Adobe Stock 4K H.264 │ "
                "High Profile 5.2 │ CRF 18 │ 3840x2160 │ yuv420p │ "
                "faststart │ 🔇 Muted (-an)",
                "INFO",
            )
            run_cfg = dict(self.config)
            run_cfg["ffmpeg"] = {
                **ff_cfg,
                "preset_name":      "adobe_stock_4k_h264",
                "mute_audio":       True,
                "replace_original": ff_cfg.get("replace_original", True),
            }
            ff = FFmpegPostProcessor(
                input_path   = out_path,
                config       = run_cfg,
                log_fn       = self.log,
                progress_fn  = self.prog,
                cancelled_fn = lambda: self._cancelled,
            )
            ok, out_path = ff.run()
            if not ok:
                self.log(
                    "⚠️ FFMPEG post-processing gagal — file A1D original tetap digunakan",
                    "WARNING",
                )

        self.log(f"💾 Tersimpan: {out_path}", "SUCCESS")
        return out_path

    # ══ EMAIL ═════════════════════════════════════════════════════════════════════
    def _fill_email(self, email: str):
        EMAIL_SELS = [
            A1D_EMAIL_ID,
            "#_R_4p5fiv9fkjb_-form-item",
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
        try:
            js_selector = "body > div.bg-background.lg\\:bg-muted\\/30.animate-in.fade-in.slide-in-from-top-16.zoom-in-95.flex.h-screen.flex-col.items-center.justify-center.gap-y-10.duration-1000.lg\\:gap-y-8 > div > form > button"
            btn = self.page.locator(js_selector).first
            if btn.is_visible(timeout=2_000):
                btn.click()
                time.sleep(1.5)
                return
        except Exception:
            pass
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

    # ══ OTP: WAIT FOR FORM ═══════════════════════════════════════════
    def _wait_for_otp_form(self, timeout: int = 30, email: str = ""):
        """
        Tunggu form OTP muncul dengan internal retry + auto-reload sign-in.

        Flow:
          Untuk setiap percobaan (max MAX_OTP_RETRIES):
            1. Poll selector OTP selama `timeout` detik.
            2. Jika ditemukan → return (sukses).
            3. Jika timeout:
               - Jika masih ada percobaan tersisa:
                 reload sign-in, isi email, klik submit, coba lagi.
               - Jika percobaan habis: raise TimeoutError.
        """
        for form_attempt in range(1, MAX_OTP_RETRIES + 1):
            deadline   = time.time() + timeout
            found_sel  = None

            self.log(
                f"🔍 Menunggu form OTP... "
                f"(percobaan {form_attempt}/{MAX_OTP_RETRIES}, timeout {timeout}s)",
                "INFO",
            )

            while time.time() < deadline:
                if self._cancelled:
                    raise InterruptedError("Dibatalkan")
                for sel in _OTP_INPUT_SELS:
                    try:
                        if self.page.locator(sel).first.is_visible(timeout=500):
                            found_sel = sel
                            break
                    except Exception:
                        continue
                if found_sel:
                    break
                time.sleep(0.8)

            if found_sel:
                self.log(f"✅ Form OTP terdeteksi via: {found_sel}", "SUCCESS")
                return

            # Timeout pada percobaan ini
            if form_attempt < MAX_OTP_RETRIES:
                self.log(
                    f"⚠️ Form OTP tidak muncul dalam {timeout}s "
                    f"(percobaan {form_attempt}/{MAX_OTP_RETRIES}) — "
                    f"reload halaman sign-in dan coba lagi...",
                    "WARNING",
                )
                try:
                    self.page.goto(self.SIGNIN_URL, wait_until="domcontentloaded")
                    time.sleep(2.5)
                    if email:
                        self._fill_email(email)
                        time.sleep(0.5)
                        self._click_submit()
                        time.sleep(1.5)
                except Exception as e:
                    self.log(f"⚠️ Reload sign-in error: {e}", "WARNING")
            else:
                raise TimeoutError(
                    f"❌ Form OTP tidak muncul setelah {MAX_OTP_RETRIES} percobaan "
                    f"({MAX_OTP_RETRIES * timeout}s total). "
                    f"Kemungkinan: koneksi lambat, a1d.ai down, atau halaman gagal load."
                )

    # ══ OTP: FILL + VALIDATE ════════════════════════════════════════
    def _fill_and_validate_otp(self, otp: str, max_attempts: int = 3):
        """
        Isi form OTP lalu validasi bahwa nilai yang ter-input benar-benar sesuai.
        Retry hingga max_attempts kali jika nilai tidak sesuai.
        Raise RuntimeError jika semua percobaan gagal.
        """
        for attempt in range(1, max_attempts + 1):
            if self._cancelled:
                raise InterruptedError("Dibatalkan")

            if attempt > 1:
                self.log(
                    f"🔄 Retry isi OTP percobaan {attempt}/{max_attempts}...",
                    "WARNING",
                )
                self._clear_otp_inputs()
                time.sleep(0.4)

            filled_via = self._do_fill_otp(otp)
            if not filled_via:
                self.log(
                    f"⚠️ Input OTP tidak ditemukan di DOM (percobaan {attempt}/{max_attempts})",
                    "WARNING",
                )
                time.sleep(0.6)
                continue

            self.log(f"   Terisi via: {filled_via}", "INFO")

            # Beri waktu React/DOM update sebelum validasi
            time.sleep(0.3)

            valid, actual = self._validate_otp_input(otp)
            if valid:
                self.log(f"✅ OTP tervalidasi: '{otp}' ✔", "SUCCESS")
                return

            self.log(
                f"⚠️ Validasi OTP gagal percobaan {attempt}/{max_attempts} — "
                f"diisi: '{otp}', terbaca: '{actual}'",
                "WARNING",
            )

        raise RuntimeError(
            f"❌ Gagal mengisi OTP '{otp}' setelah {max_attempts} percobaan — "
            f"nilai selalu tidak sesuai atau field tidak ditemukan."
        )

    def _do_fill_otp(self, otp: str) -> str:
        """
        Satu kali percobaan isi OTP tanpa validasi.
        Return: nama selector/metode yang berhasil, atau '' jika gagal.
        """
        # 1. Coba setiap selector satu-per-satu
        for sel in _OTP_INPUT_SELS:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=1_000):
                    loc.click()
                    time.sleep(0.1)
                    loc.fill(otp)
                    return sel
            except Exception:
                continue

        # 2. Digit-by-digit (maxlength="1" per digit)
        try:
            digits = self.page.locator('input[maxlength="1"]').all()
            if len(digits) >= len(otp):
                for i, ch in enumerate(otp):
                    digits[i].click()
                    digits[i].fill(ch)
                    time.sleep(0.08)
                return "digit-by-digit"
        except Exception:
            pass

        # 3. JS native setter fallback
        filled = self.page.evaluate("""
            (otp) => {
                const candidates = [
                    'input[autocomplete="one-time-code"]',
                    'input[inputmode="numeric"]',
                    'input[type="number"][maxlength]',
                    'input[type="text"][maxlength]',
                    'input[placeholder*="code" i]',
                ];
                for (const s of candidates) {
                    const el = document.querySelector(s);
                    if (el && el.offsetParent && !el.disabled && !el.readOnly) {
                        const nv = Object.getOwnPropertyDescriptor(
                            HTMLInputElement.prototype, 'value'
                        ).set;
                        nv.call(el, otp);
                        ['focus','input','change','blur'].forEach(
                            e => el.dispatchEvent(new Event(e, {bubbles: true}))
                        );
                        return 'js:' + s;
                    }
                }
                return '';
            }
        """, otp)
        return filled or ""

    def _validate_otp_input(self, otp: str) -> tuple:
        """
        Cek apakah nilai OTP benar-benar terbaca di form.
        Return: (is_valid: bool, actual_value: str)
        """
        # 1. Cek single input field via selector
        for sel in _OTP_INPUT_SELS:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=500):
                    actual = loc.input_value()
                    if actual == otp:
                        return True, actual
                    if actual:
                        return False, actual
            except Exception:
                continue

        # 2. Cek digit-by-digit
        try:
            digits = self.page.locator('input[maxlength="1"]').all()
            if len(digits) >= len(otp):
                combined = "".join(
                    digits[i].input_value() or ""
                    for i in range(len(otp))
                )
                if combined == otp:
                    return True, combined
                if combined:
                    return False, combined
        except Exception:
            pass

        # 3. JS read fallback
        result = self.page.evaluate("""
            (otp) => {
                const sels = [
                    'input[autocomplete="one-time-code"]',
                    'input[inputmode="numeric"]',
                    'input[type="number"][maxlength]',
                    'input[type="text"][maxlength]',
                    'input[placeholder*="code" i]',
                ];
                for (const s of sels) {
                    const el = document.querySelector(s);
                    if (el && el.offsetParent && el.value) return el.value;
                }
                const digs = [...document.querySelectorAll('input[maxlength="1"]')];
                if (digs.length >= otp.length) {
                    return digs.slice(0, otp.length).map(d => d.value).join('');
                }
                return '';
            }
        """, otp)
        actual = result or ""
        return actual == otp, actual

    # ══ OTP: CLEAR / RESEND / RESTART ════════════════════════════════
    def _clear_otp_inputs(self):
        for sel in _OTP_INPUT_SELS:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=500):
                    loc.fill("")
                    self.log("🧹 Input OTP dibersihkan", "INFO")
                    return
            except Exception:
                continue
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
        self.log(f"🔄 Restart sign-in: {self.SIGNIN_URL}", "INFO")
        self.page.goto(self.SIGNIN_URL, wait_until="domcontentloaded")
        time.sleep(2.5)
        self._fill_email(email)
        self._click_submit()

    # ══ OTP: SUBMIT + VERIFY ═══════════════════════════════════════
    def _click_otp_submit_and_verify(self, max_retries: int = 3) -> bool:
        for _ in range(max_retries):
            if self._cancelled:
                raise InterruptedError("Dibatalkan")
            clicked = False

            try:
                js_selector = "body > div.bg-background.lg\\:bg-muted\\/30.animate-in.fade-in.slide-in-from-top-16.zoom-in-95.flex.h-screen.flex-col.items-center.justify-center.gap-y-10.duration-1000.lg\\:gap-y-8 > div > form > div.flex.w-full.flex-col.gap-y-2 > button.focus-visible\\:ring-ring.inline-flex.items-center.justify-center.rounded-md.text-sm.font-medium.whitespace-nowrap.transition-colors.focus-visible\\:ring-1.focus-visible\\:outline-hidden.disabled\\:pointer-events-none.disabled\\:opacity-50.bg-primary.text-primary-foreground.hover\\:bg-primary\\/90.shadow-xs.h-9.px-4.py-2"
                btn = self.page.locator(js_selector).first
                if btn.is_visible(timeout=1_500):
                    btn.click()
                    clicked = True
            except Exception:
                pass

            if not clicked:
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

    # ══ UPLOAD ════════════════════════════════════════════════════════════════
    def _upload_video(self):
        abs_path = os.path.abspath(self.video_path)
        try:
            trigger_loc = self.page.locator("id*='trigger'").locator("..").locator('input[type="file"]')
            if trigger_loc.count() > 0:
                trigger_loc.first.set_input_files(abs_path)
                self.log("✅ File diupload via dynamic trigger ID", "SUCCESS")
                return
        except Exception:
            pass
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

    # ══ QUALITY ═════════════════════════════════════════════════════════════════
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

        try:
            js_selector = "body > div.flex.min-h-\\[100vh\\].flex-col > div.flex.h-\\[calc\\(100vh-72px\\)\\].w-full.flex-nowrap.gap-4 > div.mx-auto.h-full.w-full.max-w-md.min-w-\\[480px\\].space-y-6.overflow-y-auto.p-6 > div.space-y-5.rounded-xl.border.border-gray-200.bg-white.p-5.shadow-sm.dark\\:border-gray-800.dark\\:bg-gray-900 > div:nth-child(6) > div > button:nth-child(3)"
            btn = self.page.locator(js_selector).first
            if q == "4k" and btn.is_visible(timeout=1000):
                btn.click()
                self.log(f"✅ {q.upper()} via user JS_Path", "SUCCESS")
                time.sleep(0.5)
                return
        except Exception:
            pass

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

    # ══ START UPSCALE ══════════════════════════════════════════
    def _start_upscale(self):
        try:
            js_selector = "body > div.flex.min-h-\\[100vh\\].flex-col > div.flex.h-\\[calc\\(100vh-72px\\)\\].w-full.flex-nowrap.gap-4 > div.mx-auto.h-full.w-full.max-w-md.min-w-\\[480px\\].space-y-6.overflow-y-auto.p-6 > div.space-y-3 > button"
            btn = self.page.locator(js_selector).first
            if btn.is_visible(timeout=1_500) and btn.is_enabled():
                btn.scroll_into_view_if_needed()
                btn.click()
                self.log("✅ Upscale via JS Path user", "INFO")
                time.sleep(2)
                return
        except Exception:
            pass
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

    # ══ WAIT & DOWNLOAD ══════════════════════════════════════════
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
            "body > div.flex.min-h-\\[100vh\\].flex-col > div.flex.h-\\[calc\\(100vh-72px\\)\\].w-full.flex-nowrap.gap-4 > div.flex.w-full.flex-col.gap-2.overflow-y-auto > div > div > div.items-center.p-6.flex.justify-between.px-4.py-2 > div:nth-child(1)",
            "//button[normalize-space(.)='Download' or contains(normalize-space(.),'Download')]",
            "//a[contains(normalize-space(.),'Download') or contains(@href,'.mp4')]",
        ]

        while time.time() - start < timeout:
            if self._cancelled:
                raise InterruptedError("Dibatalkan")

            dl_btn = None
            for sel in DL_LOCATORS:
                try:
                    if sel.startswith("//"):
                        loc = self.page.locator(f"xpath={sel}").first
                    else:
                        loc = self.page.locator(sel).first
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
