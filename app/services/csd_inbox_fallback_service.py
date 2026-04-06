from __future__ import annotations

import email
import imaplib
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from email.header import decode_header
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class CSDInboxFallbackResult:
    status: str
    downloaded: bool
    source: str
    file_path: Optional[str]
    matched_subject: Optional[str]
    matched_from: Optional[str]
    matched_date: Optional[str]
    attachment_name: Optional[str]
    searched_terms: List[str]
    message: str

    def to_dict(self) -> Dict:
        return asdict(self)


class CSDInboxFallbackService:
    """
    Inbox fallback service for retrieving a monthly CSD report attachment
    when browser-based login/download fails.

    Expected behavior:
    - Connect to IMAP inbox
    - Search recent emails
    - Match monthly CSD report naming patterns like:
        "new CSD report 04"
        "new CSD report 05"
        ...
    - Save the best matching attachment to:
        monthly_csd_reports/YYYY-MM/csd_report_<month>.pdf
    """

    DEFAULT_SAVE_ROOT = "monthly_csd_reports"

    @staticmethod
    def _safe_str(value: object, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip()

    @classmethod
    def _env(cls, name: str, default: Optional[str] = None, required: bool = False) -> str:
        value = os.getenv(name, default)
        value = "" if value is None else str(value).strip()
        if required and not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value

    @staticmethod
    def _decode_mime_words(value: Optional[str]) -> str:
        if not value:
            return ""
        decoded_parts = decode_header(value)
        final = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    final.append(part.decode(encoding or "utf-8", errors="ignore"))
                except Exception:
                    final.append(part.decode("utf-8", errors="ignore"))
            else:
                final.append(part)
        return "".join(final).strip()

    @staticmethod
    def _extract_email_address(from_header: str) -> str:
        if not from_header:
            return ""
        match = re.search(r"<([^>]+)>", from_header)
        if match:
            return match.group(1).strip().lower()
        return from_header.strip().lower()

    @staticmethod
    def _month_token(month: Optional[int] = None) -> str:
        m = month if isinstance(month, int) and 1 <= month <= 12 else datetime.now().month
        return f"{m:02d}"

    @classmethod
    def _build_search_terms(cls, month: Optional[int] = None) -> List[str]:
        mm = cls._month_token(month)
        month_names = {
            "01": "january",
            "02": "february",
            "03": "march",
            "04": "april",
            "05": "may",
            "06": "june",
            "07": "july",
            "08": "august",
            "09": "september",
            "10": "october",
            "11": "november",
            "12": "december",
        }
        month_name = month_names.get(mm, "")

        return [
            f"new csd report {mm}",
            f"csd report {mm}",
            f"new csd report {month_name}",
            f"csd report {month_name}",
            f"monthly csd report {mm}",
            "new csd report",
            "csd report",
            "supplier database report",
        ]

    @staticmethod
    def _score_text(text: str, search_terms: List[str], month_token: str) -> int:
        score = 0
        text_l = (text or "").lower()

        for term in search_terms:
            if term.lower() in text_l:
                score += 15

        if f"new csd report {month_token}" in text_l:
            score += 40
        if f"csd report {month_token}" in text_l:
            score += 30
        if "csd" in text_l:
            score += 10
        if "report" in text_l:
            score += 10
        if month_token in text_l:
            score += 8

        return score

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        filename = re.sub(r"[^\w\-. ]+", "_", filename).strip()
        filename = re.sub(r"\s+", "_", filename)
        return filename or "attachment.bin"

    @staticmethod
    def _is_candidate_attachment(filename: str, content_type: str) -> bool:
        filename_l = (filename or "").lower()
        content_type_l = (content_type or "").lower()

        allowed_exts = (
            ".pdf",
            ".xlsx",
            ".xls",
            ".csv",
            ".docx",
            ".doc",
            ".zip",
        )
        if filename_l.endswith(allowed_exts):
            return True

        if "pdf" in content_type_l:
            return True
        if "spreadsheet" in content_type_l:
            return True
        if "excel" in content_type_l:
            return True

        return False

    @classmethod
    def _connect_imap(cls) -> imaplib.IMAP4_SSL:
        server = cls._env("IMAP_HOST", required=True)
        port = int(cls._env("IMAP_PORT", "993"))
        username = cls._env("IMAP_USERNAME", required=True)
        password = cls._env("IMAP_PASSWORD", required=True)

        client = imaplib.IMAP4_SSL(server, port)
        client.login(username, password)
        return client

    @classmethod
    def _search_recent_message_ids(cls, client: imaplib.IMAP4_SSL, max_scan: int = 100) -> List[bytes]:
        client.select("INBOX")
        status, data = client.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []

        all_ids = data[0].split()
        return all_ids[-max_scan:]

    @classmethod
    def _fetch_message(cls, client: imaplib.IMAP4_SSL, msg_id: bytes):
        status, data = client.fetch(msg_id, "(RFC822)")
        if status != "OK" or not data:
            return None
        raw_email = data[0][1]
        return email.message_from_bytes(raw_email)

    @classmethod
    def _choose_best_message_and_attachment(
        cls,
        client: imaplib.IMAP4_SSL,
        month: Optional[int] = None,
        max_scan: int = 100,
        allowed_sender_domains: Optional[List[str]] = None,
    ) -> Tuple[Optional[object], Optional[object], int]:
        search_terms = cls._build_search_terms(month)
        month_token = cls._month_token(month)
        best_message = None
        best_attachment_part = None
        best_score = -1

        message_ids = cls._search_recent_message_ids(client, max_scan=max_scan)

        for msg_id in reversed(message_ids):
            msg = cls._fetch_message(client, msg_id)
            if not msg:
                continue

            subject = cls._decode_mime_words(msg.get("Subject", ""))
            from_header = cls._decode_mime_words(msg.get("From", ""))
            sender_email = cls._extract_email_address(from_header)
            date_header = cls._decode_mime_words(msg.get("Date", ""))

            domain_bonus = 0
            if allowed_sender_domains:
                sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
                if sender_domain in [d.lower().strip() for d in allowed_sender_domains]:
                    domain_bonus = 25

            base_score = (
                cls._score_text(subject, search_terms, month_token)
                + cls._score_text(from_header, search_terms, month_token)
                + cls._score_text(date_header, search_terms, month_token)
                + domain_bonus
            )

            if msg.is_multipart():
                for part in msg.walk():
                    disposition = (part.get("Content-Disposition") or "").lower()
                    content_type = part.get_content_type() or ""
                    filename = cls._decode_mime_words(part.get_filename() or "")

                    if "attachment" not in disposition and not filename:
                        continue

                    if not cls._is_candidate_attachment(filename, content_type):
                        continue

                    attachment_score = base_score
                    attachment_score += cls._score_text(filename, search_terms, month_token)

                    if filename.lower().endswith(".pdf"):
                        attachment_score += 10

                    if attachment_score > best_score:
                        best_score = attachment_score
                        best_message = msg
                        best_attachment_part = part
            else:
                # non-multipart emails are ignored unless they carry a direct attachment, which is uncommon
                continue

        return best_message, best_attachment_part, best_score

    @classmethod
    def _save_attachment(
        cls,
        attachment_part,
        month: Optional[int] = None,
        save_root: Optional[str] = None,
    ) -> str:
        now = datetime.now()
        month_dir = f"{now.year}-{cls._month_token(month)}"
        root = Path(save_root or cls.DEFAULT_SAVE_ROOT)
        destination_dir = root / month_dir
        destination_dir.mkdir(parents=True, exist_ok=True)

        original_name = cls._decode_mime_words(attachment_part.get_filename() or "")
        original_name = cls._sanitize_filename(original_name or f"csd_report_{cls._month_token(month)}.pdf")

        payload = attachment_part.get_payload(decode=True)
        if not payload:
            raise RuntimeError("Attachment payload is empty.")

        suffix = Path(original_name).suffix or ".pdf"
        final_name = f"csd_report_{cls._month_token(month)}{suffix}"
        output_path = destination_dir / final_name

        with open(output_path, "wb") as f:
            f.write(payload)

        return str(output_path)

    @classmethod
    def fetch_latest_monthly_csd_report_from_inbox(
        cls,
        month: Optional[int] = None,
        max_scan: int = 100,
        allowed_sender_domains: Optional[List[str]] = None,
        save_root: Optional[str] = None,
    ) -> Dict:
        search_terms = cls._build_search_terms(month)

        try:
            client = cls._connect_imap()
        except Exception as exc:
            return CSDInboxFallbackResult(
                status="failed",
                downloaded=False,
                source="inbox_fallback",
                file_path=None,
                matched_subject=None,
                matched_from=None,
                matched_date=None,
                attachment_name=None,
                searched_terms=search_terms,
                message=f"IMAP connection failed: {exc}",
            ).to_dict()

        try:
            msg, attachment_part, score = cls._choose_best_message_and_attachment(
                client=client,
                month=month,
                max_scan=max_scan,
                allowed_sender_domains=allowed_sender_domains,
            )

            if not msg or not attachment_part or score < 0:
                return CSDInboxFallbackResult(
                    status="not_found",
                    downloaded=False,
                    source="inbox_fallback",
                    file_path=None,
                    matched_subject=None,
                    matched_from=None,
                    matched_date=None,
                    attachment_name=None,
                    searched_terms=search_terms,
                    message="No suitable CSD report email attachment found in inbox.",
                ).to_dict()

            saved_path = cls._save_attachment(
                attachment_part=attachment_part,
                month=month,
                save_root=save_root,
            )

            subject = cls._decode_mime_words(msg.get("Subject", ""))
            from_header = cls._decode_mime_words(msg.get("From", ""))
            date_header = cls._decode_mime_words(msg.get("Date", ""))
            attachment_name = cls._decode_mime_words(attachment_part.get_filename() or "")

            return CSDInboxFallbackResult(
                status="success",
                downloaded=True,
                source="inbox_fallback",
                file_path=saved_path,
                matched_subject=subject,
                matched_from=from_header,
                matched_date=date_header,
                attachment_name=attachment_name,
                searched_terms=search_terms,
                message="CSD report attachment downloaded from inbox fallback successfully.",
            ).to_dict()

        except Exception as exc:
            return CSDInboxFallbackResult(
                status="failed",
                downloaded=False,
                source="inbox_fallback",
                file_path=None,
                matched_subject=None,
                matched_from=None,
                matched_date=None,
                attachment_name=None,
                searched_terms=search_terms,
                message=f"Inbox fallback failed: {exc}",
            ).to_dict()

        finally:
            try:
                client.logout()
            except Exception:
                pass
