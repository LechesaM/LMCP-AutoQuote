from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


REJECT_KEYWORDS: Dict[str, List[str]] = {
    "catering": ["catering", "canteen", "meal provision", "food service"],
    "it_equipment": ["it equipment", "ict equipment", "laptop", "desktop", "printer", "server", "router", "switch", "computer"],
    "fuel_diesel": ["petrol", "diesel", "fuel", "bulk fuel", "refuelling", "refueling"],
    "professional_services": ["professional services", "consulting services", "consulting", "advisory services", "audit services"],
    "construction_execution": ["construction", "civil works", "building works", "refurbishment", "maintenance works", "road works", "installation works"],
    "medical_consumables": ["medical consumables", "medical supply", "pharmaceutical", "clinical consumables", "laboratory reagents", "surgical gloves"],
}

CATEGORY_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("technical_fabrication", ["prefabricated", "fabrication", "fabricated", "custom build", "engineered", "container", "workshop", "assembly"]),
    ("household_products", ["household products", "home products", "domestic products", "household", "laundry", "cleaning products", "detergent", "soap"]),
    ("building_materials", ["building materials", "cement", "bricks", "sand", "stone", "aggregate", "roofing", "timber", "hardware materials"]),
    ("ppe", ["ppe", "personal protective equipment", "safety boots", "safety gloves", "hard hat", "reflective vest", "protective clothing"]),
    ("equipment_supply", ["equipment", "pump", "units", "generator", "generator set", "machinery", "industrial supply", "valve", "compressor", "switchgear", "network equipment"]),
    ("consumables", ["consumable", "consumables", "office consumables", "stationery", "general supplies", "supply and delivery", "supply of"]),
]


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _collect_text(payload: Dict[str, Any]) -> str:
    parts = [
        payload.get("tender_id"),
        payload.get("title"),
        payload.get("buyer_name"),
        payload.get("category"),
        payload.get("description"),
        payload.get("submission_instructions"),
        payload.get("extracted_text"),
        payload.get("source_text"),
    ]
    for line_item in payload.get("line_items") or []:
        if isinstance(line_item, dict):
            parts.append(line_item.get("description"))
            parts.append(line_item.get("notes"))
    return _normalize(" ".join(str(part or "") for part in parts))


def _match_keywords(text: str, keywords: List[str]) -> List[str]:
    matches: List[str] = []
    for keyword in keywords:
        if keyword in text:
            matches.append(keyword)
    return matches


def _best_category(text: str, category_hint: str) -> Dict[str, Any]:
    reasons: List[str] = []
    hint = _normalize(category_hint)
    if any(keyword in text or keyword in hint for keyword in REJECT_KEYWORDS["catering"]):
        return {"category": "catering", "confidence": 0.98, "reasons": ["catering keyword detected"], "excluded_category": True, "manual_review_required": False}
    if any(keyword in text or keyword in hint for keyword in REJECT_KEYWORDS["medical_consumables"]):
        return {
            "category": "unknown",
            "confidence": 0.92,
            "reasons": ["medical consumables keyword detected"],
            "excluded_category": True,
            "manual_review_required": False,
        }
    for category, keywords in REJECT_KEYWORDS.items():
        if category in {"catering", "medical_consumables"}:
            continue
        matches = _match_keywords(text, keywords)
        if matches:
            return {
                "category": category,
                "confidence": round(min(0.99, 0.75 + (0.05 * len(matches))), 2),
                "reasons": [f"matched {match}" for match in matches[:4]],
                "excluded_category": True,
                "manual_review_required": False,
            }

    category_checks: List[Tuple[str, List[str]]] = [
        ("technical_fabrication", CATEGORY_KEYWORDS[0][1]),
        ("household_products", CATEGORY_KEYWORDS[1][1]),
        ("building_materials", CATEGORY_KEYWORDS[2][1]),
        ("ppe", CATEGORY_KEYWORDS[3][1]),
        ("equipment_supply", CATEGORY_KEYWORDS[4][1]),
        ("consumables", CATEGORY_KEYWORDS[5][1]),
    ]
    for category, keywords in category_checks:
        matches = _match_keywords(text, keywords)
        if matches:
            manual_review_required = category == "technical_fabrication" or "technical validation required" in text
            confidence = round(min(0.99, 0.7 + (0.06 * len(matches))), 2)
            reasons = [f"matched {match}" for match in matches[:4]]
            if manual_review_required:
                reasons.append("technical validation or fabrication complexity detected")
            return {
                "category": category,
                "confidence": confidence,
                "reasons": reasons,
                "excluded_category": False,
                "manual_review_required": manual_review_required,
            }

    if hint:
        reasons.append(f"category hint: {hint}")
    return {
        "category": "unknown",
        "confidence": 0.4 if not hint else 0.55,
        "reasons": reasons or ["no category keyword matched"],
        "excluded_category": False,
        "manual_review_required": True,
    }


def classify_rfq(rfq_record_or_dict: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(rfq_record_or_dict or {})
    text = _collect_text(payload)
    category_hint = str(payload.get("category") or payload.get("title") or "")
    classification = _best_category(text, category_hint)
    manual_review_required = bool(
        classification["manual_review_required"]
        or classification["category"] == "unknown"
        or bool(payload.get("technical_validation_required"))
    )
    if payload.get("technical_validation_required") and "technical validation required" not in classification["reasons"]:
        classification["reasons"].append("technical validation required")
    classification["manual_review_required"] = manual_review_required
    classification["text"] = text
    return classification
