from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

ETENDERS_URL = "https://www.etenders.gov.za/Home/opportunities?id=1"

DEFAULT_TIMEOUT = 12
DEFAULT_MAX_EXTRA_PAGES = 5
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

PRIORITY_PATHS = [
    "/tenders",
    "/tender",
    "/procurement",
    "/procurements",
    "/bids",
    "/bid",
    "/rfq",
    "/rfqs",
    "/quotations",
    "/quotation",
    "/opportunities",
    "/supply-chain-management",
    "/scm",
]

PRIORITY_LINK_TERMS = [
    "tender",
    "tenders",
    "bid",
    "bids",
    "rfq",
    "rfqs",
    "quotation",
    "quotations",
    "procurement",
    "procurements",
    "supply chain",
    "scm",
    "opportunities",
    "request for quotation",
    "request for proposal",
    "rfp",
]

PROCUREMENT_KEYWORDS = [
    "tender",
    "rfq",
    "request for quotation",
    "quotation",
    "bid",
    "bids",
    "rfp",
    "request for proposal",
    "procurement",
    "supply",
    "invitation to bid",
    "appointment of",
]

BLOCKED_SCOPE_TERMS = [
    "medical",
    "pharmaceutical",
    "clinic",
    "hospital",
    "fuel",
    "petrol",
    "diesel",
    "computer equipment",
    "laptop",
    "printer",
    "server",
    "router",
    "software license",
    "tablet",
    "catering",
    "refreshments",
    "meal supply",
    "food supply",
    "construction",
    "civil works",
    "building works",
    "roadworks",
]

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _source_name(source: Optional[Dict[str, Any]]) -> str:
    if not isinstance(source, dict):
        return ""
    return _clean(source.get("source_name") or source.get("name"))


def _source_type(source: Optional[Dict[str, Any]]) -> str:
    if not isinstance(source, dict):
        return ""
    return _safe_lower(
        source.get("type") or source.get("source_type") or source.get("source_group")
    )


def _source_url(source: Optional[Dict[str, Any]]) -> str:
    if not isinstance(source, dict):
        return ""
    return _clean(source.get("url") or source.get("list_url") or source.get("source_url"))


def _source_domain(source: Optional[Dict[str, Any]]) -> str:
    url = _source_url(source)
    if not url:
        return ""
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _is_etenders_source(source: Optional[Dict[str, Any]]) -> bool:
    name = _source_name(source).lower()
    source_type = _source_type(source)
    url = _source_url(source).lower()

    if "etenders" in name:
        return True
    if "etenders.gov.za" in url:
        return True
    if source_type in {"web", "portal", "external_portal"} and "etenders" in name:
        return True
    return False


def _looks_like_html(text: str) -> bool:
    t = _safe_lower(text)
    return "<html" in t or "<body" in t or "<a " in t or "<table" in t


def _strip_tags(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _find_links(html: str) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    if not html:
        return results

    pattern = re.compile(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        href = _clean(match.group(1))
        inner = re.sub(r"<[^>]+>", " ", match.group(2) or "")
        text = re.sub(r"\s+", " ", inner).strip()
        if href:
            results.append({"href": href, "text": text})

    return results


def _normalize_reference(text: str) -> str:
    text = _clean(text).upper()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:|/")


def _extract_reference(text: str) -> str:
    text = _clean(text)
    if not text:
        return ""

    patterns = [
        r"(RFQ\s*[:#\-]?\s*[A-Z0-9][A-Z0-9\-\/]{2,})",
        r"(BID\s*[:#\-]?\s*[A-Z0-9][A-Z0-9\-\/]{2,})",
        r"(TENDER\s*[:#\-]?\s*[A-Z0-9][A-Z0-9\-\/]{2,})",
        r"(RFP\s*[:#\-]?\s*[A-Z0-9][A-Z0-9\-\/]{2,})",
        r"([A-Z]{2,10}[-/][0-9]{2,}[-/][0-9]{1,})",
        r"([A-Z0-9]{4,}[-/][A-Z0-9]{2,})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            ref = _normalize_reference(match.group(1))
            if len(ref) > 4 and ref not in {"RFQ", "BID", "TENDER", "RFP"}:
                return ref

    return ""


def _extract_closing_date(text: str) -> str:
    if not text:
        return ""

    patterns = [
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
        r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _clean(match.group(1))
    return ""


def _looks_like_procurement_text(text: str) -> bool:
    t = _safe_lower(text)
    if not t:
        return False
    return any(keyword in t for keyword in PROCUREMENT_KEYWORDS)


def _is_blocked_scope(text: str) -> bool:
    t = _safe_lower(text)
    return any(term in t for term in BLOCKED_SCOPE_TERMS)


def _absolute_url(base_url: str, href: str) -> str:
    href = _clean(href)
    if not href:
        return ""
    if href.lower().startswith(("http://", "https://")):
        return href
    return urljoin(base_url, href)


def _same_domain_or_subdomain(base_domain: str, candidate_url: str) -> bool:
    if not candidate_url:
        return False
    try:
        candidate_domain = (urlparse(candidate_url).netloc or "").lower()
    except Exception:
        return False

    if not base_domain or not candidate_domain:
        return False

    return candidate_domain == base_domain or candidate_domain.endswith("." + base_domain)


def _priority_link_score(text: str, href: str) -> int:
    combined = f"{text} {href}".lower()
    score = 0

    for term in PRIORITY_LINK_TERMS:
        if term in combined:
            score += 10

    if "tender" in combined:
        score += 8
    if "rfq" in combined:
        score += 8
    if "bid" in combined:
        score += 6
    if "procurement" in combined:
        score += 6
    if "quotation" in combined:
        score += 6
    if "opportunit" in combined:
        score += 4

    return score


def _make_item(
    source: Dict[str, Any],
    title: str,
    description: str,
    external_url: str,
    reference: str = "",
    closing_date: str = "",
) -> Dict[str, Any]:
    source_name = _source_name(source) or "Unknown Source"
    source_type = _source_type(source) or "generic_portal"
    submission_method = _clean(source.get("submission_method") or "portal")
    source_group = _clean(source.get("source_group") or source_type or "external_portal")

    ref = reference or _extract_reference(f"{title} {description}")
    if not ref:
        ref = f"SRC-{abs(hash((source_name, title, external_url))) % 10_000_000}"

    return {
        "source": source_name,
        "source_name": source_name,
        "source_group": source_group,
        "source_type": source_type,
        "title": _clean(title) or "Untitled RFQ",
        "description": _clean(description),
        "buyer_rfq_number": ref,
        "rfq_number": ref,
        "reference_number": ref,
        "external_id": ref,
        "external_url": _clean(external_url),
        "portal_url": _clean(external_url) or _source_url(source),
        "source_url": _source_url(source),
        "closing_date": _clean(closing_date),
        "status": "active",
        "submission_method": submission_method,
        "documents": [],
        "document_urls": [],
        "eligible": True,
        "quote_ready": True,
        "harvested_at": _utc_iso(),
    }


def _dedupe_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    clean: List[Dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        key = (
            _clean(item.get("reference_number"))
            or _clean(item.get("buyer_rfq_number"))
            or _clean(item.get("external_id"))
            or _clean(item.get("external_url"))
            or _clean(item.get("title"))
        ).lower()

        if not key or key in seen:
            continue

        seen.add(key)
        clean.append(item)

    return clean


def _fetch_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=DEFAULT_TIMEOUT,
            verify=False,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.text or "", None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


class ETendersWebParser:
    """
    eTenders harvester
    - Primary: Playwright-rendered extraction
    - No HTML fallback, because the raw page shell returns junk headings
    """

    def harvest(self) -> List[Dict[str, Any]]:
        try:
            from app.services.etenders_playwright import harvest_etenders_playwright

            logger.info("[eTenders] Playwright harvest start")
            items = harvest_etenders_playwright()
            items = _dedupe_items(items)

            if items:
                logger.info("[eTenders] Playwright count=%s", len(items))
                return items

            logger.warning("[eTenders] Playwright returned 0 items. Returning 0 instead of HTML junk.")
            return []

        except Exception as exc:
            logger.warning("[eTenders] Playwright failed: %s", exc)
            return []


class GenericPortalParser:
    """
    Upgraded generic portal parser:
    - fetch base page
    - try priority pages like /tenders, /procurement, /bids, /rfq
    - follow priority links found on the page
    - extract procurement-looking rows from links
    - fallback to visible text snippets
    """

    def harvest(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = _source_url(source)
        source_name = _source_name(source) or "Unknown Source"
        base_domain = _source_domain(source)

        if not url:
            logger.info("[GENERIC] Skipping source with no URL: %s", source_name)
            return []

        if "google.com/search" in url.lower():
            logger.info("[GENERIC] Skipping Google search seed source: %s", source_name)
            return []

        pages_to_parse: List[Tuple[str, str]] = []
        visited_urls: Set[str] = set()

        def add_page(page_url: str, html: Optional[str]) -> None:
            if not page_url or not html:
                return
            normalized_url = _clean(page_url)
            if normalized_url in visited_urls:
                return
            if not _looks_like_html(html):
                return
            visited_urls.add(normalized_url)
            pages_to_parse.append((normalized_url, html))

        logger.info("[GENERIC] Fetching base page for source=%s url=%s", source_name, url)
        html, error = _fetch_url(url)
        if error:
            logger.info("[GENERIC] Base fetch failed for source=%s: %s", source_name, error)
            return []
        add_page(url, html)

        # Priority fixed paths
        for path in PRIORITY_PATHS:
            if len(pages_to_parse) >= (1 + DEFAULT_MAX_EXTRA_PAGES):
                break
            test_url = url.rstrip("/") + path
            if test_url in visited_urls:
                continue
            page_html, page_error = _fetch_url(test_url)
            if page_error:
                continue
            add_page(test_url, page_html)

        # Priority discovered links from base page
        candidate_links: List[Tuple[int, str, str]] = []
        for page_url, page_html in list(pages_to_parse):
            for link in _find_links(page_html):
                href = _absolute_url(page_url, link.get("href", ""))
                text = _clean(link.get("text"))
                if not href:
                    continue
                if href in visited_urls:
                    continue
                if not _same_domain_or_subdomain(base_domain, href):
                    continue

                score = _priority_link_score(text, href)
                if score <= 0:
                    continue

                candidate_links.append((score, href, text))

        candidate_links.sort(key=lambda row: row[0], reverse=True)

        for _, href, _ in candidate_links[:DEFAULT_MAX_EXTRA_PAGES]:
            if href in visited_urls:
                continue
            page_html, page_error = _fetch_url(href)
            if page_error:
                continue
            add_page(href, page_html)

        items: List[Dict[str, Any]] = []

        for page_url, page_html in pages_to_parse:
            items.extend(self._extract_items_from_links(source, page_url, page_html))
            items.extend(self._extract_items_from_text(source, page_url, page_html))

        items = _dedupe_items(items)
        logger.info(
            "[GENERIC] source=%s parsed_pages=%s extracted_count=%s",
            source_name,
            len(pages_to_parse),
            len(items),
        )
        return items

    def _extract_items_from_links(
        self,
        source: Dict[str, Any],
        page_url: str,
        html: str,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        for link in _find_links(html):
            href = _absolute_url(page_url, link.get("href", ""))
            text = _clean(link.get("text"))

            if not href or not text:
                continue

            combined = f"{text} {href}"
            if not _looks_like_procurement_text(combined):
                continue
            if _is_blocked_scope(combined):
                continue

            closing_date = _extract_closing_date(combined)
            reference = _extract_reference(combined)

            items.append(
                _make_item(
                    source=source,
                    title=text[:180],
                    description=text[:500],
                    external_url=href,
                    reference=reference,
                    closing_date=closing_date,
                )
            )

        return items

    def _extract_items_from_text(
        self,
        source: Dict[str, Any],
        page_url: str,
        html: str,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        visible_text = _strip_tags(html)
        if not visible_text:
            return items

        snippet_patterns = [
            r"([^\.]{0,140}\bRFQ\b[^\.]{0,220})",
            r"([^\.]{0,140}\bTENDER\b[^\.]{0,220})",
            r"([^\.]{0,140}\bBID\b[^\.]{0,220})",
            r"([^\.]{0,140}\bRFP\b[^\.]{0,220})",
            r"([^\.]{0,180}\bREQUEST FOR QUOTATION\b[^\.]{0,220})",
            r"([^\.]{0,180}\bINVITATION TO BID\b[^\.]{0,220})",
            r"([^\.]{0,180}\bAPPOINTMENT OF\b[^\.]{0,220})",
        ]

        seen_snippets = set()

        for pattern in snippet_patterns:
            for match in re.finditer(pattern, visible_text, re.IGNORECASE):
                snippet = _clean(match.group(1))
                if not snippet:
                    continue

                key = snippet.lower()
                if key in seen_snippets:
                    continue
                seen_snippets.add(key)

                if not _looks_like_procurement_text(snippet):
                    continue
                if _is_blocked_scope(snippet):
                    continue

                closing_date = _extract_closing_date(snippet)
                reference = _extract_reference(snippet)

                items.append(
                    _make_item(
                        source=source,
                        title=snippet[:180],
                        description=snippet[:500],
                        external_url=page_url,
                        reference=reference,
                        closing_date=closing_date,
                    )
                )

        return items


def harvest_etenders_opportunities() -> List[Dict[str, Any]]:
    return ETendersWebParser().harvest()


def harvest_etenders_web(source: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    logger.info("[DIRECT] Running eTenders Web via Playwright")
    return harvest_etenders_opportunities()


def harvest_generic_portal(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generic entry point expected by router/orchestrator.

    Behaviour:
    - routes eTenders to Playwright
    - uses upgraded generic HTML parser for other portal-style sources
    """
    if _is_etenders_source(source):
        return harvest_etenders_web(source)

    return GenericPortalParser().harvest(source)


def harvest_from_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(source, dict):
        return []

    if _is_etenders_source(source):
        return harvest_etenders_web(source)

    if _source_type(source) in {
        "generic_portal",
        "portal",
        "external_portal",
        "web",
        "municipality_extended",
        "municipal",
        "soe",
        "provincial",
        "national",
        "",
    }:
        return harvest_generic_portal(source)

    logger.info(
        "[DIRECT] No direct harvester mapped for source=%s type=%s",
        _source_name(source) or "Unknown Source",
        _source_type(source) or "unknown",
    )
    return []


def run_source_harvester(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    return harvest_from_source(source)


def harvest_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    return harvest_from_source(source)


def harvest_etenders(source: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return harvest_etenders_web(source)


if __name__ == "__main__":
    items = harvest_etenders_opportunities()
    print("COUNT:", len(items))
    print(items[:3])
