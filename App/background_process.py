import os
import sys
import time
import random
import string
import requests as req
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from PySide6.QtCore import QThread, Signal

from App.firefox_relay import FirefoxRelay
from App.gmail_otp import GmailOTPReader

# Selector email field spesifik a1d.ai/auth/sign-in
# (ported dari a1d-auto-upscaler/core.py)
A1D_EMAIL_ID = "#_R_4p5fiv9fkjb_-form-item"


class A1DProcessor(QThread):
    log_signal      = Signal(str, str)       # (msg, level)
    progress_signal = Signal(int, str)        # (pct, msg)
    finished_signal = Signal(bool, str, str)  # (success, msg, output_path)

    # ── URL constants (identik dengan a1d-auto-upscaler) ───────────────────────
    SIGNIN_URL = "https://a1d.ai/auth/sign-in"
    EDITOR_URL = "https://a1d.ai/video-upscaler/editor"

    QUALITY_MAP = {
        "1080p": "1080p",
        "2k":    "2K",
        "4k":    "4K",
    }

    def __init__(self, base_dir: str, video_path: str, config: dict):
        super().__init__()
        self.base_dir   = base_dir
        self.video_path = video_path
        self.config     = config
        self.driver     = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    # ── Helpers ───────────────────────────────────────────────────────────────
    def log(self, msg: str, level: str = "INFO"):
        self.log_signal.emit(msg, level)

    def prog(self, pct: int, msg: str = ""):
        self.progress_signal.emit(pct, msg)

    # ── Main thread run ───────────────────────────────────────────────────────
    def run(self):
        output_path = ""
        try:
            output_path = self._process()
            if not self._cancelled:
                self.finished_signal.emit(True, "Upscale selesai!", output_path)
        except Exception as e:
            self.log(f"Error: {e}", "ERROR")
            self.finished_signal.emit(False, str(e), "")
        finally:
            self._quit_driver()

    # ── Core process ──────────────────────────────────────────────────────────
    def _process(self) -> str:
        self.log("Memulai proses upscale...", "INFO")

        # Step 1: Buat email mask via Firefox Relay
        self.prog(5, "Membuat email mask...")
        api_key = self.config.get("relay_api_key", "").strip()
        if not api_key:
            raise ValueError("Firefox Relay API Key belum diset! Buka Settings ⚙ di kanan atas.")

        relay     = FirefoxRelay(api_key)
        mask_data = relay.create_mask("a1d-upscale-session")
        email     = mask_data["full_address"]
        mask_id   = mask_data["id"]

        self.log(f"Email mask dibuat: {email}", "SUCCESS")
        self.prog(10, "Email mask siap")

        # Step 2: Setup ChromeDriver
        drv_name    = "chromedriver.exe" if sys.platform == "win32" else "chromedriver"
        drv_path    = os.path.join(self.base_dir, "driver", drv_name)
        out_dir     = os.path.join(os.path.dirname(self.video_path), "OUTPUT")
        os.makedirs(out_dir, exist_ok=True)

        opts = Options()
        if self.config.get("headless", True):
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--incognito")
        opts.add_argument("--mute-audio")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_experimental_option("prefs", {
            "download.default_directory":  out_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade":   True,
            "safebrowsing.enabled": False,
            "profile.default_content_setting_values.automatic_downloads": 1,
        })

        svc         = Service(drv_path)
        self.driver = webdriver.Chrome(service=svc, options=opts)
        self.driver.set_page_load_timeout(60)
        wait = WebDriverWait(self.driver, 30)

        try:
            # Step 3: Buka halaman SIGN-IN langsung (bukan homepage)
            self.prog(15, "Membuka halaman sign-in...")
            self.log(f"Navigasi ke: {self.SIGNIN_URL}", "INFO")
            self.driver.get(self.SIGNIN_URL)
            time.sleep(2.5)

            # Step 4: Isi email dan submit
            self.prog(20, "Input email mask...")
            self.log(f"Input email: {email}", "INFO")
            self._fill_email(email)

            self.prog(25, "Submit email...")
            otp_request_time = int(time.time())   # catat SEBELUM klik submit
            self._click_submit()

            # Step 5: Tunggu form OTP muncul
            self.prog(30, "Menunggu form OTP...")
            self.log("⏳ Menunggu form OTP di halaman...", "INFO")
            self._wait_for_otp_form(timeout=30)
            self.log("✅ Form OTP terdeteksi", "SUCCESS")

            # Step 6: Polling Gmail OTP
            self.prog(35, "Menunggu OTP dari Gmail...")
            self.log("─" * 40, "INFO")
            self.log("📬 Membaca OTP dari Gmail...", "INFO")
            self.log("Cek email yang diteruskan Firefox Relay ke Gmail Anda", "INFO")
            self.log("─" * 40, "INFO")

            gmail = GmailOTPReader(self.base_dir)

            def _gmail_log(msg: str, level: str = "INFO"):
                self.log(f"[Gmail] {msg}", level)

            otp = gmail.wait_for_otp(
                sender          = "a1d.ai",
                mask_email      = email,
                after_timestamp = otp_request_time,
                timeout         = 180,
                interval        = 5,
                log_callback    = _gmail_log,
            )
            self.log(f"✅ OTP diterima: {otp}", "SUCCESS")

            # Step 7: Masukkan OTP ke halaman
            self.prog(50, "Memasukkan OTP ke halaman...")
            self._fill_otp(otp)

            # Step 8: Submit OTP
            self.prog(58, "Submit OTP...")
            success = self._click_otp_submit_and_verify()
            if not success:
                raise RuntimeError("❌ OTP salah atau kadaluarsa — submit gagal 3x")
            time.sleep(2)

            # Step 9: Tunggu redirect ke /home
            self.prog(65, "Menunggu login berhasil...")
            self.log("⏳ Menunggu /home...", "INFO")
            self._wait_for_home(timeout=30)
            self.log(f"✅ Login OK: {self.driver.current_url}", "SUCCESS")

            # Step 10: Navigate eksplisit ke editor (penting!)
            self.prog(72, "Membuka video editor...")
            self.log(f"Navigate ke: {self.EDITOR_URL}", "INFO")
            self.driver.get(self.EDITOR_URL)
            time.sleep(2)

            # Step 11: Upload video
            self.prog(78, "Mengupload video...")
            self.log(f"Upload: {os.path.basename(self.video_path)}", "INFO")
            self._upload_video(wait)
            time.sleep(4)

            # Step 12: Pilih kualitas
            self.prog(82, "Memilih kualitas output...")
            quality_key   = self.config.get("output_quality", "4k").lower()
            quality_label = self.QUALITY_MAP.get(quality_key, "4K")
            self._select_quality(quality_label)
            self.log(f"Kualitas dipilih: {quality_label}", "INFO")

            # Step 13: Klik upscale
            self.prog(86, "Memulai upscale...")
            self._start_upscale(wait)
            self.log("Proses upscale dimulai!", "SUCCESS")

            # Step 14: Tunggu selesai & download
            self.prog(88, "Menunggu proses selesai (5-30 menit)...")
            out_path = self._wait_and_download(wait, out_dir)
            self.log(f"Video tersimpan di: {out_path}", "SUCCESS")

        finally:
            try:
                relay.delete_mask(mask_id)
                self.log("Email mask dihapus", "INFO")
            except Exception:
                pass

        return out_path

    # ── Email fill (ported dari a1d-auto-upscaler _fill_email, 4 layers) ─────────
    def _find_email_field(self):
        id_sel = A1D_EMAIL_ID.lstrip("#")
        SELECTORS = [
            (By.ID,           id_sel),
            (By.CSS_SELECTOR, A1D_EMAIL_ID),
            (By.CSS_SELECTOR, 'input[placeholder="your@email.com"]'),
            (By.CSS_SELECTOR, 'input[placeholder*="your@"]'),
            (By.CSS_SELECTOR, 'input[type="email"]'),
            (By.CSS_SELECTOR, 'input[autocomplete="email"]'),
            (By.CSS_SELECTOR, 'input[name="email"]'),
            (By.CSS_SELECTOR, 'input[id*="email" i]'),
            (By.CSS_SELECTOR, 'input[placeholder*="email" i]'),
            (By.CSS_SELECTOR, 'input[type="text"]'),
        ]
        for by, sel in SELECTORS:
            try:
                el = self.driver.find_element(by, sel)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                continue
        return None

    def _fill_email(self, email: str):
        driver = self.driver
        wait   = WebDriverWait(driver, 20)
        try:
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass
        time.sleep(0.5)

        id_sel = A1D_EMAIL_ID.lstrip("#")

        # Layer 1: JS inject ke ID spesifik a1d.ai
        try:
            wait.until(EC.visibility_of_element_located((By.ID, id_sel)))
            res = driver.execute_script(
                """
                const el = document.getElementById(arguments[0]);
                if (!el) return 'not_found';
                el.scrollIntoView({block:'center',behavior:'instant'});
                el.focus(); el.removeAttribute('disabled'); el.removeAttribute('readOnly');
                const ns = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,'value').set;
                ns.call(el, arguments[1]);
                ['focus','input','change'].forEach(e =>
                    el.dispatchEvent(new Event(e,{bubbles:true})));
                return el.value;
                """, id_sel, email
            )
            if res == email:
                self.log("✅ Email OK (L1)", "INFO")
                return
        except Exception as e:
            self.log(f"⚠️ L1: {e}", "INFO")

        # Layer 2: Standard Selenium
        field = self._find_email_field()
        if not field:
            raise RuntimeError("❌ Input email tidak ditemukan")
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',behavior:'instant'});", field
            )
            time.sleep(0.3)
            field.click(); time.sleep(0.2); field.clear(); time.sleep(0.1)
            field.send_keys(email); time.sleep(0.5)
            if field.get_attribute("value") == email:
                self.log("✅ Email OK (L2)", "INFO")
                return
        except Exception as e:
            self.log(f"⚠️ L2: {e}", "INFO")

        # Layer 3: ActionChains
        try:
            ac = ActionChains(driver)
            ac.move_to_element(field).click(field)
            ac.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)
            ac.send_keys(Keys.DELETE).send_keys(email).perform()
            time.sleep(0.6)
            if field.get_attribute("value") == email:
                self.log("✅ Email OK (L3)", "INFO")
                return
        except Exception as e:
            self.log(f"⚠️ L3: {e}", "INFO")

        # Layer 4: JS inject fallback ke selector apapun
        try:
            driver.execute_script(
                """
                let el = document.querySelector(arguments[0]) ||
                    Array.from(document.querySelectorAll('input')).find(
                        i => i.offsetParent && !i.disabled && !i.readOnly &&
                            (i.type==='email'||(i.placeholder&&
                             i.placeholder.toLowerCase().includes('email'))));
                if (!el) return;
                el.scrollIntoView({block:'center',behavior:'instant'}); el.focus();
                el.removeAttribute('disabled'); el.removeAttribute('readOnly');
                const ns = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,'value').set;
                ns.call(el,arguments[1]);
                ['focus','input','change'].forEach(e=>
                    el.dispatchEvent(new Event(e,{bubbles:true})));
                """, A1D_EMAIL_ID, email
            )
            time.sleep(0.5)
            field = self._find_email_field()
            if field and field.get_attribute("value") == email:
                self.log("✅ Email OK (L4)", "INFO")
                return
        except Exception as e:
            self.log(f"⚠️ L4: {e}", "INFO")

        raise RuntimeError("❌ Semua layer gagal mengisi email")

    def _click_submit(self):
        """Klik tombol submit sign-in (ported dari a1d-auto-upscaler _click_submit)."""
        driver = self.driver
        for xpath in [
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
            "'abcdefghijklmnopqrstuvwxyz'),'continue with email')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
            "'abcdefghijklmnopqrstuvwxyz'),'continue')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
            "'abcdefghijklmnopqrstuvwxyz'),'send code')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
            "'abcdefghijklmnopqrstuvwxyz'),'sign in')]",
            "//button[@type='submit']",
        ]:
            try:
                btn = driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1.5)
                    return
            except NoSuchElementException:
                continue
        field = self._find_email_field()
        if field:
            field.send_keys(Keys.RETURN)
            time.sleep(1.5)
            return
        raise RuntimeError("❌ Tombol submit tidak ditemukan")

    # ── OTP form, fill, submit ───────────────────────────────────────────────
    def _wait_for_otp_form(self, timeout: int = 30):
        deadline = time.time() + timeout
        OTP_SELS = [
            'input[autocomplete="one-time-code"]',
            'input[inputmode="numeric"]',
            'input[type="number"][maxlength="6"]',
            'input[type="text"][maxlength="6"]',
            'input[maxlength="1"]',
            'input[placeholder*="code" i]',
            'input[name*="code" i]',
            'input[name*="otp" i]',
        ]
        while time.time() < deadline:
            if self._cancelled:
                raise InterruptedError("Proses dibatalkan")
            for sel in OTP_SELS:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if el.is_displayed():
                        return
                except NoSuchElementException:
                    continue
            time.sleep(0.8)
        raise TimeoutError("❌ Form OTP tidak muncul dalam 30 detik")

    def _fill_otp(self, otp: str):
        """Isi field OTP (identik dengan a1d-auto-upscaler _fill_otp)."""
        driver = self.driver
        OTP_SELS = [
            'input[autocomplete="one-time-code"]',
            'input[inputmode="numeric"]',
            'input[type="number"][maxlength="6"]',
            'input[type="text"][maxlength="6"]',
            'input[placeholder*="code" i]',
            'input[name*="code" i]',
            'input[name*="otp" i]',
        ]
        for sel in OTP_SELS:
            try:
                f = driver.find_element(By.CSS_SELECTOR, sel)
                if f.is_displayed():
                    f.click(); f.clear(); f.send_keys(otp)
                    self.log(f"OTP dimasukkan via CSS: {sel}", "INFO")
                    return
            except NoSuchElementException:
                continue
        # Fallback: individual digit boxes
        digits = driver.find_elements(By.CSS_SELECTOR, 'input[maxlength="1"]')
        if len(digits) >= len(otp):
            for i, ch in enumerate(otp):
                digits[i].click(); digits[i].send_keys(ch); time.sleep(0.08)
            self.log(f"OTP dimasukkan via {len(digits)} digit boxes", "INFO")
            return
        raise RuntimeError("❌ Input OTP tidak ditemukan")

    def _click_otp_submit_and_verify(self, max_retries: int = 3) -> bool:
        """Submit OTP dan cek hasil (identik dengan a1d-auto-upscaler)."""
        driver = self.driver
        SUBMIT_XPATHS = [
            "//button[@type='submit']",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'verify')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'confirm')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]",
        ]
        ERROR_SELS = [
            '//p[contains(translate(.,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"invalid")]',
            '//p[contains(translate(.,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"incorrect")]',
            '//p[contains(translate(.,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"expired")]',
            '[role="alert"]',
        ]
        for attempt in range(1, max_retries + 1):
            if self._cancelled:
                raise InterruptedError("Proses dibatalkan")
            clicked = False
            for xpath in SUBMIT_XPATHS:
                try:
                    btn = driver.find_element(By.XPATH, xpath)
                    if btn.is_displayed():
                        btn.click()
                        self.log(f"🔘 OTP submit percobaan {attempt}", "INFO")
                        clicked = True
                        break
                except NoSuchElementException:
                    continue
            if not clicked:
                try:
                    f = driver.find_element(
                        By.CSS_SELECTOR, 'input[autocomplete="one-time-code"]'
                    )
                    f.send_keys(Keys.RETURN)
                    clicked = True
                except Exception:
                    pass
            if not clicked:
                self.log("⚠️ Tidak ada tombol submit", "WARNING")
                return False

            time.sleep(2.5)
            url = driver.current_url
            if "/home" in url or "dashboard" in url:
                self.log("✅ OTP OK — redirect ke home", "SUCCESS")
                return True

            otp_gone = True
            for sel in [
                'input[autocomplete="one-time-code"]',
                'input[inputmode="numeric"]',
            ]:
                try:
                    if driver.find_element(By.CSS_SELECTOR, sel).is_displayed():
                        otp_gone = False
                        break
                except NoSuchElementException:
                    continue
            if otp_gone:
                self.log("✅ OTP OK — form OTP hilang", "SUCCESS")
                return True

            for err_sel in ERROR_SELS:
                try:
                    el = (
                        driver.find_element(By.XPATH, err_sel)
                        if err_sel.startswith("//")
                        else driver.find_element(By.CSS_SELECTOR, err_sel)
                    )
                    if el.is_displayed() and el.text.strip():
                        self.log(f"❌ OTP error: {el.text.strip()[:80]}", "ERROR")
                        return False
                except Exception:
                    continue

            self.log(f"⏳ Menunggu OTP response... ({attempt})", "INFO")
            time.sleep(2)

        url = driver.current_url
        return "/home" in url or "dashboard" in url

    def _wait_for_home(self, timeout: int = 30):
        """Tunggu browser redirect ke /home (ported dari a1d-auto-upscaler)."""
        start = time.time()
        while time.time() - start < timeout:
            if self._cancelled:
                raise InterruptedError("Proses dibatalkan")
            url = self.driver.current_url
            if "/home" in url or "dashboard" in url:
                return
            time.sleep(1)
        self.log(f"⚠️ Timeout /home — URL: {self.driver.current_url}", "WARNING")

    # ── Video upload & upscale ───────────────────────────────────────────────
    def _upload_video(self, wait: WebDriverWait):
        abs_path = os.path.abspath(self.video_path)
        try:
            file_inp = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, 'input[type="file"]'
            )))
            file_inp.send_keys(abs_path)
            self.log("✅ File diupload", "SUCCESS")
        except TimeoutException:
            for drop_sel in ['[class*="upload"]', '[class*="drop"]']:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, drop_sel).click()
                    time.sleep(1)
                    self.driver.find_element(
                        By.CSS_SELECTOR, 'input[type="file"]'
                    ).send_keys(abs_path)
                    self.log("✅ File via drop zone", "SUCCESS")
                    return
                except Exception:
                    continue
            raise RuntimeError("❌ Upload area tidak ditemukan")

    def _select_quality(self, quality_label: str):
        try:
            opts = self.driver.find_elements(
                By.XPATH,
                f"//button[contains(.,'{quality_label}')] | //label[contains(.,'{quality_label}')]"
                f"| //div[@role='button' and contains(.,'{quality_label}')]"
                f"| //div[@role='radio' and contains(.,'{quality_label}')]"
            )
            if opts:
                opts[0].click()
                self.log(f"✅ Kualitas {quality_label} dipilih", "INFO")
            else:
                self.log(f"⚠️ Opsi '{quality_label}' tidak ditemukan", "WARNING")
        except Exception as e:
            self.log(f"select_quality warning: {e}", "WARNING")

    def _start_upscale(self, wait: WebDriverWait):
        for xpath in [
            "//button[contains(.,'Generate')]",
            "//button[contains(.,'Upscale')]",
            "//button[contains(.,'Enhance')]",
            "//button[contains(.,'Start')]",
            "//button[@type='submit']",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(2)
                    return
            except NoSuchElementException:
                continue

    def _wait_and_download(self, wait: WebDriverWait, out_dir: str) -> str:
        timeout  = self.config.get("processing_hang_timeout", 1800)
        start    = time.time()
        last_pct = 88

        while time.time() - start < timeout:
            if self._cancelled:
                raise InterruptedError("Proses dibatalkan oleh user")
            try:
                dl_btns = self.driver.find_elements(
                    By.XPATH,
                    "//button[contains(.,'Download')] | //a[contains(.,'Download') or contains(@href,'.mp4')]"
                )
                if dl_btns:
                    self.log("Video siap di-download!", "SUCCESS")
                    self.prog(92, "Mendownload video...")
                    tag  = dl_btns[0].tag_name
                    href = dl_btns[0].get_attribute("href")
                    if tag == "a" and href and href.startswith("http"):
                        return self._download_url(href, out_dir)
                    else:
                        dl_btns[0].click()
                        time.sleep(8)
                        files = sorted(
                            [os.path.join(out_dir, f) for f in os.listdir(out_dir)
                             if f.endswith(".mp4")],
                            key=os.path.getmtime, reverse=True
                        )
                        self.prog(100, "Selesai!")
                        return files[0] if files else out_dir
            except Exception:
                pass

            elapsed = time.time() - start
            pct     = min(91, 88 + int((elapsed / timeout) * 3))
            if pct > last_pct:
                last_pct = pct
                mins = int(elapsed / 60)
                self.prog(pct, f"Upscaling... ({mins} menit berlalu)")
            time.sleep(6)

        raise TimeoutError(f"Timeout setelah {timeout // 60} menit")

    def _download_url(self, url: str, out_dir: str) -> str:
        dl_timeout = self.config.get("download_timeout", 600)
        basename   = os.path.splitext(os.path.basename(self.video_path))[0]
        quality    = self.config.get("output_quality", "4k")
        out_path   = os.path.join(out_dir, f"{basename}_upscaled_{quality}.mp4")
        self.log(f"Downloading ke: {out_path}", "INFO")
        with req.get(url, stream=True, timeout=dl_timeout) as r:
            r.raise_for_status()
            total      = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if self._cancelled:
                        raise InterruptedError("Download dibatalkan")
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct    = 92 + int((downloaded / total) * 8)
                        mb_dl  = downloaded // 1048576
                        mb_tot = total // 1048576
                        self.prog(pct, f"Download {mb_dl}/{mb_tot} MB")
        return out_path

    def _quit_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
