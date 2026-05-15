from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _predict_window(last_seen_at: Optional[str], avg_days_between_buys: Optional[float]) -> Dict[str, Optional[str]]:
    if not last_seen_at or avg_days_between_buys is None:
        return {
            "predicted_start_date": None,
            "predicted_end_date": None,
        }

    try:
        last_seen = datetime.fromisoformat(last_seen_at)
    except Exception:
        return {
            "predicted_start_date": None,
            "predicted_end_date": None,
        }

    center = last_seen + timedelta(days=int(avg_days_between_buys))
    start = center - timedelta(days=14)
    end = center + timedelta(days=21)

    return {
        "predicted_start_date": start.date().isoformat(),
        "predicted_end_date": end.date().isoformat(),
    }


def generate_procurement_signals(
    buyer_code: str,
    current_category: str,
    profile_summary: Dict[str, Any],
    behavior_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []

    avg_gap = profile_summary.get("avg_days_between_buys")
    last_seen_at = profile_summary.get("last_seen_at")
    repeat_buying_score = profile_summary.get("repeat_buying_score", 0.0)
    category_alignment_score = behavior_summary.get("category_alignment_score", 0.0)
    repeat_pattern_detected = behavior_summary.get("repeat_pattern_detected", False)

    predicted_window = _predict_window(last_seen_at, avg_gap)

    if repeat_pattern_detected:
        confidence = min(
            0.99,
            ((repeat_buying_score * 0.5) + (category_alignment_score * 0.5)) / 100.0,
        )
        signals.append(
            {
                "buyer_code": buyer_code,
                "signal_type": "repeat_category_restock",
                "category": current_category,
                "confidence_score": round(confidence, 4),
                "reason": "Buyer has repeated procurement activity in this category.",
                "predicted_start_date": predicted_window["predicted_start_date"],
                "predicted_end_date": predicted_window["predicted_end_date"],
            }
        )

    if avg_gap is not None and avg_gap <= 120:
        confidence = min(0.95, max(0.40, 1 - (avg_gap / 200)))
        signals.append(
            {
                "buyer_code": buyer_code,
                "signal_type": "active_buyer_cycle",
                "category": current_category,
                "confidence_score": round(confidence, 4),
                "reason": "Buyer has a relatively active procurement cycle based on historical spacing.",
                "predicted_start_date": predicted_window["predicted_start_date"],
                "predicted_end_date": predicted_window["predicted_end_date"],
            }
        )

    return signals
