import re
import time
from typing import Optional, Callable
from bs4 import BeautifulSoup
from playwright.sync_api import Page, TimeoutError as PWTimeout

MAILTICKING_URL = "https://mailticking.com"

# Domain yang TIDAK boleh dipakai (Google mungkin reject)
BANNED_DOMAINS = {"@gmail.com", "@googlemail.com"}

OTP_BG_COLORS = {"#eaf2ff", "#e8f0fe", "#f1f8ff", "#e3f2fd", "#f0f4ff", "#dce8fc"}
OTP_TEXT_COLORS = {
    "#1c3a70", "#1a73e8", "#4285f4", "#1558d6", "#1967d2",
    "#185abc", "#174ea6", "#0d47a1",
}


def _extract_otp_from_html(html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return None

    SKIP_WORDS = {
        "THIS", "THAT", "FROM", "WITH", "YOUR", "EMAIL", "ALIAS",
        "SENT", "STOP", "LINK", "CLICK", "HERE", "MORE", "INFO",
        "GOOGLE", "GMAIL", "VERIFY", "GEMINI", "CLOUD", "SIGN",
        "CHANGE", "DELETE", "UPDATE", "INBOX", "REFRESH", "LOGOUT", "RELOAD"
    }

    for tag in soup.find_all("span", class_="verification-code"):
        text = re.sub(r'\s+', '', tag.get_text(strip=True))
        if re.fullmatch(r'[A-Z0-9]{4,8}', text, re.IGNORECASE):
            code = text.upper()
            if code not in SKIP_WORDS:
                return code

    def _n(s): return s.lower().replace(" ", "").strip()

    def _is_otp_tag(tag) -> bool:
        style = _n(tag.get("style", "") or "")
        if not style: return False
        m = re.search(r'font-size:([\d.]+)(px|pt|em|rem)', style)
        if m:
            val = float(m.group(1))
            px  = val if m.group(2) == "px" else val * 1.333
            if px >= 18: return True
        for c in OTP_TEXT_COLORS:
            if _n(c) in style: return True
        for c in OTP_BG_COLORS:
            if _n(c) in style: return True
        if "letter-spacing" in style and "font-weight:700" in style: return True
        if "letter-spacing" in style and "font-weight:bold" in style: return True
        return False

    for tag in soup.find_all(True):
        if _is_otp_tag(tag):
            text = re.sub(r'\s+', '', tag.get_text(strip=True))
            if re.fullmatch(r'[A-Z0-9]{4,8}', text, re.IGNORECASE):
                code = text.upper()
                if code not in SKIP_WORDS:
                    return code

    STANDALONE = ["td", "div", "span", "p", "b", "strong", "h1", "h2", "h3"]
    for tag in soup.find_all(STANDALONE):
        text = re.sub(r'\s+', '', tag.get_text(strip=True))
        if re.fullmatch(r'[A-Z0-9]{4,8}', text, re.IGNORECASE):
            code = text.upper()
            if code not in SKIP_WORDS:
                return code

    plain = soup.get_text(separator=" ")
    patterns = [
        r'(?:verification|one-time)\s+code[^A-Z0-9]{0,20}([A-Z0-9]{4,8})\b',
        r'Your\s+code\s+is[:\s]+([A-Z0-9]{4,8})\b',
        r'\b([0-9]{6})\b',
        r'\b([A-Z0-9]{6})\b',
    ]
    FALSE_YEARS = {str(y) for y in range(2018, 2032)}
    FOOTER_CTX  = ["copyright", "\u00a9", "google llc", "mountain view", "privacy", "terms"]
    for pat in patterns:
        for m in re.finditer(pat, plain, re.IGNORECASE):
            code = m.group(1).upper()
            if code in FALSE_YEARS: continue
            ctx = plain[max(0, m.start()-40):m.end()+20].lower()
            if any(k in ctx for k in FOOTER_CTX): continue
            if code not in SKIP_WORDS:
                return code

    return None


class MailtickingClient:
    def __init__(self, page: Page, log_callback: Optional[Callable] = None):
        self.page = page
        self._log_cb = log_callback

    def _log(self, msg: str, level: str = "INFO"):
        if self._log_cb:
            self._log_cb(msg, level)

    def open_mailticking(self) -> str:
        self._log("Membuka mailticking.com...")
        self.page.goto(MAILTICKING_URL, wait_until="domcontentloaded")
        self.page.wait_for_load_state("networkidle", timeout=15000)
        return self.get_fresh_email()

    def get_fresh_email(self) -> str:
        # Step 3: Wait for modal and select #type4
        try:
            self.page.wait_for_selector("#type4", timeout=12000)
            self._log("Modal 'Your Temp Email is Ready' detected.")
        except PWTimeout:
            self._log("Modal not detected or slow to load", "WARNING")

        self._configure_checkboxes()
        time.sleep(0.5)

        email = self._click_change_once()
        self._log(f"Email ready after change: {email}")

        self._click_activate()

        self._log("Waiting for page to reload after Activate...")
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        final_email = self._read_email_from_navbar() or email
        self._log(f"Temp email obtained: {final_email}")
        return final_email

    def _configure_checkboxes(self):
        try:
            cb = self.page.locator("#type4").first
            if cb.is_visible() and not cb.is_checked():
                cb.check()
                self._log("Checked: abc@domain.com (#type4)")
        except Exception as e:
            self._log(f"#type4 error: {e}", "WARNING")

        try:
            checkboxes = self.page.locator("input[type='checkbox'][name='type']").all()
            for cb in checkboxes:
                try:
                    cb_id = cb.get_attribute("id") or ""
                    if cb_id == "type4":
                        continue
                    if cb.is_checked():
                        cb.uncheck()
                except Exception:
                    continue
            self._log("Checkboxes configured: only #type4 selected")
        except Exception:
            pass

    def _read_email_from_modal(self) -> str:
        selectors = [
            ".modal input[type='text']", ".modal input[type='email']",
            ".modal input[readonly]", ".modal input", "input[type='text']",
            "#email"
        ]
        for sel in selectors:
            try:
                el = self.page.locator(sel).first
                if el.is_visible():
                    val = (el.input_value() or el.text_content() or "").strip()
                    if "@" in val:
                        return val
            except Exception:
                pass
        return ""

    def _click_change_once(self) -> str:
        current_email = self._read_email_from_modal()
        self._log(f"Current email before change: {current_email}")

        try:
            btn = self.page.locator("#modalChange").first
            if not btn.is_visible():
                btn = self.page.locator("button.btn-info:has-text('Change')").first
            if btn.is_visible():
                btn.click()
                self._log("Clicked Change button once.")
        except Exception as e:
            self._log("Change button not found", "WARNING")
            return current_email

        deadline = time.time() + 3
        while time.time() < deadline:
            time.sleep(0.4)
            new_email = self._read_email_from_modal()
            if new_email and new_email != current_email:
                return new_email
        return self._read_email_from_modal()

    def _read_email_from_navbar(self) -> str:
        for sel in ["input[type='text']", "input[readonly]", ".navbar input", "#email"]:
            try:
                el = self.page.locator(sel).first
                if el.is_visible():
                    val = (el.input_value() or el.text_content() or "").strip()
                    if "@" in val:
                        return val
            except Exception:
                pass
        return ""

    def _click_activate(self):
        try:
            btn = self.page.locator("#emailActivationModal > div > div > div.modal-footer.text-center > a").first
            if btn.is_visible():
                btn.click()
                self._log("Clicked Activate button (exact)")
                return
        except Exception:
            pass

        for sel in ["a.activeBtn", "a.btn-warning.activeBtn", ".activeBtn"]:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    self._log(f"Clicked Activate button (fallback: {sel})")
                    return
            except Exception:
                pass

    def _find_gemini_row(self):
        try:
            links = self.page.locator("a[href*='/mail/view/']").all()
            for link in links:
                txt = (link.text_content() or "").lower()
                if any(k in txt for k in ["gemini", "verification", "enterprise"]):
                    return link
            if links: return links[0]
        except Exception:
            pass
        
        try:
            rows = self.page.locator("table tbody tr").all()
            for row in rows:
                txt = (row.text_content() or "").lower()
                if any(k in txt for k in ["gemini", "verification code", "enterprise", "a1d", "a1d.ai"]):
                    return row
        except Exception:
            pass
        return None

    def wait_for_verification_email(self, timeout: int = 90) -> bool:
        self._log("Checking inbox for verification email...")
        self.page.bring_to_front()

        start = time.time()
        while time.time() - start < timeout:
            try:
                self.page.reload(wait_until="domcontentloaded")
                time.sleep(2)
                
                try:
                    act_btns = self.page.locator("#emailActivationModal a.activeBtn, a.activeBtn").all()
                    for b in act_btns:
                        if b.is_visible():
                            b.click()
                            time.sleep(1)
                            break
                except Exception:
                    pass

                row = self._find_gemini_row()
                if row:
                    self._log("Verification email found!")
                    return True
            except Exception:
                pass

            elapsed = int(time.time() - start)
            if elapsed > 0 and elapsed % 10 < 3:
                self._log(f"Waiting for email... ({elapsed}s)")
            time.sleep(2)

        return False

    def extract_verification_code(self) -> Optional[str]:
        self._log("Extracting verification code from email...")
        self.page.bring_to_front()

        row = self._find_gemini_row()
        if row:
            row.click()
            self._log("Clicked verification email link")
            try:
                self.page.wait_for_selector("span.verification-code, .verification-code", timeout=15000)
            except PWTimeout:
                pass
            time.sleep(2.5)
        else:
            self._log("Could not find email link to click", "WARNING")
            time.sleep(2)

        # 1. Coba JS Path spesifik dari user untuk A1D
        a1d_js_path = "#content-wrapper > table > tbody > tr > td > table > tbody > tr > td > table.undefined > tbody > tr > td > table > tbody > tr > td > p"
        
        try:
            # Cek di main page
            a1d_el = self.page.locator(a1d_js_path).first
            if a1d_el.is_visible():
                otp = (a1d_el.text_content() or "").strip()
                if re.fullmatch(r'[0-9]{6}', otp):
                    self._log(f"Verification code extracted (A1D JS Path): {otp}")
                    return otp
        except Exception:
            pass
            
        # Cek di dalam iframes untuk JS Path A1D
        try:
            iframes = self.page.locator("iframe").all()
            for iframe in iframes:
                frame = iframe.content_frame
                if frame:
                    try:
                        a1d_el = frame.locator(a1d_js_path).first
                        if a1d_el.is_visible():
                            otp = (a1d_el.text_content() or "").strip()
                            if re.fullmatch(r'[0-9]{6}', otp):
                                self._log(f"Verification code extracted (A1D JS Path in iframe): {otp}")
                                return otp
                    except Exception:
                        continue
        except Exception:
            pass

        # 2. Pola umum span.verification-code
        try:
            otp_el = self.page.locator("span.verification-code").first
            if otp_el.is_visible():
                otp = (otp_el.text_content() or "").strip()
                if re.fullmatch(r'[A-Z0-9]{4,8}', otp, re.IGNORECASE):
                    self._log(f"Verification code extracted (span): {otp.upper()}")
                    return otp.upper()
        except Exception:
            pass

        html_content = ""
        try:
            iframes = self.page.locator("iframe").all()
            for iframe in iframes:
                frame = iframe.content_frame
                if frame:
                    content = frame.content()
                    if any(k in content.lower() for k in ["verification", "code", "gemini", "your code", "a1d"]):
                        html_content = content
                        self._log("Found code in iframe.")
                        break
        except Exception:
            pass

        if not html_content:
            html_content = self.page.content()

        otp = _extract_otp_from_html(html_content)
        if otp:
            self._log(f"Verification code extracted: {otp}")
            return otp

        self._log("Could not extract verification code from email", "WARNING")
        return None
