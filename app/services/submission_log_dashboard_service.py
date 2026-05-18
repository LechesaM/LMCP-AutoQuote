from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_submission_log_entry(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    metadata = _safe_dict(payload.get("metadata"))
    email_send_result = _safe_dict(payload.get("email_send_result"))
    submission_proof_artifacts = _safe_dict(payload.get("submission_proof_artifacts"))
    quote_pack_summary = _safe_dict(payload.get("quote_pack_summary"))

    rfq_number = _clean(
        payload.get("rfq_number")
        or payload.get("reference_number")
        or metadata.get("buyer_rfq_number")
        or "RFQ"
    )
    buyer_name = _clean(payload.get("buyer_name") or metadata.get("buyer_name"))
    title = _clean(payload.get("title") or metadata.get("title"))
    log_dir = Path(_clean(metadata.get("submission_log_dir") or "runtime/submission_logs"))
    log_path = log_dir / "submission_history.jsonl"

    entry = {
        "logged_at_utc": datetime.now(timezone.utc).isoformat(),
        "rfq_number": rfq_number,
        "buyer_name": buyer_name,
        "title": title,
        "submission_email_ready": bool(payload.get("submission_email_ready")),
        "submission_email_sent": bool(payload.get("submission_email_sent")),
        "submission_email_sent_at_utc": _clean(payload.get("submission_email_sent_at_utc")),
        "send_attempted": bool(email_send_result.get("attempted")),
        "send_message": _clean(email_send_result.get("message")),
        "used_sender_email": _clean(email_send_result.get("used_sender_email")),
        "used_recipients": _safe_list(email_send_result.get("used_recipients")),
        "used_attachments": _safe_list(email_send_result.get("used_attachments")),
        "quote_pack_total": quote_pack_summary.get("grand_total"),
        "priced_rows": quote_pack_summary.get("priced_rows"),
        "pending_rows": quote_pack_summary.get("pending_rows"),
        "review_rows_held_back": quote_pack_summary.get("review_rows_held_back"),
        "quote_pack_pdf_path": _clean(payload.get("quote_pack_pdf_path")),
        "rendered_buyer_pdf_path": _clean(payload.get("rendered_buyer_pdf_path")),
        "submission_pack_manifest_path": _clean(payload.get("submission_pack_manifest_path")),
        "submission_receipt_json_path": _clean(payload.get("submission_receipt_json_path")),
        "submission_receipt_txt_path": _clean(payload.get("submission_receipt_txt_path")),
        "submission_receipt_pdf_path": _clean(payload.get("submission_receipt_pdf_path")),
        "proof_directory": _clean(submission_proof_artifacts.get("proof_directory")),
    }

    _append_jsonl(log_path, entry)

    return {
        "submission_log_entry": entry,
        "submission_log_path": str(log_path),
    }


def build_submission_dashboard_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    email_send_result = _safe_dict(payload.get("email_send_result"))
    quote_pack_summary = _safe_dict(payload.get("quote_pack_summary"))

    dashboard = {
        "rfq_number": _clean(payload.get("rfq_number") or payload.get("reference_number")),
        "buyer_name": _clean(payload.get("buyer_name")),
        "submission_status": "sent" if payload.get("submission_email_sent") else (
            "attempted_failed" if email_send_result.get("attempted") else "prepared"
        ),
        "submission_email_ready": bool(payload.get("submission_email_ready")),
        "submission_email_sent": bool(payload.get("submission_email_sent")),
        "submission_email_sent_at_utc": _clean(payload.get("submission_email_sent_at_utc")),
        "recipient_count": len(_safe_list(email_send_result.get("used_recipients"))),
        "attachment_count": len(_safe_list(email_send_result.get("used_attachments"))),
        "priced_rows": int(quote_pack_summary.get("priced_rows") or 0),
        "pending_rows": int(quote_pack_summary.get("pending_rows") or 0),
        "review_rows_held_back": int(quote_pack_summary.get("review_rows_held_back") or 0),
        "quote_pack_total": quote_pack_summary.get("grand_total"),
        "quote_pack_pdf_path": _clean(payload.get("quote_pack_pdf_path")),
        "rendered_buyer_pdf_path": _clean(payload.get("rendered_buyer_pdf_path")),
        "submission_receipt_pdf_path": _clean(payload.get("submission_receipt_pdf_path")),
        "submission_log_path": _clean(payload.get("submission_log_path")),
    }
    return {"submission_dashboard_summary": dashboard}


def attach_submission_log_and_dashboard_to_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    payload.update(build_submission_log_entry(payload))
    payload.update(build_submission_dashboard_summary(payload))
    return payload


