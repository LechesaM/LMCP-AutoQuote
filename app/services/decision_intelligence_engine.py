from datetime import datetime
from typing import Dict, Any

CONFIG = {
    "min_profit": 30000,
    "min_margin": 25.0,
    "auto_submit_threshold": 75,
    "review_threshold": 55,
}

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))

def _score_profit(profit):
    # 0–40 points
    return _clamp((profit / 100000) * 40, 0, 40)

def _score_margin(margin):
    # 0–25 points
    return _clamp((margin / 40) * 25, 0, 25)

def _score_submission(method):
    # email easiest → more points
    if method == "email":
        return 15
    if method == "portal":
        return 8
    return 5

def _score_keyword_fit(text: str):
    # simple keyword boost (0–10)
    text = (text or "").lower()
    good = ["supply", "delivery", "goods", "materials", "equipment"]
    score = sum(1 for k in good if k in text)
    return _clamp(score * 2, 0, 10)

def evaluate_rfq(payload: Dict[str, Any]) -> Dict[str, Any]:
    pricing = payload.get("pricing_summary") or {}
    profit = float(pricing.get("total_profit", 0))
    margin = float(pricing.get("achieved_margin_percent", 0))
    method = (payload.get("submission_method") or "").lower()
    text = f"{payload.get('title','')} {payload.get('description','')}"

    # Hard stops
    if profit < CONFIG["min_profit"]:
        return {
            "decision": "skip",
            "reason": "profit_below_threshold",
            "score": 0,
        }

    if margin < CONFIG["min_margin"]:
        return {
            "decision": "skip",
            "reason": "margin_below_threshold",
            "score": 0,
        }

    score = (
        _score_profit(profit) +
        _score_margin(margin) +
        _score_submission(method) +
        _score_keyword_fit(text)
    )

    score = int(_clamp(score, 0, 100))

    if score >= CONFIG["auto_submit_threshold"]:
        decision = "auto_submit"
    elif score >= CONFIG["review_threshold"]:
        decision = "review"
    else:
        decision = "skip"

    return {
        "decision": decision,
        "score": score,
        "profit": profit,
        "margin": margin,
        "evaluated_at": datetime.utcnow().isoformat(),
    }
