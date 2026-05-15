from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.direct_portal_harvesters import (
    harvest_etenders_web,
    harvest_generic_portal,
)

logger = logging.getLogger(__name__)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _normalize_row(row: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(row or {})

    source_name = _clean(source.get("source_name") or source.get("name") or "Unknown Source")
    source_group = _clean(source.get("source_group") or source.get("type") or "external_portal")
    submission_method = _clean(source.get("submission_method") or "portal")
    intelligence_score = int(source.get("intelligence_score") or 70)

    if not item.get("source_name"):
        item["source_name"] = source_name

    if not item.get("source_group"):
        item["source_group"] = source_group

    if not item.get("submission_method"):
        item["submission_method"] = submission_method

    if not item.get("intelligence_score"):
        item["intelligence_score"] = intelligence_score

    if not item.get("source_url"):
        item["source_url"] = _clean(source.get("url") or source.get("list_url"))

    if not item.get("external_url"):
        item["external_url"] = _clean(
            item.get("url")
            or item.get("portal_url")
            or source.get("url")
            or source.get("list_url")
        )

    if not item.get("portal_url"):
        item["portal_url"] = item.get("external_url")

    return item


def _normalize_rows(rows: List[Dict[str, Any]], source: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(_normalize_row(row, source))
    return normalized


# ================================
# HARVESTERS
# ================================

def _harvest_etenders_web_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = harvest_etenders_web()
    return _normalize_rows(rows, source)


def _harvest_generic_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = harvest_generic_portal(source)
    return _normalize_rows(rows, source)


def _harvest_tenderbulletins_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = harvest_generic_portal(source)

    enriched: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        item = _normalize_row(row, source)

        combined = f"{item.get('title','')} {item.get('description','')} {item.get('external_url','')}".lower()

        if "tenderbulletins" in combined and not item.get("source_group"):
            item["source_group"] = "rfq_portals"

        enriched.append(item)

    return enriched


# ================================
# MAIN ROUTER (FIXED)
# ================================

def harvest_from_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    source_type = _safe_lower(source.get("type"))
    source_name = _clean(source.get("name") or "Unknown Source")
    source_url = _clean(source.get("url") or source.get("list_url"))

    logger.info("Routing harvest for source=%s type=%s", source_name, source_type)

    try:
        # =====================================
        # SPECIAL CASES
        # =====================================

        # eTenders (HTML)
        if source_type == "web":
            return _harvest_etenders_web_source(source)

        # TenderBulletins
        if "tenderbulletins" in source_name.lower() or "tenderbulletins" in source_url.lower():
            return _harvest_tenderbulletins_source(source)

        # =====================================
        # PRIMARY ROUTES
        # =====================================

        if source_type == "generic_portal":
            return _harvest_generic_source(source)

        # =====================================
        # 🔥 CRITICAL FIX — FALLBACK FOR ALL UNKNOWN TYPES
        # =====================================

        logger.info("FALLBACK → generic harvester for source=%s type=%s", source_name, source_type)

        rows = harvest_generic_portal(source)

        if rows:
            return _normalize_rows(rows, source)

        # If generic fails → log and return empty
        logger.info("Generic fallback returned no data for source=%s", source_name)
        return []

    except Exception as exc:
        logger.warning("Harvest route failed for source=%s: %s", source_name, exc)
        return []


def is_real_rfq(rfq: dict) -> bool:
    text = f"{rfq.get('title','')} {rfq.get('description','')}".lower()

    # HARD REQUIREMENTS
    if not rfq.get("closing_date"):
        return False

    if not any(k in text for k in ["supply", "delivery", "procurement", "purchase"]):
        return False

    # EXCLUSIONS
    exclusions = [
        "briefing", "site inspection", "compulsory briefing",
        "service provider", "framework", "panel",
        "consulting", "maintenance", "construction",
        "catering", "security", "cleaning"
    ]

    if any(x in text for x in exclusions):
        return False

    return True


def score_rfq(rfq: dict) -> float:
    score = 0

    text = f"{rfq.get('title','')} {rfq.get('description','')}".lower()

    if "supply" in text: score += 2
    if "delivery" in text: score += 2
    if rfq.get("submission_email"): score += 3
    if rfq.get("buyer"): score += 1
    if rfq.get("closing_date"): score += 2

    return score


def should_accept_rfq(rfq: dict) -> bool:
    return score_rfq(rfq) >= 6 and is_real_rfq(rfq)
