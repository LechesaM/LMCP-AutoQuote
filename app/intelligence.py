from typing import Dict, List, Optional


PREFERRED_CATEGORIES = {
    "electrical",
    "solar",
    "water",
    "plumbing",
    "hardware",
    "road_signs",
    "ppe",
    "furniture",
    "ict",
    "office_supplies",
    "medical_supplies",
}


CATEGORY_KEYWORDS = {
    "electrical": [
        "electrical",
        "cable",
        "transformer",
        "switchgear",
        "distribution board",
        "lighting",
        "meter",
    ],
    "solar": [
        "solar",
        "inverter",
        "battery",
        "pv",
        "panel",
        "charge controller",
    ],
    "water": [
        "water",
        "pump",
        "tank",
        "valve",
        "chlorine",
        "chemical",
        "treatment",
    ],
    "plumbing": [
        "plumbing",
        "pipes",
        "pipe",
        "fittings",
        "geyser",
        "tap",
        "sanitary",
    ],
    "hardware": [
        "hardware",
        "tools",
        "bolts",
        "nuts",
        "fasteners",
        "building material",
    ],
    "road_signs": [
        "road signs",
        "signage",
        "traffic signs",
        "reflective signs",
        "permanent road signs",
    ],
    "ppe": [
        "ppe",
        "uniform",
        "protective clothing",
        "boots",
        "gloves",
        "helmet",
    ],
    "furniture": [
        "furniture",
        "desk",
        "chair",
        "cabinet",
        "shelving",
    ],
    "ict": [
        "laptop",
        "computer",
        "printer",
        "toner",
        "server",
        "network",
        "router",
        "ict",
        "it equipment",
    ],
    "office_supplies": [
        "stationery",
        "office supplies",
        "paper",
        "cartridge",
        "consumables",
    ],
    "medical_supplies": [
        "medical supplies",
        "medical equipment",
        "pharmaceutical",
        "clinic equipment",
        "hospital equipment",
    ],
}


def detect_category(title: str, description: str) -> Optional[str]:
    text = f"{title} {description}".lower()

    best_category = None
    best_hits = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits:
            best_hits = hits
            best_category = category

    return best_category


def is_preferred_sector(category: Optional[str]) -> bool:
    if not category:
        return False
    return category in PREFERRED_CATEGORIES


def build_decision_reason(
    is_supply_delivery: bool,
    category: Optional[str],
    preferred_sector: bool,
    score: int,
) -> str:
    if not is_supply_delivery:
        return "Rejected: not supply and delivery"

    if not category:
        if score >= 50:
            return "Borderline: supply and delivery but category unclear"
        return "Rejected: category unclear and weak match"

    if preferred_sector and score >= 40:
        return f"Accepted: preferred sector {category}"

    if score >= 60:
        return f"Review: non-preferred sector but strong supply match ({category})"

    return f"Review: weak or borderline sector match ({category})"


def decide_review_status(
    is_supply_delivery: bool,
    category: Optional[str],
    preferred_sector: bool,
    score: int,
) -> str:
    if not is_supply_delivery:
        return "rejected"

    if preferred_sector and score >= 40:
        return "approved"

    if score >= 60:
        return "manual_review"

    return "manual_review"


def analyze_opportunity(title: str, description: str, score: int, is_supply_delivery: bool) -> Dict[str, object]:
    category = detect_category(title, description)
    preferred_sector = is_preferred_sector(category)
    review_status = decide_review_status(
        is_supply_delivery=is_supply_delivery,
        category=category,
        preferred_sector=preferred_sector,
        score=score,
    )
    decision_reason = build_decision_reason(
        is_supply_delivery=is_supply_delivery,
        category=category,
        preferred_sector=preferred_sector,
        score=score,
    )

    return {
        "category": category,
        "preferred_sector": preferred_sector,
        "review_status": review_status,
        "decision_reason": decision_reason,
    }
