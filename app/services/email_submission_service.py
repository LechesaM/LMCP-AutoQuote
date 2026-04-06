from __future__ import annotations

import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class EmailSubmissionError(Exception):
    pass


class EmailSubmissionService:
    @staticmethod
    def _safe_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        try:
            text = str(value).strip()
            return text if text else default
        except Exception:
            return default

    @classmethod
    def _get_env(cls, name: str, default: Optional[str] = None, required: bool = False) -> str:
        value = os.getenv(name, default)
        if required and not value:
            raise EmailSubmissionError(f"Missing required environment variable: {name}")
        return value or ""

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._get_env("SMTP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _bool_env(cls, name: str, default: str = "false") -> bool:
        return cls._get_env(name, default).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _safe_list(cls, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, set):
            return list(value)
        return [value]

    @classmethod
    def _normalize_emails(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple, set)):
            parts = [cls._safe_str(v) for v in value if cls._safe_str(v)]
            return ", ".join(parts)
        return cls._safe_str(value)

    @classmethod
    def _normalize_email_list(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
        elif isinstance(value, (list, tuple, set)):
            parts = [cls._safe_str(v) for v in value]
        else:
            parts = [cls._safe_str(value)]

        cleaned: List[str] = []
        seen = set()
        for part in parts:
            if not cls._is_valid_email_like(part):
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(part)
        return cleaned

    @classmethod
    def _first_non_empty(cls, *values: Any) -> str:
        for value in values:
            text = cls._safe_str(value)
            if text:
                return text
        return ""

    @classmethod
    def _deep_get(cls, data: Dict[str, Any], keys: List[str]) -> Any:
        current: Any = data
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    @classmethod
    def _is_valid_email_like(cls, value: str) -> bool:
        text = cls._safe_str(value)
        if not text:
            return False
        return "@" in text and "." in text.split("@")[-1]

    @classmethod
    def _looks_like_unknown(cls, value: Any) -> bool:
        text = cls._safe_str(value).strip().lower()
        return text in {
            "",
            "unknown",
            "rfq-unknown",
            "unknown-rfq",
            "n/a",
            "na",
            "-",
            "none",
            "null",
        }

    @classmethod
    def _normalize_document_list_to_paths(cls, value: Any) -> List[str]:
        paths: List[str] = []
        for item in cls._safe_list(value):
            if isinstance(item, dict):
                path = cls._safe_str(item.get("path") or item.get("file_path") or item.get("filename"))
                if path:
                    paths.append(path)
            else:
                path = cls._safe_str(item)
                if path:
                    paths.append(path)
        return paths

    @classmethod
    def _resolve_submission_email(cls, payload: Dict[str, Any]) -> str:
        buyer = payload.get("buyer") if isinstance(payload.get("buyer"), dict) else {}
        submission_pack = payload.get("submission_pack") if isinstance(payload.get("submission_pack"), dict) else {}
        quote_pack = payload.get("quote_pack") if isinstance(payload.get("quote_pack"), dict) else {}
        rfq = payload.get("rfq") if isinstance(payload.get("rfq"), dict) else {}
        opportunity = payload.get("opportunity") if isinstance(payload.get("opportunity"), dict) else {}

        candidates = [
            payload.get("recipient_email"),
            payload.get("buyer_email"),
            payload.get("submission_email"),
            payload.get("to_email"),
            payload.get("email"),
            submission_pack.get("recipient_email"),
            submission_pack.get("buyer_email"),
            submission_pack.get("submission_email"),
            quote_pack.get("recipient_email"),
            quote_pack.get("buyer_email"),
            quote_pack.get("submission_email"),
            buyer.get("email"),
            rfq.get("recipient_email"),
            rfq.get("buyer_email"),
            rfq.get("submission_email"),
            opportunity.get("recipient_email"),
            opportunity.get("buyer_email"),
            opportunity.get("submission_email"),
            cls._deep_get(payload, ["email_submission", "recipient_email"]),
            cls._deep_get(payload, ["rfq", "recipient_email"]),
            cls._deep_get(payload, ["rfq", "buyer_email"]),
            cls._deep_get(payload, ["submission_pack", "recipient_email"]),
            cls._deep_get(payload, ["quote_pack", "recipient_email"]),
            os.getenv("LMCP_TEST_TO_EMAIL"),
        ]

        for candidate in candidates:
            text = cls._safe_str(candidate)
            if cls._is_valid_email_like(text):
                return text
        return ""

    @classmethod
    def _resolve_quote_number(cls, payload: Dict[str, Any]) -> str:
        submission_pack = payload.get("submission_pack") if isinstance(payload.get("submission_pack"), dict) else {}
        quote_pack = payload.get("quote_pack") if isinstance(payload.get("quote_pack"), dict) else {}
        rfq = payload.get("rfq") if isinstance(payload.get("rfq"), dict) else {}
        opportunity = payload.get("opportunity") if isinstance(payload.get("opportunity"), dict) else {}

        return cls._first_non_empty(
            payload.get("quote_number"),
            payload.get("lmcp_quote_number"),
            payload.get("quotation_number"),
            payload.get("document_number"),
            submission_pack.get("quote_number"),
            quote_pack.get("quote_number"),
            rfq.get("quote_number"),
            opportunity.get("quote_number"),
        )

    @classmethod
    def _resolve_buyer_rfq_number(cls, payload: Dict[str, Any]) -> str:
        submission_pack = payload.get("submission_pack") if isinstance(payload.get("submission_pack"), dict) else {}
        quote_pack = payload.get("quote_pack") if isinstance(payload.get("quote_pack"), dict) else {}
        rfq = payload.get("rfq") if isinstance(payload.get("rfq"), dict) else {}
        opportunity = payload.get("opportunity") if isinstance(payload.get("opportunity"), dict) else {}
        buyer_schedule = payload.get("buyer_pricing_schedule") if isinstance(payload.get("buyer_pricing_schedule"), dict) else {}
        mapped_schedule = payload.get("pricing_schedule_mapped") if isinstance(payload.get("pricing_schedule_mapped"), dict) else {}

        candidates = [
            payload.get("buyer_rfq_number"),
            payload.get("rfq_number"),
            payload.get("reference_number"),
            payload.get("document_number"),
            payload.get("tender_number"),
            payload.get("bid_number"),
            payload.get("notice_number"),
            submission_pack.get("buyer_rfq_number"),
            submission_pack.get("rfq_number"),
            submission_pack.get("reference_number"),
            submission_pack.get("document_number"),
            quote_pack.get("buyer_rfq_number"),
            quote_pack.get("rfq_number"),
            quote_pack.get("reference_number"),
            quote_pack.get("document_number"),
            rfq.get("buyer_rfq_number"),
            rfq.get("rfq_number"),
            rfq.get("reference_number"),
            rfq.get("document_number"),
            rfq.get("tender_number"),
            opportunity.get("buyer_rfq_number"),
            opportunity.get("rfq_number"),
            opportunity.get("reference_number"),
            opportunity.get("notice_number"),
            buyer_schedule.get("rfq_number"),
            buyer_schedule.get("reference_number"),
            mapped_schedule.get("rfq_number"),
            mapped_schedule.get("reference_number"),
            cls._deep_get(payload, ["submission_pack", "buyer_rfq_number"]),
            cls._deep_get(payload, ["submission_pack", "document_number"]),
            cls._deep_get(payload, ["rfq", "buyer_rfq_number"]),
            cls._deep_get(payload, ["rfq", "rfq_number"]),
            cls._deep_get(payload, ["opportunity", "reference_number"]),
        ]

        for candidate in candidates:
            text = cls._safe_str(candidate)
            if text and not cls._looks_like_unknown(text):
                return text
        return ""

    @classmethod
    def _resolve_document_number(cls, payload: Dict[str, Any]) -> str:
        submission_pack = payload.get("submission_pack") if isinstance(payload.get("submission_pack"), dict) else {}
        quote_pack = payload.get("quote_pack") if isinstance(payload.get("quote_pack"), dict) else {}

        return cls._first_non_empty(
            payload.get("document_number"),
            submission_pack.get("document_number"),
            quote_pack.get("document_number"),
            cls._resolve_buyer_rfq_number(payload),
        )

    @classmethod
    def _resolve_subject(cls, payload: Dict[str, Any]) -> str:
        buyer_rfq_number = cls._resolve_buyer_rfq_number(payload)
        quote_number = cls._resolve_quote_number(payload)

        title = cls._first_non_empty(
            payload.get("quote_subject"),
            payload.get("subject"),
            payload.get("title"),
            payload.get("description"),
            "Quotation Submission",
        )

        if buyer_rfq_number and quote_number:
            return f"Quotation Submission: RFQ {buyer_rfq_number} | Quote {quote_number}"
        if buyer_rfq_number:
            return f"Quotation Submission: RFQ {buyer_rfq_number}"
        if quote_number:
            return f"Quotation Submission: Quote {quote_number}"
        return title

    @classmethod
    def _resolve_body(cls, payload: Dict[str, Any]) -> str:
        company_name = cls._first_non_empty(
            payload.get("company_name"),
            cls._deep_get(payload, ["seller", "name"]),
            cls._deep_get(payload, ["company", "name"]),
            cls._deep_get(payload, ["company_profile", "company_name"]),
            "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        )

        buyer_name = cls._first_non_empty(
            cls._deep_get(payload, ["buyer", "name"]),
            payload.get("buyer_name"),
            "Sir/Madam",
        )

        buyer_rfq_number = cls._resolve_buyer_rfq_number(payload)
        quote_number = cls._resolve_quote_number(payload)
        document_number = cls._resolve_document_number(payload)

        subject_title = cls._first_non_empty(
            payload.get("quote_subject"),
            payload.get("title"),
            payload.get("description"),
            "the requested supply and delivery",
        )

        custom_body = cls._safe_str(payload.get("submission_email_body"))
        if custom_body:
            return custom_body

        lines = [
            f"Dear {buyer_name},",
            "",
            "Please find attached our formal quotation and supporting submission documents for your consideration.",
            "",
        ]

        if buyer_rfq_number:
            lines.append(f"Buyer RFQ Number: {buyer_rfq_number}")
        if quote_number:
            lines.append(f"LMCP Quote Number: {quote_number}")
        if document_number:
            lines.append(f"Document Number: {document_number}")
        if subject_title:
            lines.append(f"Subject: {subject_title}")

        lines.extend(
            [
                "",
                "This quote is valid for 30 days from the date issued.",
                "For any queries pertaining to the quote please contact us at 0826338492 or lechesam@me.com.",
                "",
                "We trust that our submission will meet your requirements.",
                "",
                "Kind regards,",
                company_name,
            ]
        )

        return "\n".join(lines).strip()

    @classmethod
    def _dedupe_paths(cls, paths: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen = set()

        for item in paths:
            path_str = cls._safe_str(item)
            if not path_str:
                continue

            path = Path(path_str)
            if not path.exists() or not path.is_file():
                continue

            resolved = str(path.resolve())
            if resolved in seen:
                continue

            seen.add(resolved)
            cleaned.append(resolved)

        return cleaned

    @classmethod
    def _is_pdf_path(cls, path: str) -> bool:
        return Path(path).suffix.lower() == ".pdf"

    @classmethod
    def _resolve_attachment_paths(cls, payload: Dict[str, Any]) -> List[str]:
        attachment_candidates: List[Any] = []

        submission_pack = payload.get("submission_pack")
        if not isinstance(submission_pack, dict):
            submission_pack = {}

        quote_pack = payload.get("quote_pack")
        if not isinstance(quote_pack, dict):
            quote_pack = {}

        for key in [
            "submission_attachments",
            "attachment_paths",
            "supporting_documents",
            "stored_files",
        ]:
            value = payload.get(key)
            if value:
                if key == "supporting_documents":
                    attachment_candidates.extend(cls._normalize_document_list_to_paths(value))
                else:
                    attachment_candidates.extend(cls._safe_list(value))

        for key in [
            "pdf_path",
            "quote_pdf_path",
            "quote_pack_pdf",
            "final_pdf_path",
            "quote_pack_metadata_path",
        ]:
            value = payload.get(key)
            if value:
                attachment_candidates.append(value)

        for key in [
            "pdf_path",
            "final_pdf_path",
            "quote_pack_metadata_path",
            "submission_attachments",
            "supporting_documents",
        ]:
            value = submission_pack.get(key)
            if value:
                if key == "supporting_documents":
                    attachment_candidates.extend(cls._normalize_document_list_to_paths(value))
                else:
                    attachment_candidates.extend(cls._safe_list(value))

        for key in [
            "pdf_path",
            "final_pdf_path",
            "quote_pack_metadata_path",
            "submission_attachments",
            "supporting_documents",
        ]:
            value = quote_pack.get(key)
            if value:
                if key == "supporting_documents":
                    attachment_candidates.extend(cls._normalize_document_list_to_paths(value))
                else:
                    attachment_candidates.extend(cls._safe_list(value))

        raw_cleaned: List[str] = []
        for item in attachment_candidates:
            if isinstance(item, dict):
                path_value = item.get("path") or item.get("file_path") or item.get("filename")
                if path_value:
                    raw_cleaned.append(cls._safe_str(path_value))
            else:
                raw_cleaned.append(cls._safe_str(item))

        cleaned = cls._dedupe_paths(raw_cleaned)

        pdf_candidates: List[str] = [p for p in cleaned if cls._is_pdf_path(p)]
        non_pdf_candidates: List[str] = [p for p in cleaned if not cls._is_pdf_path(p)]

        preferred_pdf = cls._first_non_empty(
            payload.get("final_pdf_path"),
            payload.get("pdf_path"),
            payload.get("quote_pdf_path"),
            payload.get("quote_pack_pdf"),
            submission_pack.get("final_pdf_path"),
            submission_pack.get("pdf_path"),
            quote_pack.get("final_pdf_path"),
            quote_pack.get("pdf_path"),
        )

        if preferred_pdf:
            preferred_pdf = cls._safe_str(preferred_pdf)
            if preferred_pdf and Path(preferred_pdf).exists() and Path(preferred_pdf).is_file():
                resolved_preferred = str(Path(preferred_pdf).resolve())
                pdf_candidates = [resolved_preferred] + [p for p in pdf_candidates if p != resolved_preferred]

        ordered = cls._dedupe_paths(pdf_candidates + non_pdf_candidates)
        return ordered

    @classmethod
    def _resolve_primary_pdf_path(cls, payload: Dict[str, Any], attachments: List[str]) -> str:
        explicit = cls._first_non_empty(
            payload.get("final_pdf_path"),
            payload.get("pdf_path"),
            payload.get("quote_pdf_path"),
            payload.get("quote_pack_pdf"),
            cls._deep_get(payload, ["submission_pack", "final_pdf_path"]),
            cls._deep_get(payload, ["submission_pack", "pdf_path"]),
            cls._deep_get(payload, ["quote_pack", "final_pdf_path"]),
            cls._deep_get(payload, ["quote_pack", "pdf_path"]),
        )
        if explicit:
            path = Path(explicit)
            if path.exists() and path.is_file() and cls._is_pdf_path(str(path)):
                return str(path.resolve())

        for attachment in attachments:
            if cls._is_pdf_path(attachment):
                return attachment

        return ""

    @classmethod
    def _build_message(
        cls,
        *,
        to_email: str,
        subject: str,
        body: str,
        attachment_paths: Optional[Iterable[str]] = None,
        cc_email: Optional[str] = None,
        bcc_email: Optional[str] = None,
    ) -> EmailMessage:
        from_email = cls._get_env("SMTP_FROM") or cls._get_env("SMTP_USERNAME", required=True)

        msg = EmailMessage()
        msg["From"] = from_email
        msg["To"] = cls._normalize_emails(to_email)
        if cc_email:
            msg["Cc"] = cls._normalize_emails(cc_email)
        msg["Subject"] = subject
        msg.set_content(body)

        for attachment_path in attachment_paths or []:
            path = Path(attachment_path)
            if not path.exists() or not path.is_file():
                continue

            mime_type, _ = mimetypes.guess_type(str(path))
            if mime_type:
                maintype, subtype = mime_type.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"

            with open(path, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=path.name,
                )

        return msg

    @classmethod
    def send_email(
        cls,
        *,
        to_email: str,
        subject: str,
        body: str,
        attachment_paths: Optional[Iterable[str]] = None,
        cc_email: Optional[str] = None,
        bcc_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not cls.is_enabled():
            return {
                "success": False,
                "submitted": False,
                "status": "failed",
                "error": "SMTP is disabled.",
            }

        smtp_host = cls._get_env("SMTP_HOST", required=True)
        smtp_port = int(cls._get_env("SMTP_PORT", "587"))
        smtp_username = cls._get_env("SMTP_USERNAME", required=True)
        smtp_password = cls._get_env("SMTP_PASSWORD", required=True)
        use_tls = cls._bool_env("SMTP_USE_TLS", "true")

        if not cls._safe_str(to_email):
            return {
                "success": False,
                "submitted": False,
                "status": "failed",
                "error": "No buyer submission email found.",
            }

        try:
            normalized_to = cls._normalize_email_list(to_email)
            normalized_cc = cls._normalize_email_list(cc_email)
            normalized_bcc = cls._normalize_email_list(bcc_email)

            all_recipients = normalized_to + normalized_cc + normalized_bcc
            if not all_recipients:
                return {
                    "success": False,
                    "submitted": False,
                    "status": "failed",
                    "error": "No valid recipients found.",
                    "to_email": to_email,
                    "subject": subject,
                    "attachments": list(attachment_paths or []),
                }

            msg = cls._build_message(
                to_email=", ".join(normalized_to),
                subject=subject,
                body=body,
                attachment_paths=attachment_paths,
                cc_email=", ".join(normalized_cc) if normalized_cc else None,
                bcc_email=None,
            )

            with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(msg, to_addrs=all_recipients)

            return {
                "success": True,
                "submitted": True,
                "status": "submitted",
                "error": None,
                "to_email": ", ".join(normalized_to),
                "cc_email": ", ".join(normalized_cc),
                "bcc_email": ", ".join(normalized_bcc),
                "subject": subject,
                "attachments": list(attachment_paths or []),
            }

        except Exception as exc:
            return {
                "success": False,
                "submitted": False,
                "status": "failed",
                "error": str(exc),
                "to_email": to_email,
                "subject": subject,
                "attachments": list(attachment_paths or []),
            }

    @classmethod
    def submit_quote_email(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = payload or {}

        submission_pack = payload.get("submission_pack") if isinstance(payload.get("submission_pack"), dict) else {}
        quote_pack = payload.get("quote_pack") if isinstance(payload.get("quote_pack"), dict) else {}

        submission_method = cls._safe_str(
            payload.get("submission_method")
            or payload.get("submission_channel")
            or submission_pack.get("submission_method")
            or quote_pack.get("submission_method")
            or "email"
        ).lower()

        if submission_method and submission_method not in {"email", "mail"}:
            return {
                "success": False,
                "submitted": False,
                "status": "failed",
                "error": f"Unsupported submission method: {submission_method}",
            }

        to_email = cls._resolve_submission_email(payload)
        if not to_email:
            return {
                "success": False,
                "submitted": False,
                "status": "failed",
                "error": "No buyer submission email found.",
            }

        buyer_rfq_number = cls._resolve_buyer_rfq_number(payload)
        quote_number = cls._resolve_quote_number(payload)
        document_number = cls._resolve_document_number(payload)
        subject = cls._resolve_subject(payload)
        body = cls._resolve_body(payload)
        attachment_paths = cls._resolve_attachment_paths(payload)
        primary_pdf_path = cls._resolve_primary_pdf_path(payload, attachment_paths)

        if not primary_pdf_path:
            return {
                "success": False,
                "submitted": False,
                "status": "failed",
                "error": "No quotation PDF found. Email submission blocked.",
                "to_email": to_email,
                "subject": subject,
                "attachments": attachment_paths,
                "buyer_rfq_number": buyer_rfq_number,
                "quote_number": quote_number,
                "document_number": document_number,
            }

        if primary_pdf_path not in attachment_paths:
            attachment_paths.insert(0, primary_pdf_path)
        else:
            attachment_paths = [primary_pdf_path] + [p for p in attachment_paths if p != primary_pdf_path]

        cc_email = cls._normalize_emails(
            payload.get("cc_email")
            or cls._deep_get(payload, ["buyer", "cc_email"])
            or cls._deep_get(payload, ["submission_pack", "cc_email"])
        )
        bcc_email = cls._normalize_emails(
            payload.get("bcc_email")
            or cls._deep_get(payload, ["submission_pack", "bcc_email"])
        )

        send_result = cls.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            attachment_paths=attachment_paths,
            cc_email=cc_email or None,
            bcc_email=bcc_email or None,
        )

        return {
            **send_result,
            "submission_method": submission_method,
            "primary_pdf_path": primary_pdf_path,
            "pdf_attached": bool(primary_pdf_path),
            "attachment_count": len(attachment_paths),
            "cc_email": cc_email or "",
            "bcc_email": bcc_email or "",
            "buyer_rfq_number": buyer_rfq_number,
            "quote_number": quote_number,
            "document_number": document_number,
            "quote_folder": cls._first_non_empty(
                payload.get("quote_folder"),
                submission_pack.get("quote_folder"),
                quote_pack.get("quote_folder"),
            ),
            "quote_pack_dir": cls._first_non_empty(
                payload.get("quote_pack_dir"),
                submission_pack.get("quote_pack_dir"),
                quote_pack.get("quote_pack_dir"),
            ),
            "quote_pack_metadata_path": cls._first_non_empty(
                payload.get("quote_pack_metadata_path"),
                submission_pack.get("quote_pack_metadata_path"),
                quote_pack.get("quote_pack_metadata_path"),
            ),
        }


def send_submission_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    return EmailSubmissionService.submit_quote_email(payload)


def submit_quote_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    return EmailSubmissionService.submit_quote_email(payload)
