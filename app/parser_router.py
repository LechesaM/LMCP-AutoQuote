from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.source_health import get_harvestable_sources

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT: Tuple[int, int] = (6, 12)
MAX_PAGE_TEXT = 8000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

PROCUREMENT_KEYWORDS = [
    "tender",
    "tenders",
    "bid",
    "bids",
    "rfq",
    "quotation",
    "request for quotation",
    "request for proposal",
    "request for proposals",
    "procurement",
    "supplier",
    "suppliers",
    "supply",
    "delivery",
    "panel of suppliers",
    "framework agreement",
    "framework contract",
]

SUPPLY_KEYWORDS = [
    "supply",
    "delivery",
    "supply and delivery",
    "procurement of goods",
    "materials",
    "equipment",
    "consumables",
    "furniture",
    "stationery",
    "ppe",
    "ict equipment",
    "laptops",
    "printers",
    "toners",
    "plumbing materials",
    "electrical materials",
    "pipes",
    "valves",
    "tools",
    "hardware",
]

NEGATIVE_KEYWORDS = [
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
    "maintenance of",
    "infrastructure works",
]

DOCUMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
)

# Add difficult sources here later as you build custom parsers
CUSTOM_PARSER_DOMAINS: Dict[str, str] = {
    "eskom.co.za": "generic",
    "transnet.net": "generic",
    "prasa.com": "generic",
    "sanparks.org": "generic",
    "dbsa.org": "generic",
    "treasury.gov.za": "generic",
    "etenders.gov.za": "generic",
}


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).strip()


def _normalize_url(url: str) -> str:
    return _clean_text(url).rstrip("/")


def _absolute_url(base_url: str, href: Optional[str]) -> str:
    if not href:
        return _normalize_url(base_url)
    return _normalize_url(urljoin(base_url.rstrip("/") + "/", href))


def _is_document_url(url: str) -> bool:
    lowered = (url or "").lower()
    return lowered.endswith(DOCUMENT_EXTENSIONS)


def _find_keywords(text: str, keywords: List[str]) -> List[str]:
    lowered = text.lower()
    hits = [kw for kw in keywords if kw in lowered]
    return sorted(set(hits))


def _looks_procurement_related(text: str) -> bool:
    return len(_find_keywords(text, PROCUREMENT_KEYWORDS)) > 0


def _supply_score(text: str) -> int:
    lowered = text.lower()
    score = 0

    for kw in SUPPLY_KEYWORDS:
        if kw in lowered:
            score += 18

    for kw in NEGATIVE_KEYWORDS:
        if kw in lowered:
            score -= 20

    return max(0, min(score, 100))


def _choose_parser(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for known_domain, parser_name in CUSTOM_PARSER_DOMAINS.items():
        if known_domain in domain:
            return parser_name

    if _is_document_url(url):
        return "document"

    return "generic"


def _fetch(session: requests.Session, url: str) -> Optional[requests.Response]:
    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def _extract_page_text(soup: BeautifulSoup) -> str:
    try:
        return _clean_text(" ".join(soup.stripped_strings))[:MAX_PAGE_TEXT]
    except Exception:
        return ""


def _parse_document_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = _normalize_url(source.get("url", ""))
    if not url:
        return []

    title_guess = (
        source.get("page_title")
        or source.get("name")
        or "Procurement document"
    )

    text_blob = f"{title_guess} {url}"
    if not _looks_procurement_related(text_blob):
        return []

    return [
        {
            "external_id": f"doc::{source.get('entity_type', 'unknown')}::{source.get('name', 'unknown')}::{url}",
            "title": _clean_text(title_guess)[:500],
            "description": _clean_text(text_blob)[:3000],
            "buyer": _clean_text(source.get("name", ""))[:255],
            "source": "document_link",
            "source_url": url[:1000],
            "published_at": None,
            "closing_date": None,
            "entity_type": _clean_text(source.get("entity_type", "")),
            "procurement_confidence": int(source.get("procurement_confidence") or 0),
            "supply_score": _supply_score(text_blob),
            "parser_used": "document",
            "keywords": source.get("keywords") or [],
        }
    ]


def _parse_generic_source(session: requests.Session, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = _normalize_url(source.get("url", ""))
    if not url:
        return []

    response = _fetch(session, url)
    if response is None:
        return []

    content_type = _clean_text(response.headers.get("Content-Type", "")).lower()
    final_url = _normalize_url(str(response.url))

    if "pdf" in content_type or _is_document_url(final_url):
        return _parse_document_source({**source, "url": final_url})

    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        return []

    page_title = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    page_text = _extract_page_text(soup)

    results: List[Dict[str, Any]] = []
    seen = set()

    page_blob = f"{page_title} {page_text}"
    page_keywords = _find_keywords(page_blob, PROCUREMENT_KEYWORDS)

    if page_keywords:
        key = ("page", final_url.lower())
        seen.add(key)
        results.append(
            {
                "external_id": f"page::{source.get('entity_type', 'unknown')}::{source.get('name', 'unknown')}::{final_url}",
                "title": (page_title or source.get("name") or "Procurement page")[:500],
                "description": page_text[:3000],
                "buyer": _clean_text(source.get("name", ""))[:255],
                "source": "page_level_procurement",
                "source_url": final_url[:1000],
                "published_at": None,
                "closing_date": None,
                "entity_type": _clean_text(source.get("entity_type", "")),
                "procurement_confidence": max(
                    int(source.get("procurement_confidence") or 0),
                    len(page_keywords) * 15,
                ),
                "supply_score": _supply_score(page_blob),
                "parser_used": "generic",
                "keywords": page_keywords,
            }
        )

    for link in soup.find_all("a"):
        href = link.get("href")
        full_url = _absolute_url(final_url, href)
        if not full_url:
            continue

        link_text = _clean_text(link.get_text(" ", strip=True))
        title_attr = _clean_text(link.get("title"))
        combined_text = _clean_text(f"{link_text} {title_attr} {full_url}")

        procurement_hits = _find_keywords(combined_text, PROCUREMENT_KEYWORDS)
        if not procurement_hits and not _is_document_url(full_url):
            continue

        key = (combined_text.lower(), full_url.lower())
        if key in seen:
            continue
        seen.add(key)

        results.append(
            {
                "external_id": f"link::{source.get('entity_type', 'unknown')}::{source.get('name', 'unknown')}::{full_url}",
                "title": (link_text or title_attr or source.get("name") or "Procurement link")[:500],
                "description": combined_text[:3000],
                "buyer": _clean_text(source.get("name", ""))[:255],
                "source": "document_link" if _is_document_url(full_url) else "procurement_link",
                "source_url": full_url[:1000],
                "published_at": None,
                "closing_date": None,
                "entity_type": _clean_text(source.get("entity_type", "")),
                "procurement_confidence": max(
                    int(source.get("procurement_confidence") or 0),
                    len(procurement_hits) * 15,
                ),
                "supply_score": _supply_score(combined_text),
                "parser_used": "generic",
                "keywords": procurement_hits,
            }
        )

    return results


def parse_source(session: requests.Session, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = _normalize_url(source.get("url", ""))
    parser_name = _choose_parser(url)

    if parser_name == "document":
        return _parse_document_source(source)

    # For now, even “custom” known domains still flow through generic
    return _parse_generic_source(session, source)


def route_and_parse_sources(
    include_homepage_only: bool = True,
    include_needs_custom_parser: bool = False,
    min_confidence: int = 12,
    entity_type_filter: Optional[List[str]] = None,
    limit_sources: Optional[int] = None,
) -> Dict[str, Any]:
    sources = get_harvestable_sources(
        include_homepage_only=include_homepage_only,
        include_needs_custom_parser=include_needs_custom_parser,
        min_confidence=min_confidence,
    )

    if entity_type_filter:
        allowed = {x.strip().lower() for x in entity_type_filter if x}
        sources = [
            s for s in sources
            if (s.get("entity_type") or "").strip().lower() in allowed
        ]

    if limit_sources is not None and limit_sources > 0:
        sources = sources[:limit_sources]

    session = requests.Session()
    session.headers.update(HEADERS)

    all_items: List[Dict[str, Any]] = []
    per_source_counts: List[Dict[str, Any]] = []
    seen = set()

    for source in sources:
        parsed_items = parse_source(session, source)

        kept = 0
        for item in parsed_items:
            key = (
                (item.get("title") or "").strip().lower(),
                (item.get("source_url") or "").strip().rstrip("/").lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            all_items.append(item)
            kept += 1

        per_source_counts.append(
            {
                "name": source.get("name"),
                "entity_type": source.get("entity_type"),
                "url": source.get("url"),
                "status": source.get("status"),
                "procurement_confidence": source.get("procurement_confidence"),
                "items_found": kept,
            }
        )

    all_items.sort(
        key=lambda x: (
            -int(x.get("supply_score") or 0),
            -int(x.get("procurement_confidence") or 0),
            x.get("buyer", ""),
        )
    )

    summary = {
        "sources_used": len(sources),
        "items_found": len(all_items),
        "top_item_supply_score": all_items[0]["supply_score"] if all_items else 0,
        "by_entity_type": {},
    }

    for item in all_items:
        entity_type = item.get("entity_type") or "unknown"
        summary["by_entity_type"][entity_type] = summary["by_entity_type"].get(entity_type, 0) + 1

    return {
        "status": "success",
        "summary": summary,
        "sources": per_source_counts,
        "items": all_items,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = route_and_parse_sources(
        include_homepage_only=True,
        include_needs_custom_parser=False,
        min_confidence=12,
        entity_type_filter=None,
        limit_sources=25,
    )
    print(result["summary"])
