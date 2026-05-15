# app/services/submission_history_recent_service.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


HISTORY_CANDIDATES = [
    Path("runtime/submission_history/submission_history.json"),
    Path("runtime/submissions/submission_history.json"),
    Path("runtime/submission_scheduler/submission_history.json"),
    Path("monthly_quotes/submission_history.json"),
]


def _safe_read_json(path: Path) -> Any:
    try:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        return json.loads(text)
    except Exception:
        return None


def _normalise_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "buyer_rfq_number": "UNKNOWN",
            "buyer_name": "Unknown buyer",
            "status": "unknown",
            "raw": item,
        }

    raw_result = item.get("raw_result") or {}
    metadata = item.get("metadata") or {}

    buyer_rfq_number = (
        item.get("buyer_rfq_number")
        or raw_result.get("buyer_rfq_number")
        or raw_result.get("rfq_number")
        or raw_result.get("reference_number")
        or metadata.get("buyer_rfq_number")
        or "UNKNOWN"
    )

    quote_number = (
        item.get("quote_number")
        or raw_result.get("quote_number")
        or raw_result.get("lmcp_quote_number")
        or metadata.get("quote_number")
        or ""
    )

    buyer_name = (
        item.get("buyer_name")
        or raw_result.get("buyer_name")
        or raw_result.get("organ_of_state")
        or metadata.get("buyer_name")
        or "Unknown buyer"
    )

    status = (
        item.get("status")
        or item.get("submission_status")
        or raw_result.get("submission_status")
        or raw_result.get("pipeline_status")
        or metadata.get("status")
        or "submitted"
    )

    submitted_at = (
        item.get("submitted_at")
        or item.get("created_at")
        or item.get("updated_at")
        or raw_result.get("submitted_at")
        or raw_result.get("created_at")
        or raw_result.get("updated_at")
        or metadata.get("submitted_at")
        or ""
    )

    total_profit = (
        item.get("total_profit")
        or raw_result.get("total_profit")
        or raw_result.get("pricing_summary", {}).get("total_profit")
        or metadata.get("total_profit")
        or 0
    )

    total_sell_incl_vat = (
        item.get("total_sell_incl_vat")
        or raw_result.get("total_sell_incl_vat")
        or raw_result.get("pricing_summary", {}).get("total_sell_incl_vat")
        or metadata.get("total_sell_incl_vat")
        or 0
    )

    submission_method = (
        item.get("submission_method")
        or raw_result.get("submission_method")
        or metadata.get("submission_method")
        or ""
    )

    recipient_email = (
        item.get("recipient_email")
        or raw_result.get("recipient_email")
        or raw_result.get("submission_email")
        or raw_result.get("buyer_email")
        or metadata.get("recipient_email")
        or ""
    )

    return {
        "buyer_rfq_number": str(buyer_rfq_number),
        "quote_number": str(quote_number),
        "buyer_name": str(buyer_name),
        "status": str(status),
        "submission_status": str(status),
        "pipeline_status": str(raw_result.get("pipeline_status") or item.get("pipeline_status") or status),
        "submitted_at": str(submitted_at),
        "submission_method": str(submission_method),
        "recipient_email": str(recipient_email),
        "total_profit": float(total_profit or 0),
        "total_sell_incl_vat": float(total_sell_incl_vat or 0),
    }


def _extract_items(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []

    if isinstance(payload, list):
        return [_normalise_item(x) for x in payload]

    if isinstance(payload, dict):
        for key in ("items", "submissions", "history", "recent", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [_normalise_item(x) for x in value]

        # Single record fallback
        if payload:
            return [_normalise_item(payload)]

    return []


def load_recent_submission_history(limit: int = 20) -> Dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))

    source_path: Optional[Path] = None
    payload: Any = None

    for candidate in HISTORY_CANDIDATES:
        payload = _safe_read_json(candidate)
        if payload is not None:
            source_path = candidate
            break

    items = _extract_items(payload)

    def sort_key(x: Dict[str, Any]) -> str:
        return str(x.get("submitted_at") or "")

    items = sorted(items, key=sort_key, reverse=True)[:limit]

    submitted = len([x for x in items if "submit" in str(x.get("status", "")).lower() or str(x.get("status", "")).lower() == "success"])
    failed = len([x for x in items if "fail" in str(x.get("status", "")).lower() or "error" in str(x.get("status", "")).lower()])
    total_profit = sum(float(x.get("total_profit") or 0) for x in items)

    return {
        "status": "ok",
        "source": str(source_path) if source_path else None,
        "available": source_path is not None,
        "count": len(items),
        "submitted": submitted,
        "failed": failed,
        "total_profit": total_profit,
        "items": items,
        "submissions": items,
        "recent": items,
    }
