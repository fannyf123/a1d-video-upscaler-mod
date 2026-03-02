"""
gemini_enterprise.py

Otomasi login dan generate video di business.gemini.google
menggunakan Playwright + OTP via GmailOTPReader yang sudah ada.

Flow:
    1. Buka auth.business.gemini.google/login
    2. Input email (Firefox Relay mask)
5. Klik "+" → "Create videos with Veo"
    5. Klik "+" → "Create videos with Veo"
    6. Input prompt
    7. Submit → polling sampai video selesai
    8. Download video hasil
    9. (Opsional) Lempar ke A1DProcessor untuk upscale
"""

import os
import re
import time
import asyncio
import threading
from typing import Optional, Callable

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from App.mailticking_pw import MailtickingClient

# ─── URL Konstanta ─────────────────────────────────────────────────────────
GEMINI_LOGIN_URL = "https://auth.business.gemini.google/login?continueUrl=https://business.gemini.google/"
GEMINI_HOME_URL  = "https://business.gemini.google/"

# ─── Timeout default (detik) ───────────────────────────────────────────────
OTP_TIMEOUT          = 120    # tunggu OTP di Gmail
VIDEO_GEN_TIMEOUT    = 600    # tunggu video selesai di-generate (10 menit)
POLLING_INTERVAL     = 8      # cek status tiap 8 detik
MAX_OTP_RETRY        = 3      # max retry jika OTP gagal


class GeminiEnterpriseProcessor(threading.Thread):
    """
    Thread worker untuk satu sesi generate video di Gemini Enterprise.

    Signals (callback):
        log_callback(msg: str, level: str)     — kirim log ke UI
        progress_callback(pct: int, msg: str)  — update progress bar
        finished_callback(ok: bool, msg: str, output_path: str)
    """

    def __init__(
        self,
        base_dir:          str,
        prompt:            str,
        mask_email:        str,
        output_dir:        str,
        config:            dict,
        log_callback:      Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        finished_callback: Optional[Callable] = None,
    ):
        super().__init__(daemon=True)
        self.base_dir          = base_dir
        self.prompt            = prompt
        self.mask_email        = ""
        self.output_dir        = output_dir or os.path.join(base_dir, "OUTPUT_GEMINI")
        self.config            = config
        self.log_cb            = log_callback
        self.progress_cb       = progress_callback
        self.finished_cb       = finished_callback
        self._cancelled        = False

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _log(self, msg: str, level: str = "INFO"):
        if self.log_cb:
            self.log_cb(msg, level)

    def _progress(self, pct: int, msg: str):
        if self.progress_cb:
            self.progress_cb(pct, msg)

    def _finished(self, ok: bool, msg: str, path: str = ""):
        if self.finished_cb:
            self.finished_cb(ok, msg, path)

    def cancel(self):
        self._cancelled = True

    # ── Main Thread ─────────────────────────────────────────────────────────
    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        headless = self.config.get("headless", True)

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=headless,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                    ]
                )
                ctx = browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                )
                page = ctx.new_page()

                output_path = self._run_session(page, ctx)

                browser.close()

            if output_path:
                self._finished(True, f"Video berhasil disimpan: {output_path}", output_path)
            else:
                self._finished(False, "Generate video gagal atau dibatalkan.")

        except Exception as e:
            self._log(f"❌ Error fatal: {e}", "ERROR")
            self._finished(False, str(e))

    # ── Session Logic ────────────────────────────────────────────────────────
    def _run_session(self, page, ctx) -> Optional[str]:

        # Buka mailticking dulu
        self._log("Membuka mailticking untuk temp email...")
        self.mail_page = ctx.new_page()
        mail_client = MailtickingClient(self.mail_page, log_callback=self._log)
        self.mask_email = mail_client.open_mailticking()
        self._log(f"Temp email: {self.mask_email}", "SUCCESS")

        self.mail_page.bring_to_front()

        # ── Step 1: Buka halaman login ─────────────────────────────────────
        self._log("🌐 Membuka halaman login Gemini Enterprise...")
        page.bring_to_front()
        self._progress(5, "Membuka halaman login...")
        page.goto(GEMINI_LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2000)

        if self._cancelled: return None

        # ── Step 2: Input email ────────────────────────────────────────────
        self._log(f"📧 Input email: {self.mask_email}")
        self._progress(10, "Input email...")
        try:
            email_input = page.wait_for_selector(
                "input[type='email'], input[name='email'], input[placeholder*='mail']",
                timeout=15_000
            )
            email_input.fill(self.mask_email)
            page.wait_for_timeout(800)

            # Klik Continue / Submit
            submit_btn = page.query_selector(
                "button[type='submit'], button:has-text('Continue'), "
                "button:has-text('Next'), button:has-text('Send')"
            )
            if submit_btn:
                submit_btn.click()
            else:
                page.keyboard.press("Enter")

            self._log("✅ Email tersubmit, menunggu halaman OTP...")
            page.wait_for_timeout(2000)

        except PWTimeout:
            self._log("❌ Input email tidak ditemukan!", "ERROR")
            return None

        if self._cancelled: return None

        # ── Step 3: OTP via mailticking ──────────────────────────────────────────
        self._progress(20, "Menunggu OTP dari mailticking...")
        otp_code = None

        for attempt in range(1, MAX_OTP_RETRY + 1):
            self._log(f"📬 Polling OTP (percobaan {attempt}/{MAX_OTP_RETRY})...")
            
            found = mail_client.wait_for_verification_email(timeout=OTP_TIMEOUT)
            if found:
                otp_code = mail_client.extract_verification_code()
                if otp_code:
                    self._log(f"✅ OTP diterima: {otp_code}", "SUCCESS")
                    break

            if attempt < MAX_OTP_RETRY:
                self._log(f"⚠️  OTP gagal/timeout percobaan {attempt}", "WARNING")
                # Coba resend OTP
                page.bring_to_front()
                resend = page.query_selector(
                    "button:has-text('Resend'), a:has-text('Resend'), "
                    "button:has-text('Send again'), a:has-text('Send again')"
                )
                if resend:
                    self._log("🔄 Klik Resend OTP...")
                    resend.click()
                    page.wait_for_timeout(2000)
                else:
                    # Kembali ke halaman input email
                    self._log("🔄 Kembali ke halaman login, ulang input email...")
                    page.goto(GEMINI_LOGIN_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(1500)
                    ei = page.query_selector(
                        "input[type='email'], input[name='email']"
                    )
                    if ei:
                        ei.fill(self.mask_email)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(2000)

        if not otp_code:
            self._log("❌ Gagal mendapatkan OTP setelah semua percobaan!", "ERROR")
            return None
        
        page.bring_to_front()

        if self._cancelled: return None

        # ── Step 4: Input OTP ke form ──────────────────────────────────────
        self._progress(35, "Memasukkan OTP...")
        self._log("✏️  Input OTP ke form...")
        try:
            # Cari input OTP (bisa 1 field atau multi-digit
            otp_inputs = page.query_selector_all(
                "input[type='text'][maxlength='1'], "
                "input[autocomplete='one-time-code'], "
                "input[name*='otp'], input[name*='code'], "
                "input[placeholder*='code'], input[placeholder*='OTP']"
            )

            if len(otp_inputs) > 1:
                # Multi-digit input (1 kotak per angka)
                for i, digit in enumerate(otp_code[:len(otp_inputs)]):
                    otp_inputs[i].fill(digit)
                    page.wait_for_timeout(150)
            elif len(otp_inputs) == 1:
                otp_inputs[0].fill(otp_code)
            else:
                # Fallback: type ke element focused
                page.keyboard.type(otp_code, delay=100)

            page.wait_for_timeout(800)

            # Submit OTP
            verify_btn = page.query_selector(
                "button[type='submit'], button:has-text('Verify'), "
                "button:has-text('Continue'), button:has-text('Sign in')"
            )
            if verify_btn:
                verify_btn.click()
            else:
                page.keyboard.press("Enter")

            self._log("✅ OTP tersubmit, menunggu redirect ke dashboard...")
            page.wait_for_url(f"**/business.gemini.google/**", timeout=20_000)
            self._log("✅ Login berhasil! Masuk ke Gemini Enterprise.", "SUCCESS")

        except PWTimeout:
            self._log("❌ Login gagal — redirect timeout!", "ERROR")
            return None

        if self._cancelled: return None

        # ── Step 5: Klik "+" → "Create videos with Veo" ───────────────────
        self._progress(50, "Membuka menu Create videos with Veo...")
        self._log("🎬 Membuka menu tools...")
        page.wait_for_timeout(2500)
        try:
            # Klik tombol "+" (tools button)
            plus_btn = page.wait_for_selector(
                "button[aria-label*='tool'], button[aria-label*='attach'], "
                "button[data-test-id*='plus'], [role='button']:has-text('+')",
                timeout=10_000
            )
            plus_btn.click()
            page.wait_for_timeout(1000)

            # Klik "Create videos with Veo"
            veo_btn = page.wait_for_selector(
                "[role='menuitem']:has-text('Create videos with Veo'), "
                "li:has-text('Create videos with Veo'), "
                "button:has-text('Create videos with Veo')",
                timeout=8_000
            )
            veo_btn.click()
            self._log("✅ Menu 'Create videos with Veo' diklik!", "SUCCESS")
            page.wait_for_timeout(1500)

        except PWTimeout:
            self._log("❌ Menu 'Create videos with Veo' tidak ditemukan!", "ERROR")
            return None

        if self._cancelled: return None

        # ── Step 6: Input prompt ───────────────────────────────────────────
        self._progress(60, "Memasukkan prompt video...")
        self._log(f"✏️  Input prompt: {self.prompt[:80]}...")
        try:
            prompt_input = page.wait_for_selector(
                "textarea, [contenteditable='true'], "
                "input[placeholder*='prompt'], input[placeholder*='describe']",
                timeout=10_000
            )
            prompt_input.click()
            prompt_input.fill(self.prompt)
            page.wait_for_timeout(800)

            # Submit prompt
            send_btn = page.query_selector(
                "button[aria-label*='send'], button[aria-label*='generate'], "
                "button[type='submit'], [role='button'][aria-label*='Submit']"
            )
            if send_btn:
                send_btn.click()
            else:
                page.keyboard.press("Enter")

            self._log("✅ Prompt tersubmit! Menunggu video di-generate...", "SUCCESS")

        except PWTimeout:
            self._log("❌ Input prompt tidak ditemukan!", "ERROR")
            return None

        if self._cancelled: return None

        # ── Step 7: Polling sampai video selesai ───────────────────────────
        self._progress(70, "Menunggu Veo generate video...")
        self._log(f"⏳ Polling hasil video (max {VIDEO_GEN_TIMEOUT}s)...")

        start     = time.time()
        video_url = None

        while time.time() - start < VIDEO_GEN_TIMEOUT:
            if self._cancelled: return None

            elapsed = int(time.time() - start)
            pct     = min(70 + int((elapsed / VIDEO_GEN_TIMEOUT) * 20), 88)
            self._progress(pct, f"Generate video... {elapsed}s/{VIDEO_GEN_TIMEOUT}s")

            # Cek apakah tombol Download muncul
            dl_btn = page.query_selector(
                "button:has-text('Download'), a[download], "
                "button[aria-label*='download'], [role='button']:has-text('Download')"
            )
            if dl_btn:
                self._log("✅ Video selesai di-generate!", "SUCCESS")
                video_url = "found"
                break

            # Cek apakah ada elemen video yang selesai
            video_el = page.query_selector("video[src], video source[src]")
            if video_el:
                src = video_el.get_attribute("src") or ""
                if src and "blob" not in src:
                    video_url = src
                    self._log("✅ URL video ditemukan!", "SUCCESS")
                    break

            time.sleep(POLLING_INTERVAL)

        if not video_url:
            self._log(f"❌ Timeout {VIDEO_GEN_TIMEOUT}s — video tidak selesai!", "ERROR")
            return None

        if self._cancelled: return None

        # ── Step 8: Download video ─────────────────────────────────────────
        self._progress(90, "Mendownload video hasil...")
        self._log("📥 Mendownload video...")

        try:
            output_filename = os.path.join(
                self.output_dir,
                f"gemini_veo_{int(time.time())}.mp4"
            )

            with page.expect_download(timeout=120_000) as dl_info:
                dl_btn = page.query_selector(
                    "button:has-text('Download'), a[download], "
                    "button[aria-label*='download']"
                )
                if dl_btn:
                    dl_btn.click()
                else:
                    self._log("⚠️  Tombol download tidak ditemukan, coba klik kanan video...", "WARNING")

            download = dl_info.value
            download.save_as(output_filename)
            self._log(f"✅ Video tersimpan: {output_filename}", "SUCCESS")
            self._progress(100, "Video berhasil didownload!")
            return output_filename

        except Exception as e:
            self._log(f"❌ Download gagal: {e}", "ERROR")
            return None
