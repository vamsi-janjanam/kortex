import base64

from app.config import settings

from pipelines.ingestion.base import BaseConnector, RawChunk

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailConnector(BaseConnector):
    """Ingest Gmail messages matched by a Gmail search query.

    ``source`` is a Gmail search query string, e.g. ``"newer_than:30d"`` or
    ``"from:foo@bar.com label:inbox"``.
    """

    def _credentials(self):
        token_path = settings.gmail_token_path
        creds_path = settings.gmail_credentials_path

        if token_path:
            from google.auth.exceptions import GoogleAuthError
            from google.oauth2.credentials import Credentials

            try:
                creds = Credentials.from_authorized_user_file(token_path, _SCOPES)
            except (FileNotFoundError, ValueError, GoogleAuthError):
                creds = None
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request

                creds.refresh(Request())
                return creds

        if creds_path:
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_secrets_file(creds_path, _SCOPES)
            return flow.run_local_server(port=0)

        raise ValueError(
            "Gmail is not configured: set gmail_token_path (stored token JSON) "
            "or gmail_credentials_path (OAuth client-secrets file)."
        )

    def _service(self):
        from googleapiclient.discovery import build

        return build("gmail", "v1", credentials=self._credentials())

    @staticmethod
    def _header(headers: list[dict], name: str) -> str:
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value", "")
        return ""

    @staticmethod
    def _decode_body(payload: dict) -> str:
        """Walk MIME parts and return the first decoded text/plain body."""

        def _walk(part: dict) -> str:
            mime = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")
            if mime == "text/plain" and data:
                return base64.urlsafe_b64decode(data.encode("utf-8")).decode(
                    "utf-8", errors="replace"
                )
            for sub in part.get("parts", []) or []:
                text = _walk(sub)
                if text:
                    return text
            return ""

        return _walk(payload)

    def ingest(self, source: str) -> list[RawChunk]:
        service = self._service()
        messages = []
        page_token = None
        while True:
            resp = (
                service.users()
                .messages()
                .list(userId="me", q=source, pageToken=page_token)
                .execute()
            )
            messages.extend(resp.get("messages", []) or [])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        results: list[RawChunk] = []
        for msg in messages:
            msg_id = msg.get("id")
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            payload = detail.get("payload", {}) or {}
            headers = payload.get("headers", []) or []
            subject = self._header(headers, "Subject")
            sender = self._header(headers, "From")
            date_header = self._header(headers, "Date")

            body = self._decode_body(payload) or detail.get("snippet", "") or ""
            if not body.strip():
                continue

            metadata = {
                "source": source,
                "message_id": msg_id,
                "thread_id": detail.get("threadId"),
                "sender": sender,
                "subject": subject,
                "date": date_header,
            }
            for chunk in self._split_text(body):
                if chunk.strip():
                    results.append(RawChunk(text=chunk, metadata=dict(metadata)))

        return results
