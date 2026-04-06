import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from app.services.deduplication import deduplicate_tenders
from app.services.source_scheduler import select_sources_to_crawl

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_URLS = [
    "https://www.etenders.gov.za/Home/opportunities",
]

HARVESTED_TENDERS: List[Dict[str, Any]] = []
LAST_HARVEST_RUN: Optional[str] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_deadline_from_text(text: str) -> Optional[str]:
    if not text:
        return None

    patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{2}/\d{2}/\d{4})",
        r"(\d{2}-\d{2}-\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def keyword_score(title: str, description: str) -> int:
    """
    Score only for supply and delivery opportunities.
    Penalize works/construction tenders heavily.
    """
    text = f"{title} {description}".lower()
    score = 0

    positive_keywords = {
        "supply": 25,
        "delivery": 25,
        "deliver": 20,
        "supply and delivery": 40,
        "supply, delivery and offloading": 45,
        "supply and deliver": 40,
        "procurement": 18,
        "goods": 15,
        "materials": 15,
        "consumables": 15,
        "equipment": 18,
        "items": 10,
        "tools": 12,
        "stationery": 18,
        "furniture": 18,
        "ppe": 18,
        "uniform": 15,
        "cleaning materials": 18,
        "electrical materials": 18,
        "plumbing materials": 18,
        "water meters": 16,
        "pipes": 16,
        "valves": 16,
        "it equipment": 18,
        "ict": 15,
        "laptops": 18,
        "printers": 16,
        "toners": 16,
        "office equipment": 16,
        "hardware": 16,
        "medical supplies": 18,
        "pharmaceutical": 18,
        "fleet tyres": 14,
        "diesel": 14,
        "fuel": 14,
        "appointment of suppliers": 22,
        "panel of suppliers": 22,
        "framework agreement": 20,
        "framework contract": 20,
        "quotations for supply": 25,
        "bid for supply": 22,
        "manufacture, supply and delivery": 35,
    }

    negative_keywords = {
        "construction": -40,
        "civil": -35,
        "building": -35,
        "road works": -40,
        "roads": -30,
        "rehabilitation": -28,
        "refurbishment": -25,
        "maintenance": -20,
        "repair": -18,
        "installation": -18,
        "contractor": -15,
        "professional services": -25,
        "consulting": -20,
        "consultancy": -20,
        "works": -18,
        "asphalt": -20,
        "paving": -20,
        "stormwater": -15,
        "housing": -20,
        "earthworks": -30,
        "brickwork": -25,
        "plastering": -25,
        "painting": -20,
    }

    for word, value in positive_keywords.items():
        if word in text:
            score += value

    for word, value in negative_keywords.items():
        if word in text:
            score += value

    return max(0, min(score, 100))


def is_supply_delivery_tender(title: str, description: str) -> bool:
    """
    True only if the tender looks like supply/delivery/procurement of goods.
    """
    text = f"{title} {description}".lower()

    must_have_any = [
        "supply",
        "delivery",
        "deliver",
        "procurement",
        "goods",
        "materials",
        "equipment",
        "consumables",
        "appointment of suppliers",
        "panel of suppliers",
        "framework agreement",
        "framework contract",
    ]

    exclude_if_any = [
        "construction",
        "civil works",
        "building works",
        "road works",
        "refurbishment",
        "rehabilitation",
        "consultancy",
        "consulting services",
        "professional services",
        "maintenance of building",
        "construction of",
        "repair of road",
        "housing project",
        "contractor for",
    ]

    has_positive = any(term in text for term in must_have_any)
    has_excluded = any(term in text for term in exclude_if_any)

    return has_positive and not has_excluded


def normalize_tender(
    title: str,
    issuer: str,
    description: str,
    link: str,
    deadline: Optional[str] = None,
    source: str = "unknown",
    reference: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "reference": safe_text(reference),
        "title": safe_text(title),
        "issuer": safe_text(issuer) or "Unknown Issuer",
        "description": safe_text(description),
        "link": safe_text(link),
        "deadline": deadline or "",
        "source": safe_text(source),
        "score": keyword_score(title, description),
        "category": "supply_delivery",
        "harvested_at": utc_now_iso(),
    }


async def fetch_html(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response.text


def parse_generic_cards(html: str, base_url: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    tenders: List[Dict[str, Any]] = []

    card_candidates = soup.select(
        "article, .card, .view-content .views-row, .listing, .result, tr"
    )

    for card in card_candidates:
        text = safe_text(card.get_text(" ", strip=True))
        if len(text) < 40:
            continue

        link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = safe_text(link_tag.get("href"))
        title = safe_text(link_tag.get_text(" ", strip=True))
        if not title:
            title = text[:140]

        full_link = urljoin(base_url, href)

        issuer = ""
        issuer_candidates = [
            card.find(attrs={"class": re.compile(r"issuer|department|org|buyer", re.I)}),
            card.find("strong"),
            card.find("b"),
        ]
        for candidate in issuer_candidates:
            if candidate:
                issuer = safe_text(candidate.get_text(" ", strip=True))
                if issuer:
                    break

        deadline = parse_deadline_from_text(text)

        tender = normalize_tender(
            title=title,
            issuer=issuer,
            description=text[:1200],
            link=full_link,
            deadline=deadline,
            source=base_url,
        )
        tenders.append(tender)

    return tenders


async def harvest_from_source(url: str) -> List[Dict[str, Any]]:
    logger.info("Harvesting supply/delivery tenders from %s", url)

    async with httpx.AsyncClient(
        headers={"User-Agent": "LMCP-AutoQuote/1.0 (+Supply Delivery Harvester)"}
    ) as client:
        html = await fetch_html(client, url)

    tenders = parse_generic_cards(html, url)

    seen = set()
    cleaned: List[Dict[str, Any]] = []

    for item in tenders:
        key = (item["title"].strip().lower(), item["link"].strip().lower())
        if key in seen:
            continue
        seen.add(key)

        if len(item["title"]) < 8:
            continue

        if not is_supply_delivery_tender(item["title"], item["description"]):
            continue

        if item["score"] < 15:
            continue

        cleaned.append(item)

    cleaned.sort(key=lambda x: x.get("score", 0), reverse=True)

    logger.info("Harvested %s supply/delivery tenders from %s", len(cleaned), url)
    return cleaned


async def run_harvest() -> Dict[str, Any]:
    global HARVESTED_TENDERS, LAST_HARVEST_RUN

    env_urls = os.getenv("TENDER_SOURCE_URLS", "").strip()
    source_urls = (
        [u.strip() for u in env_urls.split(",") if u.strip()]
        if env_urls
        else DEFAULT_SOURCE_URLS
    )

    all_results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for url in source_urls:
        try:
            results = await harvest_from_source(url)
            all_results.extend(results)
        except Exception as exc:
            logger.exception("Failed harvesting from %s", url)
            errors.append({"source": url, "error": str(exc)})

    seen = set()
    unique_results: List[Dict[str, Any]] = []

    for item in all_results:
        key = (item["title"].strip().lower(), item["link"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique_results.append(item)

    unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    HARVESTED_TENDERS = unique_results[:200]
    LAST_HARVEST_RUN = utc_now_iso()

    return {
        "status": "success",
        "focus": "supply_and_delivery_only",
        "sources_checked": len(source_urls),
        "total_found": len(unique_results),
        "stored": len(HARVESTED_TENDERS),
        "last_harvest_run": LAST_HARVEST_RUN,
        "errors": errors,
    }


def get_harvested_tenders(limit: int = 50) -> List[Dict[str, Any]]:
    return HARVESTED_TENDERS[:limit]


def get_harvest_summary() -> Dict[str, Any]:
    return {
        "focus": "supply_and_delivery_only",
        "last_harvest_run": LAST_HARVEST_RUN,
        "total_tenders": len(HARVESTED_TENDERS),
        "top_score": HARVESTED_TENDERS[0]["score"] if HARVESTED_TENDERS else 0,
    }
