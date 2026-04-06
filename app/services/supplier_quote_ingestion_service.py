from __future__ import annotations

import email
import imaplib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.header import decode_header
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Optional imports
try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None

try:
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None


# ---------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------


@dataclass
class ExtractedLineItem:
    description: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    currency: str = "ZAR"
    source: str = "unknown"
    confidence: float = 0.0
    raw_line: Optional[str] = None


@dataclass
class SupplierQuoteExtractionResult:
    supplier_name: str
    pdf_path: str
    extraction_method: str
    quote_number: Optional[str] = None
    quote_date: Optional[str] = None
    vat_included: Optional[bool] = None
    subtotal: Optional[float] = None
    vat: Optional[float] = None
    total: Optional[float] = None
    items: List[ExtractedLineItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    raw_text_preview: Optional[str] = None


@dataclass
class ComparisonItem:
    normalized_description: str
    suppliers: Dict[str, Dict[str, Any]]
    cheapest_supplier: Optional[str] = None
    cheapest_unit_price: Optional[float] = None
    average_unit_price: Optional[float] = None
    quantity_reference: Optional[float] = None


# ---------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------


class SupplierQuoteIngestionService:
    """
    Supplier quote ingestion + PDF extraction service.

    Design goals:
    - Never block LMCP buyer quote generation if supplier quotes are missing
    - Match supplier replies by RFQ no / LMCP quote no / email / domain / filename
    - Save probable or unmatched replies for later review
    - Build quote comparison only when supplier PDFs are available
    - Prevent duplicate IMAP scans within the same pipeline/autonomous cycle
    """

    SUPPLIER_FILE_REGEX = re.compile(
        r"^supplier_quote_(\d+)(?:_([A-Za-z0-9_\-]+))?(?:__.*)?\.(pdf|doc|docx|xls|xlsx|csv)$",
        re.IGNORECASE,
    )

    MONEY_RE = re.compile(
        r"""
        (?:
            R\s*|
            ZAR\s*
        )?
        (?P<amount>
            (?:\d{1,3}(?:[ ,]\d{3})+|\d+)
            (?:[.,]\d{2})?
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    QUANTITY_TOKEN_RE = re.compile(
        r"""
        ^
        (?P<qty>\d+(?:[.,]\d+)?)
        \s*
        (?P<unit>each|ea|unit|units|pcs|pc|box|boxes|pack|packs|set|sets|roll|rolls|meter|metre|m|kg|g|l|ml|lot)?
        $
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    DATE_RE = re.compile(
        r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}|\d{2}\s+[A-Za-z]{3,9}\s+\d{4})\b"
    )

    QUOTE_NO_RE = re.compile(
        r"\b(?:quote\s*(?:no|number)?|quotation\s*(?:no|number)?|ref(?:erence)?|our\s*ref)\s*[:#]?\s*([A-Za-z0-9/\-_]+)\b",
        re.IGNORECASE,
    )

    SUBTOTAL_RE = re.compile(r"\bsub\s*total\b", re.IGNORECASE)
    VAT_RE = re.compile(r"\bvat\b", re.IGNORECASE)
    TOTAL_RE = re.compile(r"\bgrand\s*total\b|\btotal\s*incl(?:usive)?\b|\btotal\b", re.IGNORECASE)

    IGNORE_LINE_RE = re.compile(
        r"^\s*(page\s+\d+|tel:|fax:|email:|www\.|bank details|terms and conditions|delivery address|billing address)\b",
        re.IGNORECASE,
    )

    RFQ_REFERENCE_RE = re.compile(
        r"\b(?:RFQ|REQ|REQUEST|QUOTE|QUOTATION|TENDER|BID)[\s:_\-#/]*([A-Z0-9][A-Z0-9./\-_]{2,})\b",
        re.IGNORECASE,
    )

    LMCP_REFERENCE_RE = re.compile(
        r"\b(LMCP[-_/]?\d{8}[-_/]?\d{3,6})\b",
        re.IGNORECASE,
    )

    SIMPLE_TOKEN_RE = re.compile(r"[A-Z0-9][A-Z0-9./\-_]{2,}", re.IGNORECASE)

    COMPARISON_OUTPUT = "quote_comparison.json"
    DEFAULT_UNMATCHED_FOLDER = "supplier_quotes/unmatched_supplier_quotes"

    def ingest_once(self, payload: Optional[dict] = None) -> dict:
        logger.info("[INGEST] Starting supplier inbox ingestion")

        payload = payload or {}

        # -----------------------------------------------------------------
        # Hard guards to prevent repeated or unnecessary scans
        # -----------------------------------------------------------------

        if bool(payload.get("skip_supplier_ingestion")):
            logger.info("[INGEST] skip_supplier_ingestion=True -> skipping inbox scan")
            return self._final_result(
                success=True,
                processed=0,
                saved_attachments=0,
                folders_updated=[],
                matched_email_ids=[],
                saved_files=[],
                matched_emails=[],
                quote_folder=str(self._resolve_target_quote_folder(payload)),
                quote_comparison_json=None,
                probable_matches=[],
                unmatched_saved_files=[],
                blocking_quote_generation=False,
                should_continue_quote_generation=True,
                message="Supplier inbox ingestion skipped by payload flag",
                match_context_summary={},
                processed_quote_folder=False,
                skipped=True,
                skip_reason="skip_supplier_ingestion_flag",
            )

        if bool(payload.get("_supplier_ingestion_already_run")):
            logger.info("[INGEST] Duplicate ingestion call detected -> skipping repeat scan")
            return self._final_result(
                success=True,
                processed=0,
                saved_attachments=0,
                folders_updated=[],
                matched_email_ids=[],
                saved_files=[],
                matched_emails=[],
                quote_folder=str(self._resolve_target_quote_folder(payload)),
                quote_comparison_json=None,
                probable_matches=[],
                unmatched_saved_files=[],
                blocking_quote_generation=False,
                should_continue_quote_generation=True,
                message="Duplicate supplier ingestion call skipped",
                match_context_summary={},
                processed_quote_folder=False,
                skipped=True,
                skip_reason="duplicate_call_same_cycle",
            )

        payload["_supplier_ingestion_already_run"] = True

        imap_host = (
            os.getenv("IMAP_HOST")
            or os.getenv("EMAIL_IMAP_HOST")
            or "imap.mail.me.com"
        ).strip()

        imap_port = self._safe_int(
            os.getenv("IMAP_PORT")
            or os.getenv("EMAIL_IMAP_PORT")
            or "993",
            default=993,
        )

        email_username = (
            os.getenv("IMAP_USERNAME")
            or os.getenv("EMAIL_USERNAME")
            or os.getenv("EMAIL_ACCOUNT")
            or ""
        ).strip()

        email_password = (
            os.getenv("IMAP_PASSWORD")
            or os.getenv("EMAIL_PASSWORD")
            or ""
        ).strip()

        imap_mailbox = (
            os.getenv("IMAP_MAILBOX")
            or os.getenv("EMAIL_FOLDER")
            or "INBOX"
        ).strip()

        system_email = (
            os.getenv("SMTP_FROM")
            or os.getenv("SMTP_USERNAME")
            or os.getenv("EMAIL_USERNAME")
            or os.getenv("IMAP_USERNAME")
            or ""
        ).strip().lower()

        logger.info(
            "[INGEST] IMAP config resolved | host=%s | port=%s | username_present=%s | password_present=%s | mailbox=%s",
            imap_host,
            imap_port,
            bool(email_username),
            bool(email_password),
            imap_mailbox,
        )

        matching_context = self._build_matching_context(payload)
        logger.info(
            "[INGEST] Context | buyer_rfq=%s | quote_number=%s | expected_supplier_emails=%s | expected_supplier_domains=%s | expected_references=%s",
            matching_context["buyer_rfq_number"],
            matching_context["quote_number"],
            sorted(list(matching_context["expected_supplier_emails"])),
            sorted(list(matching_context["expected_supplier_domains"])),
            sorted(list(matching_context["expected_reference_tokens"])),
        )

        if (
            not matching_context["buyer_rfq_number"]
            and not matching_context["quote_number"]
            and not matching_context["has_expected_supplier_context"]
        ):
            logger.info("[INGEST] No identifiers or supplier context -> skipping inbox scan")
            return self._final_result(
                success=True,
                processed=0,
                saved_attachments=0,
                folders_updated=[],
                matched_email_ids=[],
                saved_files=[],
                matched_emails=[],
                quote_folder=str(self._resolve_target_quote_folder(payload)),
                quote_comparison_json=None,
                probable_matches=[],
                unmatched_saved_files=[],
                blocking_quote_generation=False,
                should_continue_quote_generation=True,
                message="No identifiers or supplier context available; inbox scan skipped",
                match_context_summary={
                    "buyer_rfq_number": matching_context["buyer_rfq_number"],
                    "quote_number": matching_context["quote_number"],
                    "expected_supplier_emails": sorted(list(matching_context["expected_supplier_emails"])),
                    "expected_supplier_domains": sorted(list(matching_context["expected_supplier_domains"])),
                    "expected_reference_tokens": sorted(list(matching_context["expected_reference_tokens"])),
                },
                processed_quote_folder=False,
                skipped=True,
                skip_reason="no_identifiers_or_supplier_context",
            )

        if not email_username or not email_password:
            logger.warning("[INGEST] Missing IMAP/EMAIL username or password")
            return self._final_result(
                success=False,
                processed=0,
                saved_attachments=0,
                folders_updated=[],
                matched_email_ids=[],
                saved_files=[],
                matched_emails=[],
                quote_folder=None,
                quote_comparison_json=None,
                probable_matches=[],
                unmatched_saved_files=[],
                blocking_quote_generation=False,
                should_continue_quote_generation=True,
                message="Missing IMAP/EMAIL username or password in .env",
                match_context_summary={
                    "buyer_rfq_number": matching_context["buyer_rfq_number"],
                    "quote_number": matching_context["quote_number"],
                    "expected_supplier_emails": sorted(list(matching_context["expected_supplier_emails"])),
                    "expected_supplier_domains": sorted(list(matching_context["expected_supplier_domains"])),
                    "expected_reference_tokens": sorted(list(matching_context["expected_reference_tokens"])),
                },
                processed_quote_folder=False,
                skipped=False,
                skip_reason=None,
            )

        saved_files: List[str] = []
        unmatched_saved_files: List[str] = []
        matched_email_ids: List[str] = []
        matched_emails: List[Dict[str, Any]] = []
        probable_matches: List[Dict[str, Any]] = []
        folders_updated: List[str] = []
        saved_attachments = 0
        processed = 0

        target_quote_folder = self._resolve_target_quote_folder(payload)
        unmatched_folder = Path(self.DEFAULT_UNMATCHED_FOLDER)
        unmatched_folder.mkdir(parents=True, exist_ok=True)
        target_quote_folder.mkdir(parents=True, exist_ok=True)

        mail: Optional[imaplib.IMAP4_SSL] = None
        try:
            logger.info(
                "[INGEST] Connecting to IMAP host=%s port=%s user=%s mailbox=%s",
                imap_host,
                imap_port,
                email_username,
                imap_mailbox,
            )

            mail = imaplib.IMAP4_SSL(imap_host, imap_port)
            mail.login(email_username, email_password)

            select_status, _ = mail.select(imap_mailbox)
            if select_status != "OK":
                logger.error("[INGEST] Failed to select mailbox: %s", imap_mailbox)
                return self._final_result(
                    success=False,
                    processed=0,
                    saved_attachments=0,
                    folders_updated=[],
                    matched_email_ids=[],
                    saved_files=[],
                    matched_emails=[],
                    quote_folder=str(target_quote_folder),
                    quote_comparison_json=None,
                    probable_matches=[],
                    unmatched_saved_files=[],
                    blocking_quote_generation=False,
                    should_continue_quote_generation=True,
                    message=f"Failed to select mailbox: {imap_mailbox}",
                    match_context_summary={
                        "buyer_rfq_number": matching_context["buyer_rfq_number"],
                        "quote_number": matching_context["quote_number"],
                        "expected_supplier_emails": sorted(list(matching_context["expected_supplier_emails"])),
                        "expected_supplier_domains": sorted(list(matching_context["expected_supplier_domains"])),
                        "expected_reference_tokens": sorted(list(matching_context["expected_reference_tokens"])),
                    },
                    processed_quote_folder=False,
                    skipped=False,
                    skip_reason=None,
                )

            search_mode = (os.getenv("SUPPLIER_INGESTION_IMAP_SEARCH_MODE", "UNSEEN") or "UNSEEN").strip().upper()
            if search_mode not in {"ALL", "UNSEEN"}:
                search_mode = "UNSEEN"

            search_criteria = "ALL" if search_mode == "ALL" else "UNSEEN"
            max_scan = self._safe_int(os.getenv("SUPPLIER_INGESTION_MAX_EMAILS", "10"), default=10)

            status, data = mail.search(None, search_criteria)

            if status != "OK":
                logger.warning("[INGEST] IMAP search failed | status=%s | criteria=%s", status, search_criteria)
                return self._final_result(
                    success=True,
                    processed=0,
                    saved_attachments=0,
                    folders_updated=[],
                    matched_email_ids=[],
                    saved_files=[],
                    matched_emails=[],
                    quote_folder=str(target_quote_folder),
                    quote_comparison_json=None,
                    probable_matches=[],
                    unmatched_saved_files=[],
                    blocking_quote_generation=False,
                    should_continue_quote_generation=True,
                    message="IMAP search returned non-OK status",
                    match_context_summary={
                        "buyer_rfq_number": matching_context["buyer_rfq_number"],
                        "quote_number": matching_context["quote_number"],
                        "expected_supplier_emails": sorted(list(matching_context["expected_supplier_emails"])),
                        "expected_supplier_domains": sorted(list(matching_context["expected_supplier_domains"])),
                        "expected_reference_tokens": sorted(list(matching_context["expected_reference_tokens"])),
                    },
                    processed_quote_folder=False,
                    skipped=False,
                    skip_reason=None,
                )

            raw_ids = data[0] if data and len(data) > 0 else b""

            if raw_ids is None:
                raw_ids = b""

            if isinstance(raw_ids, bytes):
                email_ids = raw_ids.split()[-max_scan:]
            elif isinstance(raw_ids, str):
                email_ids = raw_ids.encode().split()[-max_scan:]
            else:
                email_ids = []

            logger.info("[INGEST] Search completed | matched_email_count=%s", len(email_ids))
            logger.info("[INGEST] Raw email IDs: %s", email_ids)

            if not email_ids:
                return self._final_result(
                    success=True,
                    processed=0,
                    saved_attachments=0,
                    folders_updated=[],
                    matched_email_ids=[],
                    saved_files=[],
                    matched_emails=[],
                    quote_folder=str(target_quote_folder),
                    quote_comparison_json=None,
                    probable_matches=[],
                    unmatched_saved_files=[],
                    blocking_quote_generation=False,
                    should_continue_quote_generation=True,
                    message="No matching supplier emails found",
                    match_context_summary={
                        "buyer_rfq_number": matching_context["buyer_rfq_number"],
                        "quote_number": matching_context["quote_number"],
                        "expected_supplier_emails": sorted(list(matching_context["expected_supplier_emails"])),
                        "expected_supplier_domains": sorted(list(matching_context["expected_supplier_domains"])),
                        "expected_reference_tokens": sorted(list(matching_context["expected_reference_tokens"])),
                    },
                    processed_quote_folder=False,
                    skipped=False,
                    skip_reason=None,
                )

            logger.info("[INGEST] Total emails fetched: %s", len(email_ids))

            for num in email_ids:
                msg_id = num.decode("utf-8", errors="ignore").strip() if isinstance(num, bytes) else str(num).strip()
                if not msg_id:
                    continue

                logger.info("[INGEST] Processing email ID: %s", msg_id)

                raw_email = None
                fetch_attempts = [
                    "(RFC822)",
                    "(BODY.PEEK[])",
                    "(RFC822.PEEK)",
                ]

                for fetch_query in fetch_attempts:
                    try:
                        fetch_status, msg_data = mail.fetch(num, fetch_query)
                    except Exception as exc:
                        logger.warning(
                            "[INGEST] Fetch exception for email ID %s using %s: %s",
                            msg_id,
                            fetch_query,
                            exc,
                        )
                        continue

                    if fetch_status != "OK" or not msg_data:
                        logger.warning(
                            "[INGEST] Failed fetch for email ID %s using %s",
                            msg_id,
                            fetch_query,
                        )
                        continue

                    for response_part in msg_data:
                        if isinstance(response_part, tuple) and len(response_part) >= 2 and response_part[1]:
                            raw_email = response_part[1]
                            break

                    if raw_email:
                        logger.info(
                            "[INGEST] Raw email payload resolved for ID %s using %s",
                            msg_id,
                            fetch_query,
                        )
                        break

                if not raw_email:
                    logger.warning("[INGEST] No raw email payload for ID: %s", msg_id)
                    continue

                try:
                    msg = email.message_from_bytes(raw_email)
                except Exception as exc:
                    logger.warning("[INGEST] Failed to parse raw email payload for ID %s: %s", msg_id, exc)
                    continue

                sender = self._decode_text(msg.get("From"))
                subject = self._decode_text(msg.get("Subject"))
                body_text = self._extract_email_body_text(msg)

                sender_email = self._extract_email_address(sender)
                sender_domain = self._extract_domain_from_email(sender_email)

                logger.info("[INGEST] Email Subject: %s", subject)
                logger.info("[INGEST] Email From: %s", sender)

                if system_email and sender_email and sender_email.lower() == system_email:
                    logger.info("[INGEST] Skipping self/system email from: %s", sender)
                    continue

                processed += 1

                attachment_meta: List[Dict[str, str]] = []
                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue
                    filename = part.get_filename()
                    if not filename:
                        continue
                    decoded_filename = self._decode_text(filename)
                    content_type = str(part.get_content_type() or "")
                    attachment_meta.append(
                        {
                            "filename": decoded_filename,
                            "content_type": content_type,
                        }
                    )

                match_result = self._score_email_match(
                    sender_email=sender_email,
                    sender_domain=sender_domain,
                    subject=subject,
                    body_text=body_text,
                    matching_context=matching_context,
                    attachments=attachment_meta,
                )

                logger.info(
                    "[INGEST] Match result | email_id=%s | score=%s | matched=%s | probable=%s | reasons=%s",
                    msg_id,
                    match_result["score"],
                    match_result["matched"],
                    match_result["probable"],
                    match_result["reasons"],
                )

                email_saved_any = False
                email_saved_to_matched_folder = False
                attachment_count_for_email = 0
                saved_paths_for_email: List[str] = []
                matched_paths_for_email: List[str] = []
                unmatched_paths_for_email: List[str] = []

                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue

                    filename = part.get_filename()
                    if not filename:
                        continue

                    content_disposition = str(part.get("Content-Disposition") or "")
                    content_type = str(part.get_content_type() or "")
                    decoded_filename = self._decode_text(filename)
                    payload_bytes = part.get_payload(decode=True)

                    logger.info(
                        "[INGEST] Found attachment: %s | content_type=%s | disposition=%s",
                        decoded_filename,
                        content_type,
                        content_disposition,
                    )

                    if not payload_bytes:
                        logger.info("[INGEST] Attachment had no payload: %s", decoded_filename)
                        continue

                    looks_like_quote = self._looks_like_quote_attachment(decoded_filename, content_type)
                    destination_folder = unmatched_folder

                    if match_result["matched"] or (match_result["probable"] and looks_like_quote):
                        destination_folder = target_quote_folder

                    safe_name = self._build_saved_attachment_name(
                        decoded_filename=decoded_filename,
                        sender_email=sender_email,
                        sender_domain=sender_domain,
                        attachment_index=attachment_count_for_email + 1,
                        matched=(destination_folder == target_quote_folder),
                    )

                    file_path = self._unique_path(destination_folder / safe_name)
                    with open(file_path, "wb") as f:
                        f.write(payload_bytes)

                    email_saved_any = True
                    attachment_count_for_email += 1
                    saved_paths_for_email.append(str(file_path))

                    if destination_folder == target_quote_folder:
                        matched_paths_for_email.append(str(file_path))
                        saved_files.append(str(file_path))
                        saved_attachments += 1
                        email_saved_to_matched_folder = True
                        folders_updated.append(str(target_quote_folder))
                        logger.info("[INGEST] Saved matched/probable supplier attachment: %s", file_path)
                    else:
                        unmatched_paths_for_email.append(str(file_path))
                        unmatched_saved_files.append(str(file_path))
                        folders_updated.append(str(unmatched_folder))
                        logger.info("[INGEST] Saved unmatched supplier attachment: %s", file_path)

                if email_saved_any:
                    email_summary = {
                        "email_id": msg_id,
                        "from": sender,
                        "from_email": sender_email,
                        "from_domain": sender_domain,
                        "subject": subject,
                        "match_score": match_result["score"],
                        "match_reasons": match_result["reasons"],
                        "matched": match_result["matched"],
                        "probable": match_result["probable"],
                        "saved_paths": saved_paths_for_email,
                        "matched_paths": matched_paths_for_email,
                        "unmatched_paths": unmatched_paths_for_email,
                    }
                    matched_emails.append(email_summary)

                    if email_saved_to_matched_folder:
                        matched_email_ids.append(msg_id)

                    if match_result["probable"] and not match_result["matched"]:
                        probable_matches.append(email_summary)

                    if not email_saved_to_matched_folder and matching_context["has_expected_supplier_context"]:
                        logger.info(
                            "[INGEST] Email had attachments but was not confidently matched to target folder | email_id=%s",
                            msg_id,
                        )

            quote_comparison_json = None
            processed_quote_folder = False

            if saved_files:
                try:
                    process_result = self.process_quote_folder(target_quote_folder)
                    if isinstance(process_result, dict) and process_result.get("success"):
                        quote_comparison_json = process_result.get("comparison_path")
                        processed_quote_folder = True
                        logger.info("[INGEST] Quote folder processed successfully: %s", target_quote_folder)
                except Exception:
                    logger.exception("[INGEST] Failed to process quote folder: %s", target_quote_folder)

            result = self._final_result(
                success=True,
                processed=processed,
                saved_attachments=saved_attachments,
                folders_updated=sorted(list(set(folders_updated))),
                matched_email_ids=matched_email_ids,
                saved_files=saved_files,
                matched_emails=matched_emails,
                quote_folder=str(target_quote_folder),
                quote_comparison_json=quote_comparison_json,
                probable_matches=probable_matches,
                unmatched_saved_files=unmatched_saved_files,
                blocking_quote_generation=False,
                should_continue_quote_generation=True,
                message="Supplier inbox ingestion completed",
                match_context_summary={
                    "buyer_rfq_number": matching_context["buyer_rfq_number"],
                    "quote_number": matching_context["quote_number"],
                    "expected_supplier_emails": sorted(list(matching_context["expected_supplier_emails"])),
                    "expected_supplier_domains": sorted(list(matching_context["expected_supplier_domains"])),
                    "expected_reference_tokens": sorted(list(matching_context["expected_reference_tokens"])),
                },
                processed_quote_folder=processed_quote_folder,
                skipped=False,
                skip_reason=None,
            )

            logger.info(
                "[INGEST] Final result: processed=%s, saved_attachments=%s, matched_email_ids=%s, quote_folder=%s",
                processed,
                saved_attachments,
                matched_email_ids,
                target_quote_folder,
            )
            return result

        except Exception as exc:
            logger.exception("[INGEST] Supplier inbox ingestion failed.")
            return self._final_result(
                success=False,
                processed=processed,
                saved_attachments=saved_attachments,
                folders_updated=folders_updated,
                matched_email_ids=matched_email_ids,
                saved_files=saved_files,
                matched_emails=matched_emails,
                quote_folder=str(target_quote_folder),
                quote_comparison_json=None,
                probable_matches=probable_matches,
                unmatched_saved_files=unmatched_saved_files,
                blocking_quote_generation=False,
                should_continue_quote_generation=True,
                message=str(exc),
                match_context_summary={
                    "buyer_rfq_number": matching_context["buyer_rfq_number"],
                    "quote_number": matching_context["quote_number"],
                    "expected_supplier_emails": sorted(list(matching_context["expected_supplier_emails"])),
                    "expected_supplier_domains": sorted(list(matching_context["expected_supplier_domains"])),
                    "expected_reference_tokens": sorted(list(matching_context["expected_reference_tokens"])),
                },
                processed_quote_folder=False,
                skipped=False,
                skip_reason=None,
            )

        finally:
            if mail is not None:
                try:
                    mail.close()
                except Exception:
                    pass
                try:
                    mail.logout()
                except Exception:
                    pass

    # -----------------------------------------------------------------
    # Matching helpers
    # -----------------------------------------------------------------

    @classmethod
    def _build_matching_context(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        buyer_rfq_number = cls._first_non_empty(
            payload.get("buyer_rfq_number"),
            payload.get("rfq_number"),
            payload.get("buyer_reference"),
            cls._deep_get(payload, ["rfq", "buyer_rfq_number"]),
            cls._deep_get(payload, ["rfq", "rfq_number"]),
        )

        quote_number = cls._first_non_empty(
            payload.get("quote_number"),
            payload.get("document_number"),
            payload.get("lmcp_quote_number"),
            cls._deep_get(payload, ["rfq", "quote_number"]),
            cls._deep_get(payload, ["rfq", "document_number"]),
        )

        expected_supplier_emails: Set[str] = set()
        expected_supplier_domains: Set[str] = set()

        raw_candidates: List[Any] = []

        for key in [
            "supplier_requests",
            "supplier_request_emails",
            "requested_suppliers",
            "suppliers_contacted",
            "supplier_emails",
            "emails_sent",
            "sent_supplier_requests",
            "supplier_request_log",
            "sent_to_suppliers",
            "requested_supplier_emails",
            "recipient_email",
            "supplier_email",
            "contact_email",
        ]:
            value = payload.get(key)
            if value:
                raw_candidates.append(value)

        nested_candidates = [
            cls._deep_get(payload, ["supplier_ingestion_context", "supplier_requests"]),
            cls._deep_get(payload, ["supplier_ingestion_context", "supplier_emails"]),
            cls._deep_get(payload, ["email_submission", "supplier_requests"]),
            cls._deep_get(payload, ["supplier_quote_request", "supplier_requests"]),
            cls._deep_get(payload, ["rfq", "supplier_requests"]),
            cls._deep_get(payload, ["buyer", "supplier_requests"]),
            cls._deep_get(payload, ["buyer", "email"]),
            cls._deep_get(payload, ["buyer", "recipient_email"]),
        ]
        raw_candidates.extend([x for x in nested_candidates if x])

        flat_values = cls._flatten_mixed(raw_candidates)

        for item in flat_values:
            if isinstance(item, str):
                cls._collect_emails_and_domains_from_text(
                    item,
                    expected_supplier_emails=expected_supplier_emails,
                    expected_supplier_domains=expected_supplier_domains,
                )
            elif isinstance(item, dict):
                for k in [
                    "email",
                    "supplier_email",
                    "to",
                    "recipient",
                    "recipient_email",
                    "from_email",
                    "sender_email",
                    "website",
                    "url",
                    "domain",
                    "contact_email",
                ]:
                    v = item.get(k)
                    if isinstance(v, str) and v.strip():
                        cls._collect_emails_and_domains_from_text(
                            v,
                            expected_supplier_emails=expected_supplier_emails,
                            expected_supplier_domains=expected_supplier_domains,
                        )

        expected_reference_tokens: Set[str] = set()

        for value in [
            buyer_rfq_number,
            quote_number,
            payload.get("buyer_reference"),
            payload.get("reference_number"),
            payload.get("document_number"),
            payload.get("lmcp_quote_number"),
            cls._deep_get(payload, ["buyer", "rfq_number"]),
            cls._deep_get(payload, ["rfq", "buyer_rfq_number"]),
            cls._deep_get(payload, ["rfq", "quote_number"]),
        ]:
            expected_reference_tokens.update(cls._extract_reference_tokens(value))

        return {
            "buyer_rfq_number": str(buyer_rfq_number).strip() if buyer_rfq_number else None,
            "quote_number": str(quote_number).strip() if quote_number else None,
            "expected_supplier_emails": expected_supplier_emails,
            "expected_supplier_domains": expected_supplier_domains,
            "expected_reference_tokens": expected_reference_tokens,
            "has_expected_supplier_context": bool(
                expected_supplier_emails
                or expected_supplier_domains
                or expected_reference_tokens
                or buyer_rfq_number
                or quote_number
            ),
        }

    @classmethod
    def _score_email_match(
        cls,
        *,
        sender_email: Optional[str],
        sender_domain: Optional[str],
        subject: str,
        body_text: str,
        matching_context: Dict[str, Any],
        attachments: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        score = 0
        reasons: List[str] = []

        attachments = attachments or []
        attachment_names = [str(a.get("filename") or "").strip() for a in attachments if isinstance(a, dict)]
        attachment_content_types = [str(a.get("content_type") or "").strip().lower() for a in attachments if isinstance(a, dict)]

        combined_text = f"{subject or ''}\n{body_text or ''}\n{' '.join(attachment_names)}".lower()

        buyer_rfq_number = (matching_context.get("buyer_rfq_number") or "").strip()
        quote_number = (matching_context.get("quote_number") or "").strip()
        expected_supplier_emails = matching_context.get("expected_supplier_emails", set()) or set()
        expected_supplier_domains = matching_context.get("expected_supplier_domains", set()) or set()
        expected_reference_tokens = matching_context.get("expected_reference_tokens", set()) or set()

        email_reference_tokens: Set[str] = set()
        email_reference_tokens.update(cls._extract_reference_tokens(subject))
        email_reference_tokens.update(cls._extract_reference_tokens(body_text))
        for name in attachment_names:
            email_reference_tokens.update(cls._extract_reference_tokens(name))

        normalized_buyer_rfq = cls._normalize_identifier(buyer_rfq_number)
        normalized_quote_number = cls._normalize_identifier(quote_number)

        if normalized_buyer_rfq and normalized_buyer_rfq in email_reference_tokens:
            score += 8
            reasons.append("buyer_rfq_reference_match")

        if normalized_quote_number and normalized_quote_number in email_reference_tokens:
            score += 8
            reasons.append("quote_number_reference_match")

        overlapping_refs = expected_reference_tokens.intersection(email_reference_tokens)
        if overlapping_refs:
            score += 10
            reasons.append("reference_token_overlap")

        if sender_email and sender_email.lower() in expected_supplier_emails:
            score += 4
            reasons.append("exact_supplier_email_match")

        if sender_domain and sender_domain.lower() in expected_supplier_domains:
            score += 3
            reasons.append("supplier_domain_match")

        attachment_ref_overlap = False
        for name in attachment_names:
            attachment_tokens = cls._extract_reference_tokens(name)
            if attachment_tokens.intersection(expected_reference_tokens):
                attachment_ref_overlap = True
                break
        if attachment_ref_overlap:
            score += 6
            reasons.append("attachment_reference_match")

        quote_language_hits = 0
        for token in [
            "quote",
            "quotation",
            "pricing",
            "price",
            "attached",
            "attachment",
            "proforma",
            "invoice",
            "rfq",
            "response",
            "supplier",
        ]:
            if token in combined_text:
                quote_language_hits += 1

        if quote_language_hits >= 3:
            score += 3
            reasons.append("strong_quote_like_language")
        elif quote_language_hits >= 1:
            score += 1
            reasons.append("quote_like_language")

        has_pdf_attachment = any(name.lower().endswith(".pdf") for name in attachment_names)
        if has_pdf_attachment:
            score += 2
            reasons.append("pdf_attachment")

        if any(
            (
                "pdf" in ct
                or "spreadsheet" in ct
                or "excel" in ct
                or "officedocument" in ct
                or "word" in ct
            )
            for ct in attachment_content_types
        ):
            score += 1
            reasons.append("document_attachment_type")

        if (
            not overlapping_refs
            and sender_domain
            and sender_domain.lower() in expected_supplier_domains
            and has_pdf_attachment
            and quote_language_hits >= 1
        ):
            score += 4
            reasons.append("fallback_domain_pdf_quote_match")

        matched = score >= 8
        probable = 5 <= score < 8

        return {
            "score": score,
            "reasons": reasons,
            "matched": matched,
            "probable": probable,
        }

    @classmethod
    def _extract_reference_tokens(cls, value: Any) -> Set[str]:
        text = str(value or "").strip()
        if not text:
            return set()

        results: Set[str] = set()

        direct = cls._normalize_identifier(text)
        if direct:
            results.add(direct)

        for match in cls.RFQ_REFERENCE_RE.findall(text):
            normalized = cls._normalize_identifier(match)
            if normalized:
                results.add(normalized)

        for match in cls.LMCP_REFERENCE_RE.findall(text):
            normalized = cls._normalize_identifier(match)
            if normalized:
                results.add(normalized)

        for token in cls.SIMPLE_TOKEN_RE.findall(text):
            normalized = cls._normalize_identifier(token)
            if normalized:
                results.add(normalized)

        return {x for x in results if x and len(x) >= 3}

    @classmethod
    def _normalize_identifier(cls, value: Any) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        return re.sub(r"[^A-Z0-9]", "", text)

    @classmethod
    def _resolve_target_quote_folder(cls, payload: Dict[str, Any]) -> Path:
        supplied_folder = cls._first_non_empty(
            payload.get("supplier_quotes_folder"),
            payload.get("quote_folder"),
            payload.get("monthly_quote_folder"),
            cls._deep_get(payload, ["rfq", "supplier_quotes_folder"]),
        )
        if supplied_folder:
            return Path(str(supplied_folder))

        quote_number = cls._first_non_empty(
            payload.get("quote_number"),
            payload.get("document_number"),
            payload.get("lmcp_quote_number"),
        )
        buyer_rfq_number = cls._first_non_empty(
            payload.get("buyer_rfq_number"),
            payload.get("rfq_number"),
        )

        month_folder = datetime.utcnow().strftime("%Y-%m")
        folder_name = cls._build_folder_name(
            buyer_rfq_number=str(buyer_rfq_number).strip() if buyer_rfq_number else None,
            quote_number=str(quote_number).strip() if quote_number else None,
        )
        return Path("monthly_quotes") / month_folder / folder_name

    @classmethod
    def _build_folder_name(cls, buyer_rfq_number: Optional[str], quote_number: Optional[str]) -> str:
        buyer = cls._safe_filename_part(buyer_rfq_number or "UNKNOWN-RFQ")
        quote = cls._safe_filename_part(quote_number or "UNKNOWN-QUOTE")
        return f"{buyer}__{quote}"

    @classmethod
    def _looks_like_quote_attachment(cls, filename: str, content_type: str) -> bool:
        filename_lower = (filename or "").lower()
        content_type_lower = (content_type or "").lower()

        if filename_lower.endswith((".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc")):
            return True

        for token in ["pdf", "spreadsheet", "excel", "ms-excel", "officedocument", "word"]:
            if token in content_type_lower:
                return True

        return False

    @classmethod
    def _build_saved_attachment_name(
        cls,
        *,
        decoded_filename: str,
        sender_email: Optional[str],
        sender_domain: Optional[str],
        attachment_index: int,
        matched: bool,
    ) -> str:
        original_name = decoded_filename or f"attachment_{attachment_index}.bin"
        suffix = Path(original_name).suffix or ".bin"
        stem = Path(original_name).stem or f"attachment_{attachment_index}"

        source_tag = cls._safe_filename_part(
            sender_domain or sender_email or f"attachment_{attachment_index}"
        )

        if matched:
            base_name = f"supplier_quote_{attachment_index}_{source_tag}{suffix}"
        else:
            base_name = f"unmatched_supplier_quote_{attachment_index}_{source_tag}{suffix}"

        if stem and stem.lower() not in {"attachment", "file"}:
            base_name = f"{Path(base_name).stem}__{cls._safe_filename_part(stem)}{suffix}"

        return base_name

    @classmethod
    def _unique_path(cls, path: Path) -> Path:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            return path

        counter = 1
        while True:
            candidate = path.parent / f"{path.stem}_{counter}{path.suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    # -----------------------------------------------------------------
    # Email helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _decode_text(value: Any) -> str:
        if not value:
            return ""
        decoded_parts = decode_header(value)
        parts: List[str] = []
        for part, enc in decoded_parts:
            if isinstance(part, bytes):
                parts.append(part.decode(enc or "utf-8", errors="ignore"))
            else:
                parts.append(str(part))
        return "".join(parts).strip()

    @classmethod
    def _extract_email_body_text(cls, msg: Any) -> str:
        parts: List[str] = []

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue

                filename = part.get_filename()
                if filename:
                    continue

                content_type = str(part.get_content_type() or "").lower()
                if content_type not in {"text/plain", "text/html"}:
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                charset = part.get_content_charset() or "utf-8"
                try:
                    text = payload.decode(charset, errors="ignore")
                except Exception:
                    text = payload.decode("utf-8", errors="ignore")

                if content_type == "text/html":
                    text = re.sub(r"<[^>]+>", " ", text)

                parts.append(text)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    parts.append(payload.decode(charset, errors="ignore"))
                except Exception:
                    parts.append(payload.decode("utf-8", errors="ignore"))

        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    @classmethod
    def _extract_email_address(cls, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", text)
        return match.group(1).strip().lower() if match else None

    @classmethod
    def _extract_domain_from_email(cls, email_address: Optional[str]) -> Optional[str]:
        if not email_address or "@" not in email_address:
            return None
        return email_address.split("@", 1)[1].strip().lower()

    @classmethod
    def _collect_emails_and_domains_from_text(
        cls,
        text: str,
        *,
        expected_supplier_emails: Set[str],
        expected_supplier_domains: Set[str],
    ) -> None:
        if not text:
            return

        email_matches = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
        for email_match in email_matches:
            cleaned = email_match.strip().lower()
            expected_supplier_emails.add(cleaned)
            domain = cls._extract_domain_from_email(cleaned)
            if domain:
                expected_supplier_domains.add(domain)

        maybe_domain = cls._extract_domain_from_generic_text(text)
        if maybe_domain:
            expected_supplier_domains.add(maybe_domain)

    @classmethod
    def _extract_domain_from_generic_text(cls, text: str) -> Optional[str]:
        value = (text or "").strip().lower()
        if not value:
            return None

        if value.startswith(("http://", "https://")):
            try:
                domain = urlparse(value).netloc.strip().lower()
                return domain[4:] if domain.startswith("www.") else domain
            except Exception:
                return None

        if "@" in value:
            return cls._extract_domain_from_email(value)

        value = value.replace("www.", "").strip()
        if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", value):
            return value

        return None

    # -----------------------------------------------------------------
    # Quote folder processing
    # -----------------------------------------------------------------

    @classmethod
    def process_quote_folder(cls, folder_path: str | Path) -> Dict[str, Any]:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Quote folder not found: {folder}")

        supplier_pdfs = sorted(
            [
                p for p in folder.iterdir()
                if p.is_file() and cls.SUPPLIER_FILE_REGEX.match(p.name)
            ]
        )

        if not supplier_pdfs:
            return {
                "success": False,
                "folder": str(folder),
                "message": "No supplier_quote_* files found.",
                "supplier_files_found": [],
                "comparison_path": None,
                "results": [],
            }

        results: List[SupplierQuoteExtractionResult] = []

        for pdf_path in supplier_pdfs:
            supplier_name = cls._infer_supplier_name_from_filename(pdf_path.name)
            try:
                if pdf_path.suffix.lower() == ".pdf":
                    result = cls.extract_supplier_quote_pdf(
                        pdf_path=pdf_path,
                        supplier_name=supplier_name,
                    )
                else:
                    result = SupplierQuoteExtractionResult(
                        supplier_name=supplier_name,
                        pdf_path=str(pdf_path),
                        extraction_method="non_pdf_saved",
                        warnings=["Attachment saved but structured extraction is only implemented for PDF files."],
                    )

                results.append(result)

                extracted_json_path = folder / f"{pdf_path.stem}.extracted.json"
                cls._write_json(extracted_json_path, cls._result_to_dict(result))

            except Exception as exc:
                logger.exception("Failed to process supplier file: %s", pdf_path)
                failed = SupplierQuoteExtractionResult(
                    supplier_name=supplier_name,
                    pdf_path=str(pdf_path),
                    extraction_method="failed",
                    warnings=[f"Extraction failed: {exc}"],
                )
                results.append(failed)

                extracted_json_path = folder / f"{pdf_path.stem}.extracted.json"
                cls._write_json(extracted_json_path, cls._result_to_dict(failed))

        comparison = cls.build_quote_comparison(results)
        comparison_path = folder / cls.COMPARISON_OUTPUT
        cls._write_json(comparison_path, comparison)

        return {
            "success": True,
            "folder": str(folder),
            "supplier_files_found": [str(p) for p in supplier_pdfs],
            "comparison_path": str(comparison_path),
            "results": [cls._result_to_dict(r) for r in results],
            "comparison": comparison,
        }

    @classmethod
    def extract_supplier_quote_pdf(
        cls,
        pdf_path: str | Path,
        supplier_name: Optional[str] = None,
    ) -> SupplierQuoteExtractionResult:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Supplier PDF not found: {pdf_path}")

        supplier_name = supplier_name or cls._infer_supplier_name_from_filename(pdf_path.name)

        warnings: List[str] = []
        extraction_method = "unknown"

        tables: List[List[List[str]]] = []
        raw_text = ""

        if pdfplumber is not None:
            try:
                raw_text, tables = cls._extract_with_pdfplumber(pdf_path)
                extraction_method = "pdfplumber"
            except Exception as exc:
                warnings.append(f"pdfplumber extraction failed: {exc}")

        if not raw_text.strip() and PdfReader is not None:
            try:
                raw_text = cls._extract_with_pypdf(pdf_path)
                extraction_method = "pypdf" if extraction_method == "unknown" else extraction_method
            except Exception as exc:
                warnings.append(f"pypdf extraction failed: {exc}")

        if not raw_text.strip():
            warnings.append("No extractable text found. This may be a scanned-image PDF and may require OCR.")

        quote_number = cls._extract_quote_number(raw_text)
        quote_date = cls._extract_quote_date(raw_text)
        totals = cls._extract_totals(raw_text)

        table_items = cls._extract_line_items_from_tables(tables) if tables else []
        text_items = cls._extract_line_items_from_text(raw_text)
        items = cls._merge_items(table_items, text_items)

        if not items:
            warnings.append("No structured line items could be confidently extracted.")

        return SupplierQuoteExtractionResult(
            supplier_name=supplier_name,
            pdf_path=str(pdf_path),
            extraction_method=extraction_method,
            quote_number=quote_number,
            quote_date=quote_date,
            vat_included=cls._infer_vat_inclusion(raw_text, totals),
            subtotal=totals.get("subtotal"),
            vat=totals.get("vat"),
            total=totals.get("total"),
            items=items,
            warnings=warnings,
            raw_text_preview=raw_text[:3000] if raw_text else None,
        )

    @classmethod
    def build_quote_comparison(
        cls,
        extraction_results: List[SupplierQuoteExtractionResult],
    ) -> Dict[str, Any]:
        grouped: Dict[str, ComparisonItem] = {}

        for result in extraction_results:
            supplier = result.supplier_name
            for item in result.items:
                norm_desc = cls._normalize_description(item.description)
                if not norm_desc:
                    continue

                if norm_desc not in grouped:
                    grouped[norm_desc] = ComparisonItem(
                        normalized_description=norm_desc,
                        suppliers={},
                        quantity_reference=item.quantity,
                    )

                grouped[norm_desc].suppliers[supplier] = {
                    "original_description": item.description,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                    "confidence": item.confidence,
                    "source": item.source,
                }

                if grouped[norm_desc].quantity_reference is None and item.quantity is not None:
                    grouped[norm_desc].quantity_reference = item.quantity

        comparison_items: List[Dict[str, Any]] = []

        for _, comp in grouped.items():
            prices = []
            cheapest_supplier = None
            cheapest_price = None

            for supplier, data in comp.suppliers.items():
                unit_price = data.get("unit_price")
                if isinstance(unit_price, (int, float)) and unit_price > 0:
                    prices.append(float(unit_price))
                    if cheapest_price is None or unit_price < cheapest_price:
                        cheapest_price = float(unit_price)
                        cheapest_supplier = supplier

            average_price = round(sum(prices) / len(prices), 2) if prices else None

            comparison_items.append(
                {
                    "normalized_description": comp.normalized_description,
                    "quantity_reference": comp.quantity_reference,
                    "suppliers": comp.suppliers,
                    "cheapest_supplier": cheapest_supplier,
                    "cheapest_unit_price": cheapest_price,
                    "average_unit_price": average_price,
                }
            )

        supplier_totals = cls._build_supplier_totals(extraction_results)

        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "supplier_count": len(extraction_results),
            "suppliers": [r.supplier_name for r in extraction_results],
            "items": comparison_items,
            "supplier_totals": supplier_totals,
            "recommended_supplier_by_total": cls._recommend_by_total(supplier_totals),
        }

    # -----------------------------------------------------------------
    # PDF extraction helpers
    # -----------------------------------------------------------------

    @classmethod
    def _extract_with_pdfplumber(cls, pdf_path: Path) -> Tuple[str, List[List[List[str]]]]:
        raw_text_parts: List[str] = []
        all_tables: List[List[List[str]]] = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    raw_text_parts.append(page_text)

                try:
                    page_tables = page.extract_tables() or []
                    for table in page_tables:
                        cleaned_table: List[List[str]] = []
                        for row in table:
                            if not row:
                                continue
                            cleaned_row = [cls._clean_cell_text(c) for c in row]
                            if any(cell.strip() for cell in cleaned_row):
                                cleaned_table.append(cleaned_row)
                        if cleaned_table:
                            all_tables.append(cleaned_table)
                except Exception as exc:
                    logger.warning("Table extraction failed on page: %s", exc)

        return "\n".join(raw_text_parts).strip(), all_tables

    @classmethod
    def _extract_with_pypdf(cls, pdf_path: Path) -> str:
        if PdfReader is None:
            return ""

        reader = PdfReader(str(pdf_path))
        text_parts: List[str] = []

        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
                if txt:
                    text_parts.append(txt)
            except Exception as exc:
                logger.warning("pypdf failed on page %s: %s", pdf_path.name, exc)

        return "\n".join(text_parts).strip()

    # -----------------------------------------------------------------
    # Parsing helpers
    # -----------------------------------------------------------------

    @classmethod
    def _extract_quote_number(cls, text: str) -> Optional[str]:
        match = cls.QUOTE_NO_RE.search(text or "")
        return match.group(1).strip() if match else None

    @classmethod
    def _extract_quote_date(cls, text: str) -> Optional[str]:
        match = cls.DATE_RE.search(text or "")
        return match.group(1).strip() if match else None

    @classmethod
    def _extract_totals(cls, text: str) -> Dict[str, Optional[float]]:
        subtotal = None
        vat = None
        total = None

        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        for line in lines:
            line_lower = line.lower()
            amounts = cls._extract_money_values(line)
            if not amounts:
                continue

            last_amount = amounts[-1]

            if cls.SUBTOTAL_RE.search(line_lower):
                subtotal = last_amount
            elif cls.VAT_RE.search(line_lower):
                vat = last_amount
            elif cls.TOTAL_RE.search(line_lower):
                total = last_amount

        return {"subtotal": subtotal, "vat": vat, "total": total}

    @classmethod
    def _infer_vat_inclusion(cls, text: str, totals: Dict[str, Optional[float]]) -> Optional[bool]:
        lower = (text or "").lower()
        if "vat inclusive" in lower or "incl vat" in lower or "including vat" in lower:
            return True
        if "vat exclusive" in lower or "excl vat" in lower or "excluding vat" in lower:
            return False
        if totals.get("vat") not in (None, 0):
            return True
        return None

    @classmethod
    def _extract_line_items_from_tables(cls, tables: List[List[List[str]]]) -> List[ExtractedLineItem]:
        items: List[ExtractedLineItem] = []

        for table in tables:
            if not table:
                continue

            header_idx, header_map = cls._detect_table_header(table)
            if header_map:
                for row in table[header_idx + 1 :]:
                    item = cls._extract_item_from_structured_row(row, header_map)
                    if item:
                        items.append(item)
                continue

            for row in table:
                item = cls._extract_item_from_unstructured_row(row)
                if item:
                    items.append(item)

        return items

    @classmethod
    def _extract_line_items_from_text(cls, text: str) -> List[ExtractedLineItem]:
        items: List[ExtractedLineItem] = []
        if not text:
            return items

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        for line in lines:
            if cls._should_ignore_line(line):
                continue

            low = line.lower()
            if "subtotal" in low or "vat" in low or "grand total" in low or low == "total":
                continue

            item = cls._extract_item_from_text_line(line)
            if item:
                items.append(item)

        return items

    @classmethod
    def _detect_table_header(cls, table: List[List[str]]) -> Tuple[int, Dict[str, int]]:
        candidate_keys = {
            "description": ["description", "item", "product", "details"],
            "quantity": ["qty", "quantity"],
            "unit": ["unit", "uom"],
            "unit_price": ["unit price", "price", "rate", "cost", "selling price"],
            "line_total": ["amount", "total", "line total", "ext price", "value"],
        }

        for idx, row in enumerate(table[:5]):
            norm = [cls._normalize_header_cell(c) for c in row]
            header_map: Dict[str, int] = {}

            for i, cell in enumerate(norm):
                for target, aliases in candidate_keys.items():
                    if any(alias == cell or alias in cell for alias in aliases):
                        if target not in header_map:
                            header_map[target] = i

            if "description" in header_map and ("unit_price" in header_map or "line_total" in header_map):
                return idx, header_map

        return -1, {}

    @classmethod
    def _extract_item_from_structured_row(
        cls,
        row: List[str],
        header_map: Dict[str, int],
    ) -> Optional[ExtractedLineItem]:
        try:
            description = cls._safe_get(row, header_map.get("description"))
            qty_raw = cls._safe_get(row, header_map.get("quantity"))
            unit_raw = cls._safe_get(row, header_map.get("unit"))
            unit_price_raw = cls._safe_get(row, header_map.get("unit_price"))
            line_total_raw = cls._safe_get(row, header_map.get("line_total"))

            description = cls._clean_description(description)
            quantity = cls._parse_float(qty_raw)
            unit = cls._clean_unit(unit_raw)
            unit_price = cls._parse_money(unit_price_raw)
            line_total = cls._parse_money(line_total_raw)

            if not description:
                return None

            if quantity is None and unit_price is None and line_total is None:
                return None

            if line_total is None and quantity and unit_price:
                line_total = round(quantity * unit_price, 2)

            return ExtractedLineItem(
                description=description,
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                line_total=line_total,
                source="table_structured",
                confidence=0.95,
                raw_line=" | ".join(row),
            )
        except Exception:
            return None

    @classmethod
    def _extract_item_from_unstructured_row(cls, row: List[str]) -> Optional[ExtractedLineItem]:
        joined = " | ".join([c.strip() for c in row if c and c.strip()])
        if not joined:
            return None
        return cls._extract_item_from_text_line(joined, source="table_unstructured")

    @classmethod
    def _extract_item_from_text_line(
        cls,
        line: str,
        source: str = "text",
    ) -> Optional[ExtractedLineItem]:
        clean_line = re.sub(r"\s+", " ", line).strip()
        if not clean_line or len(clean_line) < 4:
            return None

        money_values = cls._extract_money_values(clean_line)
        if not money_values:
            return None

        unit_price = None
        line_total = None

        if len(money_values) >= 2:
            unit_price = money_values[-2]
            line_total = money_values[-1]
        else:
            unit_price = money_values[-1]

        stripped = cls._remove_money_tokens(clean_line)
        tokens = stripped.split()

        quantity = None
        unit = None

        if tokens:
            qt_match = cls.QUANTITY_TOKEN_RE.match(" ".join(tokens[-2:]))
            if qt_match:
                quantity = cls._parse_float(qt_match.group("qty"))
                unit = cls._clean_unit(qt_match.group("unit"))
                tokens = tokens[:-2]
            else:
                qt_match = cls.QUANTITY_TOKEN_RE.match(tokens[-1])
                if qt_match:
                    quantity = cls._parse_float(qt_match.group("qty"))
                    unit = cls._clean_unit(qt_match.group("unit"))
                    tokens = tokens[:-1]

        if tokens and re.fullmatch(r"\d+|[A-Za-z]{1,4}\d{1,10}", tokens[0]):
            tokens = tokens[1:]

        description = cls._clean_description(" ".join(tokens))

        if not description:
            return None

        if quantity is None and unit_price and line_total and unit_price > 0:
            guessed_qty = line_total / unit_price
            if abs(round(guessed_qty) - guessed_qty) < 0.001:
                quantity = float(round(guessed_qty))

        confidence = 0.55
        if quantity is not None:
            confidence += 0.15
        if unit_price is not None:
            confidence += 0.15
        if line_total is not None:
            confidence += 0.15

        return ExtractedLineItem(
            description=description,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            line_total=line_total,
            source=source,
            confidence=min(confidence, 0.9),
            raw_line=line,
        )

    @classmethod
    def _merge_items(
        cls,
        table_items: List[ExtractedLineItem],
        text_items: List[ExtractedLineItem],
    ) -> List[ExtractedLineItem]:
        if table_items:
            merged = table_items[:]
            table_keys = {
                (
                    cls._normalize_description(i.description),
                    i.quantity,
                    i.unit_price,
                    i.line_total,
                )
                for i in table_items
            }

            for item in text_items:
                key = (
                    cls._normalize_description(item.description),
                    item.quantity,
                    item.unit_price,
                    item.line_total,
                )
                if key not in table_keys:
                    merged.append(item)

            return cls._dedupe_items(merged)

        return cls._dedupe_items(text_items)

    @classmethod
    def _dedupe_items(cls, items: List[ExtractedLineItem]) -> List[ExtractedLineItem]:
        best: Dict[str, ExtractedLineItem] = {}

        for item in items:
            key = cls._normalize_description(item.description)
            if not key:
                continue

            if key not in best:
                best[key] = item
                continue

            existing = best[key]
            if item.confidence > existing.confidence:
                best[key] = item
                continue

            if (existing.unit_price is None and item.unit_price is not None) or (
                existing.line_total is None and item.line_total is not None
            ):
                best[key] = item

        return list(best.values())

    # -----------------------------------------------------------------
    # Comparison helpers
    # -----------------------------------------------------------------

    @classmethod
    def _build_supplier_totals(
        cls,
        extraction_results: List[SupplierQuoteExtractionResult],
    ) -> List[Dict[str, Any]]:
        totals: List[Dict[str, Any]] = []

        for result in extraction_results:
            computed_item_total = 0.0
            counted = 0

            for item in result.items:
                if item.line_total is not None:
                    computed_item_total += item.line_total
                    counted += 1
                elif item.quantity is not None and item.unit_price is not None:
                    computed_item_total += item.quantity * item.unit_price
                    counted += 1

            totals.append(
                {
                    "supplier_name": result.supplier_name,
                    "quoted_total": result.total,
                    "quoted_subtotal": result.subtotal,
                    "quoted_vat": result.vat,
                    "computed_items_total": round(computed_item_total, 2) if counted else None,
                    "item_count": len(result.items),
                    "extraction_method": result.extraction_method,
                    "warnings": result.warnings,
                }
            )

        return totals

    @classmethod
    def _recommend_by_total(cls, supplier_totals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        candidates: List[Tuple[str, float, str]] = []

        for row in supplier_totals:
            supplier_name = row.get("supplier_name")
            quoted_total = row.get("quoted_total")
            computed_total = row.get("computed_items_total")

            if isinstance(quoted_total, (int, float)) and quoted_total > 0:
                candidates.append((supplier_name, float(quoted_total), "quoted_total"))
            elif isinstance(computed_total, (int, float)) and computed_total > 0:
                candidates.append((supplier_name, float(computed_total), "computed_items_total"))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1])
        best = candidates[0]
        return {
            "supplier_name": best[0],
            "best_total": best[1],
            "based_on": best[2],
        }

    # -----------------------------------------------------------------
    # Utility helpers
    # -----------------------------------------------------------------

    @classmethod
    def _infer_supplier_name_from_filename(cls, filename: str) -> str:
        match = cls.SUPPLIER_FILE_REGEX.match(filename)
        if not match:
            return Path(filename).stem

        supplier_part = match.group(2)
        if supplier_part:
            return supplier_part.replace("_", " ").replace("-", " ").strip().title()

        return Path(filename).stem

    @classmethod
    def _write_json(cls, path: Path, payload: Dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def _result_to_dict(cls, result: SupplierQuoteExtractionResult) -> Dict[str, Any]:
        data = asdict(result)
        data["items"] = [asdict(item) for item in result.items]
        return data

    @classmethod
    def _extract_money_values(cls, text: str) -> List[float]:
        values: List[float] = []
        for match in cls.MONEY_RE.finditer(text or ""):
            amount_str = match.group("amount")
            value = cls._parse_money(amount_str)
            if value is not None:
                values.append(value)
        return values

    @classmethod
    def _parse_money(cls, value: Any) -> Optional[float]:
        if value is None:
            return None

        s = str(value).strip()
        if not s:
            return None

        s = s.replace("ZAR", "").replace("zar", "").replace("R", "").strip()
        s = s.replace(" ", "")

        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        else:
            if s.count(",") == 1 and s.count(".") == 0:
                last = s.split(",")[-1]
                if len(last) == 2:
                    s = s.replace(",", ".")
                else:
                    s = s.replace(",", "")
            else:
                s = s.replace(",", "")

        try:
            amount = Decimal(s)
            return float(round(amount, 2))
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def _parse_float(cls, value: Any) -> Optional[float]:
        if value is None:
            return None
        s = str(value).strip().replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    @classmethod
    def _normalize_header_cell(cls, text: str) -> str:
        text = cls._clean_cell_text(text).lower()
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _clean_cell_text(cls, text: Any) -> str:
        if text is None:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip()

    @classmethod
    def _safe_get(cls, row: List[str], idx: Optional[int]) -> str:
        if idx is None:
            return ""
        if idx < 0 or idx >= len(row):
            return ""
        return row[idx] or ""

    @classmethod
    def _remove_money_tokens(cls, text: str) -> str:
        return cls.MONEY_RE.sub(" ", text)

    @classmethod
    def _clean_description(cls, text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"\b(?:item|code|ref|stock)\b[:#]?\s*", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" -|:\t")
        text = re.sub(r"^[\d.\-]+\s+", "", text)

        if cls._should_ignore_line(text):
            return ""

        if len(text) < 3:
            return ""

        return text.strip()

    @classmethod
    def _normalize_description(cls, text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        text = re.sub(r"\b(the|and|for|with|each|ea|unit|units|pcs|pc)\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def _clean_unit(cls, text: Any) -> Optional[str]:
        if text is None:
            return None
        s = str(text).strip().lower()
        if not s:
            return None

        unit_map = {
            "ea": "ea",
            "each": "ea",
            "unit": "unit",
            "units": "unit",
            "pc": "pc",
            "pcs": "pc",
            "box": "box",
            "boxes": "box",
            "pack": "pack",
            "packs": "pack",
            "set": "set",
            "sets": "set",
            "roll": "roll",
            "rolls": "roll",
            "meter": "m",
            "metre": "m",
            "m": "m",
            "kg": "kg",
            "g": "g",
            "l": "l",
            "ml": "ml",
            "lot": "lot",
        }
        return unit_map.get(s, s)

    @classmethod
    def _should_ignore_line(cls, line: str) -> bool:
        if not line:
            return True

        if cls.IGNORE_LINE_RE.search(line):
            return True

        low = line.lower().strip()
        if low in {"subtotal", "vat", "total", "grand total"}:
            return True

        alpha_count = sum(1 for ch in line if ch.isalpha())
        if alpha_count < 2:
            return True

        return False

    @classmethod
    def _flatten_mixed(cls, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            result: List[Any] = []
            for item in value:
                result.extend(cls._flatten_mixed(item))
            return result
        return [value]

    @classmethod
    def _first_non_empty(cls, *values: Any) -> Optional[str]:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @classmethod
    def _deep_get(cls, data: Dict[str, Any], keys: List[str]) -> Any:
        current: Any = data
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    @classmethod
    def _safe_filename_part(cls, value: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
        return clean or "unknown"

    @classmethod
    def _safe_int(cls, value: Any, default: int = 0) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return default

    @classmethod
    def _final_result(
        cls,
        *,
        success: bool,
        processed: int,
        saved_attachments: int,
        folders_updated: List[str],
        matched_email_ids: List[str],
        saved_files: List[str],
        matched_emails: List[Dict[str, Any]],
        quote_folder: Optional[str],
        quote_comparison_json: Optional[str],
        probable_matches: List[Dict[str, Any]],
        unmatched_saved_files: List[str],
        blocking_quote_generation: bool,
        should_continue_quote_generation: bool,
        message: str,
        match_context_summary: Optional[Dict[str, Any]] = None,
        processed_quote_folder: bool = False,
        skipped: bool = False,
        skip_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "success": success,
            "processed": processed,
            "saved_attachments": saved_attachments,
            "folders_updated": folders_updated,
            "matched_email_ids": matched_email_ids,
            "saved_files": saved_files,
            "matched_emails": matched_emails,
            "quote_folder": quote_folder,
            "quote_comparison_json": quote_comparison_json,
            "probable_matches": probable_matches,
            "unmatched_saved_files": unmatched_saved_files,
            "blocking_quote_generation": blocking_quote_generation,
            "should_continue_quote_generation": should_continue_quote_generation,
            "processed_quote_folder": processed_quote_folder,
            "match_context_summary": match_context_summary or {},
            "message": message,
            "skipped": skipped,
            "skip_reason": skip_reason,
        }


# ---------------------------------------------------------------------
# Optional convenience function for pipeline use
# ---------------------------------------------------------------------


def extract_and_compare_supplier_quotes(folder_path: str | Path) -> Dict[str, Any]:
    return SupplierQuoteIngestionService.process_quote_folder(folder_path)


def ingest_supplier_quotes(payload: Optional[dict] = None) -> dict:
    """
    Compatibility wrapper for tender_pipeline.py.

    Non-blocking rule:
    even when no supplier quotes are found, buyer quote generation should continue.

    New safety rules:
    - Skip duplicate ingestion calls in the same cycle
    - Skip when payload explicitly says to skip
    - Skip when there are no usable identifiers/context
    """
    payload = payload or {}

    try:
        service = SupplierQuoteIngestionService()
        result = service.ingest_once(payload=payload)

        if not isinstance(result, dict):
            result = {}

        return {
            "supplier_quote_ingestion": result,
            "supplier_quote_files": result.get("saved_files", []),
            "supplier_quote_emails": result.get("matched_emails", []),
            "matched_email_ids": result.get("matched_email_ids", []),
            "supplier_quotes_found": result.get("saved_attachments", 0),
            "supplier_quotes_saved": result.get("saved_attachments", 0),
            "supplier_quotes_folder": result.get("quote_folder"),
            "quote_comparison_json": result.get("quote_comparison_json"),
            "supplier_reply_matches": result.get("matched_email_ids", []),
            "supplier_probable_matches": result.get("probable_matches", []),
            "supplier_unmatched_saved_files": result.get("unmatched_saved_files", []),
            "blocking_quote_generation": False,
            "should_continue_quote_generation": True,
            "pricing_mode": (
                "supplier_pricing_available"
                if result.get("saved_attachments", 0) > 0
                else "fallback_pricing_required"
            ),
            "supplier_ingestion_skipped": bool(result.get("skipped", False)),
            "supplier_ingestion_skip_reason": result.get("skip_reason"),
        }

    except Exception as exc:
        logger.exception("[INGEST] Wrapper failed")
        return {
            "supplier_quote_ingestion": {
                "success": False,
                "message": str(exc),
                "blocking_quote_generation": False,
                "should_continue_quote_generation": True,
                "skipped": False,
                "skip_reason": None,
            },
            "supplier_quote_files": [],
            "supplier_quote_emails": [],
            "matched_email_ids": [],
            "supplier_quotes_found": 0,
            "supplier_quotes_saved": 0,
            "supplier_quotes_folder": None,
            "quote_comparison_json": None,
            "supplier_reply_matches": [],
            "supplier_probable_matches": [],
            "supplier_unmatched_saved_files": [],
            "blocking_quote_generation": False,
            "should_continue_quote_generation": True,
            "pricing_mode": "fallback_pricing_required",
            "supplier_ingestion_skipped": False,
            "supplier_ingestion_skip_reason": None,
        }
