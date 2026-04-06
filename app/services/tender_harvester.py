from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None  # type: ignore

logger = logging.getLogger(__name__)

# =========================================================
# ENV CONFIG
# =========================================================

ETENDERS_BASE_URL = os.getenv(
    "ETENDERS_BASE_URL",
    "https://www.etenders.gov.za",
).rstrip("/")

ETENDERS_OPPORTUNITIES_PATH = os.getenv(
    "ETENDERS_OPPORTUNITIES_PATH",
    "/Home/opportunities",
)

ETENDERS_TIMEOUT = int(os.getenv("ETENDERS_TIMEOUT", "30"))
ETENDERS_HTML_MAX_PAGES = int(os.getenv("ETENDERS_HTML_MAX_PAGES", "5"))

ETENDERS_OCDS_BASE_URL = os.getenv(
    "ETENDERS_OCDS_BASE_URL",
    "https://ocds-api.etenders.gov.za",
).rstrip("/")

ETENDERS_OCDS_RELEASES_ENDPOINT = os.getenv(
    "ETENDERS_OCDS_RELEASES_ENDPOINT",
    "/api/OCDSReleases",
)

ETENDERS_OCDS_PAGE_SIZE = int(os.getenv("ETENDERS_OCDS_PAGE_SIZE", "100"))
ETENDERS_OCDS_MAX_PAGES = int(os.getenv("ETENDERS_OCDS_MAX_PAGES", "5"))
ETENDERS_OCDS_TIMEOUT = int(os.getenv("ETENDERS_OCDS_TIMEOUT", "30"))
ETENDERS_OCDS_LOOKBACK_DAYS = int(os.getenv("ETENDERS_OCDS_LOOKBACK_DAYS", "30"))

LMCP_HARVEST_USER_AGENT = os.getenv(
    "LMCP_HARVEST_USER_AGENT",
    "Mozilla/5.0 (compatible; LMCP-AutoQuote/1.0; +https://www.etenders.gov.za)",
)

EXTERNAL_PORTAL_TIMEOUT = int(os.getenv("EXTERNAL_PORTAL_TIMEOUT", "25"))
EXTERNAL_PORTAL_MAX_PAGES = int(os.getenv("EXTERNAL_PORTAL_MAX_PAGES", "2"))

SUPPLY_ONLY = True

# =========================================================
# FILTERS
# =========================================================

BLOCKED_KEYWORDS = [
    "medical",
    "pharmaceutical",
    "clinic",
    "hospital",
    "medicine",
    "drugs",
    "anaesthetic",
    "organs",
    "cardio-respiratory",
    "laptop",
    "computer",
    "printer",
    "software",
    "server",
    "router",
    "monitor",
    "tablet",
    "ups",
    "cisco",
    "redgate",
    "it related",
    "it electronic",
    "electronic asset destruction",
    "diesel",
    "petrol",
    "fuel",
    "bitumen",
    "construction",
    "civil",
    "building",
    "consulting",
    "services",
    "maintenance",
    "refurbishment",
    "repair",
    "installation",
    "professional services",
    "cleaning services",
    "security services",
    "skills audit",
    "technical accounting opinion",
    "assets management system",
    "investigative case management system",
    "incident control system",
]

STRICT_BLOCKED_PHRASES = [
    "procurement plan",
    "procurement plans",
    "annual procurement",
    "tender results",
    "bids received",
    "regret letter",
    "award notice",
    "awarded tender",
    "cancelled tender",
    "how to register",
    "supplier registration",
    "vendor registration",
    "database registration",
    "scm policy",
    "supply chain policy",
    "general notice",
    "invitation to register",
    "expression of interest",
    "eoi",
    "sale of goods",
    "petty cash purchases",
    "emergency procurement",
    "preferential procurement policy",
    "preferential procurement regulations",
    "pricing schedules – firm prices",
    "pricing schedules - firm prices",
    "pricing schedules – non-firm prices",
    "pricing schedules - non-firm prices",
    "pre-paid electricity",
    "fraud / theft / corruption",
    "acquaint and up-skill",
    "all prospective suppliers who wish to do business",
]

BLOCKED_DOC_WORDS = [
    "award",
    "awarded",
    "results",
    "minutes",
    "regret",
    "cancelled",
]

VALID_STATUS = {"active", "planned", "published", "open"}

SUPPLY_MARKERS = [
    "supply and delivery",
    "supply, delivery",
    "supply of",
    "delivery of",
    "supply",
    "delivery",
    "provide and deliver",
    "quotation for supply",
    "request for quotation",
    "rfq",
]

BRIEFING_REQUIRED_MARKERS = [
    "compulsory briefing",
    "mandatory briefing",
    "briefing session compulsory",
    "compulsory site inspection",
    "mandatory site inspection",
    "compulsory clarification meeting",
    "mandatory clarification meeting",
]

BRIEFING_NOT_REQUIRED_MARKERS = [
    "non-compulsory briefing",
    "briefing not compulsory",
    "not compulsory briefing",
    "non compulsory briefing",
    "optional briefing",
    "voluntary briefing",
    "there will be no briefing session",
    "no briefing session",
]

DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{2}/\d{2}/\d{4}\b",
    r"\b\d{2}-\d{2}-\d{4}\b",
]

REFERENCE_PATTERNS = [
    r"\b(?:RFQ|RFP|BID|TENDER|TNDR|QUOTATION|QUOTE|SCM|Q)\s*[:#/-]?\s*[A-Z0-9][A-Z0-9/_\-.]{2,}\b",
    r"\b[A-Z]{2,10}[-/][A-Z0-9][A-Z0-9/_\-.]{2,}\b",
    r"\b\d{5,}\b",
]

# =========================================================
# SOURCE REGISTRY
# =========================================================


def _get_source_registry() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "soe": [
            {
                "name": "Eskom Tender Bulletins",
                "list_url": "https://www.eskom.co.za/tenderbulletin/",
                "base_url": "https://www.eskom.co.za",
                "source_name": "Eskom",
                "submission_method": "portal",
                "intelligence_score": 74,
                "enabled": True,
            },
            {
                "name": "Transnet Tenders",
                "list_url": "https://transnetetenders.azurewebsites.net/",
                "base_url": "https://transnetetenders.azurewebsites.net",
                "source_name": "Transnet",
                "submission_method": "portal",
                "intelligence_score": 75,
                "enabled": True,
            },
            {
                "name": "SANRAL Tenders",
                "list_url": "https://www.nra.co.za/service-provider-zone/tenders/",
                "base_url": "https://www.nra.co.za",
                "source_name": "SANRAL",
                "submission_method": "portal",
                "intelligence_score": 78,
                "enabled": True,
            },
            {
                "name": "PRASA Tenders",
                "list_url": "https://www.prasa.com/business-with-us/tenders/",
                "base_url": "https://www.prasa.com",
                "source_name": "PRASA",
                "submission_method": "portal",
                "intelligence_score": 72,
                "enabled": True,
            },
            {
                "name": "ACSA Tenders",
                "list_url": "https://www.airports.co.za/business/tenders",
                "base_url": "https://www.airports.co.za",
                "source_name": "ACSA",
                "submission_method": "portal",
                "intelligence_score": 73,
                "enabled": True,
            },
        ],
        "municipal": [
            {
                "name": "City of Johannesburg Tenders",
                "list_url": "https://www.joburg.org.za/work_/Pages/Work%20in%20Joburg/Tenders.aspx",
                "base_url": "https://www.joburg.org.za",
                "source_name": "City of Johannesburg",
                "submission_method": "portal",
                "intelligence_score": 72,
                "enabled": True,
            },
            {
                "name": "eThekwini Tenders",
                "list_url": "https://www.durban.gov.za/pages/business/tenders",
                "base_url": "https://www.durban.gov.za",
                "source_name": "eThekwini Municipality",
                "submission_method": "portal",
                "intelligence_score": 72,
                "enabled": True,
            },
            {
                "name": "Cape Town Tenders",
                "list_url": "https://www.capetown.gov.za/City-Connect/Doing-business-in-the-city/Tenders-contracts-and-opportunities/Tenders",
                "base_url": "https://www.capetown.gov.za",
                "source_name": "City of Cape Town",
                "submission_method": "portal",
                "intelligence_score": 73,
                "enabled": True,
            },
            {
                "name": "Mangaung Tenders",
                "list_url": "https://www.mangaung.co.za/tenders/",
                "base_url": "https://www.mangaung.co.za",
                "source_name": "Mangaung Metropolitan Municipality",
                "submission_method": "portal",
                "intelligence_score": 76,
                "enabled": True,
            },
            {
                "name": "Nelson Mandela Bay Tenders",
                "list_url": "https://www.nelsonmandelabay.gov.za/business/tenders",
                "base_url": "https://www.nelsonmandelabay.gov.za",
                "source_name": "Nelson Mandela Bay Municipality",
                "submission_method": "portal",
                "intelligence_score": 71,
                "enabled": True,
            },
        ],
        "provincial": [
            {
                "name": "Gauteng eTender Portal",
                "list_url": "https://www.gauteng.gov.za/Business/Tenders",
                "base_url": "https://www.gauteng.gov.za",
                "source_name": "Gauteng Provincial Government",
                "submission_method": "portal",
                "intelligence_score": 74,
                "enabled": True,
            },
            {
                "name": "Western Cape Tenders",
                "list_url": "https://www.westerncape.gov.za/tenders",
                "base_url": "https://www.westerncape.gov.za",
                "source_name": "Western Cape Government",
                "submission_method": "portal",
                "intelligence_score": 74,
                "enabled": True,
            },
            {
                "name": "KwaZulu-Natal Tenders",
                "list_url": "https://www.kznonline.gov.za/index.php?option=com_content&view=article&id=167&Itemid=127",
                "base_url": "https://www.kznonline.gov.za",
                "source_name": "KwaZulu-Natal Provincial Government",
                "submission_method": "portal",
                "intelligence_score": 73,
                "enabled": True,
            },
            {
                "name": "Free State Tenders",
                "list_url": "https://www.freestateonline.fs.gov.za/departments/supply-chain-management/",
                "base_url": "https://www.freestateonline.fs.gov.za",
                "source_name": "Free State Provincial Government",
                "submission_method": "portal",
                "intelligence_score": 77,
                "enabled": True,
            },
            {
                "name": "Eastern Cape Tenders",
                "list_url": "https://www.ecprov.gov.za/tenders/",
                "base_url": "https://www.ecprov.gov.za",
                "source_name": "Eastern Cape Provincial Government",
                "submission_method": "portal",
                "intelligence_score": 73,
                "enabled": True,
            },
        ],
        "national": [
            {
                "name": "Department of Public Works Tenders",
                "list_url": "https://www.publicworks.gov.za/tenders.html",
                "base_url": "https://www.publicworks.gov.za",
                "source_name": "Department of Public Works and Infrastructure",
                "submission_method": "portal",
                "intelligence_score": 76,
                "enabled": True,
            },
            {
                "name": "Department of Health Tenders",
                "list_url": "https://www.health.gov.za/tenders/",
                "base_url": "https://www.health.gov.za",
                "source_name": "National Department of Health",
                "submission_method": "portal",
                "intelligence_score": 60,
                "enabled": True,
            },
            {
                "name": "Department of Basic Education Tenders",
                "list_url": "https://www.education.gov.za/Informationfor/Tenders.aspx",
                "base_url": "https://www.education.gov.za",
                "source_name": "Department of Basic Education",
                "submission_method": "portal",
                "intelligence_score": 71,
                "enabled": True,
            },
            {
                "name": "Department of Transport Tenders",
                "list_url": "https://www.transport.gov.za/tenders",
                "base_url": "https://www.transport.gov.za",
                "source_name": "Department of Transport",
                "submission_method": "portal",
                "intelligence_score": 74,
                "enabled": True,
            },
            {
                "name": "Department of Agriculture Tenders",
                "list_url": "https://www.nda.gov.za/?page_id=4818",
                "base_url": "https://www.nda.gov.za",
                "source_name": "Department of Agriculture",
                "submission_method": "portal",
                "intelligence_score": 72,
                "enabled": True,
            },
        ],
    }


# =========================================================
# HELPERS
# =========================================================


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _contains_blocked(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in BLOCKED_KEYWORDS)


def _contains_strict_blocked_phrase(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in STRICT_BLOCKED_PHRASES)


def _is_supply(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in SUPPLY_MARKERS)


def _has_explicit_supply_or_delivery(text: str) -> bool:
    lowered = text.lower()
    return "supply" in lowered or "delivery" in lowered


def _looks_like_briefing_required(text: str) -> bool:
    lowered = text.lower()

    if any(marker in lowered for marker in BRIEFING_NOT_REQUIRED_MARKERS):
        return False

    return any(marker in lowered for marker in BRIEFING_REQUIRED_MARKERS)


def _extract_first_date(text: str) -> Optional[str]:
    content = _clean(text)
    if not content:
        return None

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, content)
        if match:
            return match.group(0)

    return None


def _normalize_reference(text: str) -> str:
    value = _clean(text)
    if not value:
        return ""

    value = re.sub(r"\s+", " ", value)
    value = value.strip(" -:|")
    return value


def _extract_reference_from_text(text: str) -> str:
    content = _clean(text)
    if not content:
        return ""

    for pattern in REFERENCE_PATTERNS:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match:
            return _normalize_reference(match.group(0))

    return ""


def _is_valid_reference(ref: str) -> bool:
    ref = _clean(ref)
    if not ref:
        return False

    if len(ref) < 5:
        return False

    if not re.search(r"\d", ref):
        return False

    generic_bad = {
        "tender",
        "rfq",
        "quotation",
        "quote",
        "procurement",
        "plans",
        "queries",
        "closing",
        "bidding",
    }
    if ref.lower() in generic_bad:
        return False

    if _contains_strict_blocked_phrase(ref):
        return False

    return True


def _looks_like_junk_title(title: str) -> bool:
    lowered = _safe_lower(title)
    if not lowered:
        return True

    junk_phrases = [
        "procurement plans",
        "tenders - informal rfq",
        "fraud / theft / corruption",
        "pre-paid electricity",
        "how to use",
        "sale of goods",
        "petty cash purchases",
        "emergency procurement",
        "preferential procurement",
        "pricing schedules",
        "supplier registration",
        "vendor registration",
    ]
    return any(phrase in lowered for phrase in junk_phrases)


def _looks_like_real_opportunity(text: str) -> bool:
    lowered = _safe_lower(text)
    if not lowered:
        return False

    positive_markers = [
        "rfq",
        "tender",
        "bid",
        "quotation",
        "request for quotation",
        "closing date",
        "closing:",
        "closes",
        "supply and delivery",
    ]
    return any(marker in lowered for marker in positive_markers)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": LMCP_HARVEST_USER_AGENT,
            "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def _build_opportunities_url(page_number: int = 1) -> str:
    base = f"{ETENDERS_BASE_URL}{ETENDERS_OPPORTUNITIES_PATH}"
    parsed = urlparse(base)
    query = parse_qs(parsed.query)
    query["page"] = [str(page_number)]
    rebuilt = parsed._replace(query=urlencode(query, doseq=True))
    return urlunparse(rebuilt)


def _candidate_public_urls() -> List[str]:
    urls = [
        f"{ETENDERS_BASE_URL}{ETENDERS_OPPORTUNITIES_PATH}",
        f"{ETENDERS_BASE_URL}{ETENDERS_OPPORTUNITIES_PATH}?id=1",
    ]

    for page in range(2, ETENDERS_HTML_MAX_PAGES + 1):
        urls.append(_build_opportunities_url(page_number=page))

    deduped: List[str] = []
    seen: Set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _is_valid_status(tender: Dict[str, Any]) -> bool:
    status = _safe_lower(tender.get("status"))
    if not status:
        return True
    return status in VALID_STATUS


def _valid_documents(docs: List[Dict[str, Any]]) -> bool:
    if not docs:
        return True

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        text = f"{doc.get('title')} {doc.get('description')}".lower()
        if not any(blocked in text for blocked in BLOCKED_DOC_WORDS):
            return True

    return False


def _extract_buyer_name_from_release(release: Dict[str, Any]) -> str:
    buyer = release.get("buyer")
    if isinstance(buyer, dict):
        return _clean(buyer.get("name"))

    parties = release.get("parties")
    if isinstance(parties, list):
        for party in parties:
            if not isinstance(party, dict):
                continue
            roles = party.get("roles") or []
            if isinstance(roles, list) and "buyer" in [str(r).lower() for r in roles]:
                return _clean(party.get("name"))

    return ""


def _extract_release_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("releases", "results", "items", "data"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]

    return []


def _normalize_result(
    *,
    title: str,
    description: str,
    external_url: str,
    buyer_name: str,
    reference_number: str,
    published_date: Optional[str] = None,
    closing_date: Optional[str] = None,
    source_name: str,
    source_url: Optional[str] = None,
    submission_method: str = "portal",
    compulsory_briefing: bool = False,
    intelligence_score: int = 80,
    source_group: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    title = _clean(title)
    description = _clean(description)
    buyer_name = _clean(buyer_name)
    reference_number = _normalize_reference(reference_number)
    external_url = _clean(external_url)
    source_url = _clean(source_url or external_url)

    if not title:
        return None

    if _looks_like_junk_title(title):
        return None

    if not _is_valid_reference(reference_number):
        return None

    combined = f"{title} {description}".lower()

    if _contains_strict_blocked_phrase(combined):
        return None

    if SUPPLY_ONLY:
        if not _is_supply(combined):
            return None
        if not _has_explicit_supply_or_delivery(combined):
            return None

    if _contains_blocked(combined):
        return None

    if compulsory_briefing:
        return None

    if not _looks_like_real_opportunity(f"{title} {description} {reference_number}"):
        return None

    return {
        "title": title,
        "description": description or title,
        "external_url": external_url or f"{ETENDERS_BASE_URL}{ETENDERS_OPPORTUNITIES_PATH}",
        "published_date": published_date,
        "closing_date": closing_date,
        "buyer_name": buyer_name or "Unknown Buyer",
        "reference_number": reference_number,
        "buyer_rfq_number": reference_number,
        "rfq_number": reference_number,
        "category": "Supply / Delivery",
        "source_name": source_name,
        "source_group": _clean(source_group or source_name),
        "source_url": source_url or external_url,
        "is_supply": True,
        "intelligence_score": intelligence_score,
        "quote_ready": True,
        "submission_method": submission_method,
        "submission_email": None,
        "portal_url": external_url,
        "compulsory_briefing": False,
        "briefing_text": "",
        "eligible_for_autonomous": True,
        "harvested_at": datetime.now(timezone.utc).isoformat(),
    }


# =========================================================
# ETENDERS HTML SCRAPER
# =========================================================


def _parse_html_rows_from_soup(
    soup: Any,
    page_url: str,
    *,
    source_name: str,
    buyer_name: str,
    source_group: str,
    intelligence_score: int,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen_refs: Set[str] = set()

    if BeautifulSoup is None:
        return results

    row_candidates = soup.select("table tr")
    if not row_candidates:
        row_candidates = soup.select("div.row, div.card, div.panel, li, article")

    for row in row_candidates:
        try:
            text = " ".join(row.stripped_strings)
            if not text:
                continue

            lowered = text.lower()

            if not _is_supply(lowered):
                continue

            if not _has_explicit_supply_or_delivery(lowered):
                continue

            if _contains_blocked(lowered):
                continue

            if _contains_strict_blocked_phrase(lowered):
                continue

            if _looks_like_briefing_required(lowered):
                continue

            if not _looks_like_real_opportunity(text):
                continue

            link = row.find("a", href=True)
            href = _clean(link.get("href")) if link else ""
            full_url = urljoin(page_url, href) if href else page_url

            title = ""
            if link:
                title = _clean(link.get_text(" ", strip=True))

            if not title:
                heading = row.find(["h1", "h2", "h3", "h4", "strong", "b"])
                title = _clean(heading.get_text(" ", strip=True)) if heading else ""

            if not title:
                title = _clean(text[:250])

            reference_number = _extract_reference_from_text(text)

            if not reference_number and href:
                parsed_href = urlparse(href)
                href_parts = [p for p in parsed_href.path.split("/") if p]
                if href_parts:
                    reference_number = _normalize_reference(href_parts[-1])

            closing_date = None
            if re.search(r"closing", lowered):
                closing_date = _extract_first_date(text)
            if closing_date is None:
                closing_date = _extract_first_date(text)

            item = _normalize_result(
                title=title,
                description=text,
                external_url=full_url,
                buyer_name=buyer_name,
                reference_number=reference_number,
                published_date=None,
                closing_date=closing_date,
                source_name=source_name,
                source_url=page_url,
                submission_method="portal",
                compulsory_briefing=False,
                intelligence_score=intelligence_score,
                source_group=source_group,
            )

            if not item:
                continue

            key = item["reference_number"].lower()
            if key in seen_refs:
                continue

            seen_refs.add(key)
            results.append(item)

        except Exception as exc:
            logger.debug("Skipping HTML row due to parse issue: %s", exc)

    return results


def _parse_html_anchor_fallback(
    soup: Any,
    page_url: str,
    *,
    source_name: str,
    buyer_name: str,
    source_group: str,
    intelligence_score: int,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen_refs: Set[str] = set()

    if BeautifulSoup is None:
        return results

    for anchor in soup.find_all("a", href=True):
        try:
            href = _clean(anchor.get("href"))
            text = _clean(anchor.get_text(" ", strip=True))
            if not href and not text:
                continue

            surrounding = ""
            parent = anchor.parent
            if parent is not None:
                surrounding = " ".join(parent.stripped_strings)

            combined = f"{text} {surrounding}".lower()

            if not _is_supply(combined):
                continue

            if not _has_explicit_supply_or_delivery(combined):
                continue

            if _contains_blocked(combined):
                continue

            if _contains_strict_blocked_phrase(combined):
                continue

            if _looks_like_briefing_required(combined):
                continue

            if not _looks_like_real_opportunity(f"{text} {surrounding} {href}"):
                continue

            full_url = urljoin(page_url, href)
            title = text or surrounding[:250]
            reference_number = _extract_reference_from_text(f"{text} {surrounding} {href}")

            item = _normalize_result(
                title=title,
                description=surrounding or text,
                external_url=full_url,
                buyer_name=buyer_name,
                reference_number=reference_number,
                published_date=None,
                closing_date=_extract_first_date(surrounding),
                source_name=source_name,
                source_url=page_url,
                submission_method="portal",
                compulsory_briefing=False,
                intelligence_score=intelligence_score,
                source_group=source_group,
            )

            if not item:
                continue

            key = item["reference_number"].lower()
            if key in seen_refs:
                continue

            seen_refs.add(key)
            results.append(item)

        except Exception as exc:
            logger.debug("Skipping HTML anchor due to parse issue: %s", exc)

    return results


def harvest_etenders_html() -> List[Dict[str, Any]]:
    if BeautifulSoup is None:
        logger.warning("BeautifulSoup is not installed; skipping HTML harvesting.")
        return []

    session = _make_session()
    results: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for url in _candidate_public_urls():
        try:
            response = session.get(url, timeout=ETENDERS_TIMEOUT)
            response.raise_for_status()
            html = response.text or ""
        except Exception as exc:
            logger.warning("HTML opportunities fetch failed for %s: %s", url, exc)
            continue

        if not html.strip():
            continue

        soup = BeautifulSoup(html, "html.parser")

        page_items = _parse_html_rows_from_soup(
            soup,
            url,
            source_name="eTenders HTML",
            buyer_name="eTenders South Africa",
            source_group="etenders_html",
            intelligence_score=75,
        )
        if not page_items:
            page_items = _parse_html_anchor_fallback(
                soup,
                url,
                source_name="eTenders HTML",
                buyer_name="eTenders South Africa",
                source_group="etenders_html",
                intelligence_score=70,
            )

        for item in page_items:
            key = item["reference_number"].lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(item)

    logger.info("HTML opportunities results: %s", len(results))
    return results


# =========================================================
# OCDS SUPPORT HARVEST
# =========================================================


def _default_date_window() -> Dict[str, str]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=ETENDERS_OCDS_LOOKBACK_DAYS)
    end = today + timedelta(days=1)
    return {
        "dateFrom": start.isoformat(),
        "dateTo": end.isoformat(),
    }


def _fetch_ocds_page(
    url: str,
    page_number: int,
    page_size: int,
    date_from: str,
    date_to: str,
) -> List[Dict[str, Any]]:
    response = requests.get(
        url,
        params={
            "PageNumber": page_number,
            "PageSize": page_size,
            "dateFrom": date_from,
            "dateTo": date_to,
        },
        timeout=ETENDERS_OCDS_TIMEOUT,
        headers={"User-Agent": LMCP_HARVEST_USER_AGENT},
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_release_rows(payload)


def _parse_release(release: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tender = release.get("tender") or {}
    if not isinstance(tender, dict):
        tender = {}

    if not _is_valid_status(tender):
        return None

    title = _clean(tender.get("title") or release.get("title"))
    description = _clean(tender.get("description") or release.get("description"))
    if not title:
        return None

    combined = f"{title} {description}".lower()

    if SUPPLY_ONLY:
        if not _is_supply(combined):
            return None
        if not _has_explicit_supply_or_delivery(combined):
            return None

    if _contains_blocked(combined):
        return None

    if _contains_strict_blocked_phrase(combined):
        return None

    docs = tender.get("documents") or []
    if not isinstance(docs, list):
        docs = []

    if not _valid_documents(docs):
        return None

    if _looks_like_briefing_required(combined):
        return None

    reference_number = (
        _clean(tender.get("tenderNumber"))
        or _clean(tender.get("referenceNumber"))
        or _clean(tender.get("id"))
        or _clean(release.get("ocid"))
        or _clean(release.get("id"))
    )
    reference_number = _normalize_reference(reference_number)

    if not _is_valid_reference(reference_number):
        return None

    external_url = ""
    if _clean(tender.get("url")):
        external_url = _clean(tender.get("url"))
    elif _clean(release.get("url")):
        external_url = _clean(release.get("url"))
    else:
        external_url = f"{ETENDERS_BASE_URL}{ETENDERS_OPPORTUNITIES_PATH}"

    buyer_name = _extract_buyer_name_from_release(release)
    tender_period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}

    return _normalize_result(
        title=title,
        description=description or title,
        external_url=external_url,
        buyer_name=buyer_name or "eTenders South Africa",
        reference_number=reference_number,
        published_date=_clean(release.get("date") or tender.get("publicationDate")) or None,
        closing_date=_clean(tender_period.get("endDate")) or None,
        source_name="eTenders OCDS",
        source_url=external_url,
        submission_method="portal",
        compulsory_briefing=False,
        intelligence_score=80,
        source_group="etenders_ocds",
    )


def harvest_etenders_ocds() -> List[Dict[str, Any]]:
    url = f"{ETENDERS_OCDS_BASE_URL}{ETENDERS_OCDS_RELEASES_ENDPOINT}"

    results: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    window = _default_date_window()
    date_from = window["dateFrom"]
    date_to = window["dateTo"]

    selected_page_size: Optional[int] = None
    for candidate_size in [ETENDERS_OCDS_PAGE_SIZE, 200, 100, 50, 20]:
        try:
            first_page = _fetch_ocds_page(
                url=url,
                page_number=1,
                page_size=candidate_size,
                date_from=date_from,
                date_to=date_to,
            )
            selected_page_size = candidate_size
            logger.info(
                "OCDS accepted page size=%s dateFrom=%s dateTo=%s",
                candidate_size,
                date_from,
                date_to,
            )

            for release in first_page:
                item = _parse_release(release)
                if not item:
                    continue

                key = item["reference_number"].lower()
                if key in seen:
                    continue

                seen.add(key)
                results.append(item)
            break

        except Exception as exc:
            logger.warning(
                "OCDS rejected page size %s for date window %s -> %s: %s",
                candidate_size,
                date_from,
                date_to,
                exc,
            )

    if selected_page_size is None:
        logger.warning("No acceptable OCDS request combination found.")
        return []

    for page in range(2, ETENDERS_OCDS_MAX_PAGES + 1):
        try:
            rows = _fetch_ocds_page(
                url=url,
                page_number=page,
                page_size=selected_page_size,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as exc:
            logger.warning("OCDS failed page %s: %s", page, exc)
            break

        if not rows:
            break

        for release in rows:
            item = _parse_release(release)
            if not item:
                continue

            key = item["reference_number"].lower()
            if key in seen:
                continue

            seen.add(key)
            results.append(item)

    logger.info("OCDS clean results: %s", len(results))
    return results


# =========================================================
# EXTERNAL PORTAL HARVESTERS
# =========================================================


def _portal_candidate_urls(source: Dict[str, Any]) -> List[str]:
    list_url = _clean(source.get("list_url"))
    if not list_url:
        return []

    urls = [list_url]

    parsed = urlparse(list_url)
    query = parse_qs(parsed.query)

    for page in range(2, EXTERNAL_PORTAL_MAX_PAGES + 1):
        updated_query = dict(query)
        updated_query["page"] = [str(page)]
        rebuilt = parsed._replace(query=urlencode(updated_query, doseq=True))
        urls.append(urlunparse(rebuilt))

    deduped: List[str] = []
    seen: Set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _parse_external_portal_page(source: Dict[str, Any], page_url: str, html: str) -> List[Dict[str, Any]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html, "html.parser")

    page_items = _parse_html_rows_from_soup(
        soup,
        page_url,
        source_name=_clean(source.get("source_name") or source.get("name")),
        buyer_name=_clean(source.get("source_name") or source.get("name")),
        source_group=_clean(source.get("category_group") or "external_portal"),
        intelligence_score=_safe_int(source.get("intelligence_score"), 70),
    )
    if page_items:
        return page_items

    return _parse_html_anchor_fallback(
        soup,
        page_url,
        source_name=_clean(source.get("source_name") or source.get("name")),
        buyer_name=_clean(source.get("source_name") or source.get("name")),
        source_group=_clean(source.get("category_group") or "external_portal"),
        intelligence_score=_safe_int(source.get("intelligence_score"), 68),
    )


def harvest_external_portal(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    if BeautifulSoup is None:
        logger.warning(
            "BeautifulSoup is not installed; skipping external portal harvest for %s",
            _clean(source.get("name")),
        )
        return []

    if not bool(source.get("enabled", True)):
        return []

    session = _make_session()
    results: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    urls = _portal_candidate_urls(source)

    for url in urls:
        try:
            response = session.get(url, timeout=EXTERNAL_PORTAL_TIMEOUT)
            response.raise_for_status()
            html = response.text or ""
        except Exception as exc:
            logger.warning("External portal fetch failed for %s: %s", url, exc)
            continue

        if not html.strip():
            continue

        page_items = _parse_external_portal_page(source, url, html)

        for item in page_items:
            key = item["reference_number"].lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(item)

    logger.info(
        "External portal results for %s: %s",
        _clean(source.get("name")),
        len(results),
    )
    return results


def harvest_registry_group(group_name: str) -> List[Dict[str, Any]]:
    registry = _get_source_registry()
    group_sources = registry.get(group_name, [])

    results: List[Dict[str, Any]] = []
    for source in group_sources:
        enriched_source = dict(source)
        enriched_source["category_group"] = group_name
        harvested = harvest_external_portal(enriched_source)
        if harvested:
            results.extend(harvested)

    logger.info("Registry group %s results: %s", group_name, len(results))
    return results


def harvest_soe_portals() -> List[Dict[str, Any]]:
    return harvest_registry_group("soe")


def harvest_municipal_portals() -> List[Dict[str, Any]]:
    return harvest_registry_group("municipal")


def harvest_provincial_departments() -> List[Dict[str, Any]]:
    return harvest_registry_group("provincial")


def harvest_national_department_pages() -> List[Dict[str, Any]]:
    return harvest_registry_group("national")


# =========================================================
# HYBRID MULTI-SOURCE ENTRY
# =========================================================


def _dedupe_results(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        ref = _clean(item.get("reference_number") or item.get("buyer_rfq_number")).lower()
        title = _clean(item.get("title")).lower()
        key = (ref, title)

        if not ref and not title:
            continue

        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


def harvest_hybrid_sources() -> Dict[str, Any]:
    etenders_html = harvest_etenders_html()
    etenders_ocds = harvest_etenders_ocds()
    soe_results = harvest_soe_portals()
    municipal_results = harvest_municipal_portals()
    provincial_results = harvest_provincial_departments()
    national_results = harvest_national_department_pages()

    combined = _dedupe_results(
        etenders_html
        + etenders_ocds
        + soe_results
        + municipal_results
        + provincial_results
        + national_results
    )

    counts = {
        "etenders_html": len(etenders_html),
        "etenders_ocds": len(etenders_ocds),
        "soe_portals": len(soe_results),
        "municipal_portals": len(municipal_results),
        "provincial_departments": len(provincial_results),
        "national_department_pages": len(national_results),
        "combined": len(combined),
    }

    logger.info("Hybrid multi-source harvest counts: %s", counts)

    return {
        "counts": counts,
        "results": combined,
    }


def run_national_tender_radar(db: Any = None) -> Dict[str, Any]:
    hybrid_result = harvest_hybrid_sources()
    items = hybrid_result.get("results", [])
    counts = hybrid_result.get("counts", {})

    return {
        "enabled": True,
        "opportunities_found": len(items),
        "results": items,
        "source_strategy": "etenders_html_plus_ocds_plus_soe_plus_municipal_plus_provincial_plus_national",
        "sources_scanned": {
            "etenders_html": counts.get("etenders_html", 0),
            "etenders_ocds": counts.get("etenders_ocds", 0),
            "soe_portals": counts.get("soe_portals", 0),
            "municipal_portals": counts.get("municipal_portals", 0),
            "provincial_departments": counts.get("provincial_departments", 0),
            "national_department_pages": counts.get("national_department_pages", 0),
        },
    }
