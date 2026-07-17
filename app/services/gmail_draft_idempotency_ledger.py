from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from app.services.gmail_draft_transport_service import (
    DraftMessage,
    GmailDraftRequest,
    GmailDraftTransportService,
    GmailDraftValidationError,
    dataclass_to_dict,
)
from app.services.supplier_outreach_service import DEFAULT_MANDATORY_CC, DEFAULT_SUPPLIER_MAILBOX


LEDGER_SCHEMA_VERSION = "GMAIL_DRAFT_IDEMPOTENCY_LEDGER_V1"
VALIDATION_NAME = "gmail-real-draft-validation-6000080579"
CONTROLLED_WARNING = "THIS IS A CONTROLLED LMCP AUTOQUOTE GMAIL DRAFT-ONLY VALIDATION. DO NOT SEND."
EXPECTED_RFQ_REFERENCE = "6000080579"
EXPECTED_REQUEST_ID = "LMCP-SRFQ-6000080579-341E812698"
EXPECTED_STANDARDS = ["SANS 1028", "ISO 6787", "SANS 1211", "SANS 387"]
EXPECTED_QUANTITY_TEXT = [
    "327 | Straight Pipe Wrench 350 mm Heavy Duty | 80 | EA",
    "315 | Shifting/Open-End Adjustable Spanner 250 mm Heavy Duty | 50 | EA",
    "302 | Club Hammer 1.8 kg Steel-Reinforced Polymer Handle | 224 | EA",
    "328 | Straight Pipe Wrench 450 mm Heavy Duty | 280 | EA",
    "1304 | Cold Flat Chisel 200 mm x 20 mm | 40 | EA",
    "316 | Shifting/Open-End Adjustable Spanner 300 mm Heavy Duty | 40 | EA",
]
FORBIDDEN_DISCLOSURE_TERMS = ["internal cost", "markup", "margin", "profit"]
CLARIFICATION_SUBJECT_ALIASES = ["Clarification", "Clarification Request"]


@dataclass
class DraftResolutionResult:
    draft_type: str
    idempotency_key: str
    reference: Any
    message: DraftMessage
    new_draft_created: bool
    canonical_reused: bool
    duplicate_suppressed: bool
    duplicates_detected: int
    stale_ledger_reference: bool
    validation_errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "draft_type": self.draft_type,
            "idempotency_key_hash": stable_hash(self.idempotency_key),
            "reference": dataclass_to_dict(self.reference),
            "summary": dataclass_to_dict(self.message.summary),
            "new_draft_created": self.new_draft_created,
            "canonical_reused": self.canonical_reused,
            "duplicate_suppressed": self.duplicate_suppressed,
            "duplicates_detected": self.duplicates_detected,
            "stale_ledger_reference": self.stale_ledger_reference,
            "validation_errors": self.validation_errors,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redacted_hash(value: str) -> str:
    if not value:
        return ""
    return "redacted-" + stable_hash(value)[:12]


def stable_validation_key(rfq_reference: str, request_id: str, draft_type: str) -> str:
    return f"gmail-real-draft-validation:{rfq_reference}:{request_id}:{draft_type}"


def canonical_idempotency_key(
    *,
    mailbox: str,
    rfq_id: str,
    supplier_identity: str,
    operation: str,
    recipients: Sequence[str],
    cc: Sequence[str],
    subject: str,
    body: str,
) -> str:
    payload = {
        "mailbox": _normalise_email(mailbox),
        "rfq_id": _normalise_text(rfq_id),
        "supplier_identity": _normalise_email(supplier_identity),
        "operation": _normalise_text(operation).lower(),
        "recipients": sorted(_normalise_addresses(recipients)),
        "cc": sorted(_normalise_addresses(cc)),
        "subject": _normalise_text(subject),
        "body_fingerprint": stable_hash(_normalise_text(body)),
    }
    return stable_hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def canonical_key_for_request(mailbox: str, request: GmailDraftRequest, operation: str) -> str:
    return canonical_idempotency_key(
        mailbox=mailbox,
        rfq_id=request.rfq_id,
        supplier_identity=",".join(sorted(_normalise_addresses(request.to))),
        operation=operation,
        recipients=request.to,
        cc=request.cc,
        subject=request.subject,
        body=request.body_text,
    )


def content_checksum_for_request(request: GmailDraftRequest) -> str:
    body = _normalise_text(request.body_text)
    return stable_hash("\n".join([request.subject, body, request.supplier_request_id, request.rfq_id, request.email_type]))


def attachment_manifest_checksum(request: GmailDraftRequest) -> str:
    manifest = [
        {
            "filename": attachment.filename,
            "mime_type": attachment.mime_type,
            "checksum": attachment.checksum,
            "size": attachment.size,
            "logical_document_type": attachment.logical_document_type,
        }
        for attachment in request.attachments
    ]
    return stable_hash(json.dumps(manifest, sort_keys=True))


def load_ledger(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "validation_name": VALIDATION_NAME,
            "rfq_reference": EXPECTED_RFQ_REFERENCE,
            "sourcing_request_id": EXPECTED_REQUEST_ID,
            "entries": {},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            raise GmailDraftValidationError(f"Empty draft idempotency ledger: {path}")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GmailDraftValidationError(f"Invalid draft idempotency ledger JSON: {path}") from exc
    data.setdefault("entries", {})
    data.setdefault("schema_version", LEDGER_SCHEMA_VERSION)
    data.setdefault("validation_name", VALIDATION_NAME)
    return data


def load_ledger_with_status(path: Path) -> Tuple[Dict[str, Any], bool, str]:
    try:
        return load_ledger(path), False, ""
    except GmailDraftValidationError as exc:
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "validation_name": VALIDATION_NAME,
            "rfq_reference": EXPECTED_RFQ_REFERENCE,
            "sourcing_request_id": EXPECTED_REQUEST_ID,
            "entries": {},
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "corrupt_previous_ledger": True,
        }, True, str(exc)


def save_ledger_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["updated_at"] = utc_now()
    fd, tmp_name = tempfile.mkstemp(prefix=".draft-ledger-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


@contextmanager
def locked_ledger(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    handle = lock_path.open("a+")
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        os.chmod(lock_path, 0o600)
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass
        handle.close()


def resolve_or_create_draft(
    *,
    service: GmailDraftTransportService,
    ledger: Dict[str, Any],
    draft_type: str,
    request: GmailDraftRequest,
    expected_subject: str,
    allow_create: bool = True,
) -> DraftResolutionResult:
    key = request.idempotency_key or stable_validation_key(EXPECTED_RFQ_REFERENCE, EXPECTED_REQUEST_ID, draft_type)
    expected = _expected_payload(draft_type, request, expected_subject)
    entries = ledger.setdefault("entries", {})
    stale = False

    entry = entries.get(key) or {}
    raw_reference = str(entry.get("raw_gmail_draft_reference") or "")
    if raw_reference:
        try:
            message = service.get_draft(service.remember_draft_reference(raw_reference))
            errors = validate_message(message, expected)
            if not errors:
                _write_entry(service, entries, key, draft_type, request, message, expected, "reused_from_ledger")
                return DraftResolutionResult(draft_type, key, message.reference, message, False, True, True, 0, False, [])
            stale = True
        except Exception:
            stale = True

    candidates = discover_matching_drafts(service, draft_type=draft_type, expected=expected)
    if candidates:
        canonical, duplicates = select_canonical_draft(candidates)
        _write_entry(service, entries, key, draft_type, request, canonical, expected, "adopted_existing_draft")
        return DraftResolutionResult(
            draft_type,
            key,
            canonical.reference,
            canonical,
            False,
            True,
            bool(entry),
            len(duplicates),
            stale,
            [],
        )

    if not allow_create:
        raise GmailDraftValidationError(f"No canonical Gmail draft found for {draft_type}; creation blocked by safe idempotency policy.")
    reference = service.create_draft(request)
    message = service.get_draft(reference)
    errors = validate_message(message, expected)
    if errors:
        raise GmailDraftValidationError(f"Created Gmail draft failed validation for {draft_type}: {errors}")
    _write_entry(service, entries, key, draft_type, request, message, expected, "created_new_draft")
    return DraftResolutionResult(draft_type, key, reference, message, True, False, False, 0, stale, [])


def discover_matching_drafts(
    service: GmailDraftTransportService,
    *,
    draft_type: str,
    expected: Dict[str, Any],
) -> List[DraftMessage]:
    matches: List[DraftMessage] = []
    for message in service.list_draft_messages():
        if not validate_message(message, expected):
            matches.append(message)
    return matches


def expected_payload_for_request(draft_type: str, request: GmailDraftRequest, expected_subject: str) -> Dict[str, Any]:
    return _expected_payload(draft_type, request, expected_subject)


def select_canonical_draft(candidates: Sequence[DraftMessage]) -> Tuple[DraftMessage, List[DraftMessage]]:
    ordered = sorted(
        candidates,
        key=lambda message: (
            message.reference.created_timestamp or "",
            message.reference.redacted_draft_reference or "",
            message.summary.subject or "",
        ),
    )
    return ordered[0], list(ordered[1:])


def validate_message(message: DraftMessage, expected: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    body = _normalise_text(message.body_text)
    if message.summary.draft_status != "DRAFT":
        errors.append("not_draft_state")
    if not _subject_matches(message.summary.subject, expected):
        errors.append("subject_mismatch")
    if _normalise_addresses(message.summary.recipient) != [DEFAULT_SUPPLIER_MAILBOX]:
        errors.append("recipient_mismatch")
    if _normalise_addresses(message.summary.cc) != [DEFAULT_MANDATORY_CC]:
        errors.append("mandatory_cc_mismatch")
    if message.decoded_headers.get("bcc"):
        errors.append("bcc_present")
    if EXPECTED_REQUEST_ID not in body and message.summary.supplier_request_id != EXPECTED_REQUEST_ID:
        errors.append("request_id_missing")
    if EXPECTED_RFQ_REFERENCE not in body:
        errors.append("rfq_reference_missing")
    if CONTROLLED_WARNING not in body:
        errors.append("controlled_warning_missing")
    if expected["draft_type"] != "clarification":
        for text in EXPECTED_QUANTITY_TEXT:
            if text not in body:
                errors.append(f"quantity_missing:{text.split(' | ')[0]}")
        for standard in EXPECTED_STANDARDS:
            if standard not in body:
                errors.append(f"standard_missing:{standard}")
        for phrase in ["offered brand", "manufacturer datasheet", "sample may be requested"]:
            if phrase not in body.lower():
                errors.append(f"requirement_missing:{phrase}")
    else:
        for phrase in ["offered brand", "manufacturer datasheet", "delivery period", "formal supplier quotation"]:
            if phrase not in body.lower():
                errors.append(f"clarification_field_missing:{phrase}")
    for term in FORBIDDEN_DISCLOSURE_TERMS:
        if term in body.lower():
            errors.append(f"internal_pricing_disclosure:{term}")
    if message.summary.attachment_count != expected["attachment_count"]:
        errors.append("attachment_count_mismatch")
    checksum_matches = stable_hash(_normalise_text(message.summary.subject) + "\n" + body) == expected["stored_content_checksum"]
    if not checksum_matches and not _semantic_checksum_optional(message, expected, body):
        errors.append("content_checksum_mismatch")
    return errors


def diagnose_message(message: DraftMessage, expected: Dict[str, Any]) -> Dict[str, Any]:
    errors = validate_message(message, expected)
    body = _normalise_text(message.body_text)
    return {
        "redacted_reference": message.reference.redacted_draft_reference,
        "subject_hash": stable_hash(_normalise_text(message.summary.subject))[:16],
        "body_hash": stable_hash(body)[:16],
        "body_length": len(body),
        "subject": message.summary.subject,
        "to_count": len(message.summary.recipient),
        "cc_count": len(message.summary.cc),
        "attachment_count": message.summary.attachment_count,
        "draft_status": message.summary.draft_status,
        "has_warning": CONTROLLED_WARNING in body,
        "has_request_id": EXPECTED_REQUEST_ID in body or message.summary.supplier_request_id == EXPECTED_REQUEST_ID,
        "has_rfq_reference": EXPECTED_RFQ_REFERENCE in body,
        "has_idempotency_header": bool(message.decoded_headers.get("draft_idempotency_key")),
        "checksum_matches": stable_hash(_normalise_text(message.summary.subject) + "\n" + body) == expected["stored_content_checksum"],
        "failed_predicates": errors,
        "materially_equivalent": not errors,
    }


def _write_entry(
    service: GmailDraftTransportService,
    entries: Dict[str, Any],
    key: str,
    draft_type: str,
    request: GmailDraftRequest,
    message: DraftMessage,
    expected: Dict[str, Any],
    status: str,
) -> None:
    raw_reference = service.raw_reference_for_redacted(message.reference.redacted_draft_reference)
    entries[key] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "validation_name": VALIDATION_NAME,
        "authorised_mailbox": DEFAULT_SUPPLIER_MAILBOX,
        "rfq_reference": EXPECTED_RFQ_REFERENCE,
        "sourcing_request_id": EXPECTED_REQUEST_ID,
        "idempotency_key": key,
        "idempotency_key_hash": stable_hash(key),
        "draft_type": draft_type,
        "expected_subject": expected["subject"],
        "redacted_gmail_draft_reference": message.reference.redacted_draft_reference,
        "redacted_gmail_message_reference": message.reference.redacted_message_reference,
        "raw_gmail_draft_reference": raw_reference,
        "canonical_supplier_email": ",".join(sorted(_normalise_addresses(request.to))),
        "canonical_recipient_set": sorted(_normalise_addresses(request.to)),
        "canonical_cc_set": sorted(_normalise_addresses(request.cc)),
        "canonical_subject_fingerprint": stable_hash(_normalise_text(expected["subject"])),
        "creation_timestamp": message.reference.created_timestamp,
        "last_verification_timestamp": utc_now(),
        "current_status": status,
        "attachment_manifest_checksum": attachment_manifest_checksum(request),
        "message_content_checksum": expected["content_checksum"],
        "stored_content_checksum": expected["stored_content_checksum"],
    }
def _expected_payload(draft_type: str, request: GmailDraftRequest, expected_subject: str) -> Dict[str, Any]:
    body = _normalise_text(request.body_text)
    return {
        "draft_type": draft_type,
        "subject": expected_subject,
        "subject_aliases": _subject_aliases_for(draft_type, expected_subject),
        "attachment_count": len(request.attachments),
        "content_checksum": content_checksum_for_request(request),
        "stored_content_checksum": stable_hash(_normalise_text(expected_subject) + "\n" + body),
    }


def _subject_matches(subject: str, expected: Dict[str, Any]) -> bool:
    normalised = _normalise_text(subject)
    if normalised == _normalise_text(expected["subject"]):
        return True
    return normalised in expected.get("subject_aliases", [])


def _subject_aliases_for(draft_type: str, expected_subject: str) -> List[str]:
    if draft_type != "clarification":
        return []
    aliases = []
    for label in CLARIFICATION_SUBJECT_ALIASES:
        aliases.append(f"LMCP CONTROLLED DRAFT TEST — DO NOT SEND | {label} | {EXPECTED_RFQ_REFERENCE} | {EXPECTED_REQUEST_ID}")
    return sorted(set(aliases + [expected_subject]))


def _semantic_checksum_optional(message: DraftMessage, expected: Dict[str, Any], body: str) -> bool:
    if expected.get("draft_type") != "clarification":
        return False
    lower = body.lower()
    required = [
        CONTROLLED_WARNING.lower(),
        EXPECTED_REQUEST_ID.lower(),
        EXPECTED_RFQ_REFERENCE.lower(),
        "offered brand",
        "manufacturer datasheet",
        "delivery period",
        "formal supplier quotation",
    ]
    return all(text in lower for text in required)


def _normalise_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip().split("\n"))


def _normalise_addresses(values: Sequence[str]) -> List[str]:
    return [str(value).strip().lower() for value in values or [] if str(value).strip()]


def _normalise_email(value: str) -> str:
    return str(value or "").strip().lower()
