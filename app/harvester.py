from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.parser_router import route_and_parse_sources

# Optional existing modules from your system.
# These imports are intentionally defensive so we do not break the system
# if one helper function has a different name in your project.
try:
    from app.department_scraper import scrape_department_sites
except Exception:
    scrape_department_sites = None

try:
    from app.filtering import filter_opportunities
except Exception:
    filter_opportunities = None

try:
    import app.classify as classify_module
except Exception:
    classify_module = None

try:
    import app.scoring as scoring_module
except Exception:
    scoring_module = None


logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def normalize_url(url: str) -> str:
    return safe_text(url).rstrip("/")


def dedupe_opportunities(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result: List[Dict[str, Any]] = []

    for item in items:
        title = safe_text(item.get("title", "")).lower()
        source_url = normalize_url(item.get("source_url", "")).lower()
        external_id = safe_text(item.get("external_id", "")).lower()

        key = (external_id or "", title, source_url)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


def local_supply_score(text: str) -> int:
    lowered = text.lower()

    positive_keywords = {
        "supply": 18,
        "delivery": 18,
        "supply and delivery": 28,
        "supply, delivery and offloading": 30,
        "procurement of goods": 24,
        "materials": 14,
        "equipment": 14,
        "consumables": 14,
        "furniture": 12,
        "stationery": 12,
        "ppe": 12,
        "ict equipment": 14,
        "laptops": 12,
        "printers": 12,
        "toners": 10,
        "electrical materials": 12,
        "plumbing materials": 12,
        "pipes": 10,
        "valves": 10,
        "tools": 10,
        "hardware": 10,
        "panel of suppliers": 18,
        "framework agreement": 18,
        "framework contract": 18,
        "supplier": 10,
    }

    negative_keywords = {
        "construction": -28,
        "civil works": -28,
        "building works": -25,
        "road works": -25,
        "roadworks": -25,
        "rehabilitation": -20,
        "refurbishment": -18,
        "consulting services": -22,
        "professional services": -22,
        "appointment of contractor": -24,
        "repair works": -16,
        "maintenance of": -14,
        "infrastructure works": -20,
        "training services": -20,
        "security services": -18,
        "cleaning services": -18,
    }

    score = 0

    for keyword, value in positive_keywords.items():
        if keyword in lowered:
            score += value

    for keyword, value in negative_keywords.items():
        if keyword in lowered:
            score += value

    return max(0, min(score, 100))


def is_supply_opportunity(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()

    must_have_any = [
        "supply",
        "delivery",
        "procurement",
        "goods",
        "materials",
        "equipment",
        "consumables",
        "supplier",
        "panel of suppliers",
        "framework agreement",
        "framework contract",
    ]

    exclude_if_any = [
        "construction",
        "civil works",
        "building works",
        "road works",
        "roadworks",
        "rehabilitation",
        "refurbishment",
        "consulting services",
        "professional services",
        "appointment of contractor",
        "repair works",
        "infrastructure works",
    ]

    has_positive = any(term in text for term in must_have_any)
    has_excluded = any(term in text for term in exclude_if_any)

    return has_positive and not has_excluded


def classify_fallback(item: Dict[str, Any]) -> Dict[str, Any]:
    title = safe_text(item.get("title", ""))
    description = safe_text(item.get("description", ""))
    text = f"{title} {description}".lower()

    category = "supply_delivery" if is_supply_opportunity(title, description) else "non_supply"
    preferred_sector = "goods_procurement"

    sector_map = {
        "ict equipment": "ict",
        "laptops": "ict",
        "printers": "ict",
        "toners": "ict",
        "stationery": "office_supplies",
        "furniture": "office_furniture",
        "plumbing materials": "plumbing",
        "pipes": "plumbing",
        "valves": "plumbing",
        "electrical materials": "electrical",
        "ppe": "ppe",
        "consumables": "consumables",
        "tools": "hardware_tools",
        "hardware": "hardware_tools",
        "medical": "medical",
        "pharmaceutical": "medical",
    }

    for keyword, sector in sector_map.items():
        if keyword in text:
            preferred_sector = sector
            break

    supply_score = local_supply_score(text)

    if category != "supply_delivery":
        review_status = "rejected"
        decision_reason = "skipped_not_supply"
    elif supply_score >= 60:
        review_status = "strong_candidate"
        decision_reason = "high_supply_relevance"
    elif supply_score >= 35:
        review_status = "review"
        decision_reason = "medium_supply_relevance"
    else:
        review_status = "review"
        decision_reason = "low_confidence_supply_match"

    return {
        "category": category,
        "preferred_sector": preferred_sector,
        "review_status": review_status,
        "decision_reason": decision_reason,
        "score": supply_score,
    }


def score_via_existing_module(item: Dict[str, Any]) -> Optional[int]:
    if scoring_module is None:
        return None

    candidates = [
        "score_opportunity",
        "score_tender",
        "score_item",
        "compute_score",
    ]

    for fn_name in candidates:
        fn = getattr(scoring_module, fn_name, None)
        if callable(fn):
            try:
                value = fn(item)
                if isinstance(value, dict):
                    for key in ("score", "total_score", "relevance_score"):
                        if key in value:
                            return int(value[key] or 0)
                return int(value or 0)
            except Exception as exc:
                logger.warning("Existing scoring function %s failed: %s", fn_name, exc)

    return None


def classify_via_existing_module(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if classify_module is None:
        return None

    candidates = [
        "classify_opportunity",
        "classify_tender",
        "classify_item",
        "analyze_opportunity",
        "analyze_tender",
    ]

    for fn_name in candidates:
        fn = getattr(classify_module, fn_name, None)
        if callable(fn):
            try:
                value = fn(item)
                if isinstance(value, dict):
                    return value
            except Exception as exc:
                logger.warning("Existing classify function %s failed: %s", fn_name, exc)

    return None


def enrich_opportunity(item: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(item)

    title = safe_text(enriched.get("title", ""))
    description = safe_text(enriched.get("description", ""))

    # Try existing classify module first
    existing_analysis = classify_via_existing_module(enriched)
    fallback_analysis = classify_fallback(enriched)

    if existing_analysis:
        enriched["category"] = safe_text(existing_analysis.get("category")) or fallback_analysis["category"]
        enriched["preferred_sector"] = safe_text(existing_analysis.get("preferred_sector")) or fallback_analysis["preferred_sector"]
        enriched["review_status"] = safe_text(existing_analysis.get("review_status")) or fallback_analysis["review_status"]
        enriched["decision_reason"] = safe_text(existing_analysis.get("decision_reason")) or fallback_analysis["decision_reason"]
    else:
        enriched.update(fallback_analysis)

    # Try existing scoring module first
    existing_score = score_via_existing_module(enriched)
    if existing_score is not None:
        enriched["score"] = max(int(existing_score), int(fallback_analysis["score"]))
    else:
        enriched["score"] = int(fallback_analysis["score"])

    # Normalize core fields
    enriched["title"] = title[:500]
    enriched["description"] = description[:3000]
    enriched["buyer"] = safe_text(enriched.get("buyer", ""))[:255]
    enriched["source"] = safe_text(enriched.get("source", "unknown"))[:100]
    enriched["source_url"] = safe_text(enriched.get("source_url", ""))[:1000]
    enriched["entity_type"] = safe_text(enriched.get("entity_type", ""))[:100]
    enriched["external_id"] = safe_text(enriched.get("external_id", ""))[:1000]
    enriched["published_at"] = enriched.get("published_at")
    enriched["closing_date"] = enriched.get("closing_date")
    enriched["harvested_at"] = utc_now().isoformat()

    return enriched


# -------------------------------------------------------------------
# Harvest layers
# -------------------------------------------------------------------

def harvest_from_existing_department_scraper() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if scrape_department_sites is None:
        return [], {"layer": "department_scraper", "status": "skipped", "reason": "not_available"}

    try:
        items = scrape_department_sites() or []
        normalized = []
        for item in items:
            normalized.append(
                {
                    "external_id": safe_text(item.get("external_id")),
                    "title": safe_text(item.get("title")),
                    "description": safe_text(item.get("description")),
                    "buyer": safe_text(item.get("buyer")),
                    "source": safe_text(item.get("source") or "department_scraper"),
                    "source_url": safe_text(item.get("source_url")),
                    "published_at": item.get("published_at"),
                    "closing_date": item.get("closing_date"),
                    "entity_type": safe_text(item.get("entity_type") or "department"),
                    "procurement_confidence": int(item.get("procurement_confidence") or 0),
                    "parser_used": safe_text(item.get("parser_used") or "department_scraper"),
                    "keywords": item.get("keywords") or [],
                }
            )

        return normalized, {
            "layer": "department_scraper",
            "status": "success",
            "found": len(normalized),
        }
    except Exception as exc:
        logger.exception("department_scraper harvest failed")
        return [], {
            "layer": "department_scraper",
            "status": "error",
            "found": 0,
            "error": str(exc),
        }


def harvest_from_parser_router(
    include_homepage_only: bool = True,
    include_needs_custom_parser: bool = False,
    min_confidence: int = 12,
    entity_type_filter: Optional[List[str]] = None,
    limit_sources: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        result = route_and_parse_sources(
            include_homepage_only=include_homepage_only,
            include_needs_custom_parser=include_needs_custom_parser,
            min_confidence=min_confidence,
            entity_type_filter=entity_type_filter,
            limit_sources=limit_sources,
        )

        items = result.get("items", []) or []
        summary = result.get("summary", {}) or {}

        return items, {
            "layer": "parser_router",
            "status": "success",
            "found": len(items),
            "summary": summary,
        }
    except Exception as exc:
        logger.exception("parser_router harvest failed")
        return [], {
            "layer": "parser_router",
            "status": "error",
            "found": 0,
            "error": str(exc),
        }


# -------------------------------------------------------------------
# Public entry point
# -------------------------------------------------------------------

def harvest_opportunities(
    include_parser_router: bool = True,
    include_department_scraper: bool = True,
    include_homepage_only: bool = True,
    include_needs_custom_parser: bool = False,
    min_confidence: int = 12,
    entity_type_filter: Optional[List[str]] = None,
    limit_sources: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Main harvest entry point.

    This now integrates parser_router into the harvest pipeline so the system can
    scan validated national department / SOE / municipality / public entity sources.
    """
    all_raw: List[Dict[str, Any]] = []
    layers: List[Dict[str, Any]] = []

    if include_department_scraper:
        items, info = harvest_from_existing_department_scraper()
        all_raw.extend(items)
        layers.append(info)

    if include_parser_router:
        items, info = harvest_from_parser_router(
            include_homepage_only=include_homepage_only,
            include_needs_custom_parser=include_needs_custom_parser,
            min_confidence=min_confidence,
            entity_type_filter=entity_type_filter,
            limit_sources=limit_sources,
        )
        all_raw.extend(items)
        layers.append(info)

    total_raw = len(all_raw)
    deduped = dedupe_opportunities(all_raw)

    # Run existing keyword filter if available, otherwise use local supply-only gate.
    if callable(filter_opportunities):
        try:
            filtered = filter_opportunities(deduped)
        except Exception as exc:
            logger.warning("filter_opportunities failed, using local fallback: %s", exc)
            filtered = [
                item for item in deduped
                if is_supply_opportunity(item.get("title", ""), item.get("description", ""))
            ]
    else:
        filtered = [
            item for item in deduped
            if is_supply_opportunity(item.get("title", ""), item.get("description", ""))
        ]

    skipped_not_supply = max(0, len(deduped) - len(filtered))

    enriched = [enrich_opportunity(item) for item in filtered]

    # Sort strongest first
    enriched.sort(
        key=lambda x: (
            -int(x.get("score") or 0),
            -int(x.get("procurement_confidence") or 0),
            safe_text(x.get("buyer", "")),
        )
    )

    summary = {
        "status": "success",
        "focus": "supply_and_delivery_only",
        "layers": layers,
        "raw_found": total_raw,
        "deduped_found": len(deduped),
        "filtered_supply_found": len(filtered),
        "stored_candidates": len(enriched),
        "skipped_not_supply": skipped_not_supply,
        "timestamp": utc_now().isoformat(),
        "by_entity_type": {},
        "top_score": enriched[0]["score"] if enriched else 0,
    }

    for item in enriched:
        entity_type = safe_text(item.get("entity_type") or "unknown")
        summary["by_entity_type"][entity_type] = summary["by_entity_type"].get(entity_type, 0) + 1

    return {
        "summary": summary,
        "items": enriched,
    }


def harvest_opportunities_quick() -> List[Dict[str, Any]]:
    """
    Convenience wrapper for existing code paths that expect only the items list.
    """
    result = harvest_opportunities(
        include_parser_router=True,
        include_department_scraper=True,
        include_homepage_only=True,
        include_needs_custom_parser=False,
        min_confidence=12,
    )
    return result["items"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = harvest_opportunities(
        include_parser_router=True,
        include_department_scraper=True,
        include_homepage_only=True,
        include_needs_custom_parser=False,
        min_confidence=12,
        entity_type_filter=None,
        limit_sources=50,
    )
    print(result["summary"])
