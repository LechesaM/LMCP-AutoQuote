from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests


ETENDERS_OCDS_BASE_URL = os.getenv("ETENDERS_OCDS_BASE_URL", "https://ocds-api.etenders.gov.za")
ETENDERS_OCDS_RELEASES_ENDPOINT = os.getenv("ETENDERS_OCDS_RELEASES_ENDPOINT", "/api/OCDSReleases")
ETENDERS_OCDS_DAYS_BACK = int(os.getenv("ETENDERS_OCDS_DAYS_BACK", "30"))
ETENDERS_OCDS_PAGE_SIZE = int(os.getenv("ETENDERS_OCDS_PAGE_SIZE", "100"))
ETENDERS_OCDS_MAX_PAGES = int(os.getenv("ETENDERS_OCDS_MAX_PAGES", "20"))


def build_url() -> str:
    return f"{ETENDERS_OCDS_BASE_URL.rstrip('/')}{ETENDERS_OCDS_RELEASES_ENDPOINT}"


def extract_description(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return (
        tender.get("description")
        or tender.get("title")
        or release.get("description")
        or ""
    )


def extract_title(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return tender.get("title") or release.get("title") or ""


def extract_buyer(release: Dict[str, Any]) -> str:
    buyer = release.get("buyer") or {}
    return buyer.get("name") or ""


def extract_reference_no(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return tender.get("id") or release.get("ocid") or ""


def extract_closing_date(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return tender.get("tenderPeriod", {}).get("endDate") or ""


def extract_source_url(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    documents = tender.get("documents") or []
    for doc in documents:
        url = doc.get("url")
        if url:
            return url
    return ""


def release_to_opportunity(release: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": extract_title(release),
        "description": extract_description(release),
        "source": "eTenders",
        "source_url": extract_source_url(release),
        "buyer": extract_buyer(release),
        "reference_no": extract_reference_no(release),
        "province": "",
        "category": "",
        "closing_date": extract_closing_date(release),
    }


def harvest_etenders_opportunities() -> List[Dict[str, Any]]:
    all_items: List[Dict[str, Any]] = []
    url = build_url()

    date_from = (datetime.now() - timedelta(days=ETENDERS_OCDS_DAYS_BACK)).strftime("%Y-%m-%d")

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "LMCP-AutoQuote/1.0",
        }
    )

    for page in range(1, ETENDERS_OCDS_MAX_PAGES + 1):
        params = {
            "page": page,
            "pageSize": ETENDERS_OCDS_PAGE_SIZE,
            "fromDate": date_from,
        }

        response = session.get(url, params=params, timeout=60)
        response.raise_for_status()

        payload = response.json()

        releases = (
            payload.get("releases")
            or payload.get("data")
            or payload.get("results")
            or []
        )

        if not releases:
            break

        for release in releases:
            try:
                item = release_to_opportunity(release)
                if item.get("title"):
                    all_items.append(item)
            except Exception:
                continue

    return all_items
