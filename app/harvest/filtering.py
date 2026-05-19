from __future__ import annotations

from typing import Any, Dict, Iterable


EXCLUDED_CATEGORY_KEYWORDS = {
    "medical consumable": "medical consumables excluded",
    "medical supplies": "medical consumables excluded",
    "it equipment": "IT equipment excluded",
    "laptop": "IT equipment excluded",
    "desktop": "IT equipment excluded",
    "petrol": "fuel excluded",
    "diesel": "fuel excluded",
    "fuel": "fuel excluded",
    "catering": "catering excluded",
    "food service": "catering excluded",
    "construction only": "construction-only excluded",
    "construction": "construction-only excluded",
    "service only": "service-only excluded",
    "professional services": "service-only excluded",
}


def _lower_text(values: Iterable[Any]) -> str:
    return " ".join(str(item or "").lower() for item in values if item is not None)


def evaluate_prequalification(candidate: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = dict(candidate or {})
    text = _lower_text(
        [
            payload.get("title"),
            payload.get("buyer"),
            payload.get("reference"),
            payload.get("description"),
            payload.get("category_guess"),
            payload.get("raw_text"),
        ]
    )
    briefing_required = payload.get("briefing_required")
    reasons: list[str] = []
    low_confidence = False
    rejection_reason = ""

    if briefing_required is True or "compulsory briefing" in text or "mandatory briefing" in text:
        rejection_reason = "compulsory briefing required"
        reasons.append(rejection_reason)
    else:
        for keyword, reason in EXCLUDED_CATEGORY_KEYWORDS.items():
            if keyword in text:
                rejection_reason = reason
                reasons.append(reason)
                break

    if not payload.get("reference"):
        low_confidence = True
        reasons.append("missing reference")
    if not payload.get("closing_date"):
        low_confidence = True
        reasons.append("missing closing date")
    if not payload.get("documents"):
        low_confidence = True
        reasons.append("no documents discovered")

    value = payload.get("estimated_value") or payload.get("contract_value") or payload.get("budget")
    estimated_profit = 0.0
    if value not in (None, ""):
        try:
            estimated_profit = round(float(str(value).replace(",", "").replace("R", "").strip()) * 0.25, 2)
        except Exception:
            estimated_profit = 0.0

    eligible = not bool(rejection_reason)
    if not eligible:
        low_confidence = False

    return {
        "eligible": eligible,
        "low_confidence": low_confidence,
        "rejection_reason": rejection_reason,
        "reasons": list(dict.fromkeys(reasons)),
        "estimated_margin": 25.0,
        "estimated_profit": estimated_profit,
        "qualification_hint": "likely supply and delivery" if eligible else "rejected during pre-qualification",
    }
