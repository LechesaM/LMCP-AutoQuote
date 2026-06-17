from __future__ import annotations

import imaplib
import email
import os
import re
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header
from email.message import Message
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class CSDRefreshError(Exception):
    pass


@dataclass
class CSDSearchCandidate:
    subject: str
    attachment_name: str
    attachment_path: str
    message_date: str
    message_from: str
    source: str = "inbox_fallback"


class CSDRefreshService:
    """
    CSD refresh service with inbox fallback.

    Flow:
    1. Try primary browser-based/manual-integrated refresh path.
    2. If that fails or is unavailable, search mailbox for:
       "new CSD report 04", "new CSD report 05", etc.
    3. Save attachment to runtime/csd_reports/YYYY-MM/
    """

    DEFAULT_BASE_DIR = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "csd_reports")

    @staticmethod
    def _env(name: str, default: Optional[str] = None, required: bool = False) -> str:
        value = os.getenv(name, default)
        if required and not value:
            raise CSDRefreshError(f"Missing required environment variable: {name}")
        return value or ""

    @staticmethod
    def _safe_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip() or default

    @staticmethod
    def _month_token(month: Optional[int] = None) -> str:
        if month is None:
            month = datetime.now().month
        return f"{int(month):02d}"

    @staticmethod
    def _month_folder(year: Optional[int] = None, month: Optional[int] = None) -> str:
        now = datetime.now()
        y = year or now.year
        m = month or now.month
        return f"{y}-{int(m):02d}"

    @staticmethod
    def _decode_mime_words(value: Optional[str]) -> str:
        if not value:
            return ""

        decoded_parts = decode_header(value)
        chunks: List[str] = []

        for part, enc in decoded_parts:
            if isinstance(part, bytes):
                try:
                    chunks.append(part.decode(enc or "utf-8", errors="ignore"))
                except Exception:
                    chunks.append(part.decode("utf-8", errors="ignore"))
            else:
                chunks.append(part)

        return "".join(chunks).strip()

    @classmethod
    def _sanitize_filename(cls, filename: str) -> str:
        cleaned = re.sub(r"[^\w\-. ]+", "_", cls._safe_str(filename, "csd_report"))
        cleaned = cleaned.replace(" ", "_")
        return cleaned[:240] if cleaned else "csd_report"

    @classmethod
    def _ensure_storage_dir(cls, year: Optional[int] = None, month: Optional[int] = None) -> Path:
        base_dir = cls._env("CSD_REPORT_STORAGE_DIR", cls.DEFAULT_BASE_DIR)
        folder = cls._month_folder(year=year, month=month)
        path = Path(base_dir) / folder
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def _build_subject_patterns(cls, month: Optional[int] = None) -> List[str]:
        token = cls._month_token(month)
        token_no_zero = str(int(token))
        month_name = datetime(2000, int(token), 1).strftime("%B").lower()
        month_short = datetime(2000, int(token), 1).strftime("%b").lower()

        return [
            f"new csd report {token}",
            f"new csd report {token_no_zero}",
            f"new csd report - {token}",
            f"new csd report - {token_no_zero}",
            f"new csd report_{token}",
            f"new csd report {month_name}",
            f"new csd report {month_short}",
            f"csd report {token}",
            f"csd report {month_name}",
        ]

    @classmethod
    def _subject_matches(cls, subject: str, month: Optional[int] = None) -> bool:
        normalized = cls._safe_str(subject).lower()
        patterns = cls._build_subject_patterns(month)
        return any(p in normalized for p in patterns)

    @classmethod
    def _attachment_allowed(cls, filename: str) -> bool:
        lower = cls._safe_str(filename).lower()
        allowed_extensions = (
            ".pdf",
            ".xlsx",
            ".xls",
            ".csv",
            ".zip",
            ".docx",
            ".xml",
        )
        return lower.endswith(allowed_extensions)

    @classmethod
    def _message_has_usable_attachment(cls, msg: Message) -> bool:
        for part in msg.walk():
            content_disposition = cls._safe_str(part.get("Content-Disposition")).lower()
            if "attachment" not in content_disposition:
                continue
            filename = cls._decode_mime_words(part.get_filename())
            if filename and cls._attachment_allowed(filename):
                return True
        return False

    @classmethod
    def _extract_first_usable_attachment(
        cls,
        msg: Message,
        save_dir: Path,
        message_date_token: str,
    ) -> Tuple[str, str]:
        for part in msg.walk():
            content_disposition = cls._safe_str(part.get("Content-Disposition")).lower()
            if "attachment" not in content_disposition:
                continue

            raw_filename = cls._decode_mime_words(part.get_filename())
            if not raw_filename or not cls._attachment_allowed(raw_filename):
                continue

            filename = cls._sanitize_filename(raw_filename)
            target_name = f"{message_date_token}__{filename}"
            target_path = save_dir / target_name

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            with open(target_path, "wb") as f:
                f.write(payload)

            return filename, str(target_path)

        raise CSDRefreshError("Matching email found, but no usable attachment was available.")

    @classmethod
    def _imap_connect(cls) -> imaplib.IMAP4_SSL:
        host = cls._env("CSD_EMAIL_IMAP_HOST", required=True)
        port = int(cls._env("CSD_EMAIL_IMAP_PORT", "993"))
        username = cls._env("CSD_EMAIL_USERNAME", required=True)
        password = cls._env("CSD_EMAIL_PASSWORD", required=True)

        ssl_context = ssl.create_default_context()
        client = imaplib.IMAP4_SSL(host, port, ssl_context=ssl_context)
        client.login(username, password)
        return client

    @classmethod
    def _search_message_ids(cls, client: imaplib.IMAP4_SSL) -> List[bytes]:
        mailbox = cls._env("CSD_EMAIL_IMAP_MAILBOX", "INBOX")
        status, _ = client.select(mailbox)
        if status != "OK":
            raise CSDRefreshError(f"Unable to open mailbox: {mailbox}")

        # Broad search first. We filter subjects safely in Python.
        status, data = client.search(None, "ALL")
        if status != "OK":
            raise CSDRefreshError("IMAP search failed.")

        if not data or not data[0]:
            return []

        return data[0].split()

    @classmethod
    def _fetch_message(cls, client: imaplib.IMAP4_SSL, msg_id: bytes) -> Message:
        status, data = client.fetch(msg_id, "(RFC822)")
        if status != "OK" or not data:
            raise CSDRefreshError(f"Failed to fetch email message: {msg_id!r}")

        raw_email = None
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2:
                raw_email = item[1]
                break

        if not raw_email:
            raise CSDRefreshError(f"No RFC822 payload returned for email message: {msg_id!r}")

        return email.message_from_bytes(raw_email)

    @classmethod
    def _collect_matching_candidates(
        cls,
        client: imaplib.IMAP4_SSL,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> List[Tuple[bytes, Message]]:
        ids = cls._search_message_ids(client)
        if not ids:
            return []

        matches: List[Tuple[bytes, Message]] = []

        for msg_id in reversed(ids):
            try:
                msg = cls._fetch_message(client, msg_id)
                subject = cls._decode_mime_words(msg.get("Subject"))
                if not cls._subject_matches(subject, month=month):
                    continue

                if not cls._message_has_usable_attachment(msg):
                    continue

                if year:
                    raw_date = cls._safe_str(msg.get("Date"))
                    parsed_year = cls._extract_year_from_date(raw_date)
                    if parsed_year and parsed_year != int(year):
                        continue

                matches.append((msg_id, msg))
            except Exception:
                continue

        return matches

    @staticmethod
    def _extract_year_from_date(value: str) -> Optional[int]:
        match = re.search(r"\b(20\d{2})\b", value)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
        return None

    @staticmethod
    def _compact_message_date(value: str) -> str:
        # Produce a filename-safe token.
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            return parsed.strftime("%Y%m%d_%H%M%S")
        except Exception:
            return datetime.now().strftime("%Y%m%d_%H%M%S")

    @classmethod
    def download_csd_report_from_inbox(
        cls,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        client = cls._imap_connect()
        try:
            matches = cls._collect_matching_candidates(client, month=month, year=year)
            if not matches:
                token = cls._month_token(month)
                raise CSDRefreshError(
                    f"No inbox email with usable attachment found for subject pattern like 'new CSD report {token}'."
                )

            _, msg = matches[0]

            subject = cls._decode_mime_words(msg.get("Subject"))
            sender = cls._decode_mime_words(msg.get("From"))
            msg_date = cls._safe_str(msg.get("Date"))
            date_token = cls._compact_message_date(msg_date)

            save_dir = cls._ensure_storage_dir(year=year, month=month)
            attachment_name, attachment_path = cls._extract_first_usable_attachment(
                msg=msg,
                save_dir=save_dir,
                message_date_token=date_token,
            )

            return {
                "status": "success",
                "method": "inbox_fallback",
                "subject": subject,
                "from": sender,
                "message_date": msg_date,
                "attachment_name": attachment_name,
                "attachment_path": attachment_path,
                "storage_dir": str(save_dir),
                "month": cls._month_token(month),
                "year": year or datetime.now().year,
                "report_found": True,
            }
        finally:
            try:
                client.close()
            except Exception:
                pass
            try:
                client.logout()
            except Exception:
                pass

    @classmethod
    def try_primary_refresh(
        cls,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Primary hook for future browser/login automation.

        For now:
        - If CSD_PRIMARY_REFRESH_ENABLED=false, this returns skipped.
        - If you later wire Safari/Playwright/other automation, place it here.
        """
        enabled = cls._env("CSD_PRIMARY_REFRESH_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }

        if not enabled:
            return {
                "status": "skipped",
                "method": "primary_refresh",
                "reason": "Primary CSD browser refresh is disabled or not configured.",
                "month": cls._month_token(month),
                "year": year or datetime.now().year,
            }

        # Placeholder for future browser automation hook.
        # Raise failure to trigger inbox fallback unless you replace this block.
        raise CSDRefreshError("Primary CSD browser refresh attempted but is not yet implemented.")

    @classmethod
    def refresh_csd_with_fallback(
        cls,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        primary_result: Optional[Dict[str, Any]] = None
        primary_error: Optional[str] = None

        try:
            primary_result = cls.try_primary_refresh(month=month, year=year)
            if primary_result.get("status") == "success":
                return {
                    "status": "success",
                    "used_fallback": False,
                    "primary_result": primary_result,
                    "final_result": primary_result,
                }
        except Exception as exc:
            primary_error = str(exc)

        fallback_result = cls.download_csd_report_from_inbox(month=month, year=year)

        return {
            "status": "success",
            "used_fallback": True,
            "primary_result": primary_result,
            "primary_error": primary_error,
            "final_result": fallback_result,
        }
