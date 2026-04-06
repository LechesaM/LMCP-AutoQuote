from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ETENDERS_WEB_URL = "https://www.etenders.gov.za/Home/opportunities"


BLOCKED_KEYWORDS = [
    "medical",
    "pharmaceutical",
    "clinic",
    "hospital",
    "laptop",
    "computer",
    "printer",
    "software",
    "server",
    "router",
    "monitor",
    "tablet",
    "diesel",
    "petrol",
    "fuel",
    "construction",
    "civil",
    "building",
    "consulting",
    "services",
    "maintenance",
    "refurbishment",
    "repair",
    "installation",
]

SUPPLY_MARKERS = [
    "supply",
    "delivery",
    "goods",
    "procurement",
    "purchase",
    "supply and delivery",
    "supply of",
    "delivery of",
]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _contains_blocked(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in BLOCKED_KEYWORDS)


def _is_supply(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in SUPPLY_MARKERS)


def _looks_compulsory(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "compulsory briefing",
        "mandatory briefing",
        "compulsory site inspection",
        "mandatory site inspection",
        "compulsory clarification meeting",
        "mandatory clarification meeting",
    ]
    return any(marker in lowered for marker in markers)


def _extract_reference(text: str) -> str:
    patterns = [
        r"\bRFQ[:\s-]*([A-Z0-9/\-.]+)\b",
        r"\bRFP[:\s-]*([A-Z0-9/\-.]+)\b",
        r"\bBID[:\s-]*([A-Z0-9/\-.]+)\b",
        r"\bQUO(?:TE)?[:\s-]*([A-Z0-9/\-.]+)\b",
        r"\bSCM[:\s-]*([A-Z0-9/\-.]+)\b",
        r"\b[A-Z]{2,10}[-/][A-Z0-9/-]{2,30}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            if match.groups():
                return _clean(match.group(1)).upper()
            return _clean(match.group(0)).upper()
    return ""


def _parse_etenders_cards(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[Dict[str, Any]] = []

    anchors = soup.find_all("a", href=True)
    seen_urls = set()

    for anchor in anchors:
        href = _clean(anchor.get("href"))
        text = " ".join(anchor.stripped_strings).strip()

        if not href:
            continue

        full_url = href
        if href.startswith("/"):
            full_url = f"https://www.etenders.gov.za{href}"

        combined_text = f"{text} {full_url}".strip()
        lowered = combined_text.lower()

        if "opportunit" not in lowered and "tender" not in lowered and "bid" not in lowered and "rfq" not in lowered:
            continue

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        context_parts: List[str] = [text]

        parent = anchor.parent
        hops = 0
        while parent is not None and hops < 3:
            parent_text = " ".join(parent.stripped_strings).strip()
            if parent_text:
                context_parts.append(parent_text)
            parent = parent.parent
            hops += 1

        context = " | ".join(dict.fromkeys([p for p in context_parts if p]))
        if not context:
            continue

        if _contains_blocked(context):
            continue

        if not _is_supply(context):
            continue

        if _looks_compulsory(context):
            continue

        title = text or context[:180]
        reference = _extract_reference(context) or _extract_reference(full_url)
        if not reference:
            reference = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").upper()[:60]

        rows.append(
            {
                "title": title[:250],
                "description": context[:2000],
                "external_url": full_url,
                "published_date": None,
                "closing_date": None,
                "buyer_name": "eTenders South Africa",
                "reference_number": reference,
                "buyer_rfq_number": reference,
                "rfq_number": reference,
                "category": "Supply / Delivery",
                "source_name": "eTenders Web",
                "source_url": ETENDERS_WEB_URL,
                "is_supply": True,
                "intelligence_score": 72,
                "quote_ready": True,
                "submission_method": "portal",
                "submission_email": None,
                "portal_url": full_url,
                "compulsory_briefing": False,
                "briefing_text": "",
                "eligible_for_autonomous": True,
                "harvested_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return rows


def harvest_etenders_web(timeout: int = 30) -> List[Dict[str, Any]]:
    logger.info("Harvesting eTenders web opportunities from %s", ETENDERS_WEB_URL)
    try:
        response = requests.get(
            ETENDERS_WEB_URL,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        rows = _parse_etenders_cards(response.text)
        logger.info("eTenders web harvest found %s candidate opportunities", len(rows))
        return rows
    except Exception as exc:
        logger.warning("eTenders web harvest failed: %s", exc)
        return []


def harvest_generic_portal(source: Dict[str, Any], timeout: int = 20) -> List[Dict[str, Any]]:
    """
    Generic portal harvester placeholder.
    Safe fallback for sources that only expose list pages.
    """
    name = _clean(source.get("name")) or "Unknown Portal"
    url = _clean(source.get("url"))
    if not url:
        return []

    logger.info("Harvesting generic portal: %s (%s)", name, url)

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        logger.warning("Generic portal harvest failed for %s: %s", name, exc)
        return []

    soup = BeautifulSoup(html, "html.parser")
    rows: List[Dict[str, Any]] = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        text = " ".join(anchor.stripped_strings).strip()
        href = _clean(anchor.get("href"))
        if not text or not href:
            continue

        full_url = href
        if href.startswith("/"):
            base = re.match(r"^(https?://[^/]+)", url)
            if base:
                full_url = f"{base.group(1)}{href}"

        combined = f"{text} {full_url}".strip()
        lowered = combined.lower()

        if not any(token in lowered for token in ["tender", "bid", "rfq", "quotation", "quote", "supply", "delivery"]):
            continue
        if _contains_blocked(combined):
            continue
        if not _is_supply(combined):
            continue
        if _looks_compulsory(combined):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)

        reference = _extract_reference(combined)
        if not reference:
            reference = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").upper()[:60]

        rows.append(
            {
                "title": text[:250],
                "description": combined[:1500],
                "external_url": full_url,
                "published_date": None,
                "closing_date": None,
                "buyer_name": name,
                "reference_number": reference,
                "buyer_rfq_number": reference,
                "rfq_number": reference,
                "category": "Supply / Delivery",
                "source_name": name,
                "source_url": url,
                "is_supply": True,
                "intelligence_score": 65,
                "quote_ready": True,
                "submission_method": "portal",
                "submission_email": None,
                "portal_url": full_url,
                "compulsory_briefing": False,
                "briefing_text": "",
                "eligible_for_autonomous": True,
                "harvested_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    logger.info("Generic portal %s yielded %s opportunities", name, len(rows))
    return rows
