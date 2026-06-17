from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List

import smtplib
from email.message import EmailMessage
from pathlib import Path


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


def _env_or_metadata(metadata: Dict[str, Any], key: str, env_key: str, default: Any = "") -> Any:
    env_value = os.getenv(env_key)
    if env_value not in (None, ""):
        return env_value
    return metadata.get(key, default)


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _build_message(payload: Dict[str, Any], sender_email: str) -> EmailMessage:
    message = EmailMessage()
    to_list = _dedupe_strings([str(x) for x in _safe_list(payload.get("to"))])
    cc_list = _dedupe_strings([str(x) for x in _safe_list(payload.get("cc"))])
    bcc_list = _dedupe_strings([str(x) for x in _safe_list(payload.get("bcc"))])

    message["From"] = sender_email
    message["To"] = ", ".join(to_list)
    if cc_list:
        message["Cc"] = ", ".join(cc_list)
    message["Subject"] = _clean(payload.get("subject"))
    message.set_content(_clean(payload.get("body")))

    for attachment in _safe_list(payload.get("attachments")):
        path = Path(_clean(attachment))
        if not path.exists() or not path.is_file():
            continue
        data = path.read_bytes()
        message.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=path.name,
        )

    return message


def build_email_send_result(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    metadata = _safe_dict(payload.get("metadata"))
    email_payload = _safe_dict(payload.get("submission_email_payload"))

    ready_to_send = bool(payload.get("submission_email_ready")) and bool(email_payload.get("ready_to_send"))
    sender_email = _clean(_env_or_metadata(metadata, "smtp_sender_email", "LMCP_SMTP_SENDER_EMAIL"))
    smtp_host = _clean(_env_or_metadata(metadata, "smtp_host", "LMCP_SMTP_HOST"))
    smtp_port = _to_int(_env_or_metadata(metadata, "smtp_port", "LMCP_SMTP_PORT", 587), 587)
    smtp_username = _clean(_env_or_metadata(metadata, "smtp_username", "LMCP_SMTP_USERNAME"))
    smtp_password = _clean(_env_or_metadata(metadata, "smtp_password", "LMCP_SMTP_PASSWORD"))
    smtp_use_tls = _to_bool(_env_or_metadata(metadata, "smtp_use_tls", "LMCP_SMTP_USE_TLS", True), True)
    auto_send = _to_bool(_env_or_metadata(metadata, "auto_send_submission_email", "LMCP_AUTO_SEND_SUBMISSION_EMAIL", False), False)

    recipients = _dedupe_strings(
        [str(x) for x in _safe_list(email_payload.get("to"))]
        + [str(x) for x in _safe_list(email_payload.get("cc"))]
        + [str(x) for x in _safe_list(email_payload.get("bcc"))]
    )
    attachments = _dedupe_strings([str(x) for x in _safe_list(email_payload.get("attachments"))])

    result = {
        "email_send_result": {
            "attempted": False,
            "sent": False,
            "ready_to_send": ready_to_send,
            "auto_send_enabled": auto_send,
            "recipient_count": len(recipients),
            "attachment_count": len(attachments),
            "sent_at_utc": "",
            "message": "",
            "used_sender_email": sender_email,
            "used_recipients": recipients,
            "used_attachments": attachments,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_use_tls": smtp_use_tls,
        }
    }

    if not ready_to_send:
        result["email_send_result"]["message"] = "Submission email payload is not ready to send."
        result["submission_email_sent"] = False
        return result

    if not auto_send:
        result["email_send_result"]["message"] = "Auto-send is disabled. Email payload is prepared but not sent."
        result["submission_email_sent"] = False
        return result

    required_missing = []
    if not sender_email:
        required_missing.append("smtp_sender_email / LMCP_SMTP_SENDER_EMAIL")
    if not smtp_host:
        required_missing.append("smtp_host / LMCP_SMTP_HOST")
    if not smtp_username:
        required_missing.append("smtp_username / LMCP_SMTP_USERNAME")
    if not smtp_password:
        required_missing.append("smtp_password / LMCP_SMTP_PASSWORD")

    if required_missing:
        result["email_send_result"]["message"] = "Missing SMTP settings: " + ", ".join(required_missing)
        result["submission_email_sent"] = False
        return result

    try:
        message = _build_message(email_payload, sender_email=sender_email)

        if smtp_use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
                server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(message)

        sent_at = datetime.now(timezone.utc).isoformat()
        result["email_send_result"].update(
            {
                "attempted": True,
                "sent": True,
                "sent_at_utc": sent_at,
                "message": "Submission email sent successfully.",
            }
        )
        result["submission_email_sent"] = True
        result["submission_email_sent_at_utc"] = sent_at
        return result

    except Exception as exc:
        result["email_send_result"].update(
            {
                "attempted": True,
                "sent": False,
                "message": f"Submission email send failed: {exc}",
            }
        )
        result["submission_email_sent"] = False
        return result


def attach_email_send_result_to_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    payload.update(build_email_send_result(payload))
    return payload


