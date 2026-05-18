from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.department_sources import DEPARTMENT_SOURCES


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

KEYWORDS = [
    "rfq",
    "quotation",
    "request for quotation",
    "request for proposals",
    "request for proposal",
    "rfi",
    "bid",
    "bids",
    "tender",
    "tenders",
    "supply",
    "delivery",
    "procurement",
    "supplier",
    "suppliers",
    "panel of suppliers",
    "framework agreement",
]

DOCUMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
)


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(value.split()).strip()


def _looks_like_procurement_text(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in KEYWORDS)


def _absolute_url(base_url: str, href: Optional[str]) -> str:
    if not href:
        return base_url
    return urljoin(base_url, href)


def _looks_like_document(href: str) -> bool:
    lowered = (href or "").lower()
    return lowered.endswith(DOCUMENT_EXTENSIONS)


def scrape_department_sites() -> List[Dict]:
    opportunities: List[Dict] = []

    session = requests.Session()
    session.headers.update(HEADERS)

    for source in DEPARTMENT_SOURCES:
        source_name = source["name"]
        source_url = source["url"]
        entity_type = source.get("entity_type", "department")

        try:
            response = session.get(
                source_url,
                timeout=(6, 10),
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.RequestException:
            continue

        try:
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            continue

        page_title = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
        page_text = _clean_text(" ".join(soup.stripped_strings))[:5000]

        # Page-level opportunity if the page itself is obviously procurement-focused.
        if _looks_like_procurement_text(f"{page_title} {page_text}"):
            opportunities.append(
                {
                    "external_id": f"dept::{entity_type}::{source_name}::{source_url}",
                    "title": page_title[:500] or f"{source_name} procurement page",
                    "description": page_text[:3000],
                    "buyer": source_name[:255],
                    "source": f"{entity_type}_site",
                    "source_url": source_url[:1000],
                    "published_at": datetime.now(timezone.utc),
                    "closing_date": None,
                }
            )

        for link in soup.find_all("a"):
            href = link.get("href")
            full_url = _absolute_url(source_url, href)
            link_text = _clean_text(link.get_text(" ", strip=True))
            title_attr = _clean_text(link.get("title"))
            combined_text = _clean_text(f"{link_text} {title_attr}")

            if not combined_text and not _looks_like_document(full_url):
                continue

            candidate_text = combined_text or full_url

            if not _looks_like_procurement_text(candidate_text) and not _looks_like_document(full_url):
                continue

            opportunities.append(
                {
                    "external_id": f"dept::{entity_type}::{source_name}::{full_url}",
                    "title": (combined_text or page_title or source_name)[:500],
                    "description": candidate_text[:3000],
                    "buyer": source_name[:255],
                    "source": f"{entity_type}_site",
                    "source_url": full_url[:1000],
                    "published_at": datetime.now(timezone.utc),
                    "closing_date": None,
                }
            )

    deduped: List[Dict] = []
    seen = set()

    for item in opportunities:
        key = item["external_id"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped
