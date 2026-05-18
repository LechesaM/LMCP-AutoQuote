from __future__ import annotations

from typing import Dict, List, Tuple


LMCP_HIGH_PRIORITY_KEYWORDS = [
    "supply",
    "delivery",
    "supply and delivery",
    "procurement of",
    "purchase of",
    "supply, deliver and offload",
    "supply and install",
    "supply, delivery and installation",
    "furniture",
    "office furniture",
    "stationery",
    "consumables",
    "ppe",
    "protective clothing",
    "laptops",
    "computers",
    "printers",
    "toners",
    "water",
    "bottled water",
    "cleaning materials",
    "cleaning products",
    "groceries",
    "catering",
    "electrical materials",
    "plumbing materials",
    "building materials",
    "road signs",
    "traffic signs",
    "solar",
    "inverter",
    "generator",
    "tools",
    "equipment",
    "uniform",
    "sewing",
    "textiles",
]


LMCP_MEDIUM_PRIORITY_KEYWORDS = [
    "installation",
    "maintenance support",
    "framework agreement",
    "panel of service providers",
    "supply and maintenance",
    "it equipment",
    "hardware",
    "school furniture",
    "medical supplies",
    "office equipment",
    "general supplies",
    "municipal stores",
    "warehouse stock",
]


LMCP_LOW_FIT_OR_EXCLUSION_KEYWORDS = [
    "civil works",
    "construction",
    "building works",
    "professional services",
    "consulting",
    "consultancy",
    "audit services",
    "legal services",
    "architectural services",
    "engineering services",
    "repairs",
    "refurbishment",
    "renovation",
    "lease",
    "rental",
    "hiring",
    "security services",
    "cleaning services",
    "insurance",
    "training services",
]


PREFERRED_BUYERS = [
    "department",
    "municipality",
    "local municipality",
    "district municipality",
    "provincial government",
    "state owned",
    "university",
    "hospital",
    "school",
    "sanral",
    "eskom",
    "transnet",
    "sassa",
    "department of health",
    "department of education",
    "department of public works",
]


def normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def keyword_hits(text: str, keywords: List[str]) -> List[str]:
    hits: List[str] = []
    for keyword in keywords:
        if keyword in text:
            hits.append(keyword)
    return hits


def classify_score(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def score_opportunity(
    title: str | None,
    description: str | None,
    buyer: str | None,
    category: str | None = None,
) -> Dict[str, object]:
    text = " ".join(
        [
            normalize(title),
            normalize(description),
            normalize(category),
        ]
    ).strip()

    buyer_text = normalize(buyer)

    score = 0.0
    reasons: List[str] = []

    high_hits = keyword_hits(text, LMCP_HIGH_PRIORITY_KEYWORDS)
    medium_hits = keyword_hits(text, LMCP_MEDIUM_PRIORITY_KEYWORDS)
    low_fit_hits = keyword_hits(text, LMCP_LOW_FIT_OR_EXCLUSION_KEYWORDS)
    buyer_hits = keyword_hits(buyer_text, PREFERRED_BUYERS)

    if high_hits:
        score += min(len(high_hits) * 12, 48)
        reasons.append(f"High-fit keywords matched: {', '.join(high_hits[:6])}")

    if medium_hits:
        score += min(len(medium_hits) * 6, 18)
        reasons.append(f"Medium-fit keywords matched: {', '.join(medium_hits[:6])}")

    if buyer_hits:
        score += min(len(buyer_hits) * 5, 15)
        reasons.append(f"Preferred buyer matched: {', '.join(buyer_hits[:4])}")

    if "supply and delivery" in text or "supply & delivery" in text:
        score += 18
        reasons.append("Direct supply-and-delivery match")

    if "request for quotation" in text or "rfq" in text:
        score += 8
        reasons.append("RFQ pattern detected")

    if low_fit_hits:
        score -= min(len(low_fit_hits) * 15, 60)
        reasons.append(f"Low-fit keywords matched: {', '.join(low_fit_hits[:6])}")

    if score < 0:
        score = 0.0
    if score > 100:
        score = 100.0

    relevance_level = classify_score(score)
    auto_bid_recommended = score >= 70

    if not reasons:
        reasons.append("No strong LMCP keyword match found")

    return {
        "relevance_score": round(score, 2),
        "relevance_level": relevance_level,
        "score_reason": " | ".join(reasons),
        "auto_bid_recommended": auto_bid_recommended,
    }
