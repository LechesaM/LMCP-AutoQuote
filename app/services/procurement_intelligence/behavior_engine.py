from typing import Any, Dict, List


def analyze_buyer_behavior(
    current_category: str,
    profile_summary: Dict[str, Any],
    historical_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    top_categories = profile_summary.get("top_categories", [])
    avg_gap = profile_summary.get("avg_days_between_buys")
    event_count = profile_summary.get("event_count", 0)

    category_alignment_score = 90.0 if current_category in top_categories else 55.0

    if event_count >= 12:
        buyer_maturity = "high_history"
    elif event_count >= 5:
        buyer_maturity = "moderate_history"
    else:
        buyer_maturity = "low_history"

    repeat_pattern_detected = current_category in top_categories and event_count >= 3

    seasonal_pattern_score = 0.0
    if avg_gap is not None:
        if 25 <= avg_gap <= 45:
            seasonal_pattern_score = 70.0
        elif 80 <= avg_gap <= 110:
            seasonal_pattern_score = 80.0
        elif 170 <= avg_gap <= 210:
            seasonal_pattern_score = 85.0
        else:
            seasonal_pattern_score = 45.0

    competition_favorability_score = 60.0
    if event_count < 4:
        competition_favorability_score = 72.0
    elif event_count > 15:
        competition_favorability_score = 52.0

    return {
        "buyer_maturity": buyer_maturity,
        "repeat_pattern_detected": repeat_pattern_detected,
        "category_alignment_score": round(category_alignment_score, 2),
        "seasonal_pattern_score": round(seasonal_pattern_score, 2),
        "competition_favorability_score": round(competition_favorability_score, 2),
    }
