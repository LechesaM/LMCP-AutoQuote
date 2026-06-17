from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


_RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
_HISTORY_DIR = _RUNTIME_DIR / "submission_history"
_HISTORY_FILE = _HISTORY_DIR / "submission_history.json"

_LOCK = Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_storage() -> None:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if not _HISTORY_FILE.exists():
        _HISTORY_FILE.write_text("[]", encoding="utf-8")


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _round_money(value: Any) -> float:
    return round(_safe_float(value, 0.0), 2)


def _round_margin(value: Any) -> float:
    return round(_safe_float(value, 0.0), 4)


def _extract_financials_from_sources(*sources: Any) -> Dict[str, float]:
    revenue = 0.0
    cost = 0.0
    profit = 0.0
    margin = 0.0

    revenue_keys = [
        "estimated_revenue",
        "quotation_total",
        "grand_total",
        "total_including_vat",
        "total_incl_vat",
        "total",
    ]
    cost_keys = [
        "estimated_cost",
        "supplier_cost_total",
        "selected_quote_total",
        "cost_estimate",
        "cost",
    ]
    profit_keys = [
        "estimated_profit",
        "profit",
    ]
    margin_keys = [
        "estimated_margin",
        "margin_percent",
        "margin_rate",
        "profit_margin",
    ]

    for source in sources:
        if not isinstance(source, dict):
            continue

        totals = source.get("totals")
        if isinstance(totals, dict):
            for key in revenue_keys:
                revenue = revenue or _safe_float(totals.get(key), 0.0)
            for key in cost_keys:
                cost = cost or _safe_float(totals.get(key), 0.0)
            for key in profit_keys:
                profit = profit or _safe_float(totals.get(key), 0.0)
            for key in margin_keys:
                margin = margin or _safe_float(totals.get(key), 0.0)

        for key in revenue_keys:
            revenue = revenue or _safe_float(source.get(key), 0.0)
        for key in cost_keys:
            cost = cost or _safe_float(source.get(key), 0.0)
        for key in profit_keys:
            profit = profit or _safe_float(source.get(key), 0.0)
        for key in margin_keys:
            margin = margin or _safe_float(source.get(key), 0.0)

    if revenue > 0 and cost > 0 and profit <= 0:
        profit = max(0.0, revenue - cost)

    if revenue > 0 and profit > 0 and cost <= 0:
        cost = max(0.0, revenue - profit)

    if revenue > 0 and profit > 0 and margin <= 0:
        margin = profit / revenue

    return {
        "estimated_revenue": _round_money(revenue),
        "estimated_cost": _round_money(cost),
        "estimated_profit": _round_money(profit),
        "estimated_margin": _round_margin(margin),
    }


def _read_all() -> List[Dict[str, Any]]:
    _ensure_storage()
    try:
        raw = _HISTORY_FILE.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []
    except Exception:
        return []


def _write_all(records: List[Dict[str, Any]]) -> None:
    _ensure_storage()
    _HISTORY_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _normalize_submission_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_result = _safe_dict(payload.get("raw_result"))
    metadata = _safe_dict(payload.get("metadata"))

    financials = _extract_financials_from_sources(
        payload,
        raw_result,
        metadata,
        _safe_dict(payload.get("financials")),
        _safe_dict(raw_result.get("financials")),
        _safe_dict(metadata.get("financials")),
        _safe_dict(payload.get("submission_pack")),
        _safe_dict(payload.get("quote_pack")),
        _safe_dict(raw_result.get("submission_pack")),
        _safe_dict(raw_result.get("quote_pack")),
        _safe_dict(metadata.get("submission_pack")),
        _safe_dict(metadata.get("quote_pack")),
    )

    raw_result["estimated_revenue"] = financials["estimated_revenue"]
    raw_result["estimated_cost"] = financials["estimated_cost"]
    raw_result["estimated_profit"] = financials["estimated_profit"]
    raw_result["estimated_margin"] = financials["estimated_margin"]

    metadata["estimated_revenue"] = financials["estimated_revenue"]
    metadata["estimated_cost"] = financials["estimated_cost"]
    metadata["estimated_profit"] = financials["estimated_profit"]
    metadata["estimated_margin"] = financials["estimated_margin"]

    return {
        "id": str(payload.get("id") or uuid.uuid4()),
        "created_at": str(payload.get("created_at") or _utc_now_iso()),
        "updated_at": str(payload.get("updated_at") or _utc_now_iso()),
        "buyer_name": str(payload.get("buyer_name") or "").strip(),
        "buyer_rfq_number": str(payload.get("buyer_rfq_number") or "").strip(),
        "quote_number": str(payload.get("quote_number") or "").strip(),
        "title": str(payload.get("title") or "").strip(),
        "submission_method": str(payload.get("submission_method") or "").strip(),
        "recipient_email": str(payload.get("recipient_email") or "").strip(),
        "portal_name": str(payload.get("portal_name") or "").strip(),
        "status": str(payload.get("status") or "unknown").strip(),
        "status_message": str(payload.get("status_message") or "").strip(),
        "document_path": str(payload.get("document_path") or "").strip(),
        "proof_path": str(payload.get("proof_path") or "").strip(),
        "submission_log_path": str(payload.get("submission_log_path") or "").strip(),
        "attachments": [str(x) for x in _safe_list(payload.get("attachments")) if str(x).strip()],
        "artifacts": [str(x) for x in _safe_list(payload.get("artifacts")) if str(x).strip()],
        "source": str(payload.get("source") or "").strip(),
        "submitted_by": str(payload.get("submitted_by") or "system").strip(),
        "retry_count": int(payload.get("retry_count") or 0),
        "raw_result": raw_result,
        "metadata": metadata,
    }


def log_submission_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = _normalize_submission_record(payload)

    with _LOCK:
        records = _read_all()
        records.insert(0, record)
        _write_all(records)

    return record


def update_submission_event(history_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    history_id = str(history_id or "").strip()
    if not history_id:
        return None

    with _LOCK:
        records = _read_all()
        for idx, record in enumerate(records):
            if str(record.get("id")) == history_id:
                merged = dict(record)
                merged.update(updates or {})
                merged["id"] = record["id"]
                merged["created_at"] = record.get("created_at") or _utc_now_iso()
                merged["updated_at"] = _utc_now_iso()

                normalized = _normalize_submission_record(merged)
                normalized["id"] = record["id"]
                normalized["created_at"] = record.get("created_at") or normalized["created_at"]
                normalized["updated_at"] = _utc_now_iso()

                records[idx] = normalized
                _write_all(records)
                return normalized

    return None


def get_submission_history_item(history_id: str) -> Optional[Dict[str, Any]]:
    history_id = str(history_id or "").strip()
    if not history_id:
        return None

    for record in _read_all():
        if str(record.get("id")) == history_id:
            return record
    return None


def list_submission_history(
    *,
    status: Optional[str] = None,
    buyer_name: Optional[str] = None,
    buyer_rfq_number: Optional[str] = None,
    quote_number: Optional[str] = None,
    submission_method: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    records = _read_all()

    def _matches(record: Dict[str, Any]) -> bool:
        if status and str(record.get("status") or "").lower() != status.lower():
            return False
        if buyer_name and buyer_name.lower() not in str(record.get("buyer_name") or "").lower():
            return False
        if buyer_rfq_number and buyer_rfq_number.lower() not in str(record.get("buyer_rfq_number") or "").lower():
            return False
        if quote_number and quote_number.lower() not in str(record.get("quote_number") or "").lower():
            return False
        if submission_method and str(record.get("submission_method") or "").lower() != submission_method.lower():
            return False
        return True

    filtered = [r for r in records if _matches(r)]
    total = len(filtered)

    safe_offset = max(0, int(offset or 0))
    safe_limit = max(1, min(int(limit or 100), 500))
    items = filtered[safe_offset : safe_offset + safe_limit]

    return {
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "items": items,
    }


def get_submission_summary() -> Dict[str, Any]:
    records = _read_all()

    summary = {
        "total": len(records),
        "submitted": 0,
        "failed": 0,
        "manual_action_required": 0,
        "queued": 0,
        "unknown": 0,
        "recent": records[:10],
        "history_file": str(_HISTORY_FILE),
    }

    for record in records:
        status = str(record.get("status") or "unknown").strip().lower()
        if status in summary:
            summary[status] += 1
        else:
            summary["unknown"] += 1

    return summary


def get_submission_history_by_rfq(buyer_rfq_number: str) -> List[Dict[str, Any]]:
    target = str(buyer_rfq_number or "").strip().lower()
    if not target:
        return []

    return [
        r
        for r in _read_all()
        if str(r.get("buyer_rfq_number") or "").strip().lower() == target
    ]




def search_submission_history_by_buyer_rfq(buyer_rfq_number: str) -> Optional[Dict[str, Any]]:
    """
    Returns the most recent record for an RFQ, or None.
    Added for Channel 2 duplicate-submission prevention compatibility.
    """
    items = get_submission_history_by_rfq(buyer_rfq_number)
    return items[0] if items else None


def has_recent_submission_retry_lock(
    buyer_rfq_number: str,
    statuses: Optional[List[str]] = None,
) -> bool:
    """
    Simple retry lock:
    If the latest record for the RFQ is queued, submitted, or manual_action_required,
    treat it as locked against blind retry.
    """
    statuses = statuses or ["queued", "submitted", "manual_action_required"]
    latest = search_submission_history_by_buyer_rfq(buyer_rfq_number)
    if not latest:
        return False
    return str(latest.get("status") or "").strip().lower() in {
        s.strip().lower() for s in statuses
    }

