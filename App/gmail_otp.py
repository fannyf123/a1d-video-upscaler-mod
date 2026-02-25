import base64
import os
import pickle
import re
import time
from typing import Callable, Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.modify"]

# ─── Subject yang DIABAIKAN (bukan email OTP) ──────────────────────────────────
# FIX: Welcome email, newsletter, dll tidak boleh dibaca sebagai OTP
_IGNORE_SUBJECTS = [
    "welcome",
    "let's get started",
    "lets get started",
    "get started",
    "newsletter",
    "subscription",
    "announcement",
    "thank you for joining",
    "account created",
    "free trial",
    "upgrade",
    "invite",
    "tips",
]

# ─── Subject yang WAJIB ADA di email OTP ──────────────────────────────────────
_OTP_SUBJECTS = [
    "confirm",
    "verify",
    "verification",
    "code",
    "otp",
    "sign in",
    "one-time",
    "a1d.ai signup",
]


class GmailOTPReader:
    """
    Baca OTP dari Gmail secara otomatis menggunakan Gmail API.
    Butuh file credentials.json dari Google Cloud Console.

    Fitur:
    - Filter by mask_email: hanya baca email yang dikirim ke mask tertentu
    - Filter by after_timestamp: abaikan email sebelum registrasi dikirim
    - Ignore subjects: skip Welcome, newsletter, dll
    - Multi-query fallback
    - Live countdown callback ke UI
    - Recursive MIME body extraction
    - Auto-mark as read setelah OTP ditemukan
    """

    def __init__(self, base_dir: str):
        self.base_dir   = base_dir
        self.token_path = os.path.join(base_dir, "token.pickle")
        self.creds_path = os.path.join(base_dir, "credentials.json")
        self._service   = None

    # ── Auth ──────────────────────────────────────────────────────────────────
    def _auth(self):
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds or not creds.valid:
                if not os.path.exists(self.creds_path):
                    raise FileNotFoundError(
                        "credentials.json tidak ditemukan!\n"
                        "Download dari Google Cloud Console (Gmail API -> OAuth 2.0)\n"
                        "dan letakkan di folder yang sama dengan main.py."
                    )
                flow  = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)

            with open(self.token_path, "wb") as f:
                pickle.dump(creds, f)

        self._service = build("gmail", "v1", credentials=creds)

    def _svc(self):
        if not self._service:
            self._auth()
        return self._service

    # ── Main: wait_for_otp ────────────────────────────────────────────────────
    def wait_for_otp(
        self,
        sender: str = "a1d.ai",
        timeout: int = 180,
        interval: int = 5,
        log_callback: Optional[Callable[[str, str], None]] = None,
        mask_email: Optional[str] = None,
        after_timestamp: int = 0,
    ) -> str:
        """
        Poll Gmail sampai OTP ditemukan.

        Args:
            sender:          Hint sender (dipakai di query)
            timeout:         Batas waktu tunggu (detik)
            interval:        Jeda antar polling (detik)
            log_callback:    Fungsi (msg, level) untuk kirim log ke UI
            mask_email:      Email mask Firefox Relay — HANYA baca email ke mask ini
            after_timestamp: Unix timestamp registrasi — abaikan email sebelum waktu ini

        Returns:
            String OTP 6 digit

        Raises:
            TimeoutError jika OTP tidak diterima dalam `timeout` detik
        """
        def _log(msg: str, level: str = "INFO"):
            if log_callback:
                log_callback(msg, level)

        svc     = self._svc()
        start   = time.time()
        attempt = 0

        # Cutoff: hanya terima email yang datang SETELAH registrasi
        # Beri toleransi -30 detik untuk clock skew
        cutoff_ts = max(0, after_timestamp - 30) if after_timestamp > 0 else 0

        _log(f"Memulai polling Gmail (timeout: {timeout}s, interval: {interval}s)", "INFO")
        if mask_email:
            _log(f"Filter mask: [{mask_email}]", "INFO")
        if cutoff_ts > 0:
            import datetime
            _log(f"Hanya email setelah: {datetime.datetime.fromtimestamp(cutoff_ts).strftime('%H:%M:%S')}", "INFO")
        _log("Menunggu email OTP dari a1d.ai...", "INFO")

        # ── Bangun daftar query (prioritas: mask_email dulu) ──────────────────
        queries = []

        # PRIORITAS 1: Filter by mask_email (paling spesifik)
        if mask_email:
            queries.append(f"to:{mask_email} is:unread")
            queries.append(f"to:{mask_email}")  # fallback tanpa is:unread

        # PRIORITAS 2: Filter by sender
        queries.append(f"from:{sender} is:unread subject:confirm")
        queries.append(f"from:{sender} is:unread subject:verify")
        queries.append(f"from:{sender} is:unread subject:code")
        queries.append(f"from:{sender} is:unread")
        queries.append(f"from:noreply@{sender} is:unread")
        queries.append(f"from:no-reply@{sender} is:unread")

        # PRIORITAS 3: Subject-based fallback
        queries.append("subject:\"Confirm Your A1D\" is:unread")
        queries.append("subject:\"verification code\" is:unread")
        queries.append("subject:\"Your code\" is:unread")

        seen_ids: set = set()

        while time.time() - start < timeout:
            if attempt > 0 and attempt % 5 == 0:
                elapsed   = int(time.time() - start)
                remaining = timeout - elapsed
                _log(f"Menunggu OTP... ({elapsed}s berlalu, sisa {remaining}s)", "INFO")

            attempt += 1

            for query in queries:
                try:
                    otp = self._search_and_extract(
                        svc, query, cutoff_ts, seen_ids, log_callback
                    )
                    if otp:
                        _log(f"OTP ditemukan via query: [{query}]", "SUCCESS")
                        return otp
                except Exception as e:
                    _log(f"Query error [{query[:50]}]: {e}", "WARNING")
                    continue

            time.sleep(interval)

        elapsed = int(time.time() - start)
        raise TimeoutError(
            f"OTP tidak diterima dalam {elapsed} detik.\n"
            f"Pastikan:\n"
            f"  1. Firefox Relay meneruskan email ke Gmail Anda\n"
            f"  2. credentials.json sudah benar\n"
            f"  3. Gmail API aktif di Google Cloud Console"
        )

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _get_message_timestamp(self, msg: dict) -> int:
        """Ambil timestamp email (Unix seconds) dari internalDate."""
        try:
            return int(msg.get("internalDate", 0)) // 1000
        except Exception:
            return 0

    def _is_ignore_subject(self, subject: str) -> bool:
        """
        FIX: Cek apakah subject email harus diabaikan.
        Welcome email, newsletter, dll tidak boleh dibaca sebagai OTP.
        """
        subj_lower = subject.lower()
        for ignore in _IGNORE_SUBJECTS:
            if ignore in subj_lower:
                return True
        return False

    def _is_otp_subject(self, subject: str) -> bool:
        """
        Cek apakah subject email kemungkinan berisi OTP.
        Tidak wajib — hanya untuk prioritas.
        """
        subj_lower = subject.lower()
        for keyword in _OTP_SUBJECTS:
            if keyword in subj_lower:
                return True
        return False

    def _search_and_extract(
        self,
        svc,
        query: str,
        cutoff_ts: int,
        seen_ids: set,
        log_callback: Optional[Callable] = None,
    ) -> str:
        """Jalankan satu query Gmail dan cari OTP di hasilnya."""
        def _log(msg: str, level: str = "INFO"):
            if log_callback:
                log_callback(msg, level)

        # Selalu tambahkan newer_than agar tidak scan email lama
        newer_val = "15m" if cutoff_ts <= 0 else "30m"
        full_query = f"{query} newer_than:{newer_val}"

        results = svc.users().messages().list(
            userId="me",
            q=full_query,
            maxResults=10
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return ""

        for ref in messages:
            msg_id = ref["id"]

            # Skip jika sudah pernah diperiksa di iterasi sebelumnya
            if msg_id in seen_ids:
                continue

            msg = svc.users().messages().get(
                userId="me",
                id=msg_id,
                format="full"
            ).execute()

            # ── FIX 1: Filter by timestamp ────────────────────────────────────
            if cutoff_ts > 0:
                msg_ts = self._get_message_timestamp(msg)
                if msg_ts > 0 and msg_ts < cutoff_ts:
                    import datetime
                    _log(
                        f"Skip email lama ("
                        f"{datetime.datetime.fromtimestamp(msg_ts).strftime('%H:%M:%S')}"
                        f" < cutoff {datetime.datetime.fromtimestamp(cutoff_ts).strftime('%H:%M:%S')}"
                        f") — bukan email sesi ini",
                        "INFO"
                    )
                    seen_ids.add(msg_id)
                    continue

            subject = self._get_header(msg, "Subject")
            _log(f"Memeriksa email: \"{subject[:60]}...\"", "INFO")

            # ── FIX 2: Abaikan Welcome / Newsletter email ─────────────────────
            if self._is_ignore_subject(subject):
                _log(f"Skip email diabaikan (subject: '{subject[:40]}')", "INFO")
                seen_ids.add(msg_id)
                continue

            # Tandai sebagai seen agar tidak diperiksa ulang
            seen_ids.add(msg_id)

            # Ekstrak semua teks (recursive)
            body = self._extract_body_recursive(msg.get("payload", {}))
            otp  = self._extract_otp(body + " " + subject)

            if otp:
                _log(f"OTP diekstrak dari subject: '{subject[:40]}'", "SUCCESS")
                # Tandai sebagai sudah dibaca
                try:
                    svc.users().messages().modify(
                        userId="me",
                        id=msg_id,
                        body={"removeLabelIds": ["UNREAD"]}
                    ).execute()
                except Exception:
                    pass
                return otp
            else:
                _log(f"Email tidak mengandung OTP valid, skip", "INFO")

        return ""

    def _extract_body_recursive(self, payload: dict) -> str:
        """Rekursif ekstrak semua teks dari semua MIME part."""
        text = ""

        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            try:
                decoded = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="ignore")
                text += decoded + " "
            except Exception:
                pass

        for part in payload.get("parts", []):
            mime = part.get("mimeType", "")
            if mime.startswith("text/") or mime.startswith("multipart/"):
                text += self._extract_body_recursive(part)

        return text

    def _get_header(self, msg: dict, name: str) -> str:
        """Ambil nilai header dari pesan Gmail."""
        headers = msg.get("payload", {}).get("headers", [])
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value", "")
        return ""

    def _extract_otp(self, text: str) -> str:
        """
        Ekstrak kode OTP 6 digit dari teks.
        Prioritaskan kode yang dekat dengan kata kunci OTP.
        """
        # Pattern 1: Langsung setelah kata kunci OTP
        priority_patterns = [
            r"(?:code|kode|OTP|pin|token|verification|verify)[\s:=]+([0-9]{6})\b",
            r"\b([0-9]{6})\b(?:[\s\S]{0,30}(?:valid|expire|berlaku|minutes|menit))",
            r"(?:your|kamu|kode)[\s\S]{0,20}\b([0-9]{6})\b",
        ]
        for p in priority_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1)

        # Pattern 2: 6 digit yang berdiri sendiri
        matches = re.findall(r"(?<![0-9])([0-9]{6})(?![0-9])", text)
        for candidate in matches:
            # Filter: bukan tahun (1900-2099)
            if 1900 <= int(candidate) <= 2099:
                continue
            # Filter: bukan angka monoton (111111, 000000)
            if len(set(candidate)) <= 1:
                continue
            return candidate

        return ""
