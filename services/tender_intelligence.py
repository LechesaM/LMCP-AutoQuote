from datetime import datetime

SUPPLY_KEYWORDS = [
    "supply",
    "delivery",
    "supply and delivery",
    "procurement",
    "supply of",
    "supply & delivery"
]

CONSTRUCTION_KEYWORDS = [
    "construction",
    "building",
    "civil works",
    "roadworks",
    "infrastructure",
    "upgrade",
    "refurbishment",
]

HIGH_VALUE_BUYERS = [
    "eskom",
    "transnet",
    "sanral",
    "department",
    "municipality",
    "treasury",
    "public works",
]

PRIORITY_SECTORS = [
    "water",
    "energy",
    "electrical",
    "materials",
    "equipment",
    "maintenance",
]


def classify_sector(title: str, description: str):
    text = f"{title} {description}".lower()

    for sector in PRIORITY_SECTORS:
        if sector in text:
            return sector

    return "general"


def detect_supply_tender(title: str, description: str):
    text = f"{title} {description}".lower()

    for word in SUPPLY_KEYWORDS:
        if word in text:
            return True

    for word in CONSTRUCTION_KEYWORDS:
        if word in text:
            return False

    return False


def buyer_score(buyer: str):

    if not buyer:
        return 0

    buyer = buyer.lower()

    for entity in HIGH_VALUE_BUYERS:
        if entity in buyer:
            return 25

    return 10


def keyword_relevance_score(title: str, description: str):

    text = f"{title} {description}".lower()

    score = 0

    for sector in PRIORITY_SECTORS:
        if sector in text:
            score += 10

    if "framework agreement" in text:
        score += 15

    if "panel" in text:
        score += 15

    if "three year" in text or "3 year" in text:
        score += 10

    return score


def deadline_score(deadline):

    if not deadline:
        return 0

    try:
        days_left = (deadline - datetime.utcnow()).days

        if days_left > 30:
            return 15

        if days_left > 14:
            return 10

        if days_left > 7:
            return 5

        return -10

    except:
        return 0


def calculate_intelligence_score(opportunity):

    title = opportunity.title or ""
    description = opportunity.description or ""
    buyer = opportunity.buyer or ""
    deadline = opportunity.deadline

    score = 0

    score += buyer_score(buyer)
    score += keyword_relevance_score(title, description)
    score += deadline_score(deadline)

    return score


def analyze_opportunity(opportunity):

    title = opportunity.title or ""
    description = opportunity.description or ""

    sector = classify_sector(title, description)

    supply = detect_supply_tender(title, description)

    score = calculate_intelligence_score(opportunity)

    return {
        "sector": sector,
        "is_supply": supply,
        "intelligence_score": score,
        "quote_ready": score >= 40 and supply,
    }
