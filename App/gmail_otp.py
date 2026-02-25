"""
gmail_otp.py

Port langsung dari a1d-auto-upscaler/core.py GmailWatcher.
Logika yang sama persis, sudah terbukti no-error.
"""
import base64
import os
import pickle
import re
import time
import datetime
import threading
from typing import Callable, Optional
from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# ── Daftar subject OTP yang valid ─────────────────────────────────────────
A1D_OTP_SUBJECTS = [
    '"Confirm Your A1D.AI Signup"',
    '"Your verification code"',
    '"Your code"',
    '"Sign in to A1D"',
    '"One-time code"',
]

# ── Subject yang DIABAIKAN (Welcome, newsletter, dll) ─────────────────────
A1D_IGNORE_SUBJECTS = [
    "welcome",
    "let's get started",
    "get started",
    "newsletter",
    "subscription",
    "announcement",
]


class GmailOTPReader:
    """
    Port langsung dari GmailWatcher di a1d-auto-upscaler/core.py.
    Logika identik, hanya disesuaikan interface-nya untuk v2.
    """

    def __init__(self, base_dir: str):
        self.base_dir   = base_dir
        self.token_path = os.path.join(base_dir, "token.pickle")
        self.creds_path = os.path.join(base_dir, "credentials.json")
        self._service   = None
        self._log_cb: Optional[Callable] = None

    def _log(self, msg: str, level: str = "INFO"):
        if self._log_cb:
            self._log_cb(msg, level)

    # ── Auth (identik dengan GmailWatcher._authenticate) ─────────────────────
    def _authenticate(self):
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self._log("🔄 Gmail token di-refresh")
                except Exception as e:
                    self._log(f"⚠️  Refresh gagal: {e}")
                    creds = None
            if not creds:
                self._log("🔐 Memulai OAuth Gmail...")
                if not os.path.exists(self.creds_path):
                    raise FileNotFoundError(
                        f"credentials.json tidak ditemukan di: {self.creds_path}\n"
                        "Download dari Google Cloud Console (Gmail API -> OAuth 2.0)\n"
                        "dan letakkan di folder yang sama dengan main.py."
                    )
                flow  = InstalledAppFlow.from_client_secrets_file(
                    self.creds_path, GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "wb") as f:
                pickle.dump(creds, f)

        self._log("✅ Gmail API terautentikasi")
        self._service = build("gmail", "v1", credentials=creds)

    def _svc(self):
        if not self._service:
            self._authenticate()
        return self._service

    # ── _get_message_timestamp (identik) ─────────────────────────────────────
    def _get_message_timestamp(self, msg_id: str) -> int:
        try:
            meta = self._svc().users().messages().get(
                userId="me", id=msg_id,
                format="metadata",
                metadataHeaders=[]
            ).execute()
            return int(meta.get("internalDate", 0)) // 1000
        except Exception:
            return 0

    # ── _is_otp_email (identik) ─────────────────────────────────────────────
    def _is_otp_email(self, msg_id: str) -> bool:
        try:
            msg = self._svc().users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            self._log(f"⚠️  Gagal ambil pesan: {e}")
            return False

        headers = {
            h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }
        subject = headers.get("subject", "").lower()
        self._log(f"   📧 Subject : {headers.get('subject', '')}")
        self._log(f"   📧 From    : {headers.get('from', '')}")

        # Abaikan email Welcome/Newsletter
        for ignore in A1D_IGNORE_SUBJECTS:
            if ignore in subject:
                self._log(f"   ⛔ Diabaikan (subject: '{ignore}')")
                return False

        body = self._decode_body(msg["payload"])

        # Cek apakah ada OTP code
        for pattern in [
            r'\b([0-9]{6})\b', r'\b([0-9]{4})\b',
            r'code[:\s]+([0-9]{4,8})',
            r'Your\s+(?:verification\s+)?code\s+is[:\s]+([0-9]{4,8})',
            r'OTP[:\s]+([0-9]{4,8})',
        ]:
            if re.search(pattern, body, re.IGNORECASE):
                return True

        # Cek apakah ada verification link
        for pattern in [
            r'https?://[^\s"\' <>]+(?:verify|confirm|activate|token|magic)[^\s"\' <>]*',
            r'https?://a1d\.ai/[^\s"\' <>]+',
        ]:
            if re.search(pattern, body, re.IGNORECASE):
                return True

        self._log("   ⚠️  Email tidak mengandung OTP/link")
        return False

    # ── _build_queries (identik) ─────────────────────────────────────────────
    def _build_queries(
        self,
        sender:     str,
        mask_email: str = None,
        after_ts:   int = 0,
    ) -> list:
        ts_filter = f" after:{max(0, after_ts - 60)}" if after_ts > 0 else ""
        q = []

        # Subject-based queries (paling spesifik)
        for subj in A1D_OTP_SUBJECTS:
            q.append((f"subject:{subj}", f"subject:{subj} is:unread{ts_filter}"))

        # Mask email queries
        if mask_email:
            q.append((f"from:{mask_email}", f"from:{mask_email} is:unread{ts_filter}"))

        # mozmail.com forwarded queries
        q.append(("from:mozmail.com subject:Confirm",
                   f"from:mozmail.com subject:Confirm is:unread{ts_filter}"))
        q.append(("from:mozmail.com subject:code",
                   f"from:mozmail.com subject:code is:unread{ts_filter}"))
        q.append(("from:mozmail.com subject:verify",
                   f"from:mozmail.com subject:verify is:unread{ts_filter}"))

        # Sender-based queries
        if sender:
            q.append((f"from:{sender}", f"from:{sender} is:unread{ts_filter}"))

        # Fallback tanpa is:unread
        if mask_email:
            q.append((f"from:{mask_email} (any)", f"from:{mask_email}{ts_filter}"))

        return q

    # ── _search_messages (identik) ──────────────────────────────────────────
    def _search_messages(self, query: str, max_results: int = 5) -> list:
        try:
            result = self._svc().users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            return [m["id"] for m in result.get("messages", [])]
        except Exception as e:
            self._log(f"⚠️  Search gagal [{query[:60]}]: {e}")
            return []

    # ── _decode_body (identik) ──────────────────────────────────────────────
    def _decode_body(self, payload) -> str:
        body_text = ""
        if "parts" in payload:
            for part in payload["parts"]:
                body_text += self._decode_body(part)
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                decoded = base64.urlsafe_b64decode(
                    data + "=="
                ).decode("utf-8", errors="ignore")
                if "html" in payload.get("mimeType", ""):
                    soup = BeautifulSoup(decoded, "lxml")
                    body_text += soup.get_text(separator=" ")
                else:
                    body_text += decoded
        return body_text

    # ── _extract_otp_code (identik) ─────────────────────────────────────────
    def _extract_otp_code(self, msg_id: str) -> Optional[str]:
        try:
            msg  = self._svc().users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
            body = self._decode_body(msg["payload"])
        except Exception:
            return None
        for pattern in [
            r'Your\s+(?:verification\s+)?code\s+is[:\s]+([0-9]{4,8})',
            r'OTP[:\s]+([0-9]{4,8})',
            r'code[:\s]+([0-9]{4,8})',
            r'\b([0-9]{6})\b', r'\b([0-9]{4})\b', r'\b([0-9]{8})\b',
        ]:
            m = re.search(pattern, body, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    # ── _extract_verification_link (identik) ──────────────────────────────
    def _extract_verification_link(self, msg_id: str) -> Optional[str]:
        try:
            msg  = self._svc().users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
            body = self._decode_body(msg["payload"])
        except Exception:
            return None
        for pattern in [
            r'https?://[^\s"\' <>]+(?:verify|confirm|activate|token|magic)[^\s"\' <>]*',
            r'https?://a1d\.ai/[^\s"\' <>]+',
        ]:
            urls = re.findall(pattern, body, re.IGNORECASE)
            if urls:
                return urls[0].replace("&amp;", "&").strip()
        return None

    # ── mark_as_read (identik) ───────────────────────────────────────────────
    def mark_as_read(self, msg_id: str):
        try:
            self._svc().users().messages().modify(
                userId="me", id=msg_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except Exception as e:
            self._log(f"⚠️  mark_as_read gagal: {e}")

    # ── wait_for_otp (identik dengan GmailWatcher.wait_for_otp) ───────────────
    def wait_for_otp(
        self,
        sender:          str                = "a1d.ai",
        timeout:         int                = 180,
        interval:        int                = 5,
        log_callback:    Optional[Callable] = None,
        mask_email:      str                = None,
        after_timestamp: int                = 0,
    ) -> str:
        """
        Poll Gmail sampai OTP ditemukan.
        Logika identik dengan GmailWatcher.wait_for_otp() dari a1d-auto-upscaler.

        Args:
            sender:          Hint sender (e.g. 'a1d.ai')
            timeout:         Batas waktu tunggu (detik)
            interval:        Jeda antar polling (detik)
            log_callback:    Fungsi (msg, level) untuk kirim log ke UI
            mask_email:      Email mask Firefox Relay aktif — filter by To
            after_timestamp: Unix timestamp registrasi — abaikan email sebelumnya

        Returns:
            String OTP (6 digit)

        Raises:
            TimeoutError  jika OTP tidak diterima dalam timeout
        """
        self._log_cb = log_callback

        # Inisialisasi Gmail service
        self._svc()

        queries = self._build_queries(
            sender     = sender,
            mask_email = mask_email,
            after_ts   = after_timestamp,
        )

        ts_human = (
            datetime.datetime.fromtimestamp(after_timestamp).strftime("%H:%M:%S")
            if after_timestamp > 0 else "N/A"
        )

        self._log(
            f"Memulai polling Gmail (timeout: {timeout}s, interval: {interval}s)"
        )
        self._log(
            f"📬 Polling Gmail — {len(queries)} strategi "
            f"| hanya email setelah {ts_human}:"
        )
        for i, (label, _q) in enumerate(queries, 1):
            self._log(f"   [{i}] {label}")
        self._log("Menunggu email OTP dari a1d.ai...")

        start     = time.time()
        seen_ids: set = set()

        while time.time() - start < timeout:
            found_id = matched_label = None

            for label, q in queries:
                ids = self._search_messages(q)
                new = [i for i in ids if i not in seen_ids]
                if new:
                    for candidate_id in new:
                        seen_ids.add(candidate_id)

                        # Filter timestamp: skip email lama
                        if after_timestamp > 0:
                            msg_ts = self._get_message_timestamp(candidate_id)
                            if msg_ts > 0 and msg_ts < (after_timestamp - 60):
                                self._log(
                                    f"   ⏩ Email lama ("
                                    f"{datetime.datetime.fromtimestamp(msg_ts).strftime('%H:%M:%S')}"
                                    f" < cutoff {ts_human}) — skip"
                                )
                                continue

                        self._log(f"📩 Kandidat [{label}] — validasi...")
                        if self._is_otp_email(candidate_id):
                            found_id      = candidate_id
                            matched_label = label
                            break
                        else:
                            self._log("   ⏩ Bukan email OTP, skip")

                    if found_id:
                        break

            if found_id:
                self._log(f"✅ Email OTP valid — strategi: [{matched_label}]")

                otp = self._extract_otp_code(found_id)
                if otp:
                    self.mark_as_read(found_id)
                    self._log(f"✅ OTP diekstrak: {otp}")
                    return otp

                link = self._extract_verification_link(found_id)
                if link:
                    self.mark_as_read(found_id)
                    self._log("✅ Link verifikasi ditemukan (magic link)")
                    # Untuk saat ini raise — background_process perlu handle link
                    raise ValueError(f"MAGIC_LINK:{link}")

                self._log("⚠️  OTP/link tidak terbaca, lanjut poll...")

            elapsed = int(time.time() - start)
            self._log(f"⏳ Polling... {elapsed}s/{timeout}s")
            time.sleep(interval)

        raise TimeoutError(
            f"❌ Timeout {timeout}s — OTP tidak diterima.\n"
            f"Pastikan Firefox Relay meneruskan email ke Gmail Anda."
        )
