"""Win-probability ranking engine (v1: rules + weights)

This produces:
- priority_score (0..100+)
- priority_band (A/B/C)
- score_features (json)

Start simple, then learn from outcomes.
"""

from datetime import datetime, timezone

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def compute_priority(opp: dict) -> dict:
    # Expected fields in `opp` dict:
    # closing_dt (iso), submission_method, email_allowed, response_email,
    # soe_id, soe_match_confidence, pricing_flags.needs_review, has_compliance_docs

    score = 0.0
    feats = {}

    # Time to close
    td_hours = 9999.0
    try:
        if opp.get("closing_dt"):
            dt = datetime.fromisoformat(opp["closing_dt"].replace("Z","+00:00"))
            td_hours = (dt - datetime.now(timezone.utc)).total_seconds()/3600.0
    except Exception:
        td_hours = 9999.0

    if td_hours <= 24:
        score += 18; feats["time_close_24h"]=1
    elif td_hours <= 72:
        score += 12; feats["time_close_72h"]=1
    elif td_hours <= 168:
        score += 6; feats["time_close_7d"]=1
    else:
        score += 2; feats["time_close_long"]=1

    # Submission method
    if opp.get("email_allowed") and opp.get("response_email"):
        score += 20; feats["email_allowed"]=1
    if (opp.get("submission_method") or "").lower() == "portal":
        score -= 8; feats["portal_only_penalty"]=1

    # SOE match confidence
    conf = float(opp.get("soe_match_confidence") or 0)
    if opp.get("soe_id"):
        if conf >= 0.85: score += 12; feats["soe_high"]=1
        elif conf >= 0.70: score += 6; feats["soe_mid"]=1
        elif conf >= 0.60: score += 2; feats["soe_low"]=1

    # Review/compliance gates
    needs_review = bool(((opp.get("pricing_flags") or {}).get("needs_review")))
    if needs_review:
        score -= 20; feats["needs_review_penalty"]=1

    if opp.get("has_compliance_docs"):
        score += 10; feats["compliance_ready"]=1
    else:
        score -= 5; feats["compliance_missing"]=1

    score = clamp(score, 0, 120)

    band = "C"
    if score >= 70: band = "A"
    elif score >= 45: band = "B"

    return {"priority_score": score, "priority_band": band, "score_features": feats}
