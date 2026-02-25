import os
import sys
import json
import time
import shutil
import datetime
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

A1D_EMAIL_ID = "#_R_4p5fiv9fkjb_-form-item"

QUALITY_TEXTS = {
    "1080p": ["1080p", "1080", "Full HD", "FHD", "1080P", "Full HD (1080p)"],
    "2k":    ["2K", "2k", "1440p", "QHD", "2K (1440p)", "1440", "2K QHD"],
    "4k":    ["4K", "4k", "2160p", "UHD", "Ultra HD", "4K (2160p)",
               "2160", "4K Ultra HD", "4K UHD"],
}

QUALITY_PRIORITY: dict[str, list[str]] = {}


class A1DProcessor(QThread):
    log_signal      = Signal(str, str)
    progress_signal = Signal(int, str)
    finished_signal = Signal(bool, str, str)

    SIGNIN_URL = "https://a1d.ai/auth/sign-in"
    EDITOR_URL = "https://a1d.ai/video-upscaler/editor"

    QUALITY_SELECTORS = {
        "1080p": [
            '[data-value="1080p"]', '[data-value="1080"]',
            '[data-resolution="1080p"]', '[data-quality="1080p"]',
            'button[class*="1080"]',
            '//button[contains(.,"1080")]', '//label[contains(.,"1080")]',
            '//div[@role="radio" and contains(.,"1080")]',
        ],
        "2k": [
            '[data-value="2k"]', '[data-value="2K"]', '[data-value="1440p"]',
            '[data-resolution="2k"]',
            '//button[contains(.,"2K")]', '//label[contains(.,"2K")]',
            '//div[@role="radio" and contains(.,"2K")]',
            '//button[contains(.,"1440")]',
        ],
        "4k": [
            '[data-value="4k"]', '[data-value="4K"]', '[data-value="2160p"]',
            '[data-resolution="4k"]', '[data-quality="4k"]',
            'button[class*="4K"]',
            '//button[contains(.,"4K")]', '//label[contains(.,"4K")]',
            '//div[@role="radio" and contains(.,"4K")]',
            '//div[@role="button" and contains(.,"4K")]',
            '//button[contains(.,"2160")]',
        ],
    }

    def __init__(self, base_dir: str, video_path: str, config: dict):
        super().__init__()
        self.base_dir   = base_dir
        self.video_path = video_path
        self.config     = config
        self.driver     = None
        self._cancelled = False

    def cancel(self):    self._cancelled = True
    def log(self, msg, level="INFO"): self.log_signal.emit(msg, level)
    def prog(self, pct, msg=""):      self.progress_signal.emit(pct, msg)

    # ══ MAIN RUN ═══════════════════════════════════════════════════════════════════════
    def run(self):
        try:
            out = self._process()
            if not self._cancelled:
                self.finished_signal.emit(True, "Upscale selesai!", out)
        except Exception as e:
            self.log(f"Error: {e}", "ERROR")
            self.finished_signal.emit(False, str(e), "")
        finally:
            self._quit_driver()

    # ══ CORE PROCESS ════════════════════════════════════════════════════════════════════
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
        self.log(f"Email mask: {email}", "SUCCESS")
        self.prog(10, "Email mask siap")

        out_dir_custom = self.config.get("output_dir", "").strip()
        raw_dir = out_dir_custom if (out_dir_custom and os.path.isdir(out_dir_custom)) \
                  else os.path.join(os.path.dirname(self.video_path), "OUTPUT")
        out_dir = os.path.normpath(os.path.abspath(raw_dir))
        os.makedirs(out_dir, exist_ok=True)
        self.log(f"📁 Output: {out_dir}", "INFO")

        drv_name = "chromedriver.exe" if sys.platform == "win32" else "chromedriver"
        drv_path = os.path.join(self.base_dir, "driver", drv_name)

        opts = Options()
        if self.config.get("headless", True):
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--mute-audio")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_experimental_option("prefs", {
            "download.default_directory":               out_dir,
            "download.prompt_for_download":              False,
            "download.directory_upgrade":                True,
            "download_restrictions":                     0,
            "safebrowsing.enabled":                      False,
            "safebrowsing.disable_download_protection":  True,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
        })

        self.driver = webdriver.Chrome(service=Service(drv_path), options=opts)
        self.driver.set_page_load_timeout(60)
        wait = WebDriverWait(self.driver, 30)
        self._apply_download_cdp(out_dir, silent=False)

        try:
            self.prog(15, "Membuka halaman sign-in...")
            self.log(f"[1] Buka: {self.SIGNIN_URL}", "INFO")
            self.driver.get(self.SIGNIN_URL)
            time.sleep(2.5)

            self.prog(20, "Input email mask...")
            self._fill_email(email)

            self.prog(25, "Submit email...")
            otp_request_time = int(time.time())
            self._click_submit()

            self.prog(30, "Menunggu form OTP...")
            self._wait_for_otp_form(timeout=30)
            self.log("✅ Form OTP terdeteksi", "SUCCESS")

            self.prog(38, "Menunggu OTP dari Gmail...")
            gmail = GmailOTPReader(self.base_dir)
            otp = gmail.wait_for_otp(
                sender          = "a1d.ai",
                mask_email      = email,
                after_timestamp = otp_request_time,
                timeout         = 180,
                interval        = 5,
                log_callback    = lambda m, lv="INFO": self.log(f"[Gmail] {m}", lv),
            )
            self.log(f"✅ OTP: {otp}", "SUCCESS")

            self.prog(50, "Memasukkan OTP...")
            self._fill_otp(otp)
            self.prog(58, "Submit OTP...")
            if not self._click_otp_submit_and_verify():
                raise RuntimeError("❌ OTP salah/kadaluarsa")
            time.sleep(2)

            self.prog(65, "Menunggu login berhasil...")
            self._wait_for_home(timeout=30)
            self.log(f"✅ Login: {self.driver.current_url}", "SUCCESS")

            self.prog(72, "Membuka video editor...")
            self.log(f"[2] Buka: {self.EDITOR_URL}", "INFO")
            self.driver.get(self.EDITOR_URL)
            time.sleep(3)

            self.prog(78, "Mengupload video...")
            self._upload_video(wait)
            time.sleep(6)

            self.prog(82, "Memilih kualitas...")
            self._select_quality(self.config.get("output_quality", "4k").lower())

            self.prog(86, "Memulai upscale...")
            self._start_upscale()
            self.log("⚙️ Proses upscale dimulai!", "SUCCESS")

            self.prog(88, "Menunggu proses selesai (5-30 menit)...")
            out_path = self._wait_and_download(out_dir)
            self.log(f"💾 Tersimpan: {out_path}", "SUCCESS")

        finally:
            try:
                relay.delete_mask(mask_id)
                self.log("Email mask dihapus", "INFO")
            except Exception:
                pass

        return out_path

    # ── CDP helper ──────────────────────────────────────────────────────────────────────
    def _apply_download_cdp(self, out_dir: str, silent: bool = False):
        norm = os.path.normpath(os.path.abspath(out_dir))
        try:
            self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow", "downloadPath": norm,
            })
            if not silent:
                self.log(f"✅ CDP download path: {norm}", "INFO")
        except Exception as e:
            if not silent:
                self.log(f"⚠️ CDP: {e}", "WARNING")

    # ══ EMAIL (4 layers) ═══════════════════════════════════════════════════════════════════
    def _find_email_field(self):
        id_sel = A1D_EMAIL_ID.lstrip("#")
        for by, sel in [
            (By.ID, id_sel), (By.CSS_SELECTOR, A1D_EMAIL_ID),
            (By.CSS_SELECTOR, 'input[placeholder="your@email.com"]'),
            (By.CSS_SELECTOR, 'input[type="email"]'),
            (By.CSS_SELECTOR, 'input[autocomplete="email"]'),
            (By.CSS_SELECTOR, 'input[name="email"]'),
            (By.CSS_SELECTOR, 'input[id*="email" i]'),
            (By.CSS_SELECTOR, 'input[placeholder*="email" i]'),
            (By.CSS_SELECTOR, 'input[type="text"]'),
        ]:
            try:
                el = self.driver.find_element(by, sel)
                if el.is_displayed(): return el
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
        try:
            wait.until(EC.visibility_of_element_located((By.ID, id_sel)))
            res = driver.execute_script("""
                const el = document.getElementById(arguments[0]);
                if (!el) return 'not_found';
                el.scrollIntoView({block:'center',behavior:'instant'});
                el.focus(); el.removeAttribute('disabled'); el.removeAttribute('readOnly');
                const ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                ns.call(el, arguments[1]);
                ['focus','input','change'].forEach(e => el.dispatchEvent(new Event(e,{bubbles:true})));
                return el.value;
            """, id_sel, email)
            if res == email: self.log("✅ Email OK (L1)", "INFO"); return
        except Exception as e:
            self.log(f"⚠️ L1: {e}", "INFO")
        field = self._find_email_field()
        if not field: raise RuntimeError("❌ Input email tidak ditemukan")
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',behavior:'instant'});", field)
            time.sleep(0.3)
            field.click(); time.sleep(0.2); field.clear(); time.sleep(0.1)
            field.send_keys(email); time.sleep(0.5)
            if field.get_attribute("value") == email: self.log("✅ Email OK (L2)", "INFO"); return
        except Exception as e:
            self.log(f"⚠️ L2: {e}", "INFO")
        try:
            ac = ActionChains(driver)
            ac.move_to_element(field).click(field)
            ac.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)
            ac.send_keys(Keys.DELETE).send_keys(email).perform()
            time.sleep(0.6)
            if field.get_attribute("value") == email: self.log("✅ Email OK (L3)", "INFO"); return
        except Exception as e:
            self.log(f"⚠️ L3: {e}", "INFO")
        try:
            driver.execute_script("""
                let el = document.querySelector(arguments[0]) ||
                    Array.from(document.querySelectorAll('input')).find(
                        i => i.offsetParent && !i.disabled && !i.readOnly &&
                            (i.type==='email'||(i.placeholder&&i.placeholder.toLowerCase().includes('email'))));
                if (!el) return;
                el.scrollIntoView({block:'center',behavior:'instant'}); el.focus();
                el.removeAttribute('disabled'); el.removeAttribute('readOnly');
                const ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                ns.call(el,arguments[1]);
                ['focus','input','change'].forEach(e=>el.dispatchEvent(new Event(e,{bubbles:true})));
            """, A1D_EMAIL_ID, email)
            time.sleep(0.5)
            field = self._find_email_field()
            if field and field.get_attribute("value") == email:
                self.log("✅ Email OK (L4)", "INFO"); return
        except Exception as e:
            self.log(f"⚠️ L4: {e}", "INFO")
        raise RuntimeError("❌ Semua layer gagal mengisi email")

    def _click_submit(self):
        for xpath in [
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue with email')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send code')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",
            "//button[@type='submit']",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed(): btn.click(); time.sleep(1.5); return
            except NoSuchElementException:
                continue
        field = self._find_email_field()
        if field: field.send_keys(Keys.RETURN); time.sleep(1.5); return
        raise RuntimeError("❌ Tombol submit tidak ditemukan")

    # ══ OTP ═════════════════════════════════════════════════════════════════════════════
    def _wait_for_otp_form(self, timeout: int = 30):
        deadline = time.time() + timeout
        OTP_SELS = [
            'input[autocomplete="one-time-code"]', 'input[inputmode="numeric"]',
            'input[type="number"][maxlength="6"]', 'input[type="text"][maxlength="6"]',
            'input[maxlength="1"]', 'input[placeholder*="code" i]',
        ]
        while time.time() < deadline:
            if self._cancelled: raise InterruptedError("Dibatalkan")
            for sel in OTP_SELS:
                try:
                    if self.driver.find_element(By.CSS_SELECTOR, sel).is_displayed(): return
                except NoSuchElementException:
                    continue
            time.sleep(0.8)
        raise TimeoutError("❌ Form OTP tidak muncul")

    def _fill_otp(self, otp: str):
        for sel in [
            'input[autocomplete="one-time-code"]', 'input[inputmode="numeric"]',
            'input[type="number"][maxlength="6"]', 'input[type="text"][maxlength="6"]',
            'input[placeholder*="code" i]',
        ]:
            try:
                f = self.driver.find_element(By.CSS_SELECTOR, sel)
                if f.is_displayed():
                    f.click(); f.clear(); f.send_keys(otp)
                    self.log(f"OTP via: {sel}", "INFO"); return
            except NoSuchElementException:
                continue
        digits = self.driver.find_elements(By.CSS_SELECTOR, 'input[maxlength="1"]')
        if len(digits) >= len(otp):
            for i, ch in enumerate(otp):
                digits[i].click(); digits[i].send_keys(ch); time.sleep(0.08)
            return
        raise RuntimeError("❌ Input OTP tidak ditemukan")

    def _click_otp_submit_and_verify(self, max_retries: int = 3) -> bool:
        XPATHS = [
            "//button[@type='submit']",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'verify')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]",
        ]
        for _ in range(1, max_retries + 1):
            if self._cancelled: raise InterruptedError("Dibatalkan")
            clicked = False
            for xpath in XPATHS:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    if btn.is_displayed(): btn.click(); clicked = True; break
                except NoSuchElementException:
                    continue
            if not clicked:
                try:
                    self.driver.find_element(
                        By.CSS_SELECTOR, 'input[autocomplete="one-time-code"]'
                    ).send_keys(Keys.RETURN)
                    clicked = True
                except Exception:
                    pass
            if not clicked: return False
            time.sleep(2.5)
            url = self.driver.current_url
            if "/home" in url or "dashboard" in url: return True
            otp_gone = not any(
                self._safe_visible(s)
                for s in ['input[autocomplete="one-time-code"]', 'input[inputmode="numeric"]']
            )
            if otp_gone: return True
            time.sleep(2)
        return "/home" in self.driver.current_url or "dashboard" in self.driver.current_url

    def _safe_visible(self, css_sel: str) -> bool:
        try: return self.driver.find_element(By.CSS_SELECTOR, css_sel).is_displayed()
        except Exception: return False

    def _wait_for_home(self, timeout: int = 30):
        start = time.time()
        while time.time() - start < timeout:
            if self._cancelled: raise InterruptedError("Dibatalkan")
            if "/home" in self.driver.current_url or "dashboard" in self.driver.current_url: return
            time.sleep(1)
        self.log(f"⚠️ Timeout /home — {self.driver.current_url}", "WARNING")

    # ══ UPLOAD ═════════════════════════════════════════════════════════════════════════════
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
                    self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys(abs_path)
                    self.log("✅ File via drop zone", "SUCCESS")
                    return
                except Exception:
                    continue
            raise RuntimeError("❌ Upload area tidak ditemukan")

    # ══ QUALITY SELECTION ═════════════════════════════════════════════════════════════════
    def _wait_for_quality_options(self, timeout: int = 15):
        keywords = ["4K", "2K", "1080", "quality", "resolution", "UHD", "HD"]
        deadline = time.time() + timeout
        self.log("⏳ Tunggu quality options...", "INFO")
        while time.time() < deadline:
            try:
                found = self.driver.execute_script("""
                    const kw = arguments[0];
                    const els = document.querySelectorAll(
                        'button,[role="radio"],[role="button"],label,[class*="quality"],[class*="resolution"],[class*="option"],[class*="tab"],[class*="card"]'
                    );
                    for (const el of els) {
                        const r = el.getBoundingClientRect();
                        if (r.width===0||r.height===0) continue;
                        if (kw.some(k => el.textContent.trim().toUpperCase().includes(k))) return true;
                    } return false;
                """, keywords)
                if found: self.log("✅ Quality options terdeteksi", "INFO"); return
            except Exception:
                pass
            time.sleep(0.5)
        self.log("⚠️ Quality options belum muncul — lanjut", "WARNING")

    def _debug_dump_quality(self):
        try:
            ts        = datetime.datetime.now().strftime("%H%M%S")
            debug_dir = os.path.join(self.base_dir, "debug")
            os.makedirs(debug_dir, exist_ok=True)
            ss_path = os.path.join(debug_dir, f"quality_{ts}.png")
            self.driver.save_screenshot(ss_path)
            self.log(f"📸 Screenshot → {ss_path}", "WARNING")
            html_path = os.path.join(debug_dir, f"quality_{ts}.html")
            with open(html_path, "w", encoding="utf-8") as f: f.write(self.driver.page_source)
            self.log(f"📄 HTML dump → {html_path}", "WARNING")
            raw = self.driver.execute_script("""
                const SELS=['button','[role="button"]','[role="radio"]','[role="tab"]','label',
                    '[class*="option"]','[class*="quality"]','[class*="resolution"]',
                    '[class*="select"]','[class*="card"]','[class*="pill"]','[class*="btn"]','input[type="radio"]'];
                const seen=new Set(); const out=[];
                for(const sel of SELS){
                    let els; try{els=document.querySelectorAll(sel);}catch(e){continue;}
                    for(const el of els){
                        if(seen.has(el))continue; seen.add(el);
                        const r=el.getBoundingClientRect();
                        if(r.width===0||r.height===0)continue;
                        out.push({tag:el.tagName,text:el.textContent.trim().substring(0,70),
                            cls:el.className.substring(0,100),id:el.id||'',
                            dv:el.getAttribute('data-value')||'',
                            al:el.getAttribute('aria-label')||'',role:el.getAttribute('role')||''});
                    }
                } return JSON.stringify(out.slice(0,60));
            """)
            items = json.loads(raw or '[]')
            json_path = os.path.join(debug_dir, f"quality_{ts}.json")
            with open(json_path, "w", encoding="utf-8") as f: json.dump(items, f, indent=2, ensure_ascii=False)
            self.log(f"📊 JSON → {json_path} ({len(items)} items)", "WARNING")
            kw = ['4k','2k','1080','quality','resolution','hd','uhd']
            for it in items:
                low=(it.get('text','')+it.get('dv','')+it.get('al','')+it.get('cls','')).lower()
                if not any(k in low for k in kw): continue
                sels=[]
                if it.get('id'):  sels.append(f'#{it["id"]}')
                if it.get('dv'):  sels.append(f'[data-value="{it["dv"]}"]')
                if it.get('al'):  sels.append(f'[aria-label="{it["al"]}"]')
                txt=it.get('text','').strip(); tag=it.get('tag','*').lower()
                if txt: sels.append(f'//{tag}[normalize-space(.)="{txt}"]')
                self.log(f"  🎯 <{it['tag']}> '{it['text'][:30]}' | {sels[0] if sels else '?'}", "WARNING")
            self.log("💡 Jalankan: python tools/inspect_quality.py", "WARNING")
        except Exception as e:
            self.log(f"_debug_dump_quality: {e}", "INFO")

    def _log_quality_elements(self):
        try:
            result = self.driver.execute_script("""
                const kw=['4k','2k','1080','quality','resolution','hd','uhd','fhd'];
                const found=[];
                document.querySelectorAll('button,[role="button"],[role="radio"],label,[class*="option"],[class*="quality"],[class*="resolution"],[class*="tab"],[class*="card"],[class*="btn"]'
                ).forEach(el=>{
                    const r=el.getBoundingClientRect();
                    if(r.width===0||r.height===0)return;
                    const txt=el.textContent.trim().toLowerCase();
                    if(!kw.some(k=>txt.includes(k)))return;
                    found.push({tag:el.tagName,text:el.textContent.trim().substring(0,60),
                        cls:el.className.substring(0,80),dv:el.getAttribute('data-value')||''});
                }); return JSON.stringify(found.slice(0,10));
            """)
            items = json.loads(result or '[]')
            if items:
                self.log(f"🔍 Quality di DOM ({len(items)}):", "INFO")
                for it in items: self.log(f"   <{it['tag']}> '{it['text']}' dv='{it['dv']}'", "INFO")
            else:
                self.log("🔍 Tidak ada quality element di DOM", "INFO")
        except Exception as e:
            self.log(f"_log_quality_elements: {e}", "INFO")

    def _select_quality(self, quality: str):
        q     = quality.lower().strip()
        texts = QUALITY_TEXTS.get(q, QUALITY_TEXTS["4k"])
        self.log(f"📺 Pilih kualitas: {q.upper()}", "INFO")
        self._wait_for_quality_options(timeout=15)
        priority_cfg  = self.config.get(f"quality_css_{q}", "").strip()
        priority_list = list(QUALITY_PRIORITY.get(q, []))
        if priority_cfg: priority_list.insert(0, priority_cfg)
        for sel in priority_list:
            try:
                el = (self.driver.find_element(By.XPATH, sel) if sel.startswith("//")
                      else self.driver.find_element(By.CSS_SELECTOR, sel))
                if el.is_displayed():
                    el.click()
                    self.log(f"✅ {q.upper()} (PRIORITY): {sel}", "SUCCESS")
                    time.sleep(0.5); return
            except Exception: continue
        js_result = None
        try:
            js_result = self.driver.execute_script("""
                const targets=arguments[0];
                const CLICKABLE=['button','div[role="button"]','div[role="radio"]','span[role="button"]',
                    'span[role="radio"]','label','a','input[type="radio"]','input[type="button"]',
                    '[class*="option"],[class*="quality"],[class*="resolution"],[class*="select"]',
                    '[class*="choice"],[class*="item"],[class*="card"],[class*="tab"]',
                    '[class*="pill"],[class*="btn"],[class*="radio"],[tabindex="0"]'];
                for(const sel of CLICKABLE){
                    let els; try{els=document.querySelectorAll(sel);}catch(e){continue;}
                    for(const el of els){
                        const rect=el.getBoundingClientRect();
                        if(rect.width===0||rect.height===0)continue;
                        const txt=el.textContent.trim();
                        const val=(el.value||el.getAttribute('data-value')||el.getAttribute('data-quality')||
                            el.getAttribute('data-resolution')||el.getAttribute('aria-label')||'');
                        for(const t of targets){
                            if(txt===t||txt.toLowerCase()===t.toLowerCase()||
                               txt.trim().toUpperCase()===t.toUpperCase()||
                               txt.includes(t)||val.toLowerCase()===t.toLowerCase()||
                               val.toLowerCase().includes(t.toLowerCase())){
                                el.scrollIntoView({block:'center',behavior:'instant'}); el.click();
                                ['click','mousedown','mouseup'].forEach(ev=>{
                                    try{el.dispatchEvent(new MouseEvent(ev,{bubbles:true}));}catch(_){}
                                });
                                return 'OK|'+sel+'|'+txt.substring(0,40);
                            }
                        }
                    }
                } return 'NOT_FOUND';
            """, texts)
        except Exception as e:
            self.log(f"⚠️ JS quality: {e}", "WARNING")
        if js_result and js_result.startswith("OK|"):
            parts = js_result.split("|")
            self.log(f"✅ {q.upper()} (JS) text='{parts[2]}'", "SUCCESS")
            time.sleep(0.8); return
        for sel in self.QUALITY_SELECTORS.get(q, self.QUALITY_SELECTORS["4k"]):
            try:
                el = (self.driver.find_element(By.XPATH, sel) if sel.startswith("//")
                      else self.driver.find_element(By.CSS_SELECTOR, sel))
                if el.is_displayed():
                    el.click()
                    self.log(f"✅ {q.upper()} (CSS/XPath): {sel}", "SUCCESS")
                    time.sleep(0.5); return
            except Exception: continue
        self._log_quality_elements()
        self._debug_dump_quality()
        self.log(f"⚠️ Quality {q.upper()} tidak ditemukan — lanjut", "WARNING")

    # ══ START UPSCALE ════════════════════════════════════════════════════════════════════
    def _start_upscale(self):
        for xpath in [
            "//button[contains(.,'Generate')]", "//button[contains(.,'Upscale')]",
            "//button[contains(.,'Enhance')]", "//button[contains(.,'Start')]",
            "//button[contains(.,'Process')]", "//button[@type='submit' and not(@disabled)]",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed() and btn.is_enabled():
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    btn.click()
                    self.log(f"✅ Upscale via: {xpath}", "INFO")
                    time.sleep(2); return
            except NoSuchElementException: continue
        try:
            res = self.driver.execute_script("""
                const btns=document.querySelectorAll('button');
                for(const b of btns){
                    const t=b.textContent.trim().toLowerCase();
                    if(t.includes('generate')||t.includes('upscale')||t.includes('enhance')||
                       t.includes('start')||t.includes('process')){
                        b.scrollIntoView({block:'center'}); b.click();
                        return 'clicked:'+b.textContent.trim();
                    }
                } return 'not_found';
            """)
            if res and res.startswith('clicked:'):
                self.log(f"✅ Upscale (JS): {res}", "INFO")
        except Exception as e:
            self.log(f"⚠️ _start_upscale JS: {e}", "WARNING")

    # ══ WAIT & DOWNLOAD ══════════════════════════════════════════════════════════════════
    def _wait_and_download(self, out_dir: str) -> str:
        timeout      = self.config.get("processing_hang_timeout", 1800)
        start        = time.time()
        last_pct     = 88
        # Flag: cegah "Video siap di-download!" muncul berulang
        dl_triggered = False

        while time.time() - start < timeout:
            if self._cancelled: raise InterruptedError("Dibatalkan")

            if not dl_triggered:
                # Deteksi tombol Download (hanya sekali)
                try:
                    dl_btns = self.driver.find_elements(
                        By.XPATH,
                        "//button[normalize-space(.)='Download' or "
                        "contains(normalize-space(.),'Download')] | "
                        "//a[contains(normalize-space(.),'Download') or "
                        "contains(@href,'.mp4')]"
                    )
                    if dl_btns:
                        dl_triggered = True
                except Exception:
                    pass

            if dl_triggered:
                self.log("✅ Video siap di-download!", "SUCCESS")
                self.prog(92, "Mendownload video...")
                self._apply_download_cdp(out_dir, silent=True)

                # Cek href (bisa jadi <a> parent dari <button>)
                href = None
                try:
                    href = self.driver.execute_script("""
                        let el = arguments[0];
                        for (let i = 0; i < 6; i++) {
                            const h = el.getAttribute('href') || el.href || '';
                            if (h && h.startsWith('http')) return h;
                            if (!el.parentElement) break;
                            el = el.parentElement;
                        } return null;
                    """, dl_btns[0])
                except Exception:
                    href = None

                # Layer A: direct URL → requests (paling stabil)
                if href and href.startswith("http"):
                    self.log(f"🔗 Download via URL", "INFO")
                    return self._download_url(href, out_dir)

                # Layer B/C: blob/button → Chrome download
                # ⚠️ KRITIS: snapshot diambil SEBELUM klik agar file baru terdeteksi
                default_dl     = os.path.join(os.path.expanduser("~"), "Downloads")
                dl_snapshot_pre = set()
                if os.path.isdir(default_dl):
                    try: dl_snapshot_pre = set(os.listdir(default_dl))
                    except Exception: pass

                before_out   = set(os.listdir(out_dir))
                click_time   = time.time()
                dl_btns[0].click()
                self.log("⏳ Tunggu Chrome download selesai...", "INFO")

                # Panggil tracker — exception di sini TIDAK di-catch agar tidak loop
                return self._wait_for_chrome_download(
                    out_dir, before_out, dl_snapshot_pre, click_time, timeout=600
                )

            # Belum ada tombol download — update progress
            elapsed = time.time() - start
            pct = min(91, 88 + int((elapsed / timeout) * 3))
            if pct > last_pct:
                last_pct = pct
                self.prog(pct, f"Upscaling... ({int(elapsed/60)} menit)")
            time.sleep(6)

        raise TimeoutError(f"Timeout setelah {timeout//60} menit")

    def _wait_for_chrome_download(
        self,
        out_dir:        str,
        before_out:     set,
        dl_snapshot_pre: set,   # snapshot Downloads SEBELUM klik
        click_time:     float,  # waktu klik tombol download
        timeout:        int = 600,
    ) -> str:
        """
        Tunggu Chrome selesai download lalu kembalikan path file.

        Strategi (urutan prioritas):
          1. File baru di out_dir (CDP berhasil mengarahkan ke out_dir)
          2. File baru di ~/Downloads berdasarkan SNAPSHOT (dl_snapshot_pre)
             diambil SEBELUM klik → akurat mendeteksi GUID.tmp
          3. File di ~/Downloads berdasarkan mtime >= click_time (fallback timing)
          4. .tmp stabil (ukuran tidak berubah, > 500 KB) → rename ke .mp4
        """
        start      = time.time()
        default_dl = os.path.join(os.path.expanduser("~"), "Downloads")
        use_fb     = (os.path.isdir(default_dl) and
                      os.path.abspath(default_dl) != os.path.abspath(out_dir))
        if use_fb:
            self.log(f"🔍 Fallback monitor: {default_dl}", "INFO")

        last_log = start  # throttle log

        while time.time() - start < timeout:
            if self._cancelled: raise InterruptedError("Dibatalkan")

            # ─ 1. Cek out_dir ────────────────────────────────────────────────
            try:
                new_out = [
                    os.path.join(out_dir, f)
                    for f in (set(os.listdir(out_dir)) - before_out)
                    if not f.endswith(".crdownload") and not f.endswith(".tmp")
                ]
                if new_out:
                    best = max(new_out, key=os.path.getmtime)
                    if os.path.getsize(best) > 500_000:
                        self.log(f"✅ Download selesai (out_dir): {os.path.basename(best)}", "SUCCESS")
                        return best
            except Exception:
                pass

            # ─ 2. Fallback ~/Downloads ──────────────────────────────────────────
            if use_fb:
                try:
                    current_dl = set(os.listdir(default_dl))

                    # Kandidat dari dua sumber: snapshot diff + mtime
                    by_snapshot = current_dl - dl_snapshot_pre
                    by_mtime    = {
                        f for f in current_dl
                        if os.path.getmtime(os.path.join(default_dl, f)) >= click_time - 2
                    }
                    candidates = by_snapshot | by_mtime

                    # Cek in-progress (.crdownload / .tmp)
                    in_prog = [f for f in candidates
                               if f.endswith(".crdownload") or f.endswith(".tmp")]

                    if in_prog:
                        # Log throttle — maksimal 1x per 8 detik
                        now = time.time()
                        if now - last_log >= 8:
                            try:
                                sz = os.path.getsize(os.path.join(default_dl, in_prog[0]))
                                self.log(
                                    f"📥 Mendownload... "
                                    f"{sz / 1048576:.1f} MB "
                                    f"({int(now - start)}s)",
                                    "INFO"
                                )
                            except Exception:
                                self.log(f"📥 Mendownload... ({int(now - start)}s)", "INFO")
                            last_log = now
                        time.sleep(2)
                        continue

                    # Tidak ada in-progress: cari file yang sudah selesai
                    completed = [
                        f for f in candidates
                        if not f.endswith(".crdownload") and not f.endswith(".tmp")
                    ]

                    # Cek .tmp yang mungkin sudah selesai tapi Chrome tidak rename
                    # (kasus blob URL — ukuran stabil & > 500 KB)
                    for f in list(candidates):  # list() agar aman dari modifikasi set
                        if not f.endswith(".tmp"): continue
                        fp = os.path.join(default_dl, f)
                        try:
                            sz1 = os.path.getsize(fp)
                            time.sleep(1.5)
                            sz2 = os.path.getsize(fp)
                            if sz1 == sz2 and sz1 > 500_000:
                                completed.append(f)  # .tmp stabil = selesai download
                        except Exception:
                            pass

                    # Sort by newest
                    completed.sort(
                        key=lambda f: os.path.getmtime(os.path.join(default_dl, f)),
                        reverse=True
                    )

                    for fname in completed:
                        fpath = os.path.join(default_dl, fname)
                        try:
                            fsize = os.path.getsize(fpath)
                        except Exception:
                            continue
                        if fsize < 500_000: continue  # skip file kecil

                        # Rename ke nama yang benar
                        base    = os.path.splitext(os.path.basename(self.video_path))[0]
                        quality = self.config.get("output_quality", "4k")
                        dest    = os.path.join(out_dir, f"{base}_upscaled_{quality}.mp4")
                        cnt = 1
                        while os.path.exists(dest):
                            dest = os.path.join(out_dir, f"{base}_upscaled_{quality}_{cnt}.mp4")
                            cnt += 1

                        shutil.move(fpath, dest)
                        self.log(
                            f"📦 Dipindah dari Downloads → "
                            f"{os.path.basename(dest)} ({fsize // 1048576} MB)",
                            "SUCCESS"
                        )
                        return dest

                except Exception as e:
                    self.log(f"⚠️ Monitor Downloads: {e}", "INFO")

            time.sleep(1.5)

        # Last resort
        try:
            all_out = sorted(
                [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".mp4")],
                key=os.path.getmtime, reverse=True
            )
            if all_out: return all_out[0]
        except Exception:
            pass
        raise TimeoutError("❌ Download Chrome tidak selesai")

    def _download_url(self, url: str, out_dir: str) -> str:
        basename = os.path.splitext(os.path.basename(self.video_path))[0]
        quality  = self.config.get("output_quality", "4k")
        out_path = os.path.join(out_dir, f"{basename}_upscaled_{quality}.mp4")
        self.log(f"Downloading: {out_path}", "INFO")
        with req.get(url, stream=True, timeout=self.config.get("download_timeout", 600)) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(65536):
                    if self._cancelled: raise InterruptedError("Download dibatalkan")
                    f.write(chunk); done += len(chunk)
                    if total:
                        self.prog(92 + int((done / total) * 8),
                                  f"Download {done//1048576}/{total//1048576} MB")
        return out_path

    def _quit_driver(self):
        if self.driver:
            try: self.driver.quit()
            except Exception: pass
            self.driver = None
