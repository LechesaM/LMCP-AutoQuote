def is_supply_delivery_opportunity(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()

    strong_positive_keywords = [
        "supply and delivery",
        "supply & delivery",
        "supply, delivery",
        "supply of",
        "delivery of",
        "request for quotation",
        "rfq",
        "quotation",
        "procurement of",
        "purchase of",
    ]

    product_keywords = [
        "equipment",
        "materials",
        "electrical",
        "plumbing",
        "hardware",
        "inverter",
        "solar",
        "battery",
        "generator",
        "transformer",
        "pump",
        "pipes",
        "valves",
        "tanks",
        "road signs",
        "furniture",
        "stationery",
        "laptops",
        "computers",
        "printers",
        "toner",
        "consumables",
        "uniform",
        "ppe",
        "water treatment chemicals",
        "tools",
        "vehicles parts",
        "medical supplies",
        "office equipment",
    ]

    strong_negative_keywords = [
        "construction",
        "civil works",
        "building works",
        "roadworks",
        "repair works",
        "maintenance",
        "consulting",
        "professional services",
        "appointment of a service provider",
        "appointment of a contractor",
        "infrastructure",
        "renovation",
        "refurbishment",
        "cleaning services",
        "security services",
        "training services",
        "auditing services",
        "legal services",
        "project management services",
        "technical advisory",
        "labour broker",
    ]

    install_phrases = [
        "supply, deliver and install",
        "supply and install",
        "supply, installation and commissioning",
    ]

    has_strong_positive = any(k in text for k in strong_positive_keywords)
    has_product_keyword = any(k in text for k in product_keywords)
    has_install_phrase = any(k in text for k in install_phrases)
    has_strong_negative = any(k in text for k in strong_negative_keywords)

    if has_strong_negative and not has_install_phrase:
        return False

    if has_strong_positive and (has_product_keyword or has_install_phrase):
        return True

    if "supply" in text and "delivery" in text and (has_product_keyword or has_install_phrase):
        return True

    return False


def score_opportunity(title: str, description: str) -> int:
    text = f"{title} {description}".lower()

    if not is_supply_delivery_opportunity(title, description):
        return 0

    score = 0

    positive_keywords = {
        "supply and delivery": 30,
        "supply & delivery": 30,
        "supply of": 20,
        "delivery of": 20,
        "procurement of": 15,
        "purchase of": 15,
        "quotation": 10,
        "rfq": 15,
        "equipment": 10,
        "materials": 10,
        "electrical": 10,
        "plumbing": 10,
        "hardware": 10,
        "inverter": 15,
        "solar": 15,
        "battery": 12,
        "pump": 12,
        "pipes": 10,
        "tanks": 10,
        "road signs": 15,
        "ppe": 10,
        "furniture": 10,
        "stationery": 8,
        "computers": 10,
        "printers": 10,
        "office equipment": 10,
        "medical supplies": 12,
        "water": 10,
    }

    negative_keywords = {
        "construction": -100,
        "civil works": -100,
        "building works": -100,
        "roadworks": -100,
        "consulting": -80,
        "professional services": -80,
        "maintenance": -60,
        "repair works": -60,
        "appointment of a contractor": -80,
        "infrastructure": -70,
        "cleaning services": -80,
        "security services": -80,
        "training services": -80,
    }

    for keyword, points in positive_keywords.items():
        if keyword in text:
            score += points

    for keyword, points in negative_keywords.items():
        if keyword in text:
            score += points

    if score < 0:
        score = 0

    if score > 100:
        score = 100

    return score

from typing import Any, Dict, List


def score_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compatibility wrapper for autonomous_engine.py.
    Keeps existing score_opportunity(...) logic unchanged.
    """
    scored: List[Dict[str, Any]] = []

    for opportunity in opportunities or []:
        item = dict(opportunity)

        title = str(item.get("title") or item.get("opportunity_title") or "")
        description = str(item.get("description") or "")

        raw_score = score_opportunity(title, description)

        try:
            normalized_score = round(float(raw_score) / 100.0, 4)
        except Exception:
            normalized_score = 0.0

        item["score"] = normalized_score
        item["raw_score"] = raw_score
        scored.append(item)

    return scored


def score(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return score_opportunities(items)
