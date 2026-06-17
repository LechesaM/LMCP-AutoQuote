from collections import Counter
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional


def _safe_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def build_profile_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not events:
        return {
            "event_count": 0,
            "first_seen_at": None,
            "last_seen_at": None,
            "avg_days_between_buys": None,
            "top_categories": [],
            "buyer_activity_score": 0.0,
            "procurement_frequency_score": 0.0,
            "repeat_buying_score": 0.0,
        }

    parsed_dates = []
    category_counter = Counter()

    for event in events:
        published_at = _safe_datetime(event.get("published_at"))
        if published_at:
            parsed_dates.append(published_at)

        category = event.get("category")
        if category:
            category_counter[category] += 1

    parsed_dates.sort()

    gaps = []
    for i in range(1, len(parsed_dates)):
        delta = (parsed_dates[i] - parsed_dates[i - 1]).days
        if delta >= 0:
            gaps.append(delta)

    avg_gap = round(mean(gaps), 2) if gaps else None
    event_count = len(events)
    top_categories = [category for category, _ in category_counter.most_common(5)]

    buyer_activity_score = min(100.0, event_count * 5.0)
    procurement_frequency_score = 0.0
    if avg_gap is not None:
        if avg_gap <= 30:
            procurement_frequency_score = 95.0
        elif avg_gap <= 60:
            procurement_frequency_score = 85.0
        elif avg_gap <= 90:
            procurement_frequency_score = 75.0
        elif avg_gap <= 180:
            procurement_frequency_score = 60.0
        else:
            procurement_frequency_score = 40.0

    most_common_count = category_counter.most_common(1)[0][1] if category_counter else 0
    repeat_buying_score = min(100.0, most_common_count * 20.0)

    return {
        "event_count": event_count,
        "first_seen_at": parsed_dates[0].isoformat() if parsed_dates else None,
        "last_seen_at": parsed_dates[-1].isoformat() if parsed_dates else None,
        "avg_days_between_buys": avg_gap,
        "top_categories": top_categories,
        "buyer_activity_score": round(buyer_activity_score, 2),
        "procurement_frequency_score": round(procurement_frequency_score, 2),
        "repeat_buying_score": round(repeat_buying_score, 2),
    }
