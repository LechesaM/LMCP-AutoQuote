import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    )
}


@dataclass
class CrawlResult:
    portal_code: str
    portal_name: str
    listing_url: str
    fetched_at: str
    success: bool
    status_code: Optional[int]
    error: Optional[str]
    item_count: int
    items: List[Dict[str, Any]]


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _looks_like_procurement_text(text: str) -> bool:
    haystack = (text or "").lower()
    keywords = [
        "tender",
        "bid",
        "rfq",
        "quotation",
        "request for quotation",
        "request for proposal",
        "supply",
        "delivery",
        "procurement",
    ]
    return any(keyword in haystack for keyword in keywords)


def _extract_candidate_links(base_url: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        text = _clean_text(anchor.get_text(" ", strip=True))

        full_url = urljoin(base_url, href)
        signature = f"{text}||{full_url}"

        if signature in seen:
            continue
        seen.add(signature)

        if not text:
            continue

        if _looks_like_procurement_text(text) or _looks_like_procurement_text(full_url):
            candidates.append(
                {
                    "title": text,
                    "url": full_url,
                    "description": None,
                }
            )

    return candidates


def crawl_listing_page(portal: Dict[str, Any], listing_url: str, timeout: int = 25) -> CrawlResult:
    try:
        response = requests.get(
            listing_url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        items = _extract_candidate_links(listing_url, soup)

        return CrawlResult(
            portal_code=portal.get("portal_code", "unknown"),
            portal_name=portal.get("name", "Unknown Portal"),
            listing_url=listing_url,
            fetched_at=datetime.utcnow().isoformat(),
            success=True,
            status_code=response.status_code,
            error=None,
            item_count=len(items),
            items=items,
        )

    except Exception as exc:
        return CrawlResult(
            portal_code=portal.get("portal_code", "unknown"),
            portal_name=portal.get("name", "Unknown Portal"),
            listing_url=listing_url,
            fetched_at=datetime.utcnow().isoformat(),
            success=False,
            status_code=None,
            error=str(exc),
            item_count=0,
            items=[],
        )


def crawl_portal(portal: Dict[str, Any]) -> Dict[str, Any]:
    listing_urls = portal.get("listing_urls") or []
    results: List[Dict[str, Any]] = []

    for listing_url in listing_urls:
        crawl_result = crawl_listing_page(portal, listing_url)
        results.append(asdict(crawl_result))

    total_items = sum(result.get("item_count", 0) for result in results)
    success_count = sum(1 for result in results if result.get("success"))

    return {
        "portal_code": portal.get("portal_code"),
        "portal_name": portal.get("name"),
        "portal_type": portal.get("portal_type"),
        "buyer_scope": portal.get("buyer_scope"),
        "results": results,
        "total_items": total_items,
        "successful_fetches": success_count,
        "total_fetches": len(results),
    }
