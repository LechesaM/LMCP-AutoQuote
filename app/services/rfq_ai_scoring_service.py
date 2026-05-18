from typing import Dict, Any

SUPPLY_POSITIVE = [
    "supply", "delivery", "supply and delivery", "stationery",
    "office supplies", "material", "equipment", "goods"
]

NEGATIVE = [
    "construction", "maintenance", "service provider", "consulting",
    "catering", "cleaning", "security", "briefing", "site inspection",
    "medical", "software", "laptop", "diesel", "petrol"
]

HIGH_VALUE_HINTS = [
    "36 months", "12 months", "as and when required", "panel",
    "bulk", "framework", "municipality", "transnet", "eskom"
]


def score_rfq_ai(rfq: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join([
        str(rfq.get("title", "")),
        str(rfq.get("description", "")),
        str(rfq.get("raw_text", "")),
        str(rfq.get("buyer_name", "")),
    ]).lower()

    score = 0
    reasons = []

    for word in SUPPLY_POSITIVE:
        if word in text:
            score += 12
            reasons.append(f"supply signal: {word}")

    for word in HIGH_VALUE_HINTS:
        if word in text:
            score += 8
            reasons.append(f"value signal: {word}")

    for word in NEGATIVE:
        if word in text:
            score -= 25
            reasons.append(f"risk/exclusion signal: {word}")

    if "rfq" in text or "request for quotation" in text:
        score += 15
        reasons.append("RFQ wording detected")

    if rfq.get("closing_date"):
        score += 8
        reasons.append("closing date present")

    score = max(0, min(100, score))

    return {
        "ai_score": score,
        "ai_decision": "accept" if score >= 60 else "reject",
        "ai_reasons": reasons,
    }
