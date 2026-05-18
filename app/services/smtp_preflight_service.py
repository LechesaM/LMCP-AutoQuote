from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def build_smtp_preflight(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    metadata = _safe_dict(payload.get("metadata"))
    email_payload = _safe_dict(payload.get("submission_email_payload"))

    smtp_host = _clean(metadata.get("smtp_host"))
    smtp_port_raw = metadata.get("smtp_port", 587)
    smtp_username = _clean(metadata.get("smtp_username"))
    smtp_password = _clean(metadata.get("smtp_password"))
    smtp_sender_email = _clean(metadata.get("smtp_sender_email"))
    smtp_use_tls = bool(metadata.get("smtp_use_tls", True))
    auto_send = bool(metadata.get("auto_send_submission_email", False))

    try:
        smtp_port = int(smtp_port_raw or 587)
    except Exception:
        smtp_port = 587

    recipients = [str(x) for x in _safe_list(email_payload.get("to"))]
    attachments = [str(x) for x in _safe_list(email_payload.get("attachments"))]

    missing: List[str] = []
    if auto_send:
        if not smtp_host:
            missing.append("smtp_host")
        if not smtp_username:
            missing.append("smtp_username")
        if not smtp_password:
            missing.append("smtp_password")
        if not smtp_sender_email:
            missing.append("smtp_sender_email")

    warnings: List[str] = []
    if not recipients:
        warnings.append("No submission recipients resolved.")
    if not attachments:
        warnings.append("No submission attachments resolved.")
    if smtp_port <= 0:
        warnings.append("SMTP port is invalid.")

    ready = auto_send and not missing and not warnings and bool(payload.get("submission_email_ready"))

    return {
        "smtp_preflight": {
            "auto_send_enabled": auto_send,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_use_tls": smtp_use_tls,
            "smtp_username_present": bool(smtp_username),
            "smtp_password_present": bool(smtp_password),
            "smtp_sender_email_present": bool(smtp_sender_email),
            "submission_email_ready": bool(payload.get("submission_email_ready")),
            "recipient_count": len(recipients),
            "attachment_count": len(attachments),
            "missing_required_fields": missing,
            "warnings": warnings,
            "ready_for_live_send": ready,
        }
    }


def attach_smtp_preflight_to_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    payload.update(build_smtp_preflight(payload))
    return payload


