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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from PySide6.QtCore import QThread, Signal

from App.firefox_relay import FirefoxRelay
from App.gmail_otp import GmailOTPReader


class A1DProcessor(QThread):
    log_signal      = Signal(str, str)       # (msg, level)
    progress_signal = Signal(int, str)        # (pct, msg)
    finished_signal = Signal(bool, str, str)  # (success, msg, output_path)

    A1D_URL     = "https://a1d.ai"
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

    def _make_password(self, length: int = 14) -> str:
        chars = string.ascii_letters + string.digits
        pwd   = (
            random.choice(string.ascii_uppercase) +
            random.choice(string.digits) +
            "!#" +
            "".join(random.choices(chars, k=length - 3))
        )
        return "".join(random.sample(pwd, len(pwd)))

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
        password  = self._make_password()

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
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_experimental_option("prefs", {
            "download.default_directory":  out_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade":   True,
        })

        svc         = Service(drv_path)
        self.driver = webdriver.Chrome(service=svc, options=opts)
        self.driver.set_page_load_timeout(60)
        wait = WebDriverWait(self.driver, 30)

        try:
            # Step 3: Buka a1d.ai dan register
            self.prog(15, "Membuka a1d.ai...")
            self.log("Navigasi ke a1d.ai...", "INFO")
            self.driver.get(self.A1D_URL)
            time.sleep(3)

            self.prog(20, "Registrasi akun baru...")
            self._register(wait, email, password)
            self.log(f"Register dengan email: {email}", "INFO")

            # Step 3b: Tunggu form OTP muncul di halaman SEBELUM polling Gmail
            # FIX: Tanpa ini, _input_otp dipanggil saat halaman belum siap
            self.prog(25, "Menunggu form OTP muncul di halaman...")
            self.log("⏳ Menunggu form OTP di halaman...", "INFO")
            self._wait_for_otp_form(timeout=30)
            self.log("✅ Form OTP terdeteksi di halaman", "SUCCESS")

            # Step 4: Baca OTP dari Gmail — dengan live log callback
            self.prog(30, "Menunggu OTP dari Gmail...")
            self.log("─" * 40, "INFO")
            self.log("📬 Membaca OTP dari Gmail...", "INFO")
            self.log(f"   Cek email yang diteruskan Firefox Relay ke Gmail Anda", "INFO")
            self.log("─" * 40, "INFO")

            gmail = GmailOTPReader(self.base_dir)

            def _gmail_log(msg: str, level: str):
                self.log(f"   [Gmail] {msg}", level)
                if "berlalu" in msg:
                    self.prog(30, msg)

            otp = gmail.wait_for_otp(
                sender="a1d.ai",
                timeout=180,
                interval=5,
                log_callback=_gmail_log
            )

            self.log(f"✅ OTP diterima: {otp}", "SUCCESS")

            # Step 5: Masukkan OTP ke halaman
            self.prog(40, "Memasukkan OTP ke halaman...")
            self._input_otp(wait, otp)

            # Step 5b: Submit OTP dan verifikasi redirect
            self.prog(45, "Submit & verifikasi OTP...")
            success = self._click_otp_submit_and_verify(wait)
            if not success:
                raise RuntimeError("❌ OTP salah atau kadaluarsa — submit OTP gagal setelah 3x percobaan")
            time.sleep(2)

            # Step 6: Upload video
            self.prog(50, "Mengupload video...")
            self.log(f"Upload: {os.path.basename(self.video_path)}", "INFO")
            self._upload_video(wait)
            time.sleep(3)

            # Step 7: Pilih kualitas
            self.prog(60, "Memilih kualitas output...")
            quality_key   = self.config.get("output_quality", "4k").lower()
            quality_label = self.QUALITY_MAP.get(quality_key, "4K")
            self._select_quality(quality_label)
            self.log(f"Kualitas dipilih: {quality_label}", "INFO")

            # Step 8: Klik upscale
            self.prog(65, "Memulai upscale di server...")
            self._start_upscale(wait)
            self.log("Proses upscale dimulai!", "SUCCESS")

            # Step 9: Tunggu & download
            self.prog(70, "Menunggu proses selesai (bisa 5-30 menit)...")
            out_path = self._wait_and_download(wait, out_dir)
            self.log(f"Video tersimpan di: {out_path}", "SUCCESS")

        finally:
            try:
                relay.delete_mask(mask_id)
                self.log("Email mask dihapus", "INFO")
            except Exception:
                pass

        return out_path

    # ── Selenium sub-steps ────────────────────────────────────────────────────
    def _register(self, wait: WebDriverWait, email: str, password: str):
        try:
            btn = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(.,'Sign Up') or contains(.,'Get Started') or contains(.,'Register')]"
                "| //a[contains(.,'Sign Up') or contains(.,'Get Started')]"
            )))
            btn.click()
            time.sleep(1)
        except TimeoutException:
            self.driver.get(f"{self.A1D_URL}/auth/signup")
            time.sleep(2)

        email_inp = wait.until(EC.presence_of_element_located((
            By.XPATH, "//input[@type='email' or @name='email' or @placeholder[contains(.,'mail')]]"
        )))
        email_inp.clear()
        email_inp.send_keys(email)

        try:
            pwd_inp = self.driver.find_element(
                By.XPATH, "//input[@type='password' or @name='password']"
            )
            pwd_inp.clear()
            pwd_inp.send_keys(password)
        except Exception:
            pass

        submit = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[@type='submit' or contains(.,'Sign Up') or contains(.,'Create') or contains(.,'Register')]"
        )))
        submit.click()

    def _wait_for_otp_form(self, timeout: int = 30):
        """
        FIX: Tunggu sampai form OTP benar-benar muncul di halaman.
        Ini adalah langkah krusial yang hilang di versi sebelumnya —
        tanpa ini, _input_otp dipanggil saat halaman belum menampilkan
        form OTP sehingga OTP tidak bisa dimasukkan.
        Ported dari a1d-auto-upscaler/core.py _wait_for_otp_form()
        """
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
        self.log("⚠️ Form OTP tidak terdeteksi dalam timeout — lanjut tetap", "WARNING")

    def _input_otp(self, wait: WebDriverWait, otp: str):
        """
        FIX: Gunakan CSS selectors lengkap dari a1d-auto-upscaler/core.py
        untuk mencari dan mengisi field OTP.
        Urutan prioritas:
          1. CSS selectors spesifik OTP (one-time-code, numeric, dsb)
          2. Individual digit boxes (maxlength=1)
          3. XPATH fallback
        Submit sekarang dipisah ke _click_otp_submit_and_verify().
        """
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
                    f.click()
                    f.clear()
                    f.send_keys(otp)
                    self.log(f"OTP dimasukkan via CSS: {sel}", "INFO")
                    return
            except NoSuchElementException:
                continue

        # Fallback: individual digit boxes (maxlength="1")
        digits = driver.find_elements(By.CSS_SELECTOR, 'input[maxlength="1"]')
        if len(digits) >= len(otp):
            for i, ch in enumerate(otp):
                digits[i].click()
                digits[i].send_keys(ch)
                time.sleep(0.08)
            self.log(f"OTP dimasukkan via {len(digits)} digit boxes", "INFO")
            return

        # Fallback XPATH
        try:
            otp_inp = wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//input[contains(@name,'otp') or contains(@name,'code') or contains(@placeholder,'code')]"
            )))
            otp_inp.clear()
            otp_inp.send_keys(otp)
            self.log("OTP dimasukkan via XPATH fallback", "INFO")
        except Exception as e:
            raise RuntimeError(f"❌ Input OTP tidak ditemukan di halaman: {e}")

    def _click_otp_submit_and_verify(self, wait: WebDriverWait, max_retries: int = 3) -> bool:
        """
        FIX: Submit OTP dan verifikasi redirect ke home/dashboard.
        Dipisah dari _input_otp agar bisa retry jika gagal.
        Ported dari a1d-auto-upscaler/core.py _click_otp_submit_and_verify()
        """
        driver = self.driver
        SUBMIT_XPATHS = [
            "//button[@type='submit']",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'verify')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'confirm')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]",
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

            # Fallback: Enter key di field OTP
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
                self.log("⚠️ Tidak ada tombol submit OTP ditemukan", "WARNING")
                return False

            time.sleep(2.5)

            # Cek redirect ke home/dashboard
            url = driver.current_url
            if any(p in url for p in ["/home", "dashboard", "/video-upscaler", "/editor"]):
                self.log("✅ OTP diterima — redirect berhasil", "SUCCESS")
                return True

            # Cek apakah form OTP sudah hilang (artinya berhasil)
            otp_gone = True
            for sel in [
                'input[autocomplete="one-time-code"]',
                'input[inputmode="numeric"]',
                'input[maxlength="1"]',
            ]:
                try:
                    if driver.find_element(By.CSS_SELECTOR, sel).is_displayed():
                        otp_gone = False
                        break
                except NoSuchElementException:
                    continue
            if otp_gone:
                self.log("✅ OTP berhasil — form OTP sudah hilang", "SUCCESS")
                return True

            self.log(f"⏳ Menunggu respons OTP... (percobaan {attempt})", "INFO")
            time.sleep(2)

        url = driver.current_url
        return any(p in url for p in ["/home", "dashboard", "/video-upscaler", "/editor"])

    def _upload_video(self, wait: WebDriverWait):
        abs_path = os.path.abspath(self.video_path)
        try:
            file_inp = wait.until(EC.presence_of_element_located((
                By.XPATH, "//input[@type='file']"
            )))
            file_inp.send_keys(abs_path)
        except TimeoutException:
            try:
                upload_area = wait.until(EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(.,'Upload') or contains(.,'Add Video')]"
                    "| //div[contains(@class,'upload') or contains(@class,'drop')]"
                )))
                upload_area.click()
                time.sleep(1)
                file_inp = wait.until(EC.presence_of_element_located((
                    By.XPATH, "//input[@type='file']"
                )))
                file_inp.send_keys(abs_path)
            except Exception as e:
                raise RuntimeError(f"Gagal menemukan upload input: {e}")

    def _select_quality(self, quality_label: str):
        try:
            opts = self.driver.find_elements(
                By.XPATH,
                f"//button[contains(.,'{quality_label}')] | //label[contains(.,'{quality_label}')]"
                f"| //div[contains(@class,'option') and contains(.,'{quality_label}')]"
            )
            if opts:
                opts[0].click()
            else:
                self.log(f"Opsi '{quality_label}' tidak ditemukan di halaman.", "WARNING")
        except Exception as e:
            self.log(f"select_quality warning: {e}", "WARNING")

    def _start_upscale(self, wait: WebDriverWait):
        btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(.,'Upscale') or contains(.,'Enhance') or contains(.,'Process') or contains(.,'Start')]"
        )))
        btn.click()
        time.sleep(2)

    def _wait_and_download(self, wait: WebDriverWait, out_dir: str) -> str:
        timeout  = self.config.get("processing_hang_timeout", 1800)
        start    = time.time()
        last_pct = 70

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
                    self.prog(90, "Mendownload video...")
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
            pct     = min(89, 70 + int((elapsed / timeout) * 19))
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
                        pct    = 90 + int((downloaded / total) * 9)
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
