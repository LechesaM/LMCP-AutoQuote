from __future__ import annotations

import imaplib
import email
import logging
import os
import re
from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.header import decode_header
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SupplierQuoteLine:
    description: str
    quantity: float
    unit: str
    unit_price: float
    line_total: float
    item_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupplierQuoteEnvelope:
    supplier_name: str
    supplier_email: str
    quote_reference: str
    subject: str
    received_at: str
    items: List[SupplierQuoteLine]
    attachment_filenames: List[str]
    message_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["items"] = [item.to_dict() for item in self.items]
        return payload


class SupplierQuoteIngestionService:
    DEFAULT_IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
    DEFAULT_IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

    SUPPLIER_HINT_FIELDS = (
        "supplier_name",
        "supplier_email",
        "quote_reference",
        "quote_number",
        "reference",
    )

    FILE_HINT_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".txt"}

    @classmethod
    def ingest_supplier_quotes(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(payload if isinstance(payload, dict) else {})
        result.setdefault("supplier_quotes", [])

        skip_external = cls._to_bool(result.get("skip_external_calls"), False)
        pipeline_test_mode = cls._to_bool(result.get("pipeline_test_mode"), False)

        if skip_external:
            result["supplier_quote_ingestion"] = {
                "status": "skipped",
                "reason": "External calls skipped by payload flag",
                "matched_count": 0,
                "quotes": [],
            }
            return result

        if pipeline_test_mode and result.get("supplier_quotes"):
            normalized = cls._normalize_supplier_quotes(result.get("supplier_quotes") or [])
            result["supplier_quotes"] = normalized
            result["supplier_quote_ingestion"] = {
                "status": "ok",
                "reason": "Used supplier_quotes already present on payload",
                "matched_count": len(normalized),
                "quotes": normalized,
            }
            return result

        username = (
            os.getenv("EMAIL_USERNAME")
            or os.getenv("IMAP_USERNAME")
            or os.getenv("GMAIL_USERNAME")
        )
        password = (
            os.getenv("EMAIL_PASSWORD")
            or os.getenv("IMAP_PASSWORD")
            or os.getenv("GMAIL_APP_PASSWORD")
        )

        if not username or not password:
            print("[INGEST] Missing IMAP/EMAIL username or password")
            result["supplier_quote_ingestion"] = {
                "status": "skipped",
                "reason": "Missing IMAP/EMAIL username or password",
                "matched_count": 0,
                "quotes": [],
            }
            return result

        try:
            host = os.getenv("IMAP_HOST", cls.DEFAULT_IMAP_HOST)
            port = int(os.getenv("IMAP_PORT", str(cls.DEFAULT_IMAP_PORT)))

            query = cls._build_imap_search_query(result)
            messages = cls._read_matching_messages(
                host=host,
                port=port,
                username=username,
                password=password,
                search_query=query,
                max_messages=25,
            )

            extracted_quotes = cls._extract_quotes_from_messages(messages, result)
            normalized_quotes = cls._normalize_supplier_quotes(extracted_quotes)

            result["supplier_quotes"] = normalized_quotes
            result["supplier_quote_ingestion"] = {
                "status": "ok",
                "reason": "IMAP supplier quote ingestion completed",
                "matched_count": len(normalized_quotes),
                "quotes": normalized_quotes,
                "search_query": query,
            }
            return result

        except Exception as exc:
            logger.exception("Supplier quote ingestion failed.")
            result["supplier_quote_ingestion"] = {
                "status": "failed",
                "reason": str(exc),
                "matched_count": 0,
                "quotes": [],
            }
            return result

    @classmethod
    def _safe_decode(cls, value: Any, charset: Optional[str] = "utf-8") -> str:
        """
        Production-safe decoder.

        Fixes the observed crash:
            'int' object has no attribute 'decode'

        Rules:
        - bytes -> decode
        - str -> return as-is
        - int/float/bool -> convert to string
        - None -> empty string
        - anything else -> str(value)
        """
        if value is None:
            return ""

        if isinstance(value, str):
            return value

        if isinstance(value, bytes):
            try:
                return value.decode(charset or "utf-8", errors="replace")
            except Exception:
                return value.decode("utf-8", errors="replace")

        return str(value)

    @classmethod
    def _safe_str(cls, value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = cls._safe_decode(value).strip()
        return text if text else default

    @classmethod
    def _safe_lower(cls, value: Any) -> str:
        return cls._safe_str(value).lower()

    @classmethod
    def _to_bool(cls, value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        text = cls._safe_lower(value)
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
        return default

    @classmethod
    def _to_float(cls, value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            cleaned = (
                cls._safe_decode(value)
                .replace("R", "")
                .replace("ZAR", "")
                .replace("zar", "")
                .replace(",", "")
                .replace(" ", "")
                .strip()
            )
            if not cleaned:
                return default
            return float(cleaned)
        except Exception:
            return default

    @classmethod
    def _dedupe_quotes(cls, quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen = set()

        for quote in quotes:
            if not isinstance(quote, dict):
                continue

            key = (
                cls._safe_lower(quote.get("supplier_name")),
                cls._safe_lower(quote.get("supplier_email")),
                cls._safe_lower(quote.get("quote_reference")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(quote)

        return deduped

    @classmethod
    def _normalize_unit(cls, value: Any) -> str:
        text = cls._safe_lower(value)
        mapping = {
            "ea": "Each",
            "each": "Each",
            "unit": "Each",
            "item": "Each",
            "pcs": "Each",
            "piece": "Each",
            "pieces": "Each",
            "set": "Set",
            "sets": "Set",
            "box": "Box",
            "boxes": "Box",
            "pack": "Pack",
            "packs": "Pack",
            "ream": "Ream",
            "reams": "Ream",
        }
        return mapping.get(text, cls._safe_str(value, "Each").title())

    @classmethod
    def _decode_header_value(cls, value: Any) -> str:
        if value is None:
            return ""

        safe_value = cls._safe_decode(value)
        if not safe_value:
            return ""

        try:
            decoded_parts = decode_header(safe_value)
        except Exception:
            return safe_value.strip()

        output: List[str] = []
        for part, enc in decoded_parts:
            if isinstance(part, bytes):
                output.append(cls._safe_decode(part, enc or "utf-8"))
            else:
                output.append(cls._safe_decode(part))
        return "".join(output).strip()

    @classmethod
    def _extract_email_address(cls, raw_from: Any) -> str:
        text = cls._decode_header_value(raw_from)
        match = re.search(r"<([^>]+@[^>]+)>", text or "")
        if match:
            return match.group(1).strip()
        return text if "@" in text else ""

    @classmethod
    def _extract_display_name(cls, raw_from: Any) -> str:
        raw = cls._decode_header_value(raw_from)
        if "<" in raw:
            return raw.split("<", 1)[0].strip().strip('"').strip()
        if "@" in raw:
            return raw.split("@", 1)[0].strip()
        return raw

    @classmethod
    def _build_imap_search_query(cls, payload: Dict[str, Any]) -> str:
        buyer_rfq_number = cls._safe_str(
            payload.get("_locked_buyer_rfq_number")
            or payload.get("buyer_rfq_number")
            or payload.get("rfq_number")
            or payload.get("reference_number")
            or payload.get("document_number")
        )
        title = cls._safe_str(payload.get("title"))
        description = cls._safe_str(payload.get("description"))

        keywords: List[str] = []
        if buyer_rfq_number:
            keywords.append(buyer_rfq_number)

        title_words = re.findall(r"[A-Za-z0-9]{4,}", title)
        description_words = re.findall(r"[A-Za-z0-9]{4,}", description)

        for word in title_words[:4]:
            keywords.append(word)
        for word in description_words[:4]:
            keywords.append(word)

        # IMAP search syntax is fragile. Keep one strong search token.
        # If it fails, _read_matching_messages falls back safely.
        for keyword in keywords:
            clean = cls._safe_str(keyword).replace('"', "").strip()
            if clean:
                return clean[:80]

        return "quote"

    @classmethod
    def _read_matching_messages(
        cls,
        host: str,
        port: int,
        username: str,
        password: str,
        search_query: str,
        max_messages: int = 25,
    ) -> List[Dict[str, Any]]:
        mail = imaplib.IMAP4_SSL(host, port)
        try:
            mail.login(username, password)
            mail.select("inbox")

            query = cls._safe_str(search_query, "quote").replace('"', "").strip()
            search_attempts = [
                f'(OR SUBJECT "{query}" BODY "{query}")',
                f'(SUBJECT "{query}")',
                f'(BODY "{query}")',
                "ALL",
            ]

            status = "NO"
            data: List[Any] = []

            for search_expr in search_attempts:
                try:
                    status, data = mail.search(None, search_expr)
                    if status == "OK" and data and data[0]:
                        break
                except Exception:
                    continue

            if status != "OK" or not data or not data[0]:
                return []

            raw_ids = data[0]
            if isinstance(raw_ids, bytes):
                message_ids = raw_ids.split()
            elif isinstance(raw_ids, str):
                message_ids = raw_ids.encode("utf-8", errors="ignore").split()
            else:
                message_ids = cls._safe_decode(raw_ids).encode("utf-8", errors="ignore").split()

            message_ids = message_ids[-max_messages:]
            messages: List[Dict[str, Any]] = []

            for msg_id in reversed(message_ids):
                try:
                    status, fetched = mail.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not fetched:
                        continue

                    raw_email = cls._extract_raw_email_from_fetch(fetched)
                    if not raw_email:
                        continue

                    msg = email.message_from_bytes(raw_email)

                    subject = cls._decode_header_value(msg.get("Subject"))
                    from_raw = cls._decode_header_value(msg.get("From"))
                    message_id = cls._safe_str(msg.get("Message-ID"))
                    date_raw = cls._decode_header_value(msg.get("Date"))

                    body_text, attachments = cls._extract_email_body_and_attachments(msg)

                    messages.append(
                        {
                            "message_id": message_id,
                            "subject": subject,
                            "from_raw": from_raw,
                            "from_email": cls._extract_email_address(from_raw),
                            "from_name": cls._extract_display_name(from_raw),
                            "date": date_raw,
                            "body_text": body_text,
                            "attachments": attachments,
                        }
                    )
                except Exception as exc:
                    logger.warning("Failed to parse supplier quote email: %s", exc)
                    continue

            return messages

        finally:
            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass

    @classmethod
    def _extract_raw_email_from_fetch(cls, fetched: Any) -> bytes:
        """
        IMAP fetch can return tuples, bytes, strings, ints, or closing metadata.
        This prevents tuple/int decode crashes.
        """
        if not fetched:
            return b""

        for entry in fetched:
            if isinstance(entry, tuple) and len(entry) >= 2:
                candidate = entry[1]
                if isinstance(candidate, bytes):
                    return candidate
                if isinstance(candidate, str):
                    return candidate.encode("utf-8", errors="replace")
                continue

            if isinstance(entry, bytes) and b"From:" in entry:
                return entry

            if isinstance(entry, str) and "From:" in entry:
                return entry.encode("utf-8", errors="replace")

        return b""

    @classmethod
    def _extract_email_body_and_attachments(
        cls,
        msg: email.message.Message,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        body_chunks: List[str] = []
        attachments: List[Dict[str, Any]] = []

        if msg.is_multipart():
            for part in msg.walk():
                try:
                    content_disposition = cls._safe_lower(part.get("Content-Disposition"))
                    content_type = cls._safe_lower(part.get_content_type())
                    filename = cls._decode_header_value(part.get_filename())

                    if "attachment" in content_disposition or filename:
                        payload_bytes = part.get_payload(decode=True)
                        if not isinstance(payload_bytes, bytes):
                            payload_bytes = cls._safe_decode(payload_bytes).encode("utf-8", errors="replace")
                        attachments.append(
                            {
                                "filename": filename,
                                "content_type": content_type,
                                "size": len(payload_bytes),
                            }
                        )
                        continue

                    if content_type == "text/plain":
                        payload_bytes = part.get_payload(decode=True)
                        if payload_bytes is None:
                            payload_bytes = part.get_payload()
                        body_chunks.append(
                            cls._safe_decode(payload_bytes, part.get_content_charset() or "utf-8")
                        )

                    elif content_type == "text/html" and not body_chunks:
                        payload_bytes = part.get_payload(decode=True)
                        if payload_bytes is None:
                            payload_bytes = part.get_payload()
                        html_text = cls._safe_decode(payload_bytes, part.get_content_charset() or "utf-8")
                        body_chunks.append(cls._strip_html(html_text))
                except Exception as exc:
                    logger.warning("Failed to parse email part: %s", exc)
                    continue
        else:
            payload_bytes = msg.get_payload(decode=True)
            if payload_bytes is None:
                payload_bytes = msg.get_payload()
            body_chunks.append(cls._safe_decode(payload_bytes, msg.get_content_charset() or "utf-8"))

        return "\n".join([chunk for chunk in body_chunks if chunk]).strip(), attachments

    @classmethod
    def _strip_html(cls, html_text: Any) -> str:
        text = cls._safe_decode(html_text)
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<br\s*/?>", "\n", text)
        text = re.sub(r"(?s)</p>", "\n", text)
        text = re.sub(r"(?s)<.*?>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @classmethod
    def _extract_quotes_from_messages(
        cls,
        messages: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        quotes: List[Dict[str, Any]] = []

        expected_items = payload.get("items") or payload.get("line_items") or []
        default_description = ""
        if isinstance(expected_items, list) and expected_items:
            first_item = expected_items[0]
            if isinstance(first_item, dict):
                default_description = cls._safe_str(first_item.get("description"))

        for message in messages:
            subject = cls._safe_str(message.get("subject"))
            body_text = cls._safe_str(message.get("body_text"))
            from_email = cls._safe_str(message.get("from_email"))
            from_name = cls._safe_str(message.get("from_name"))
            received_at = cls._safe_str(message.get("date")) or datetime.now(timezone.utc).isoformat()
            attachments = message.get("attachments") or []

            quote_reference = cls._extract_quote_reference(subject, body_text, attachments)
            parsed_items = cls._extract_items_from_text(body_text, default_description=default_description)

            if not parsed_items:
                parsed_items = cls._build_fallback_items_from_payload(payload)

            envelope = SupplierQuoteEnvelope(
                supplier_name=from_name or from_email or "Unknown Supplier",
                supplier_email=from_email,
                quote_reference=quote_reference,
                subject=subject,
                received_at=received_at,
                items=parsed_items,
                attachment_filenames=[
                    cls._safe_str(item.get("filename"))
                    for item in attachments
                    if isinstance(item, dict) and cls._safe_str(item.get("filename"))
                ],
                message_id=cls._safe_str(message.get("message_id")),
            )
            quotes.append(envelope.to_dict())

        return quotes

    @classmethod
    def _extract_quote_reference(
        cls,
        subject: Any,
        body_text: Any,
        attachments: List[Dict[str, Any]],
    ) -> str:
        patterns = [
            r"\b(?:quote|quotation|ref|reference)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/\-_.]{2,})\b",
            r"\b([A-Z]{2,}[-/][A-Z0-9][A-Z0-9/\-_.]{2,})\b",
        ]
        search_spaces = [cls._safe_str(subject), cls._safe_str(body_text)]

        for attachment in attachments or []:
            if not isinstance(attachment, dict):
                continue
            filename = cls._safe_str(attachment.get("filename"))
            if filename:
                search_spaces.append(filename)

        for text in search_spaces:
            for pattern in patterns:
                match = re.search(pattern, text or "", flags=re.IGNORECASE)
                if match:
                    return cls._safe_str(match.group(1))

        return ""

    @classmethod
    def _extract_items_from_text(cls, body_text: Any, default_description: str = "") -> List[SupplierQuoteLine]:
        text = cls._safe_str(body_text)
        if not text:
            return []

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        extracted: List[SupplierQuoteLine] = []

        line_pattern = re.compile(
            r"(?P<description>[A-Za-z0-9\s\-/(),.&]+?)\s+"
            r"(?P<qty>\d+(?:\.\d+)?)\s+"
            r"(?P<unit>[A-Za-z]+)\s+"
            r"(?P<unit_price>R?\s?\d[\d,]*(?:\.\d{1,2})?)\s+"
            r"(?P<total>R?\s?\d[\d,]*(?:\.\d{1,2})?)$",
            flags=re.IGNORECASE,
        )

        for line in lines:
            match = line_pattern.search(line)
            if not match:
                continue

            description = cls._safe_str(match.group("description")) or default_description or "Quoted item"
            quantity = cls._to_float(match.group("qty"), 1.0)
            unit = cls._normalize_unit(match.group("unit"))
            unit_price = cls._to_float(match.group("unit_price"), 0.0)
            line_total = cls._to_float(match.group("total"), unit_price * quantity)

            extracted.append(
                SupplierQuoteLine(
                    description=description,
                    quantity=quantity if quantity > 0 else 1.0,
                    unit=unit,
                    unit_price=round(unit_price, 2),
                    line_total=round(line_total, 2),
                    item_code="",
                )
            )

        return extracted

    @classmethod
    def _build_fallback_items_from_payload(cls, payload: Dict[str, Any]) -> List[SupplierQuoteLine]:
        items = payload.get("items") or payload.get("line_items") or []
        output: List[SupplierQuoteLine] = []

        if not isinstance(items, list):
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue

            description = cls._safe_str(item.get("description") or item.get("item_description") or item.get("name"))
            if not description:
                continue

            quantity = cls._to_float(item.get("quantity") or item.get("qty") or 1, 1.0)
            unit = cls._normalize_unit(item.get("unit") or item.get("uom") or item.get("unit_of_measure") or "Each")
            unit_price = cls._to_float(
                item.get("supplier_unit_cost")
                or item.get("unit_cost")
                or item.get("unit_price")
                or item.get("price")
                or 0,
                0.0,
            )
            line_total = round(unit_price * quantity, 2) if unit_price > 0 else 0.0

            output.append(
                SupplierQuoteLine(
                    description=description,
                    quantity=quantity if quantity > 0 else 1.0,
                    unit=unit,
                    unit_price=round(unit_price, 2),
                    line_total=line_total,
                    item_code=cls._safe_str(item.get("item_code")),
                )
            )

        return output

    @classmethod
    def _normalize_supplier_quotes(cls, quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized_quotes: List[Dict[str, Any]] = []

        if not isinstance(quotes, list):
            return []

        for quote in quotes:
            if not isinstance(quote, dict):
                continue

            supplier_name = cls._safe_str(quote.get("supplier_name"), "Unknown Supplier")
            supplier_email = cls._safe_str(quote.get("supplier_email"))
            quote_reference = cls._safe_str(
                quote.get("quote_reference")
                or quote.get("quote_number")
                or quote.get("reference")
            )
            subject = cls._safe_str(quote.get("subject"))
            received_at = cls._safe_str(quote.get("received_at")) or datetime.now(timezone.utc).isoformat()
            attachment_filenames = quote.get("attachment_filenames") or []
            if not isinstance(attachment_filenames, list):
                attachment_filenames = [attachment_filenames]

            raw_items = quote.get("items") or quote.get("line_items") or []
            if not isinstance(raw_items, list):
                raw_items = []

            normalized_items: List[Dict[str, Any]] = []

            for idx, item in enumerate(raw_items, start=1):
                if isinstance(item, SupplierQuoteLine):
                    normalized_items.append(item.to_dict())
                    continue

                if not isinstance(item, dict):
                    continue

                description = cls._safe_str(
                    item.get("description")
                    or item.get("item_description")
                    or item.get("name")
                    or f"Item {idx}"
                )
                quantity = cls._to_float(item.get("quantity") or item.get("qty") or 1, 1.0)
                if quantity <= 0:
                    quantity = 1.0

                unit = cls._normalize_unit(
                    item.get("unit")
                    or item.get("uom")
                    or item.get("unit_of_measure")
                    or "Each"
                )
                unit_price = cls._to_float(
                    item.get("unit_price")
                    or item.get("unit_cost")
                    or item.get("supplier_unit_cost")
                    or item.get("price")
                    or item.get("rate")
                    or 0,
                    0.0,
                )
                line_total = cls._to_float(
                    item.get("line_total")
                    or item.get("amount")
                    or item.get("total_price")
                    or 0,
                    0.0,
                )
                if line_total <= 0 and unit_price > 0:
                    line_total = round(unit_price * quantity, 2)
                if unit_price <= 0 and line_total > 0 and quantity > 0:
                    unit_price = round(line_total / quantity, 2)

                normalized_items.append(
                    {
                        "description": description,
                        "quantity": round(quantity, 2),
                        "unit": unit,
                        "unit_price": round(unit_price, 2),
                        "line_total": round(line_total, 2),
                        "item_code": cls._safe_str(item.get("item_code")),
                    }
                )

            normalized_quotes.append(
                {
                    "supplier_name": supplier_name,
                    "supplier_email": supplier_email,
                    "quote_reference": quote_reference,
                    "quote_number": quote_reference,
                    "reference": quote_reference,
                    "subject": subject,
                    "received_at": received_at,
                    "attachment_filenames": [
                        cls._safe_str(name) for name in attachment_filenames if cls._safe_str(name)
                    ],
                    "items": normalized_items,
                    "line_items": deepcopy(normalized_items),
                }
            )

        return cls._dedupe_quotes(normalized_quotes)


def ingest_supplier_quotes(payload: Dict[str, Any]) -> Dict[str, Any]:
    return SupplierQuoteIngestionService.ingest_supplier_quotes(payload)
