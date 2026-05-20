from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 2)
    except Exception:
        return round(float(default), 2)


def parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def to_bucket_label(value: datetime | None, window: str) -> str:
    if not value:
        return "unknown"
    if window == "month":
        return f"{value.year:04d}-{value.month:02d}"
    iso = value.isocalendar()
    if window == "week":
        return f"{iso.year:04d}-W{iso.week:02d}"
    return value.date().isoformat()


def group_trend_records(records: Sequence[Dict[str, Any]], *, window: str = "week", limit: int = 12) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"label": "", "count": 0, "total": 0.0, "go": 0, "manual_review": 0, "reject": 0})
    for record in records:
        created_at = parse_iso(record.get("created_at") or record.get("updated_at"))
        bucket = to_bucket_label(created_at, window)
        entry = buckets[bucket]
        entry["label"] = bucket
        entry["count"] += 1
        entry["total"] += safe_float(
            record.get("estimated_profit")
            or record.get("gross_profit")
            or record.get("payload", {}).get("estimated_profit")
            or record.get("payload", {}).get("gross_profit")
        )
        recommendation = str(record.get("recommendation") or record.get("outcome_status") or record.get("result") or "").upper()
        if recommendation == "GO":
            entry["go"] += 1
        elif recommendation == "MANUAL_REVIEW":
            entry["manual_review"] += 1
        elif recommendation == "REJECT":
            entry["reject"] += 1
    ordered = sorted(buckets.values(), key=lambda item: item["label"], reverse=True)
    return ordered[: max(1, int(limit or 12))]


def rolling_average(values: Sequence[float], window: int = 3) -> List[float]:
    window = max(1, int(window or 1))
    result: List[float] = []
    for index in range(len(values)):
        chunk = values[max(0, index - window + 1) : index + 1]
        result.append(round(mean(chunk), 2) if chunk else 0.0)
    return result


def summarize_counts(records: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    counter = Counter(str(record.get(key) or "unknown") for record in records)
    return dict(counter)

