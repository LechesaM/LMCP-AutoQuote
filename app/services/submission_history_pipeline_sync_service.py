from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


RUNTIME_DIR = Path("runtime")
SUBMISSION_HISTORY_DIR = RUNTIME_DIR / "submission_history"
SUBMISSION_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

SUBMISSION_HISTORY_FILE = SUBMISSION_HISTORY_DIR / "submission_history.json"
MONTHLY_QUOTES_DIR = Path("monthly_quotes")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        text = str(value).strip()
        return text if text else default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = (
                value.replace("R", "")
                .replace("ZAR", "")
                .replace("zar", "")
                .replace(",", "")
                .strip()
            )
        return float(value)
    except Exception:
        return default


def _read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = []
    try:
        if not path.exists() or not path.is_file():
            return default
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _find_value(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data.get(key) not in (None, ""):
            return data.get(key)

    for value in data.values():
        if isinstance(value, dict):
            found = _find_value(value, *keys)
            if found not in (None, ""):
                return found
    return None


def _extract_financials(data: Dict[str, Any]) -> Dict[str, float]:
    pricing = data.get("pricing_summary") if isinstance(data.get("pricing_summary"), dict) else {}
    totals = data.get("totals") if isinstance(data.get("totals"), dict) else {}
    quote_pack = data.get("quote_pack_result") if isinstance(data.get("quote_pack_result"), dict) else {}
    quote_totals = quote_pack.get("totals") if isinstance(quote_pack.get("totals"), dict) else {}

    total_profit = _safe_float(
        _find_value(data, "total_profit", "estimated_profit", "profit")
        or pricing.get("total_profit")
        or totals.get("estimated_profit")
        or quote_totals.get("estimated_profit"),
        0.0,
    )

    total_sell_incl_vat = _safe_float(
        _find_value(data, "total_sell_incl_vat", "total_incl_vat", "quotation_total", "grand_total")
        or pricing.get("total_sell_incl_vat")
        or totals.get("total_incl_vat")
        or quote_totals.get("total_incl_vat"),
        0.0,
    )

    return {
        "total_profit": round(total_profit, 2),
        "total_sell_incl_vat": round(total_sell_incl_vat, 2),
    }


def _normalise_status(data: Dict[str, Any]) -> str:
    raw = _safe_str(
        data.get("submission_status")
        or data.get("pipeline_status")
        or _find_value(data, "submission_status", "status")
        or "unknown"
    ).lower()

    if raw in {"sent", "success", "ok", "submitted"}:
        return "submitted"
    if "sent successfully" in _safe_str(data.get("submission_message")).lower():
        return "submitted"
    if raw in {"failed", "error"}:
        return "failed"
    return raw or "unknown"


def _extract_record_from_json(path: Path) -> Optional[Dict[str, Any]]:
    data = _read_json(path, default={})
    if not isinstance(data, dict):
        return None

    status = _normalise_status(data)
    message = _safe_str(_find_value(data, "submission_message", "status_message", "message", "error"))

    # Only sync real pipeline records that actually reached submission status.
    if status not in {"submitted", "failed"} and "email submission sent successfully" not in message.lower():
        return None

    submission_pack = data.get("submission_pack") if isinstance(data.get("submission_pack"), dict) else {}
    buyer = data.get("buyer") if isinstance(data.get("buyer"), dict) else {}
    quote_pack = data.get("quote_pack_result") if isinstance(data.get("quote_pack_result"), dict) else {}

    buyer_rfq_number = _safe_str(
        data.get("buyer_rfq_number")
        or data.get("rfq_number")
        or submission_pack.get("buyer_rfq_number")
        or submission_pack.get("document_number")
        or buyer.get("rfq_number")
        or quote_pack.get("buyer", {}).get("rfq_number") if isinstance(quote_pack.get("buyer"), dict) else ""
    )

    quote_number = _safe_str(
        data.get("quote_number")
        or data.get("lmcp_quote_number")
        or submission_pack.get("quote_number")
        or quote_pack.get("quote_number")
    )

    buyer_name = _safe_str(
        data.get("buyer_name")
        or buyer.get("name")
        or buyer.get("company_name")
        or quote_pack.get("buyer", {}).get("name") if isinstance(quote_pack.get("buyer"), dict) else ""
    )

    title = _safe_str(
        data.get("title")
        or data.get("description")
        or quote_pack.get("rfq_title")
        or "Submitted RFQ"
    )

    recipient_email = _safe_str(
        data.get("recipient_email")
        or data.get("submission_email")
        or data.get("buyer_email")
        or submission_pack.get("recipient_email")
        or submission_pack.get("submission_email")
        or submission_pack.get("buyer_email")
        or buyer.get("email")
    )

    submitted_at = _safe_str(
        data.get("submitted_at")
        or data.get("updated_at")
        or submission_pack.get("submitted_at")
        or _now()
    )

    pdf_path = _safe_str(
        data.get("final_pdf_path")
        or data.get("pdf_path")
        or submission_pack.get("final_pdf_path")
        or submission_pack.get("pdf_path")
    )

    financials = _extract_financials(data)

    return {
        "buyer_rfq_number": buyer_rfq_number or "UNKNOWN",
        "quote_number": quote_number or "",
        "buyer_name": buyer_name or "Unknown buyer",
        "title": title,
        "status": status,
        "submission_status": status,
        "pipeline_status": _safe_str(data.get("pipeline_status"), status),
        "submission_method": _safe_str(data.get("submission_method") or submission_pack.get("submission_method"), "email"),
        "recipient_email": recipient_email,
        "submitted_at": submitted_at,
        "submission_message": message,
        "total_profit": financials["total_profit"],
        "total_sell_incl_vat": financials["total_sell_incl_vat"],
        "pdf_path": pdf_path,
        "source": "monthly_quotes_pipeline_log",
        "source_json": str(path),
        "raw_result": data,
        "metadata": {
            "synced_from_real_pipeline_logs": True,
            "synced_at": _now(),
        },
    }


def _record_key(record: Dict[str, Any]) -> str:
    return "|".join(
        [
            _safe_str(record.get("buyer_rfq_number")).lower(),
            _safe_str(record.get("quote_number")).lower(),
            _safe_str(record.get("submitted_at")),
            _safe_str(record.get("recipient_email")).lower(),
        ]
    )


def sync_submission_history_from_pipeline_logs(limit: int = 500) -> Dict[str, Any]:
    existing = _read_json(SUBMISSION_HISTORY_FILE, default=[])
    if not isinstance(existing, list):
        existing = []

    existing_by_key = {_record_key(item): item for item in existing if isinstance(item, dict)}

    scanned = 0
    added = 0
    updated = 0
    skipped = 0
    records: List[Dict[str, Any]] = []

    candidates: List[Path] = []
    if MONTHLY_QUOTES_DIR.exists():
        candidates.extend(MONTHLY_QUOTES_DIR.rglob("*quote_pack*.json"))
        candidates.extend(MONTHLY_QUOTES_DIR.rglob("*submission*.json"))
        candidates.extend(MONTHLY_QUOTES_DIR.rglob("*.json"))

    # Newest first by modified time.
    candidates = sorted(
        set(candidates),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )[: max(1, int(limit or 500))]

    for path in candidates:
        scanned += 1
        record = _extract_record_from_json(path)
        if not record:
            skipped += 1
            continue

        key = _record_key(record)
        if key in existing_by_key:
            existing_by_key[key].update(record)
            updated += 1
        else:
            existing.append(record)
            existing_by_key[key] = record
            added += 1

        records.append(record)

    existing = sorted(
        existing,
        key=lambda x: _safe_str(x.get("submitted_at")) if isinstance(x, dict) else "",
        reverse=True,
    )

    _write_json(SUBMISSION_HISTORY_FILE, existing)

    submitted = len([x for x in existing if isinstance(x, dict) and _safe_str(x.get("status")).lower() == "submitted"])
    failed = len([x for x in existing if isinstance(x, dict) and _safe_str(x.get("status")).lower() == "failed"])
    total_profit = sum(_safe_float(x.get("total_profit"), 0.0) for x in existing if isinstance(x, dict))

    return {
        "status": "ok",
        "history_file": str(SUBMISSION_HISTORY_FILE),
        "monthly_quotes_dir": str(MONTHLY_QUOTES_DIR),
        "scanned": scanned,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "count": len(existing),
        "submitted": submitted,
        "failed": failed,
        "total_profit": round(total_profit, 2),
        "synced_records": records,
    }


def get_synced_submission_history(limit: int = 20) -> Dict[str, Any]:
    sync_submission_history_from_pipeline_logs(limit=500)
    items = _read_json(SUBMISSION_HISTORY_FILE, default=[])
    if not isinstance(items, list):
        items = []

    items = sorted(
        items,
        key=lambda x: _safe_str(x.get("submitted_at")) if isinstance(x, dict) else "",
        reverse=True,
    )[: max(1, int(limit or 20))]

    return {
        "status": "ok",
        "source": str(SUBMISSION_HISTORY_FILE),
        "available": SUBMISSION_HISTORY_FILE.exists(),
        "count": len(items),
        "submitted": len([x for x in items if _safe_str(x.get("status")).lower() == "submitted"]),
        "failed": len([x for x in items if _safe_str(x.get("status")).lower() == "failed"]),
        "total_profit": round(sum(_safe_float(x.get("total_profit"), 0.0) for x in items), 2),
        "items": items,
        "submissions": items,
        "recent": items,
    }
