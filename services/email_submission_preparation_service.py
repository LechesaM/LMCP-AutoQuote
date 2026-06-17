from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        cleaned = _clean(value)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(cleaned)
    return output


def build_email_submission_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    metadata = _safe_dict(payload.get("metadata"))

    buyer_name = _clean(payload.get("buyer_name") or metadata.get("buyer_name"))
    rfq_number = _clean(
        payload.get("rfq_number")
        or payload.get("reference_number")
        or metadata.get("buyer_rfq_number")
        or metadata.get("rfq_number")
    )
    document_title = _clean(payload.get("title") or metadata.get("title"))
    quote_reference = _clean(
        metadata.get("quote_reference")
        or payload.get("quote_reference")
        or rfq_number
    )

    recipients = _dedupe_strings(
        [str(x) for x in _safe_list(metadata.get("submission_recipients"))]
        + [str(x) for x in _safe_list(payload.get("emails"))]
    )
    cc_recipients = _dedupe_strings([str(x) for x in _safe_list(metadata.get("submission_cc"))])
    bcc_recipients = _dedupe_strings([str(x) for x in _safe_list(metadata.get("submission_bcc"))])

    attachment_candidates = [str(x) for x in _safe_list(payload.get("submission_pack_files"))]
    attachment_candidates += [_clean(payload.get("submission_pack_manifest_path"))]
    attachment_paths = []
    for item in attachment_candidates:
        cleaned = _clean(item)
        if cleaned:
            attachment_paths.append(cleaned)
    attachment_paths = _dedupe_strings(attachment_paths)

    subject = _clean(
        metadata.get("submission_subject")
        or f"Submission: {rfq_number} - {document_title or 'Tender Response'}"
    )

    body = _clean(
        metadata.get("submission_body")
        or (
            f"Dear Sir/Madam,\n\n"
            f"Please find attached our submission for {rfq_number}"
            f"{' - ' + document_title if document_title else ''}.\n\n"
            f"Buyer: {buyer_name or 'N/A'}\n"
            f"Quote Reference: {quote_reference or 'N/A'}\n\n"
            f"Kind regards,\n"
            f"Lechesa Manaba Consulting and Projects (Pty) Ltd"
        )
    )

    ready_to_send = bool(recipients and attachment_paths)

    return {
        "email_submission_preparation": {
            "recipient_count": len(recipients),
            "cc_count": len(cc_recipients),
            "bcc_count": len(bcc_recipients),
            "attachment_count": len(attachment_paths),
            "ready_to_send": ready_to_send,
            "quote_reference": quote_reference,
        },
        "submission_email_payload": {
            "to": recipients,
            "cc": cc_recipients,
            "bcc": bcc_recipients,
            "subject": subject,
            "body": body,
            "attachments": attachment_paths,
            "ready_to_send": ready_to_send,
        },
        "submission_email_ready": ready_to_send,
    }


def attach_email_submission_payload_to_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    payload.update(build_email_submission_payload(payload))
    return payload


