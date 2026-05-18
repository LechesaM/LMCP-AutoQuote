from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

ETENDERS_API_BASES = [
    "https://ocds-api.etenders.gov.za/api/OCDSReleases",
    "https://ocds-api.etenders.gov.za/api/ocdsreleases",
]

ETENDERS_OCDS_PAGE_SIZE = 100
ETENDERS_OCDS_MAX_PAGES = 5
ETENDERS_OCDS_DAYS_BACK = 30
REQUEST_TIMEOUT = 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_date_days_back(days_back: int = ETENDERS_OCDS_DAYS_BACK) -> str:
    return (utc_now() - timedelta(days=days_back)).strftime("%Y-%m-%d")


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def get_nested(data: Any, path: List[str], default: Any = "") -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def extract_title(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return first_non_empty(
        tender.get("title"),
        release.get("title"),
        get_nested(release, ["planning", "rationale"]),
        get_nested(release, ["buyer", "name"]),
        "Untitled eTender Opportunity",
    )


def extract_description(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return first_non_empty(
        tender.get("description"),
        release.get("description"),
        get_nested(release, ["planning", "rationale"]),
        extract_title(release),
    )


def extract_buyer(release: Dict[str, Any]) -> str:
    buyer = release.get("buyer") or {}
    tender = release.get("tender") or {}
    return first_non_empty(
        buyer.get("name"),
        get_nested(tender, ["procuringEntity", "name"]),
        get_nested(tender, ["procuringEntity", "identifier", "legalName"]),
        "Unknown Buyer",
    )


def extract_reference_no(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return first_non_empty(
        tender.get("id"),
        tender.get("tenderNumber"),
        release.get("ocid"),
        release.get("id"),
    )


def extract_closing_date(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return first_non_empty(
        tender.get("tenderPeriod", {}).get("endDate"),
        tender.get("closingDate"),
        tender.get("bidClosingDate"),
    )


def extract_source_url(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}

    documents = tender.get("documents") or []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        url = safe_text(doc.get("url"))
        if url:
            return url

    links = release.get("links") or []
    for link in links:
        if not isinstance(link, dict):
            continue
        url = safe_text(link.get("url"))
        if url:
            return url

    uri = safe_text(release.get("uri"))
    if uri:
        return uri

    return "https://www.etenders.gov.za/"


def extract_province(release: Dict[str, Any]) -> str:
    text_blob = " ".join(
        [
            safe_text(release.get("buyer", {}).get("name")),
            safe_text(release.get("tender", {}).get("description")),
            safe_text(release.get("tender", {}).get("title")),
            safe_text(release.get("tender", {}).get("mainProcurementCategory")),
        ]
    ).lower()

    provinces = [
        "eastern cape",
        "free state",
        "gauteng",
        "kwazulu-natal",
        "limpopo",
        "mpumalanga",
        "northern cape",
        "north west",
        "western cape",
        "national",
    ]

    for province in provinces:
        if province in text_blob:
            return province.title()

    return "National"


def release_to_opportunity(release: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": extract_title(release),
        "description": extract_description(release),
        "source": "eTenders",
        "source_url": extract_source_url(release),
        "buyer": extract_buyer(release),
        "reference_no": extract_reference_no(release),
        "province": extract_province(release),
        "category": "aggregator",
        "closing_date": extract_closing_date(release),
    }


def _candidate_param_sets(page: int, date_from: str) -> List[Dict[str, Any]]:
    return [
        {"page": page, "pageSize": ETENDERS_OCDS_PAGE_SIZE, "fromDate": date_from},
        {"page": page, "pageSize": ETENDERS_OCDS_PAGE_SIZE, "dateFrom": date_from},
        {"page": page, "size": ETENDERS_OCDS_PAGE_SIZE, "fromDate": date_from},
        {"page": page, "size": ETENDERS_OCDS_PAGE_SIZE, "dateFrom": date_from},
        {"page": page, "pageSize": ETENDERS_OCDS_PAGE_SIZE},
        {"page": page, "size": ETENDERS_OCDS_PAGE_SIZE},
        {"page": page},
        {},
    ]


def _extract_releases(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    candidates = [
        payload.get("releases"),
        payload.get("data"),
        payload.get("results"),
        payload.get("items"),
        payload.get("value"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]

    return []


def _fetch_page(session: requests.Session, page: int, date_from: str) -> List[Dict[str, Any]]:
    for base_url in ETENDERS_API_BASES:
        for params in _candidate_param_sets(page, date_from):
            try:
                response = session.get(base_url, params=params, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                payload = response.json()
                releases = _extract_releases(payload)

                logger.info(
                    "eTenders page fetch succeeded. url=%s params=%s releases=%s",
                    base_url,
                    params,
                    len(releases),
                )
                return releases

            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else "unknown"
                logger.warning(
                    "eTenders request rejected. url=%s params=%s status=%s",
                    base_url,
                    params,
                    status_code,
                )
                continue

            except Exception as exc:
                logger.warning(
                    "eTenders request failed. url=%s params=%s error=%s",
                    base_url,
                    params,
                    exc,
                )
                continue

    # Critical fix:
    # Do NOT raise here. Return [] so the harvest cycle can continue with
    # SANRAL, Eskom, and any other live sources.
    logger.warning("All eTenders endpoint variants failed for page %s. Returning no releases.", page)
    return []


def harvest_etenders_opportunities() -> List[Dict[str, Any]]:
    all_items: List[Dict[str, Any]] = []
    date_from = iso_date_days_back(ETENDERS_OCDS_DAYS_BACK)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; LMCP-AutoQuote/1.0)",
            "Accept": "application/json",
        }
    )

    for page in range(1, ETENDERS_OCDS_MAX_PAGES + 1):
        releases = _fetch_page(session, page, date_from)

        if not releases:
            break

        page_items: List[Dict[str, Any]] = []

        for release in releases:
            try:
                item = release_to_opportunity(release)
                if item.get("title"):
                    page_items.append(item)
            except Exception:
                continue

        all_items.extend(page_items)

        if len(releases) < ETENDERS_OCDS_PAGE_SIZE:
            break

    return all_items
