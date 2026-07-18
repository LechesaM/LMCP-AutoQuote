from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from email import policy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.services.gmail_oauth_provider import GmailAuthUnavailable, GmailOAuthProvider
from app.services.supplier_outreach_service import (
    DEFAULT_MANDATORY_CC,
    DEFAULT_SUPPLIER_MAILBOX,
    EMAIL_TYPE_CLARIFICATION,
    EMAIL_TYPE_FOLLOWUP_1,
    EMAIL_TYPE_INITIAL,
    enforce_mandatory_cc,
)


TRANSPORT_DISABLED = "DISABLED"
TRANSPORT_DRAFT_ONLY = "DRAFT_ONLY"
TRANSPORT_LIVE_SEND = "LIVE_SEND"
VALID_TRANSPORT_MODES = {TRANSPORT_DISABLED, TRANSPORT_DRAFT_ONLY, TRANSPORT_LIVE_SEND}
CONTROLLED_TEST_SUBJECT_PREFIX = "LMCP AUTOQUOTE CONTROLLED DRAFT TEST"
CONTROLLED_TEST_BODY_PREFIX = "THIS IS A CONTROLLED GMAIL DRAFT-ONLY VALIDATION. IT MUST NOT BE SENT TO A SUPPLIER."
SAFE_TEST_RECIPIENTS = {DEFAULT_SUPPLIER_MAILBOX.lower(), DEFAULT_MANDATORY_CC.lower()}
UNSAFE_ATTACHMENT_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".js", ".vbs", ".scr", ".ps1"}


class EmailTransportOperationBlocked(Exception):
    def __init__(self, operation: str, mode: str, reason: str, required_authority: str = "operator_controlled_authority"):
        super().__init__(f"{operation} blocked in {mode}: {reason}")
        self.operation = operation
        self.mode = mode
        self.reason = reason
        self.required_authority = required_authority

    def to_dict(self) -> Dict[str, str]:
        return {
            "operation": self.operation,
            "transport_mode": self.mode,
            "reason": self.reason,
            "required_authority": self.required_authority,
        }


class GmailDraftValidationError(ValueError):
    pass


@dataclass
class GmailAttachmentRequest:
    filename: str
    mime_type: str
    content: bytes = b""
    safe_local_path: str = ""
    logical_document_type: str = ""
    checksum: str = ""
    size: int = 0

    def normalised(self) -> "GmailAttachmentRequest":
        content = self.content
        if not content and self.safe_local_path:
            path = Path(self.safe_local_path)
            content = path.read_bytes()
        checksum = self.checksum or hashlib.sha256(content).hexdigest()
        size = self.size or len(content)
        suffix = Path(self.filename).suffix.lower()
        if suffix in UNSAFE_ATTACHMENT_EXTENSIONS:
            raise GmailDraftValidationError(f"Unsafe attachment rejected: {self.filename}")
        return GmailAttachmentRequest(
            filename=Path(self.filename).name,
            mime_type=self.mime_type or "application/octet-stream",
            content=content,
            safe_local_path="",
            logical_document_type=self.logical_document_type,
            checksum=checksum,
            size=size,
        )

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "checksum": self.checksum,
            "size": self.size,
            "logical_document_type": self.logical_document_type,
        }


@dataclass
class GmailDraftRequest:
    to: List[str]
    cc: List[str]
    subject: str
    body_text: str
    supplier_request_id: str
    rfq_id: str
    email_type: str
    idempotency_key: str
    bcc: List[str] = field(default_factory=list)
    body_html: str = ""
    attachments: List[GmailAttachmentRequest] = field(default_factory=list)


@dataclass
class DraftReference:
    redacted_draft_reference: str
    redacted_message_reference: str
    thread_reference: str
    created_timestamp: str
    transport_mode: str
    status: str
    duplicate_suppressed: bool = False


@dataclass
class DraftSummary:
    subject: str
    recipient: List[str]
    cc: List[str]
    draft_status: str
    updated_timestamp: str
    supplier_request_id: str
    rfq_id: str
    attachment_count: int


@dataclass
class DraftMessage:
    reference: DraftReference
    summary: DraftSummary
    raw_mime_base64url: str
    decoded_headers: Dict[str, Any]
    body_text: str
    attachment_manifest: List[Dict[str, Any]]


def resolve_transport_mode(env: Optional[Dict[str, str]] = None) -> str:
    env = env or os.environ
    raw = str(env.get("LMCP_EMAIL_TRANSPORT_MODE") or TRANSPORT_DRAFT_ONLY).strip().upper()
    return raw if raw in VALID_TRANSPORT_MODES else TRANSPORT_DISABLED


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _redact_reference(value: str) -> str:
    if not value:
        return ""
    return "redacted-" + _hash(value)


def _normalise_address(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text)
    if not match:
        raise GmailDraftValidationError(f"Malformed email address: {text}")
    return text.lower()


def _normalise_addresses(values: Optional[Iterable[Any]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        address = _normalise_address(value)
        if address and address not in seen:
            seen.add(address)
            out.append(address)
    return out


def _assert_draft_allowed(mode: str, operation: str) -> None:
    if mode != TRANSPORT_DRAFT_ONLY:
        raise EmailTransportOperationBlocked(operation, mode, "Gmail draft operations require DRAFT_ONLY mode.", "LMCP_EMAIL_TRANSPORT_MODE=DRAFT_ONLY")


def _assert_send_blocked(mode: str, operation: str) -> None:
    raise EmailTransportOperationBlocked(operation, mode, "Live supplier email sending is not enabled for controlled reactivation.", "separate live supplier outreach authority")


def validate_and_normalise_request(request: GmailDraftRequest, *, controlled_test_mode: bool = True) -> GmailDraftRequest:
    to = _normalise_addresses(request.to)
    if not to:
        raise GmailDraftValidationError("At least one recipient is required.")
    if controlled_test_mode:
        for address in to:
            if address not in SAFE_TEST_RECIPIENTS:
                raise GmailDraftValidationError(f"Controlled draft test recipient is not allowed: {address}")
    cc = _normalise_addresses(enforce_mandatory_cc(request.cc))
    bcc = [address for address in _normalise_addresses(request.bcc) if address != DEFAULT_MANDATORY_CC.lower()]
    if DEFAULT_MANDATORY_CC.lower() not in cc:
        cc.append(DEFAULT_MANDATORY_CC.lower())
    attachments = [attachment.normalised() for attachment in request.attachments]
    if any(term in (request.body_text + " " + request.subject).lower() for term in ["gross profit", "markup", "internal cost", "margin on sales"]):
        raise GmailDraftValidationError("Internal commercial data is not allowed in supplier draft content.")
    if request.email_type not in {EMAIL_TYPE_INITIAL, EMAIL_TYPE_FOLLOWUP_1, EMAIL_TYPE_CLARIFICATION}:
        raise GmailDraftValidationError(f"Unsupported supplier draft email type: {request.email_type}")
    return GmailDraftRequest(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=request.subject,
        body_text=request.body_text,
        body_html=request.body_html,
        attachments=attachments,
        supplier_request_id=request.supplier_request_id,
        rfq_id=request.rfq_id,
        email_type=request.email_type,
        idempotency_key=request.idempotency_key,
    )


def build_gmail_mime_message(request: GmailDraftRequest, *, from_address: str = DEFAULT_SUPPLIER_MAILBOX) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_address
    msg["To"] = ", ".join(request.to)
    msg["Cc"] = ", ".join(request.cc)
    msg["Subject"] = request.subject
    msg["X-LMCP-Supplier-Request-ID"] = request.supplier_request_id
    msg["X-LMCP-RFQ-ID"] = request.rfq_id
    msg["X-LMCP-Email-Type"] = request.email_type
    msg["X-LMCP-Idempotency-Key"] = _hash(request.idempotency_key)
    msg["X-LMCP-Draft-Idempotency-Key"] = hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest()
    msg.set_content(request.body_text, subtype="plain", charset="utf-8")
    if request.body_html:
        msg.add_alternative(request.body_html, subtype="html", charset="utf-8")
    for attachment in request.attachments:
        maintype, subtype = (attachment.mime_type.split("/", 1) + ["octet-stream"])[:2]
        msg.add_attachment(attachment.content, maintype=maintype, subtype=subtype, filename=attachment.filename)
    return msg


def encode_gmail_raw_message(message: EmailMessage) -> str:
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


class FakeGmailDraftClient:
    def __init__(self):
        self._drafts: Dict[str, Dict[str, Any]] = {}
        self._by_idempotency: Dict[str, str] = {}
        self.send_attempts = 0

    def create_draft(self, *, user_id: str, raw_message: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        key = str(metadata.get("idempotency_key"))
        if key in self._by_idempotency:
            draft_id = self._by_idempotency[key]
            record = dict(self._drafts[draft_id])
            record["duplicate_suppressed"] = True
            return record
        draft_id = "fake-draft-" + _hash(key)
        message_id = "fake-message-" + _hash(raw_message)
        thread_id = "fake-thread-" + _hash(str(metadata.get("supplier_request_id")) + str(metadata.get("recipient")))
        record = {
            "id": draft_id,
            "message": {"id": message_id, "threadId": thread_id, "raw": raw_message},
            "metadata": dict(metadata),
            "duplicate_suppressed": False,
        }
        self._drafts[draft_id] = record
        self._by_idempotency[key] = draft_id
        return dict(record)

    def list_drafts(self, *, user_id: str, query: Optional[str] = None) -> List[Dict[str, Any]]:
        return [dict(value) for value in self._drafts.values()]

    def get_draft(self, *, user_id: str, draft_id: str) -> Dict[str, Any]:
        return dict(self._drafts[draft_id])


class GmailApiDraftClient:
    def __init__(self, gmail_resource: Any):
        self.gmail_resource = gmail_resource

    def create_draft(self, *, user_id: str, raw_message: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        response = (
            self.gmail_resource.users()
            .drafts()
            .create(userId=user_id, body={"message": {"raw": raw_message}})
            .execute()
        )
        return self._normalise_response(response, raw_message=raw_message, metadata=metadata)

    def list_drafts(self, *, user_id: str, query: Optional[str] = None) -> List[Dict[str, Any]]:
        request: Dict[str, Any] = {"userId": user_id}
        if query:
            request["q"] = query
        response = self.gmail_resource.users().drafts().list(**request).execute()
        records: List[Dict[str, Any]] = []
        for item in response.get("drafts") or []:
            draft_id = item.get("id")
            if not draft_id:
                continue
            records.append(self.get_draft(user_id=user_id, draft_id=draft_id))
        return records

    def get_draft(self, *, user_id: str, draft_id: str) -> Dict[str, Any]:
        response = (
            self.gmail_resource.users()
            .drafts()
            .get(userId=user_id, id=draft_id, format="raw")
            .execute()
        )
        raw_message = ((response.get("message") or {}).get("raw")) or ""
        metadata = _metadata_from_raw(raw_message)
        return self._normalise_response(response, raw_message=raw_message, metadata=metadata)

    @staticmethod
    def _normalise_response(response: Dict[str, Any], *, raw_message: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        message = response.get("message") or {}
        internal_date = message.get("internalDate")
        if internal_date and not metadata.get("created_at"):
            try:
                metadata = dict(metadata)
                metadata["created_at"] = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
        return {
            "id": response.get("id", ""),
            "message": {
                "id": message.get("id", ""),
                "threadId": message.get("threadId", ""),
                "raw": raw_message,
            },
            "metadata": metadata,
            "duplicate_suppressed": False,
        }


def _metadata_from_raw(raw_message: str) -> Dict[str, Any]:
    try:
        raw_bytes = base64.urlsafe_b64decode(raw_message.encode("ascii"))
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
        body_text = ""
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                    body_text += part.get_content()
        else:
            body_text = message.get_content()
        attachments = []
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                payload = part.get_payload(decode=True) or b""
                attachments.append({
                    "filename": part.get_filename() or "attachment",
                    "mime_type": part.get_content_type(),
                    "checksum": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                    "logical_document_type": "",
                })
        return {
            "subject": message.get("Subject", ""),
            "recipient": _normalise_addresses((message.get("To") or "").split(",")),
            "cc": _normalise_addresses((message.get("Cc") or "").split(",")),
            "bcc": [],
            "supplier_request_id": message.get("X-LMCP-Supplier-Request-ID", ""),
            "rfq_id": message.get("X-LMCP-RFQ-ID", ""),
            "email_type": message.get("X-LMCP-Email-Type", ""),
            "idempotency_key": message.get("X-LMCP-Idempotency-Key", ""),
            "idempotency_key_hash": message.get("X-LMCP-Idempotency-Key", ""),
            "draft_idempotency_key": message.get("X-LMCP-Draft-Idempotency-Key", ""),
            "attachment_count": len(attachments),
            "attachments": attachments,
            "body_text": body_text,
            "created_at": _now(),
        }
    except Exception:
        return {"subject": "", "recipient": [], "cc": [], "attachment_count": 0, "attachments": [], "body_text": ""}


class GmailDraftTransportService:
    def __init__(
        self,
        *,
        gmail_client: Optional[Any] = None,
        oauth_provider: Optional[GmailOAuthProvider] = None,
        env: Optional[Dict[str, str]] = None,
        controlled_test_mode: bool = True,
    ):
        self.env = env or os.environ
        self.mode = resolve_transport_mode(self.env)
        self.oauth_provider = oauth_provider
        self.gmail_client = gmail_client
        self.controlled_test_mode = controlled_test_mode
        self.user_id = self.env.get("LMCP_GMAIL_USER_ID") or "me"
        self._draft_reference_map: Dict[str, str] = {}

    def create_draft(self, request: GmailDraftRequest) -> DraftReference:
        _assert_draft_allowed(self.mode, "create_draft")
        client = self._client()
        normalised = validate_and_normalise_request(request, controlled_test_mode=self.controlled_test_mode)
        message = build_gmail_mime_message(normalised)
        raw = encode_gmail_raw_message(message)
        metadata = self._metadata(normalised, raw)
        response = client.create_draft(user_id=self.user_id, raw_message=raw, metadata=metadata)
        reference = self._reference(response)
        raw_id = str(response.get("id") or "")
        if raw_id:
            self._draft_reference_map[reference.redacted_draft_reference] = raw_id
        return reference

    def list_drafts(self, query: Optional[str] = None) -> List[DraftSummary]:
        _assert_draft_allowed(self.mode, "list_drafts")
        return [message.summary for message in self.list_draft_messages(query=query)]

    def list_draft_messages(self, query: Optional[str] = None) -> List[DraftMessage]:
        _assert_draft_allowed(self.mode, "list_draft_messages")
        messages: List[DraftMessage] = []
        for record in self._client().list_drafts(user_id=self.user_id, query=query):
            reference = self._reference(record)
            raw_id = str(record.get("id") or "")
            if raw_id:
                self._draft_reference_map[reference.redacted_draft_reference] = raw_id
            messages.append(self._message_from_record(record, reference=reference))
        return messages

    def get_draft(self, draft_reference: DraftReference) -> DraftMessage:
        _assert_draft_allowed(self.mode, "get_draft")
        draft_id = self._resolve_fake_reference(draft_reference.redacted_draft_reference)
        record = self._client().get_draft(user_id=self.user_id, draft_id=draft_id)
        return self._message_from_record(record)

    def remember_draft_reference(self, raw_draft_reference: str) -> DraftReference:
        reference = DraftReference(
            redacted_draft_reference=_redact_reference(raw_draft_reference),
            redacted_message_reference="",
            thread_reference="",
            created_timestamp="",
            transport_mode=TRANSPORT_DRAFT_ONLY,
            status="DRAFT",
        )
        self._draft_reference_map[reference.redacted_draft_reference] = raw_draft_reference
        return reference

    def raw_reference_for_redacted(self, redacted_draft_reference: str) -> str:
        return self._draft_reference_map.get(redacted_draft_reference, "")

    def delete_draft(self, draft_reference: DraftReference) -> None:
        raise EmailTransportOperationBlocked("delete_draft", self.mode, "Draft deletion is not authorised in this validation step.", "separate cleanup authority")

    def send_draft(self, draft_reference: DraftReference) -> None:
        _assert_send_blocked(self.mode, "send_draft")

    def send_email(self, request: GmailDraftRequest) -> None:
        _assert_send_blocked(self.mode, "send_email")

    def smtp_fallback_send(self, request: GmailDraftRequest) -> None:
        _assert_send_blocked(self.mode, "smtp_fallback_send")

    def scheduler_dispatch(self, request: GmailDraftRequest) -> None:
        _assert_send_blocked(self.mode, "scheduler_dispatch")

    def audit_record(self, *, operation: str, request: Optional[GmailDraftRequest], blocked: Optional[EmailTransportOperationBlocked] = None, draft: Optional[DraftReference] = None) -> Dict[str, Any]:
        return {
            "attempted_operation": operation,
            "transport_mode": self.mode,
            "supplier_request_id": request.supplier_request_id if request else "",
            "rfq_id": request.rfq_id if request else "",
            "email_type": request.email_type if request else "",
            "recipient": request.to if request else [],
            "mandatory_cc": DEFAULT_MANDATORY_CC,
            "subject": request.subject if request else "",
            "attachment_count": len(request.attachments) if request else 0,
            "idempotency_key_hash": _hash(request.idempotency_key) if request else "",
            "draft_created": draft is not None,
            "draft_reference": draft.redacted_draft_reference if draft else "",
            "send_prevented": blocked is not None,
            "timestamp": _now(),
            "error_category": blocked.reason if blocked else "",
        }

    def _client(self) -> Any:
        if self.gmail_client is not None:
            return self.gmail_client
        if self.oauth_provider is None:
            self.oauth_provider = GmailOAuthProvider()
        try:
            self.gmail_client = GmailApiDraftClient(self.oauth_provider.get_authenticated_client())
        except GmailAuthUnavailable:
            raise
        return self.gmail_client

    def _metadata(self, request: GmailDraftRequest, raw: str) -> Dict[str, Any]:
        return {
            "subject": request.subject,
            "recipient": request.to,
            "cc": request.cc,
            "bcc": [],
            "supplier_request_id": request.supplier_request_id,
            "rfq_id": request.rfq_id,
            "email_type": request.email_type,
            "idempotency_key": request.idempotency_key,
            "idempotency_key_hash": _hash(request.idempotency_key),
            "attachment_count": len(request.attachments),
            "attachments": [attachment.to_manifest() for attachment in request.attachments],
            "body_text": request.body_text,
            "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "created_at": _now(),
        }

    @staticmethod
    def _reference(record: Dict[str, Any]) -> DraftReference:
        metadata = record.get("metadata") or {}
        return DraftReference(
            redacted_draft_reference=_redact_reference(record.get("id", "")),
            redacted_message_reference=_redact_reference((record.get("message") or {}).get("id", "")),
            thread_reference=_redact_reference((record.get("message") or {}).get("threadId", "")),
            created_timestamp=metadata.get("created_at") or _now(),
            transport_mode=TRANSPORT_DRAFT_ONLY,
            status="DRAFT",
            duplicate_suppressed=bool(record.get("duplicate_suppressed")),
        )

    @staticmethod
    def _summary(record: Dict[str, Any]) -> DraftSummary:
        metadata = record.get("metadata") or {}
        return DraftSummary(
            subject=metadata.get("subject", ""),
            recipient=list(metadata.get("recipient") or []),
            cc=list(metadata.get("cc") or []),
            draft_status="DRAFT",
            updated_timestamp=metadata.get("created_at") or _now(),
            supplier_request_id=metadata.get("supplier_request_id", ""),
            rfq_id=metadata.get("rfq_id", ""),
            attachment_count=int(metadata.get("attachment_count") or 0),
        )

    def _message_from_record(self, record: Dict[str, Any], *, reference: Optional[DraftReference] = None) -> DraftMessage:
        metadata = record.get("metadata") or {}
        decoded_headers = {k: metadata.get(k) for k in ["subject", "recipient", "cc", "supplier_request_id", "rfq_id", "email_type", "draft_idempotency_key"]}
        if metadata.get("bcc"):
            decoded_headers["bcc"] = metadata.get("bcc")
        return DraftMessage(
            reference=reference or self._reference(record),
            summary=self._summary(record),
            raw_mime_base64url=(record.get("message") or {}).get("raw", ""),
            decoded_headers=decoded_headers,
            body_text=metadata.get("body_text", ""),
            attachment_manifest=metadata.get("attachments", []),
        )

    def _resolve_fake_reference(self, redacted: str) -> str:
        if redacted in self._draft_reference_map:
            return self._draft_reference_map[redacted]
        if not isinstance(self.gmail_client, FakeGmailDraftClient):
            raise GmailDraftValidationError("Non-fake client draft retrieval requires raw reference mapping from provider.")
        for draft_id in self.gmail_client._drafts:
            if _redact_reference(draft_id) == redacted:
                return draft_id
        raise KeyError(redacted)


def build_supplier_gmail_draft_request(
    email_model: Dict[str, Any],
    *,
    recipient: str,
    email_type: str,
    body_prefix: str = CONTROLLED_TEST_BODY_PREFIX,
    subject_prefix: str = CONTROLLED_TEST_SUBJECT_PREFIX,
    attachments: Optional[Sequence[GmailAttachmentRequest]] = None,
    missing_fields: Optional[Sequence[str]] = None,
) -> GmailDraftRequest:
    request_id = str(email_model.get("request_id") or "")
    rfq_reference = "6000080579"
    subject = f"{subject_prefix} | Supplier RFQ {rfq_reference} | {request_id}"
    source_body = str(email_model.get("body") or "")
    if email_type == EMAIL_TYPE_FOLLOWUP_1:
        source_body = "\n".join([
            body_prefix,
            "",
            "Controlled theoretical two-day follow-up draft. No real elapsed-time claim is made.",
            f"Calculated follow-up due time: {email_model.get('followup_due_at')}",
            "",
            source_body,
        ])
    elif email_type == EMAIL_TYPE_CLARIFICATION:
        source_body = "\n".join([
            body_prefix,
            "",
            "Controlled clarification draft for incomplete supplier response.",
            "Missing information requested:",
            *[f"- {field}" for field in (missing_fields or [])],
            "",
            source_body,
        ])
    else:
        source_body = body_prefix + "\n\n" + source_body
    return GmailDraftRequest(
        to=[recipient],
        cc=[DEFAULT_MANDATORY_CC],
        subject=subject,
        body_text=source_body,
        attachments=list(attachments or []),
        supplier_request_id=request_id,
        rfq_id=f"TEMP-RFQ-{rfq_reference}",
        email_type=email_type,
        idempotency_key=f"{request_id}:{email_type}:{recipient.lower()}",
    )


def dataclass_to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: dataclass_to_dict(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_to_dict(item) for key, item in value.items()}
    return value


def inspect_gmail_draft_capability(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    provider = GmailOAuthProvider()
    return {
        "transport_mode": resolve_transport_mode(env),
        "oauth": provider.inspect_configuration(),
        "credentials_exposed": False,
    }
