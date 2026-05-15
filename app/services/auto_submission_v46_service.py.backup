from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import mimetypes
import os
import re
import smtplib
import ssl
import traceback

SERVICE_VERSION = "V46_AUTO_SUBMISSION_ENGINE"
DEFAULT_OUTPUT_DIR = Path("runtime/auto_submission_v46")
DEFAULT_HISTORY_PATH = Path("runtime/submission_history/v46_submission_history.json")

BLOCKED_ATTACHMENT_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".exe", ".bat", ".cmd", ".sh", ".js", ".vbs"
}

DEFAULT_FROM_NAME = "Lechesa Manaba Consulting and Projects (Pty) Ltd"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _resolve_path(value: str | Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _read_json(path_value: str | Path) -> Dict[str, Any]:
    path = _resolve_path(path_value)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_blocked_attachment(path_value: str) -> bool:
    suffix = Path(path_value).suffix.lower()
    return suffix in BLOCKED_ATTACHMENT_EXTENSIONS


def _sanitize_attachments(attachments: List[Any]) -> Dict[str, Any]:
    included: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    seen = set()

    for raw in attachments or []:
        path_str = str(raw or "").strip()
        if not path_str:
            continue

        path = _resolve_path(path_str)
        key = str(path)

        if key in seen:
            continue
        seen.add(key)

        if _is_blocked_attachment(str(path)):
            excluded.append({
                "path": str(path),
                "reason": "blocked file type for buyer email",
                "extension": path.suffix.lower(),
            })
            continue

        if not path.exists():
            excluded.append({
                "path": str(path),
                "reason": "file not found",
                "extension": path.suffix.lower(),
            })
            continue

        if not path.is_file():
            excluded.append({
                "path": str(path),
                "reason": "not a file",
                "extension": path.suffix.lower(),
            })
            continue

        included.append({
            "path": str(path),
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "extension": path.suffix.lower(),
        })

    return {
        "included": included,
        "excluded": excluded,
        "included_count": len(included),
        "excluded_count": len(excluded),
        "zip_allowed_for_submission": False,
    }


def _load_email_draft_from_v45_workspace(workspace_path: str) -> Dict[str, Any]:
    workspace = _resolve_path(workspace_path)
    draft_path = workspace / "email_draft_v45.json"
    if not draft_path.exists():
        raise FileNotFoundError(f"email_draft_v45.json not found in {workspace}")
    draft = _read_json(draft_path)
    draft["_source_email_draft_json"] = str(draft_path)
    draft["_source_workspace"] = str(workspace)
    return draft


def _load_email_draft_from_json(email_draft_json: str) -> Dict[str, Any]:
    path = _resolve_path(email_draft_json)
    if not path.exists():
        raise FileNotFoundError(f"Email draft JSON not found: {path}")
    draft = _read_json(path)
    draft["_source_email_draft_json"] = str(path)
    draft["_source_workspace"] = str(path.parent)
    return draft


def _smtp_config_from_env() -> Dict[str, Any]:
    host = os.getenv("SMTP_HOST") or os.getenv("MAIL_HOST") or os.getenv("EMAIL_HOST")
    port = int(os.getenv("SMTP_PORT") or os.getenv("MAIL_PORT") or "587")
    username = os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER") or os.getenv("MAIL_USERNAME") or os.getenv("EMAIL_USERNAME")
    password = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS") or os.getenv("MAIL_PASSWORD") or os.getenv("EMAIL_PASSWORD")
    sender = os.getenv("SMTP_FROM_EMAIL") or os.getenv("MAIL_FROM") or os.getenv("EMAIL_FROM") or username
    use_tls = str(os.getenv("SMTP_USE_TLS") or "true").lower() in {"1", "true", "yes", "on"}

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "use_tls": use_tls,
        "configured": bool(host and port and username and password and sender),
    }


def _build_email_message(
    draft: Dict[str, Any],
    attachments: List[Dict[str, Any]],
    smtp_config: Dict[str, Any],
) -> EmailMessage:
    msg = EmailMessage()

    sender = smtp_config.get("sender")
    msg["From"] = f"{DEFAULT_FROM_NAME} <{sender}>" if sender else DEFAULT_FROM_NAME
    msg["To"] = draft.get("to") or ""
    if draft.get("cc"):
        msg["Cc"] = draft.get("cc")
    if draft.get("bcc"):
        msg["Bcc"] = draft.get("bcc")
    msg["Subject"] = draft.get("subject") or "Quotation Submission"
    msg.set_content(draft.get("body") or "")

    for row in attachments:
        path = Path(row["path"])
        ctype, encoding = mimetypes.guess_type(str(path))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)

        with path.open("rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=path.name,
            )

    return msg


def _send_email_smtp(draft: Dict[str, Any], attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    config = _smtp_config_from_env()
    if not config["configured"]:
        return {
            "status": "error",
            "message": "SMTP is not fully configured in environment variables.",
            "smtp_configured": False,
            "required_env": [
                "SMTP_HOST",
                "SMTP_PORT",
                "SMTP_USERNAME",
                "SMTP_PASSWORD",
                "SMTP_FROM_EMAIL",
            ],
        }

    msg = _build_email_message(draft, attachments, config)

    try:
        if config["use_tls"]:
            context = ssl.create_default_context()
            with smtplib.SMTP(config["host"], config["port"], timeout=60) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(config["username"], config["password"])
                refused = server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(config["host"], config["port"], timeout=60) as server:
                server.login(config["username"], config["password"])
                refused = server.send_message(msg)

        return {
            "status": "sent",
            "message": "Email sent successfully via SMTP.",
            "smtp_configured": True,
            "refused_recipients": refused,
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": "SMTP send failed.",
            "smtp_configured": True,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def _append_history(record: Dict[str, Any]) -> None:
    history_path = _resolve_path(DEFAULT_HISTORY_PATH)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    else:
        history = []

    history.append(record)
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def submit_from_email_draft_payload(
    draft: Dict[str, Any],
    buyer_rfq_number: Optional[str] = None,
    dry_run: bool = True,
    output_dir: Optional[str] = None,
    allow_send: bool = False,
) -> Dict[str, Any]:
    started_at = _now_iso()

    rfq = buyer_rfq_number or draft.get("buyer_rfq_number") or "RFQ"
    safe_rfq = _safe_name(rfq)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not out_root.is_absolute():
        out_root = Path.cwd() / out_root

    workspace = out_root / f"{safe_rfq}__SUBMISSION-{timestamp}"
    workspace.mkdir(parents=True, exist_ok=True)

    sanitized = _sanitize_attachments(draft.get("attachments") or [])

    if not draft.get("to"):
        status = "blocked"
        send_result = {
            "status": "blocked",
            "message": "No recipient email address detected.",
        }
    elif not sanitized["included"]:
        status = "blocked"
        send_result = {
            "status": "blocked",
            "message": "No valid non-zip attachments available.",
        }
    elif dry_run or not allow_send:
        status = "dry_run"
        send_result = {
            "status": "dry_run",
            "message": "Dry run completed. Email was not sent.",
        }
    else:
        send_result = _send_email_smtp(draft, sanitized["included"])
        status = send_result.get("status") or "unknown"

    record = {
        "status": status,
        "service_version": SERVICE_VERSION,
        "message": "Submission processed.",
        "buyer_rfq_number": rfq,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "workspace": str(workspace),
        "dry_run": dry_run,
        "allow_send": allow_send,
        "email": {
            "to": draft.get("to"),
            "cc": draft.get("cc"),
            "bcc": draft.get("bcc"),
            "subject": draft.get("subject"),
            "body": draft.get("body"),
        },
        "attachments_policy": {
            "zip_allowed_for_submission": False,
            "blocked_extensions": sorted(BLOCKED_ATTACHMENT_EXTENSIONS),
        },
        "attachments": sanitized,
        "send_result": send_result,
        "source": {
            "email_draft_json": draft.get("_source_email_draft_json"),
            "workspace": draft.get("_source_workspace"),
        },
        "artifacts": {
            "submission_record_json": str(workspace / "submission_record_v46.json"),
            "email_preview_json": str(workspace / "email_preview_v46.json"),
            "history_json": str(_resolve_path(DEFAULT_HISTORY_PATH)),
        },
    }

    _write_json(workspace / "submission_record_v46.json", record)
    _write_json(workspace / "email_preview_v46.json", {
        "to": draft.get("to"),
        "subject": draft.get("subject"),
        "body": draft.get("body"),
        "attachments": sanitized["included"],
        "excluded_attachments": sanitized["excluded"],
        "zip_allowed_for_submission": False,
    })
    _append_history(record)

    return record


def submit_from_v45_workspace(
    workspace_path: str,
    buyer_rfq_number: Optional[str] = None,
    dry_run: bool = True,
    output_dir: Optional[str] = None,
    allow_send: bool = False,
) -> Dict[str, Any]:
    try:
        draft = _load_email_draft_from_v45_workspace(workspace_path)
        return submit_from_email_draft_payload(
            draft=draft,
            buyer_rfq_number=buyer_rfq_number,
            dry_run=dry_run,
            output_dir=output_dir,
            allow_send=allow_send,
        )
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V46 submission from V45 workspace failed.",
            "workspace_path": workspace_path,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": _now_iso(),
            "completed_at": _now_iso(),
        }


def submit_from_email_draft_json(
    email_draft_json: str,
    buyer_rfq_number: Optional[str] = None,
    dry_run: bool = True,
    output_dir: Optional[str] = None,
    allow_send: bool = False,
) -> Dict[str, Any]:
    try:
        draft = _load_email_draft_from_json(email_draft_json)
        return submit_from_email_draft_payload(
            draft=draft,
            buyer_rfq_number=buyer_rfq_number,
            dry_run=dry_run,
            output_dir=output_dir,
            allow_send=allow_send,
        )
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V46 submission from email draft JSON failed.",
            "email_draft_json": email_draft_json,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": _now_iso(),
            "completed_at": _now_iso(),
        }


def submit_from_pdf_workflow(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    dry_run: bool = True,
    output_dir: Optional[str] = None,
    allow_send: bool = False,
    margin_percent: float = 25.0,
    minimum_profit_required: float = 30000.0,
    apply_profit_floor: bool = True,
    min_confidence: float = 0.35,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        from app.services.submission_pack_v45_service import prepare_submission_from_pdf

        v45_result = prepare_submission_from_pdf(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            margin_percent=margin_percent,
            minimum_profit_required=minimum_profit_required,
            apply_profit_floor=apply_profit_floor,
            min_confidence=min_confidence,
            create_zip=True,
        )

        if v45_result.get("status") != "ok":
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V45 failed, so V46 could not continue.",
                "v45_result": v45_result,
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        workspace = v45_result.get("workspace")
        result = submit_from_v45_workspace(
            workspace_path=workspace,
            buyer_rfq_number=buyer_rfq_number,
            dry_run=dry_run,
            output_dir=output_dir,
            allow_send=allow_send,
        )
        result["v45_workspace"] = workspace
        result["v45_artifacts"] = v45_result.get("artifacts")
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V46 full PDF workflow failed.",
            "input_pdf": input_pdf,
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v46_status() -> Dict[str, Any]:
    smtp_config = _smtp_config_from_env()
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V46 Auto Submission Engine",
        "description": "Reads V45 email draft, excludes ZIP/unsafe files from buyer email, performs dry-run or SMTP send, and records submission proof/history.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "history_path": str(DEFAULT_HISTORY_PATH),
        "submission_policy": {
            "zip_allowed_for_submission": False,
            "blocked_attachment_extensions": sorted(BLOCKED_ATTACHMENT_EXTENSIONS),
            "default_mode": "dry_run",
        },
        "smtp": {
            "configured": smtp_config.get("configured"),
            "host": smtp_config.get("host"),
            "port": smtp_config.get("port"),
            "sender": smtp_config.get("sender"),
            "use_tls": smtp_config.get("use_tls"),
        },
        "endpoints": {
            "status": "/v46-auto-submission/status",
            "submit_from_v45_workspace": "/v46-auto-submission/submit-from-v45-workspace",
            "submit_from_email_draft_json": "/v46-auto-submission/submit-from-email-draft-json",
            "submit_from_pdf": "/v46-auto-submission/submit-from-pdf",
        },
        "ready": True,
    }
