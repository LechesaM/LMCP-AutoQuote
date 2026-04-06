from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


TENDER_HINTS = re.compile(r"\b(tender|rfq|rfp|quotation|bid|procurement|scm)\b", re.IGNORECASE)
DATE_HINTS = re.compile(
    r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b"  # 2026-03-01 or 2026/03/01
    r"|\b(\d{2}[-/]\d{2}[-/]\d{4})\b",  # 01-03-2026 or 01/03/2026
    re.IGNORECASE,
)


@dataclass
class EntitySite:
    name: str
    base_url: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(s: str) -> str:
    return " ".join((s or "").split()).strip()


def load_entity_sites_from_env() -> List[EntitySite]:
    """
    Configure via env var:
      ENTITY_SITES="Name1|https://example.org/tenders,Name2|https://example.com/procurement"
    If empty, we return an empty list (system still runs eTenders).
    """
    raw = (os.getenv("ENTITY_SITES") or "").strip()
    if not raw:
        return []

    sites: List[EntitySite] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "|" in part:
            name, url = part.split("|", 1)
        else:
            name, url = part, part
        sites.append(EntitySite(name=_clean(name), base_url=_clean(url)))
    return sites


def _same_host(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


async def fetch_site_opportunities(
    site: EntitySite,
    client: httpx.AsyncClient,
    max_pages: int = 2,
    max_links: int = 80,
) -> List[Dict[str, Any]]:
    """
    Generic fetch:
    - Fetch base_url
    - Collect tender-ish links
    - Fetch a small number of linked pages
    - Emit opportunity dicts aligned with our storage schema
    """
    out: List[Dict[str, Any]] = []

    try:
        r = await client.get(site.base_url, follow_redirects=True, timeout=30)
        r.raise_for_status()
    except Exception:
        return out

    soup = BeautifulSoup(r.text, "html.parser")

    # Collect candidate links
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href:
            continue
        url = urljoin(site.base_url, href)
        txt = _clean(a.get_text(" "))
        blob = f"{txt} {url}"
        if TENDER_HINTS.search(blob):
            # Keep same-host links to avoid drifting off
            if _same_host(site.base_url, url):
                links.append(url)

    # Deduplicate & cap
    uniq: List[str] = []
    seen = set()
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
        if len(uniq) >= max_links:
            break

    # If no obvious links, treat base_url as the tender page itself
    if not uniq:
        uniq = [site.base_url]

    # Fetch a few pages
    pages_to_fetch = uniq[:max_pages]
    for page_url in pages_to_fetch:
        try:
            pr = await client.get(page_url, follow_redirects=True, timeout=30)
            pr.raise_for_status()
        except Exception:
            continue

        psoup = BeautifulSoup(pr.text, "html.parser")

        # Try to extract "items" from list/table rows first
        candidates = []

        # Table rows
        for tr in psoup.find_all("tr"):
            text = _clean(tr.get_text(" "))
            if TENDER_HINTS.search(text):
                candidates.append((text, page_url))

        # List items
        for li in psoup.find_all(["li", "article", "div"]):
            text = _clean(li.get_text(" "))
            if len(text) < 40:
                continue
            if TENDER_HINTS.search(text):
                candidates.append((text, page_url))

        # Fall back: whole page
        if not candidates:
            page_text = _clean(psoup.get_text(" "))
            if TENDER_HINTS.search(page_text):
                candidates.append((page_text[:600], page_url))

        for text, src_url in candidates[:30]:
            # Best-effort title
            title = text.split("  ")[0][:160] if text else f"Tender notice - {site.name}"

            # Best-effort closing date (very rough)
            closing_date: Optional[str] = None
            m = DATE_HINTS.search(text)
            if m:
                closing_date = m.group(0)

            out.append(
                {
                    "source": "entity_site",
                    "source_url": src_url,
                    "buyer": {"name": site.name},
                    "tender": {
                        "title": title,
                        "description": text[:1200],
                        "mainProcurementCategory": "goods",  # unknown -> default goods for filtering, still validated later
                    },
                    "fetched_at": _now_iso(),
                    "closing_date_hint": closing_date,
                }
            )

    return out


async def fetch_all_entity_sites() -> List[Dict[str, Any]]:
    sites = load_entity_sites_from_env()
    if not sites:
        return []

    headers = {
        "User-Agent": "LMCP-AutoQuoteBot/1.0 (+contact: admin@lmcp.local)",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(headers=headers) as client:
        results: List[Dict[str, Any]] = []
        for site in sites:
            items = await fetch_site_opportunities(site, client)
            results.extend(items)
        return results
