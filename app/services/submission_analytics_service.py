from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_RUNTIME_DIR = Path("runtime")
_HISTORY_FILE = _RUNTIME_DIR / "submission_history" / "submission_history.json"


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(_RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


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
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = (
            str(value)
            .replace(",", "")
            .replace("R", "")
            .replace("ZAR", "")
            .replace("zar", "")
            .strip()
        )
        return float(cleaned)
    except Exception:
        return default


def _read_history_records(runtime_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    history_file = _resolve_runtime_path(_HISTORY_FILE, runtime_dir)
    if not history_file.exists():
        return []
    try:
        raw = history_file.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except Exception:
        return []
    return []


def _extract_financials(record: Dict[str, Any]) -> Dict[str, float]:
    metadata = _safe_dict(record.get("metadata"))
    raw_result = _safe_dict(record.get("raw_result"))

    estimated_revenue = 0.0
    estimated_cost = 0.0
    estimated_profit = 0.0
    estimated_margin = 0.0

    candidates_revenue = [
        metadata.get("estimated_revenue"),
        metadata.get("quotation_total"),
        metadata.get("grand_total"),
        metadata.get("total_including_vat"),
        metadata.get("total"),
        raw_result.get("estimated_revenue"),
        raw_result.get("quotation_total"),
        raw_result.get("grand_total"),
        raw_result.get("total_including_vat"),
        raw_result.get("total"),
    ]
    for value in candidates_revenue:
        estimated_revenue = _safe_float(value, 0.0)
        if estimated_revenue > 0:
            break

    candidates_cost = [
        metadata.get("estimated_cost"),
        raw_result.get("estimated_cost"),
    ]
    for value in candidates_cost:
        estimated_cost = _safe_float(value, 0.0)
        if estimated_cost > 0:
            break

    candidates_profit = [
        metadata.get("estimated_profit"),
        raw_result.get("estimated_profit"),
    ]
    for value in candidates_profit:
        estimated_profit = _safe_float(value, 0.0)
        if estimated_profit > 0:
            break

    candidates_margin = [
        metadata.get("estimated_margin"),
        raw_result.get("estimated_margin"),
    ]
    for value in candidates_margin:
        estimated_margin = _safe_float(value, 0.0)
        if estimated_margin > 0:
            break

    if estimated_profit <= 0 and estimated_revenue > 0 and estimated_cost > 0:
        estimated_profit = max(0.0, estimated_revenue - estimated_cost)

    if estimated_margin <= 0 and estimated_profit > 0 and estimated_revenue > 0:
        estimated_margin = estimated_profit / estimated_revenue

    return {
        "estimated_revenue": round(estimated_revenue, 2),
        "estimated_cost": round(estimated_cost, 2),
        "estimated_profit": round(estimated_profit, 2),
        "estimated_margin": round(estimated_margin, 4),
    }


def _record_date_bucket(record: Dict[str, Any]) -> str:
    raw = _safe_str(record.get("created_at"))
    if not raw:
        return ""
    try:
        return raw[:10]
    except Exception:
        return ""


def _is_success_status(status: str) -> bool:
    return status.lower() in {"submitted", "sent", "success", "ok"}


def _is_failure_status(status: str) -> bool:
    return status.lower() in {"failed"}


def get_submission_success_tracking(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    records = _read_history_records(runtime_dir=runtime_dir)

    total = len(records)
    submitted = 0
    failed = 0
    manual_action_required = 0
    queued = 0
    other = 0

    by_method: Dict[str, Dict[str, Any]] = {}
    by_day = defaultdict(lambda: {
        "date": "",
        "total": 0,
        "submitted": 0,
        "failed": 0,
        "manual_action_required": 0,
        "queued": 0,
    })

    for record in records:
        status = _safe_str(record.get("status"), "unknown").lower()
        method = _safe_str(record.get("submission_method"), "unknown").lower() or "unknown"
        day = _record_date_bucket(record)

        if status == "submitted":
            submitted += 1
        elif status == "failed":
            failed += 1
        elif status == "manual_action_required":
            manual_action_required += 1
        elif status == "queued":
            queued += 1
        else:
            other += 1

        method_bucket = by_method.setdefault(method, {
            "submission_method": method,
            "total": 0,
            "submitted": 0,
            "failed": 0,
            "manual_action_required": 0,
            "queued": 0,
            "success_rate": 0.0,
        })
        method_bucket["total"] += 1
        if status in method_bucket:
            method_bucket[status] += 1

        if day:
            by_day[day]["date"] = day
            by_day[day]["total"] += 1
            if status in by_day[day]:
                by_day[day][status] += 1

    for bucket in by_method.values():
        total_method = int(bucket["total"] or 0)
        bucket["success_rate"] = round((bucket["submitted"] / total_method) if total_method > 0 else 0.0, 4)

    success_rate = round((submitted / total) if total > 0 else 0.0, 4)
    failure_rate = round((failed / total) if total > 0 else 0.0, 4)

    return {
        "status": "ok",
        "checked_at": _utc_now_iso(),
        "history_file": str(_resolve_runtime_path(_HISTORY_FILE, runtime_dir)),
        "total": total,
        "submitted": submitted,
        "failed": failed,
        "manual_action_required": manual_action_required,
        "queued": queued,
        "other": other,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "by_method": sorted(by_method.values(), key=lambda x: (-x["total"], x["submission_method"])),
        "by_day": sorted(by_day.values(), key=lambda x: x["date"], reverse=True)[:30],
    }


def get_submission_profit_tracking(submitted_only: bool = True, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    records = _read_history_records(runtime_dir=runtime_dir)

    total_revenue = 0.0
    total_cost = 0.0
    total_profit = 0.0

    by_method: Dict[str, Dict[str, Any]] = {}
    by_day = defaultdict(lambda: {
        "date": "",
        "count": 0,
        "estimated_revenue": 0.0,
        "estimated_cost": 0.0,
        "estimated_profit": 0.0,
    })

    counted = 0
    uncosted_records = 0

    for record in records:
        status = _safe_str(record.get("status"), "unknown")
        if submitted_only and not _is_success_status(status):
            continue

        method = _safe_str(record.get("submission_method"), "unknown").lower() or "unknown"
        day = _record_date_bucket(record)
        financials = _extract_financials(record)

        revenue = financials["estimated_revenue"]
        cost = financials["estimated_cost"]
        profit = financials["estimated_profit"]

        if revenue <= 0 and cost <= 0 and profit <= 0:
            uncosted_records += 1
            continue

        counted += 1
        total_revenue += revenue
        total_cost += cost
        total_profit += profit

        bucket = by_method.setdefault(method, {
            "submission_method": method,
            "count": 0,
            "estimated_revenue": 0.0,
            "estimated_cost": 0.0,
            "estimated_profit": 0.0,
            "average_profit": 0.0,
        })
        bucket["count"] += 1
        bucket["estimated_revenue"] += revenue
        bucket["estimated_cost"] += cost
        bucket["estimated_profit"] += profit

        if day:
            by_day[day]["date"] = day
            by_day[day]["count"] += 1
            by_day[day]["estimated_revenue"] += revenue
            by_day[day]["estimated_cost"] += cost
            by_day[day]["estimated_profit"] += profit

    for bucket in by_method.values():
        count = int(bucket["count"] or 0)
        bucket["estimated_revenue"] = round(bucket["estimated_revenue"], 2)
        bucket["estimated_cost"] = round(bucket["estimated_cost"], 2)
        bucket["estimated_profit"] = round(bucket["estimated_profit"], 2)
        bucket["average_profit"] = round((bucket["estimated_profit"] / count) if count > 0 else 0.0, 2)

    by_day_list = []
    for bucket in by_day.values():
        bucket["estimated_revenue"] = round(bucket["estimated_revenue"], 2)
        bucket["estimated_cost"] = round(bucket["estimated_cost"], 2)
        bucket["estimated_profit"] = round(bucket["estimated_profit"], 2)
        by_day_list.append(bucket)

    realized_margin = round((total_profit / total_revenue) if total_revenue > 0 else 0.0, 4)

    return {
        "status": "ok",
        "checked_at": _utc_now_iso(),
        "history_file": str(_resolve_runtime_path(_HISTORY_FILE, runtime_dir)),
        "submitted_only": submitted_only,
        "counted_records": counted,
        "uncosted_records": uncosted_records,
        "estimated_revenue": round(total_revenue, 2),
        "estimated_cost": round(total_cost, 2),
        "estimated_profit": round(total_profit, 2),
        "estimated_margin": realized_margin,
        "by_method": sorted(by_method.values(), key=lambda x: (-x["estimated_profit"], x["submission_method"])),
        "by_day": sorted(by_day_list, key=lambda x: x["date"], reverse=True)[:30],
    }


def get_submission_success_and_profit_summary(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    success = get_submission_success_tracking(runtime_dir=runtime_dir)
    profit = get_submission_profit_tracking(submitted_only=True, runtime_dir=runtime_dir)

    return {
        "status": "ok",
        "checked_at": _utc_now_iso(),
        "success_tracking": success,
        "profit_tracking": profit,
        "note": (
            "Profit tracking currently relies on estimated financial values present in submission history "
            "metadata/raw_result. For full accuracy, persist estimated_revenue, estimated_cost, and "
            "estimated_profit into submission history when the tender pipeline writes submission events."
        ),
    }

