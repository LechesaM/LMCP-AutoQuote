from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_lower(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _contains_any(text: str, keywords: List[str]) -> bool:
    text = _safe_lower(text)
    return any(keyword in text for keyword in keywords)


def _normalize_opportunity(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    title = opportunity.get("title") or opportunity.get("name") or "Untitled Opportunity"
    description = opportunity.get("description") or opportunity.get("scope") or ""
    buyer = opportunity.get("buyer") or opportunity.get("department") or opportunity.get("entity") or "Unknown Buyer"
    category = opportunity.get("category") or opportunity.get("sector") or ""
    province = opportunity.get("province") or opportunity.get("region") or ""
    compulsory_briefing = bool(
        opportunity.get("compulsory_briefing", False)
        or opportunity.get("requires_briefing", False)
    )
    submission_channel = (
        opportunity.get("submission_channel")
        or opportunity.get("channel")
        or (
            "email"
            if opportunity.get("email_submission")
            else "portal" if opportunity.get("portal_submission") else "unknown"
        )
    )

    return {
        "id": opportunity.get("id"),
        "title": title,
        "description": description,
        "buyer": buyer,
        "category": category,
        "province": province,
        "compulsory_briefing": compulsory_briefing,
        "submission_channel": submission_channel,
        "estimated_value": opportunity.get("estimated_value"),
        "closing_date": opportunity.get("closing_date"),
        "source_url": opportunity.get("source_url") or opportunity.get("url"),
        "raw": opportunity,
    }


def _lmcp_fit_score(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristic fit scoring for LMCP.
    Focuses on:
    - civil works
    - building works
    - water / sanitation
    - plumbing
    - roads
    - maintenance
    - infrastructure
    - general construction supply/delivery fit
    """

    title = _safe_lower(opportunity["title"])
    description = _safe_lower(opportunity["description"])
    category = _safe_lower(opportunity["category"])
    combined = " ".join([title, description, category])

    strong_fit_keywords = [
        "civil",
        "construction",
        "building",
        "road",
        "roads",
        "stormwater",
        "water",
        "wastewater",
        "sanitation",
        "sewer",
        "plumbing",
        "reticulation",
        "maintenance",
        "refurbishment",
        "infrastructure",
        "paving",
        "earthworks",
        "concrete",
        "pipe",
        "drainage",
        "fencing",
        "housing",
        "electrical maintenance",
    ]

    medium_fit_keywords = [
        "supply",
        "delivery",
        "materials",
        "hardware",
        "facility",
        "repair",
        "upgrade",
        "rehabilitation",
        "municipal",
        "public works",
        "human settlements",
    ]

    low_fit_keywords = [
        "ict",
        "software",
        "laptop",
        "desktop",
        "stationery",
        "travel",
        "catering",
        "security guarding",
        "cleaning only",
        "medical consumables",
        "pharmaceutical",
    ]

    score = 0
    reasons: List[str] = []

    strong_hits = [k for k in strong_fit_keywords if k in combined]
    medium_hits = [k for k in medium_fit_keywords if k in combined]
    low_hits = [k for k in low_fit_keywords if k in combined]

    if strong_hits:
        score += min(len(strong_hits) * 12, 48)
        reasons.append(f"Strong sector fit: {', '.join(strong_hits[:5])}")

    if medium_hits:
        score += min(len(medium_hits) * 6, 18)
        reasons.append(f"Commercial fit signals: {', '.join(medium_hits[:5])}")

    if low_hits:
        score -= min(len(low_hits) * 15, 45)
        reasons.append(f"Low-fit indicators: {', '.join(low_hits[:5])}")

    if opportunity["submission_channel"] in ("email", "portal"):
        score += 10
        reasons.append(f"Accepted submission channel: {opportunity['submission_channel']}")

    if opportunity["compulsory_briefing"]:
        score -= 35
        reasons.append("Compulsory briefing reduces suitability")

    buyer_text = _safe_lower(opportunity["buyer"])
    if _contains_any(
        buyer_text,
        [
            "municipality",
            "public works",
            "human settlements",
            "water",
            "sanral",
            "roads",
            "infrastructure",
            "department",
        ],
    ):
        score += 12
        reasons.append("Buyer profile aligns with public infrastructure work")

    estimated_value = opportunity.get("estimated_value")
    if estimated_value is not None:
        try:
            value = float(estimated_value)
            if 100000 <= value <= 50000000:
                score += 10
                reasons.append("Value range appears commercially relevant")
        except Exception:
            pass

    score = max(0, min(score, 100))

    if score >= 75:
        hunter_band = "high-priority"
    elif score >= 50:
        hunter_band = "good-fit"
    elif score >= 30:
        hunter_band = "watchlist"
    else:
        hunter_band = "low-fit"

    return {
        "hunter_score": score,
        "hunter_band": hunter_band,
        "hunter_reasons": reasons,
    }


def rank_opportunities_for_lmcp(opportunities: List[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = [_normalize_opportunity(item) for item in opportunities if isinstance(item, dict)]
    ranked: List[Dict[str, Any]] = []

    for item in normalized:
        score_payload = _lmcp_fit_score(item)
        ranked.append(
            {
                "id": item["id"],
                "title": item["title"],
                "buyer": item["buyer"],
                "category": item["category"],
                "province": item["province"],
                "submission_channel": item["submission_channel"],
                "compulsory_briefing": item["compulsory_briefing"],
                "estimated_value": item["estimated_value"],
                "closing_date": item["closing_date"],
                "source_url": item["source_url"],
                "hunter_score": score_payload["hunter_score"],
                "hunter_band": score_payload["hunter_band"],
                "hunter_reasons": score_payload["hunter_reasons"],
                "raw": item["raw"],
            }
        )

    ranked.sort(
        key=lambda x: (
            x["hunter_score"],
            0 if x["hunter_band"] == "high-priority" else
            1 if x["hunter_band"] == "good-fit" else
            2 if x["hunter_band"] == "watchlist" else 3
        ),
        reverse=True,
    )

    return {
        "status": "ok",
        "service": "autonomous_tender_hunter",
        "timestamp": _utc_now_iso(),
        "total_ranked": len(ranked),
        "high_priority": len([x for x in ranked if x["hunter_band"] == "high-priority"]),
        "good_fit": len([x for x in ranked if x["hunter_band"] == "good-fit"]),
        "watchlist": len([x for x in ranked if x["hunter_band"] == "watchlist"]),
        "low_fit": len([x for x in ranked if x["hunter_band"] == "low-fit"]),
        "results": ranked,
    }


def rank_demo_opportunities() -> Dict[str, Any]:
    """
    Safe demo endpoint so the feature works immediately,
    even before wiring it into your DB harvest pipeline.
    """
    demo = [
        {
            "id": 1,
            "title": "Construction of stormwater drainage and road rehabilitation",
            "description": "Civil engineering works including drainage, concrete, and road layerworks.",
            "buyer": "Mangaung Metropolitan Municipality",
            "category": "Civil Works",
            "province": "Free State",
            "submission_channel": "portal",
            "compulsory_briefing": False,
            "estimated_value": 12500000,
        },
        {
            "id": 2,
            "title": "Supply and delivery of laptops and printers",
            "description": "ICT equipment for district offices.",
            "buyer": "Provincial Treasury",
            "category": "ICT",
            "province": "Gauteng",
            "submission_channel": "email",
            "compulsory_briefing": False,
            "estimated_value": 850000,
        },
        {
            "id": 3,
            "title": "Plumbing maintenance and refurbishment of government buildings",
            "description": "Routine and emergency plumbing maintenance including pipe replacement.",
            "buyer": "Department of Public Works",
            "category": "Building Maintenance",
            "province": "Free State",
            "submission_channel": "email",
            "compulsory_briefing": False,
            "estimated_value": 3200000,
        },
    ]
    return rank_opportunities_for_lmcp(demo)
