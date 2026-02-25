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

# ─── Daftar query yang dicoba berurutan ────────────────────────────────────────
# Firefox Relay mem-forward email dengan menjaga original sender,
# tapi kadang header bisa berubah. Kita coba semua kemungkinan.
_SEARCH_QUERIES = [
    "from:a1d.ai is:unread",
    "from:noreply@a1d.ai is:unread",
    "from:no-reply@a1d.ai is:unread",
    "from:support@a1d.ai is:unread",
    # Kalau sender berubah karena relay, cari dari subject/keyword
    "subject:verify is:unread",
    "subject:verification is:unread",
    "subject:OTP is:unread",
    "subject:code is:unread",
    "subject:a1d is:unread",
    # Paling broad: semua unread terbaru yang ada angka 6 digit
    "is:unread newer_than:10m",
]

# Window waktu pencarian (menit) - lebih lebar dari sebelumnya
_NEWER_THAN = "15m"


class GmailOTPReader:
    """
    Baca OTP dari Gmail secara otomatis menggunakan Gmail API.
    Butuh file credentials.json dari Google Cloud Console.

    Fitur:
    - Multi-query fallback (tidak hanya from:a1d.ai)
    - Window pencarian lebih lebar (15 menit)
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
                    creds = None  # Force re-auth jika refresh gagal

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
    ) -> str:
        """
        Poll Gmail sampai OTP ditemukan.

        Args:
            sender:       Hint sender (dipakai di query pertama)
            timeout:      Batas waktu tunggu (detik)
            interval:     Jeda antar polling (detik)
            log_callback: Fungsi (msg, level) untuk kirim log ke UI

        Returns:
            String OTP 6 digit

        Raises:
            TimeoutError jika OTP tidak diterima dalam `timeout` detik
        """
        def _log(msg: str, level: str = "INFO"):
            if log_callback:
                log_callback(msg, level)

        svc   = self._svc()
        start = time.time()
        attempt = 0

        _log(f"Memulai polling Gmail (timeout: {timeout}s, interval: {interval}s)", "INFO")
        _log("Menunggu email OTP dari a1d.ai...", "INFO")

        # Bangun daftar query: prioritaskan berdasarkan sender hint
        queries = [
            f"from:{sender} is:unread",
            f"from:noreply@{sender} is:unread",
            f"from:no-reply@{sender} is:unread",
        ]
        # Tambahkan sisa query fallback (hindari duplikat)
        for q in _SEARCH_QUERIES:
            if q not in queries:
                queries.append(q)

        while time.time() - start < timeout:
            if attempt > 0 and attempt % 5 == 0:  # Log setiap 5 attempt
                elapsed  = int(time.time() - start)
                remaining = timeout - elapsed
                _log(f"Menunggu OTP... ({elapsed}s berlalu, sisa {remaining}s)", "INFO")

            attempt += 1

            # Coba setiap query
            for query in queries:
                # Tambahkan filter waktu ke query
                full_query = f"{query} newer_than:{_NEWER_THAN}"
                try:
                    otp = self._search_and_extract(svc, full_query, log_callback)
                    if otp:
                        _log(f"OTP ditemukan via query: [{query}]", "SUCCESS")
                        return otp
                except Exception as e:
                    _log(f"Query error [{query}]: {e}", "WARNING")
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
    def _search_and_extract(
        self,
        svc,
        query: str,
        log_callback: Optional[Callable] = None,
    ) -> str:
        """Jalankan satu query Gmail dan cari OTP di hasilnya."""
        results = svc.users().messages().list(
            userId="me",
            q=query,
            maxResults=10
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return ""

        for ref in messages:
            msg  = svc.users().messages().get(
                userId="me",
                id=ref["id"],
                format="full"
            ).execute()

            # Ekstrak semua teks (recursive)
            body = self._extract_body_recursive(msg.get("payload", {}))
            # Juga cek subject
            subject = self._get_header(msg, "Subject")

            if log_callback:
                log_callback(f"Memeriksa email: \"{subject[:60]}...\"", "INFO")

            otp = self._extract_otp(body + " " + subject)
            if otp:
                # Tandai sebagai sudah dibaca
                try:
                    svc.users().messages().modify(
                        userId="me",
                        id=ref["id"],
                        body={"removeLabelIds": ["UNREAD"]}
                    ).execute()
                except Exception:
                    pass
                return otp

        return ""

    def _extract_body_recursive(self, payload: dict) -> str:
        """Rekursif ekstrak semua teks dari semua MIME part."""
        text = ""

        # Cek body di level ini
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            try:
                decoded = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="ignore")
                text += decoded + " "
            except Exception:
                pass

        # Rekursif ke sub-parts
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
        # Pattern 1: Langsung setelah kata kunci
        priority_patterns = [
            r"(?:code|kode|OTP|pin|token|verification|verify)[\s:=]+([0-9]{6})\b",
            r"\b([0-9]{6})\b(?:[\s\S]{0,30}(?:valid|expire|berlaku|minutes|menit))",
            r"(?:your|kamu|kode)[\s\S]{0,20}\b([0-9]{6})\b",
        ]
        for p in priority_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1)

        # Pattern 2: 6 digit yang berdiri sendiri (tidak bagian dari angka lebih panjang)
        # Hindari tahun (1900-2099) dan nomor telepon
        matches = re.findall(r"(?<![0-9])([0-9]{6})(?![0-9])", text)
        for candidate in matches:
            # Filter: bukan tahun
            if 1900 <= int(candidate) <= 2099:
                continue
            # Filter: bukan angka dengan banyak pengulangan (111111, 000000)
            if len(set(candidate)) <= 1:
                continue
            return candidate

        return ""
