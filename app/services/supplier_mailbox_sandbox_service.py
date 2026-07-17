from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.services.supplier_outreach_service import (
    DEFAULT_MANDATORY_CC,
    DEFAULT_SUPPLIER_MAILBOX,
    EMAIL_TYPE_CLARIFICATION,
    RESPONSE_COVERAGE_NONE_FALLBACK,
    build_followup_model,
    build_no_response_pricing_state,
    build_supplier_outreach_status,
    enforce_mandatory_cc,
)


VALID_SUPPLIER_QUOTATION = "VALID_SUPPLIER_QUOTATION"
SUPPLIER_RESPONSE_INCOMPLETE = "SUPPLIER_RESPONSE_INCOMPLETE"
SUPPLIER_DECLINED = "SUPPLIER_DECLINED"
PERMANENT_BOUNCE = "PERMANENT_BOUNCE"
UNRELATED_EMAIL = "UNRELATED_EMAIL"
DUPLICATE_RESPONSE = "DUPLICATE_RESPONSE"

MATCH_REQUEST_ID_EXACT = "REQUEST_ID_EXACT"
MATCH_EMAIL_THREAD_EXACT = "EMAIL_THREAD_EXACT"
MATCH_RFQ_AND_SUPPLIER = "RFQ_AND_SUPPLIER_MATCH"
MATCH_QUOTATION_REFERENCE = "QUOTATION_REFERENCE_MATCH"
MATCH_AMBIGUOUS = "AMBIGUOUS_OPERATOR_REVIEW"
MATCH_UNMATCHED = "UNMATCHED"

SAFE_ATTACHMENT_MIME_PREFIXES = ("application/pdf", "image/", "text/")
SAFE_ATTACHMENT_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/json",
}
UNSAFE_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".js", ".vbs", ".scr", ".ps1"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalise_email(value: Any) -> str:
    text = _safe_str(value).lower()
    match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    return match.group(0) if match else text


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _safe_str(value).lower() in {"true", "yes", "1", "y"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha256("|".join(_safe_str(part) for part in parts).encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _body_text(message: EmailMessage) -> str:
    if message.is_multipart():
        chunks: List[str] = []
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                try:
                    chunks.append(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    chunks.append(payload.decode("utf-8", errors="replace"))
        return "\n".join(chunks)
    try:
        return message.get_content()
    except Exception:
        payload = message.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def _headers_to_list(value: Any) -> List[str]:
    return [item.strip() for item in _safe_str(value).split(",") if item.strip()]


def build_outbound_mime(email_model: Dict[str, Any], *, message_id: str, thread_id: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = _safe_str(email_model.get("from") or DEFAULT_SUPPLIER_MAILBOX)
    msg["To"] = _safe_str(email_model.get("to"))
    msg["Cc"] = ", ".join(enforce_mandatory_cc(email_model.get("cc") or []))
    msg["Subject"] = _safe_str(email_model.get("subject"))
    msg["Message-ID"] = message_id
    msg["X-LMCP-Thread-ID"] = thread_id
    msg["X-LMCP-Sourcing-Request-ID"] = _safe_str(email_model.get("request_id"))
    msg["X-LMCP-Sandbox"] = "true"
    msg.set_content(_safe_str(email_model.get("body")))
    return msg


def build_inbound_mime(
    *,
    from_addr: str,
    to_addr: str,
    cc: Optional[Sequence[str]],
    subject: str,
    body: str,
    message_id: str,
    thread_id: str = "",
    in_reply_to: str = "",
    attachments: Optional[Sequence[Tuple[str, str, bytes]]] = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Cc"] = ", ".join(cc or [])
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    if thread_id:
        msg["X-LMCP-Thread-ID"] = thread_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    for filename, mime_type, payload in attachments or []:
        maintype, subtype = (mime_type.split("/", 1) + ["octet-stream"])[:2]
        msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def parse_mime_message(path: Path) -> Dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    body = _body_text(message)
    attachments: List[Dict[str, Any]] = []
    for part in message.walk():
        if part.get_content_disposition() != "attachment":
            continue
        payload = part.get_payload(decode=True) or b""
        attachments.append({
            "filename": part.get_filename() or "attachment",
            "mime_type": part.get_content_type(),
            "size": len(payload),
            "sha256": _sha256_bytes(payload),
            "payload": payload,
        })
    return {
        "path": str(path),
        "message_id": _safe_str(message.get("Message-ID")),
        "thread_id": _safe_str(message.get("X-LMCP-Thread-ID")),
        "in_reply_to": _safe_str(message.get("In-Reply-To")),
        "references": _safe_str(message.get("References")),
        "from": _safe_str(message.get("From")),
        "to": _headers_to_list(message.get("To")),
        "cc": _headers_to_list(message.get("Cc")),
        "subject": _safe_str(message.get("Subject")),
        "body": body,
        "attachments": attachments,
    }


def match_supplier_response(
    parsed_message: Dict[str, Any],
    request_context: Dict[str, Any],
) -> Dict[str, Any]:
    subject_body = f"{parsed_message.get('subject', '')}\n{parsed_message.get('body', '')}"
    request_id = _safe_str(request_context.get("request_id"))
    rfq_reference = _safe_str(request_context.get("reference_number"))
    supplier_emails = {_normalise_email(supplier.get("supplier_email")) for supplier in request_context.get("suppliers") or []}
    sender = _normalise_email(parsed_message.get("from"))
    outbound_message_ids = set(request_context.get("outbound_message_ids") or [])
    outbound_thread_ids = set(request_context.get("thread_ids") or [])
    quotation_ref_match = re.search(r"\b(?:quote|quotation)\s*(?:no\.?|reference|ref)?\s*[:#-]?\s*([A-Z0-9\-_/]+)", subject_body, re.I)

    if request_id and request_id in subject_body:
        return {"method": MATCH_REQUEST_ID_EXACT, "confidence": 1.0, "associated": True}
    if parsed_message.get("in_reply_to") in outbound_message_ids or parsed_message.get("thread_id") in outbound_thread_ids:
        return {"method": MATCH_EMAIL_THREAD_EXACT, "confidence": 0.95, "associated": True}
    if rfq_reference and rfq_reference in subject_body and sender in supplier_emails:
        return {"method": MATCH_RFQ_AND_SUPPLIER, "confidence": 0.85, "associated": True}
    if quotation_ref_match and sender in supplier_emails:
        return {
            "method": MATCH_QUOTATION_REFERENCE,
            "confidence": 0.65,
            "associated": True,
            "quotation_reference": quotation_ref_match.group(1),
        }
    if rfq_reference and rfq_reference in subject_body:
        return {"method": MATCH_AMBIGUOUS, "confidence": 0.35, "associated": False}
    return {"method": MATCH_UNMATCHED, "confidence": 0.0, "associated": False}


def classify_attachment(filename: str, mime_type: str) -> Dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    lower = filename.lower()
    unsafe = suffix in UNSAFE_EXTENSIONS or mime_type == "application/x-msdownload"
    if unsafe:
        return {"document_type": "unsafe_attachment", "safe": False, "parsing_status": "REJECTED_UNSAFE_TYPE"}
    if "datasheet" in lower:
        return {"document_type": "manufacturer_datasheet", "safe": True, "parsing_status": "CAPTURED_METADATA_ONLY"}
    if "quote" in lower or "quotation" in lower:
        return {"document_type": "formal_supplier_quotation", "safe": True, "parsing_status": "CAPTURED_METADATA_ONLY"}
    if "schedule" in lower or suffix in {".xls", ".xlsx", ".csv"}:
        return {"document_type": "supplier_pricing_schedule", "safe": True, "parsing_status": "CAPTURED_METADATA_ONLY"}
    if "cert" in lower or "compliance" in lower:
        return {"document_type": "compliance_certificate", "safe": True, "parsing_status": "CAPTURED_METADATA_ONLY"}
    if mime_type.startswith("image/"):
        return {"document_type": "product_image_or_sheet", "safe": True, "parsing_status": "CAPTURED_METADATA_ONLY"}
    if mime_type.startswith(SAFE_ATTACHMENT_MIME_PREFIXES) or mime_type in SAFE_ATTACHMENT_MIME_TYPES:
        return {"document_type": "supplier_attachment", "safe": True, "parsing_status": "CAPTURED_METADATA_ONLY"}
    return {"document_type": "unsupported_attachment", "safe": False, "parsing_status": "REJECTED_UNSUPPORTED_TYPE"}


def capture_attachment_manifest(
    parsed_message: Dict[str, Any],
    *,
    attachment_root: Path,
    linked_sourcing_groups: Sequence[str],
    seen_checksums: Optional[set] = None,
    received_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    attachment_root.mkdir(parents=True, exist_ok=True)
    quarantine_root = attachment_root / "quarantine"
    quarantine_root.mkdir(parents=True, exist_ok=True)
    seen_checksums = seen_checksums if seen_checksums is not None else set()
    received_at = received_at or _now_utc()
    manifest: List[Dict[str, Any]] = []
    for attachment in parsed_message.get("attachments") or []:
        filename = _safe_str(attachment.get("filename") or "attachment")
        payload = attachment.get("payload") if isinstance(attachment.get("payload"), bytes) else b""
        checksum = attachment.get("sha256") or _sha256_bytes(payload)
        mime_type = _safe_str(attachment.get("mime_type"))
        classification = classify_attachment(filename, mime_type)
        duplicate = checksum in seen_checksums
        if not duplicate:
            seen_checksums.add(checksum)
        target_dir = quarantine_root if not classification["safe"] else attachment_root
        target_path = target_dir / f"{checksum[:12]}-{Path(filename).name}"
        if not duplicate:
            target_path.write_bytes(payload)
        manifest.append({
            "original_filename": filename,
            "mime_type": mime_type,
            "size": len(payload),
            "checksum": checksum,
            "source_message_id": parsed_message.get("message_id"),
            "received_timestamp": _iso(received_at),
            "inferred_document_type": classification["document_type"],
            "linked_sourcing_groups": list(linked_sourcing_groups),
            "parsing_status": "DUPLICATE_ATTACHMENT" if duplicate else classification["parsing_status"],
            "operator_review_required": not classification["safe"],
            "safe": classification["safe"],
            "duplicate": duplicate,
            "stored_path": "" if duplicate else str(target_path),
        })
    return manifest


def parse_supplier_quotation_fields(parsed_message: Dict[str, Any], attachment_manifest: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    body = parsed_message.get("body") or ""
    lower = body.lower()
    items = re.findall(r"(?:material|item)\s+([0-9A-Za-z\-]+).*?(?:unit\s*price|price)\s*[:=]?\s*R?\s*([0-9,.]+)", body, re.I | re.S)
    offered_brands = re.findall(r"brand\s*[:=]\s*([A-Za-z0-9 .\-]+)", body, re.I)
    delivery = re.search(r"delivery\s*period\s*[:=]\s*([^\n]+)", body, re.I)
    validity = re.search(r"valid(?:ity)?\s*[:=]\s*([^\n]+)", body, re.I)
    quote_ref = re.search(r"(?:quotation|quote)\s*(?:number|no\.?|reference|ref)?\s*[:=]\s*([A-Z0-9\-_/]+)", body, re.I)
    supplier_name = re.search(r"supplier\s*(?:legal\s*)?name\s*[:=]\s*([^\n]+)", body, re.I)
    has_formal_quote = any(item.get("inferred_document_type") == "formal_supplier_quotation" for item in attachment_manifest)
    has_datasheet = any(item.get("inferred_document_type") == "manufacturer_datasheet" for item in attachment_manifest)
    missing: List[str] = []
    if not supplier_name:
        missing.append("supplier_legal_name")
    if len(items) < 6:
        missing.append("six_item_prices")
    if not offered_brands:
        missing.append("offered_brands")
    if not delivery:
        missing.append("delivery_period")
    if not validity:
        missing.append("quotation_validity")
    if not has_formal_quote:
        missing.append("formal_supplier_quotation_attachment")
    if not has_datasheet:
        missing.append("manufacturer_datasheet_attachment")
    return {
        "supplier_name": supplier_name.group(1).strip() if supplier_name else "",
        "supplier_email": _normalise_email(parsed_message.get("from")),
        "quotation_reference": quote_ref.group(1).strip() if quote_ref else "",
        "quotation_date": _extract_line_value(body, "quotation date"),
        "validity_period": validity.group(1).strip() if validity else "",
        "offered_brands": [brand.strip() for brand in offered_brands],
        "manufacturer": _extract_line_value(body, "manufacturer"),
        "model_or_part_numbers": re.findall(r"(?:model|part)\s*(?:no\.?|number)?\s*[:=]\s*([A-Za-z0-9\-_/]+)", body, re.I),
        "unit_prices": [{"item": item, "unit_price": price} for item, price in items],
        "total_prices": re.findall(r"total\s*(?:excluding vat|ex vat|incl vat)?\s*[:=]?\s*R?\s*([0-9,.]+)", body, re.I),
        "vat": _extract_line_value(body, "VAT"),
        "delivery_cost": _extract_line_value(body, "delivery cost"),
        "delivery_period": delivery.group(1).strip() if delivery else "",
        "stock_availability": _extract_line_value(body, "stock"),
        "warranty": _extract_line_value(body, "warranty"),
        "technical_document_coverage": {
            "formal_supplier_quotation": has_formal_quote,
            "manufacturer_datasheet": has_datasheet,
            "compliance_certificate": any(item.get("inferred_document_type") == "compliance_certificate" for item in attachment_manifest),
        },
        "line_matching_confidence": 0.9 if len(items) >= 6 else 0.45,
        "missing_fields": missing,
        "valid_supplier_quote": not missing,
    }


def _extract_line_value(text: str, label: str) -> str:
    pattern = re.compile(re.escape(label) + r"\s*[:=]\s*([^\n]+)", re.I)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def classify_supplier_response(
    parsed_message: Dict[str, Any],
    request_context: Dict[str, Any],
    attachment_manifest: Sequence[Dict[str, Any]],
    seen_message_keys: set,
) -> Dict[str, Any]:
    body = parsed_message.get("body") or ""
    message_key = _stable_id(
        "MSG",
        [
            parsed_message.get("message_id"),
            parsed_message.get("from"),
            parsed_message.get("subject"),
            parsed_message.get("body"),
        ],
    )
    match = match_supplier_response(parsed_message, request_context)
    if message_key in seen_message_keys:
        return {
            "message_key": message_key,
            "response_status": DUPLICATE_RESPONSE,
            "matching": match,
            "duplicate": True,
            "supplier_quote_created": False,
            "attachment_records_created": False,
        }
    seen_message_keys.add(message_key)
    if "delivery status notification" in _safe_str(parsed_message.get("subject")).lower() or "permanent failure" in body.lower():
        return {
            "message_key": message_key,
            "response_status": PERMANENT_BOUNCE,
            "matching": match,
            "supplier_contact_status": "permanent_bounce",
            "replacement_supplier_recommended": True,
        }
    if re.search(r"\b(decline|unable to quote|cannot quote|not quoting)\b", body, re.I):
        return {
            "message_key": message_key,
            "response_status": SUPPLIER_DECLINED,
            "matching": match,
            "supplier_contact_status": "declined",
            "replacement_supplier_recommended": True,
        }
    if not match.get("associated"):
        return {
            "message_key": message_key,
            "response_status": UNRELATED_EMAIL,
            "matching": match,
            "supplier_quote_created": False,
            "sourcing_status_changed": False,
        }
    parsed_quote = parse_supplier_quotation_fields(parsed_message, attachment_manifest)
    status = VALID_SUPPLIER_QUOTATION if parsed_quote.get("valid_supplier_quote") else SUPPLIER_RESPONSE_INCOMPLETE
    return {
        "message_key": message_key,
        "response_status": status,
        "matching": match,
        "supplier_quote_created": status == VALID_SUPPLIER_QUOTATION,
        "operator_review_required": status != VALID_SUPPLIER_QUOTATION,
        "parsed_supplier_quote": parsed_quote,
        "missing_fields": parsed_quote.get("missing_fields") or [],
    }


def evaluate_followup_eligibility(
    *,
    initial_email: Dict[str, Any],
    state: str,
    now: datetime,
    buyer_closing_at: Optional[datetime] = None,
    existing_followup_keys: Optional[set] = None,
) -> Dict[str, Any]:
    existing_followup_keys = existing_followup_keys if existing_followup_keys is not None else set()
    request_id = _safe_str(initial_email.get("request_id"))
    supplier_email = _normalise_email(initial_email.get("to"))
    due_at_text = _safe_str(initial_email.get("followup_due_at"))
    due_at = datetime.fromisoformat(due_at_text.replace("Z", "+00:00")) if due_at_text else now + timedelta(days=2)
    idempotency_key = _stable_id("FOLLOWUP1", [request_id, supplier_email, due_at.date().isoformat()])

    if buyer_closing_at is not None and now >= buyer_closing_at:
        return _followup_decision(False, "buyer_rfq_closed", due_at, idempotency_key)
    if state == VALID_SUPPLIER_QUOTATION:
        return _followup_decision(False, "valid_supplier_quotation_received", due_at, idempotency_key)
    if state == SUPPLIER_RESPONSE_INCOMPLETE:
        return _followup_decision(False, "clarification_required_instead_of_no_response_followup", due_at, idempotency_key, clarification_allowed=True)
    if state == SUPPLIER_DECLINED:
        return _followup_decision(False, "supplier_declined", due_at, idempotency_key, replacement_supplier_recommended=True)
    if state == PERMANENT_BOUNCE:
        return _followup_decision(False, "permanent_bounce", due_at, idempotency_key, replacement_supplier_recommended=True)
    if idempotency_key in existing_followup_keys:
        return _followup_decision(False, "duplicate_scheduler_execution_suppressed", due_at, idempotency_key)
    if now >= due_at:
        existing_followup_keys.add(idempotency_key)
        model = build_followup_model(initial_email, 1)
        model["idempotency_key"] = idempotency_key
        return {
            **_followup_decision(True, "no_response_followup_due", due_at, idempotency_key),
            "followup_model": model,
        }
    return _followup_decision(False, "not_due_yet", due_at, idempotency_key)


def _followup_decision(
    permitted: bool,
    reason: str,
    due_at: datetime,
    idempotency_key: str,
    *,
    clarification_allowed: bool = False,
    replacement_supplier_recommended: bool = False,
) -> Dict[str, Any]:
    return {
        "followup_permitted": permitted,
        "reason": reason,
        "followup_due_at": _iso(due_at),
        "idempotency_key": idempotency_key,
        "clarification_allowed": clarification_allowed,
        "replacement_supplier_recommended": replacement_supplier_recommended,
    }


def build_clarification_email_model(
    *,
    initial_email: Dict[str, Any],
    parsed_response: Dict[str, Any],
    missing_fields: Sequence[str],
) -> Dict[str, Any]:
    request_id = _safe_str(initial_email.get("request_id"))
    return {
        "email_type": EMAIL_TYPE_CLARIFICATION,
        "request_id": request_id,
        "from": initial_email.get("from"),
        "to": parsed_response.get("from"),
        "cc": enforce_mandatory_cc(initial_email.get("cc") or []),
        "subject": f"Clarification Required | Supplier RFQ | LMCP Request {request_id}",
        "body": "\n".join([
            "Dear Supplier,",
            "",
            f"Thank you for your response to LMCP supplier request {request_id}.",
            "Please provide the missing information below so the quotation can be assessed:",
            *[f"- {field}" for field in missing_fields],
            "",
            "Please retain the same request reference in your response.",
            "",
            "Regards,",
            "LMCP AutoQuote Supplier RFQ Desk",
        ]),
        "linked_response_message_id": parsed_response.get("message_id"),
        "live_email_sent": False,
        "exposes_internal_pricing": False,
    }


def build_mailbox_validation_no_response_state(status: Dict[str, Any]) -> Dict[str, Any]:
    state = build_no_response_pricing_state(status)
    state.update({
        "supplier_quote_coverage": RESPONSE_COVERAGE_NONE_FALLBACK,
        "buyer_quote_preparation_allowed": True,
        "buyer_autonomous_submission_enabled": False,
        "supplier_pricing_confirmed": False,
        "manual_pricing_review_required": True,
    })
    return state


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def safe_tmp_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    allowed_tmp_roots = [Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve()]
    repo_runtime = Path(__file__).resolve().parents[2] / "runtime"
    repo_runtime = repo_runtime.resolve()
    if resolved == repo_runtime or repo_runtime in resolved.parents:
        raise ValueError(f"Refusing production runtime output path: {resolved}")
    if not any(resolved == tmp_root or tmp_root in resolved.parents for tmp_root in allowed_tmp_roots):
        raise ValueError(f"Refusing non-temporary output path: {resolved}")
    return resolved


def build_mailbox_audit_event(
    *,
    request_id: str,
    rfq_id: str,
    message: Dict[str, Any],
    response_status: str,
    matching: Dict[str, Any],
    attachment_manifest: Sequence[Dict[str, Any]],
    event_type: str,
) -> Dict[str, Any]:
    return {
        "sourcing_request_id": request_id,
        "rfq_id": rfq_id,
        "message_id": message.get("message_id"),
        "thread_id": message.get("thread_id"),
        "sender": message.get("from"),
        "recipient": message.get("to"),
        "cc": message.get("cc"),
        "subject": message.get("subject"),
        "message_type": event_type,
        "timestamp": _iso(_now_utc()),
        "matching_method": matching.get("method"),
        "matching_confidence": matching.get("confidence"),
        "attachment_manifest": list(attachment_manifest),
        "response_status": response_status,
        "followup_state": "",
        "audit_action": "local_mime_simulation_only",
    }


def build_sandbox_status(
    *,
    supplier_count: int,
    minimum_supplier_target: int,
    valid_quotes_received: int,
    declined_requests: int,
    bounced_requests: int,
    followups_due: int,
) -> Dict[str, Any]:
    status = build_supplier_outreach_status(
        supplier_count=supplier_count,
        minimum_supplier_target=minimum_supplier_target,
        initial_email_count=supplier_count,
        followup_count=followups_due,
        sourcing_deadline=_iso(_now_utc() + timedelta(days=2)),
        pricing_cutoff=_iso(_now_utc() + timedelta(days=3)),
    )
    status.update({
        "initial_requests_sent": 0,
        "supplier_responses_received": valid_quotes_received + declined_requests + bounced_requests,
        "valid_quotes_received": valid_quotes_received,
        "declined_requests": declined_requests,
        "bounced_requests": bounced_requests,
        "pending_responses": max(0, supplier_count - valid_quotes_received - declined_requests - bounced_requests),
    })
    return status
