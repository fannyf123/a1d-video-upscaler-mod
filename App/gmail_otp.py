import base64
import os
import pickle
import re
import time

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailOTPReader:
    """
    Baca OTP dari Gmail secara otomatis menggunakan Gmail API.
    Butuh file credentials.json dari Google Cloud Console.
    """

    def __init__(self, base_dir: str):
        self.base_dir   = base_dir
        self.token_path = os.path.join(base_dir, "token.pickle")
        self.creds_path = os.path.join(base_dir, "credentials.json")
        self._service   = None

    def _auth(self):
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.creds_path):
                    raise FileNotFoundError(
                        "credentials.json tidak ditemukan!\n"
                        "Download dari Google Cloud Console dan letakkan di folder app."
                    )
                flow  = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "wb") as f:
                pickle.dump(creds, f)
        self._service = build("gmail", "v1", credentials=creds)

    def _svc(self):
        if not self._service:
            self._auth()
        return self._service

    def wait_for_otp(
        self,
        sender: str = "a1d.ai",
        timeout: int = 120,
        interval: int = 4
    ) -> str:
        """Tunggu email OTP masuk dan kembalikan kode 6 digit."""
        svc   = self._svc()
        start = time.time()
        while time.time() - start < timeout:
            try:
                results = svc.users().messages().list(
                    userId="me",
                    q=f"from:{sender} is:unread newer_than:3m",
                    maxResults=5
                ).execute()
                for ref in results.get("messages", []):
                    msg  = svc.users().messages().get(
                        userId="me", id=ref["id"], format="full"
                    ).execute()
                    body = self._body(msg)
                    otp  = self._extract_otp(body)
                    if otp:
                        # Tandai sudah dibaca
                        svc.users().messages().modify(
                            userId="me", id=ref["id"],
                            body={"removeLabelIds": ["UNREAD"]}
                        ).execute()
                        return otp
            except Exception:
                pass
            time.sleep(interval)
        raise TimeoutError(f"OTP tidak diterima dalam {timeout} detik")

    def _body(self, msg: dict) -> str:
        payload = msg.get("payload", {})
        for part in payload.get("parts", []):
            if part.get("mimeType") in ("text/plain", "text/html"):
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore") if data else ""

    def _extract_otp(self, text: str) -> str:
        patterns = [
            r"\b([0-9]{6})\b",
            r"code[:\s]+([0-9]{6})",
            r"OTP[:\s]+([0-9]{6})",
            r"verification[:\s]+([0-9]{6})",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""
