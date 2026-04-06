import os
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.filters import filter_open_opportunities
from app.models import Opportunity


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


ETENDERS_OCDS_BASE_URL = _env("ETENDERS_OCDS_BASE_URL", "https://ocds-api.etenders.gov.za")
ETENDERS_OCDS_RELEASES_ENDPOINT = _env("ETENDERS_OCDS_RELEASES_ENDPOINT", "/api/OCDSReleases")
ETENDERS_OCDS_PAGE_SIZE = int(_env("ETENDERS_OCDS_PAGE_SIZE", "100"))
ETENDERS_OCDS_MAX_PAGES = int(_env("ETENDERS_OCDS_MAX_PAGES", "3"))
HTTP_TIMEOUT = int(_env("HTTP_TIMEOUT", "30"))


def sample_opportunities() -> list[dict[str, Any]]:
    return [
        {
            "id": "sample-1",
            "title": "Supply and delivery of office furniture",
            "description": "Supply and delivery of desks, chairs and filing cabinets.",
            "category": "Supply and delivery",
            "buyer_name": "Department of Public Works",
            "closing_date": "2026-12-31",
            "source": "sample",
            "source_url": None,
            "published_date": "2026-03-01",
        },
        {
            "id": "sample-2",
            "title": "Provision of consulting services for strategy review",
            "description": "Professional consulting services.",
            "category": "Consulting",
            "buyer_name": "Municipality",
            "closing_date": "2026-12-31",
            "source": "sample",
            "source_url": None,
            "published_date": "2026-03-01",
        },
        {
            "id": "sample-3",
            "title": "Supply, delivery and installation of water tanks",
            "description": "Supply and installation of 10 000L water tanks.",
            "category": "Supply and installation",
            "buyer_name": "Local Municipality",
            "closing_date": "2026-12-31",
            "source": "sample",
            "source_url": None,
            "published_date": "2026-03-01",
        },
    ]


def normalize_opportunity(raw: dict[str, Any]) -> dict[str, Any]:
    tender_id = (
        raw.get("id")
        or raw.get("ocid")
        or raw.get("tender_number")
        or raw.get("bidNumber")
        or raw.get("bid_number")
        or ""
    )

    title = (
        raw.get("title")
        or raw.get("tenderTitle")
        or raw.get("description")
        or raw.get("buyer")
        or "Untitled opportunity"
    )

    description = (
        raw.get("description")
        or raw.get("tenderDescription")
        or raw.get("details")
        or ""
    )

    category = (
        raw.get("category")
        or raw.get("procurement_method_details")
        or raw.get("classification")
        or ""
    )

    buyer_name = (
        raw.get("buyer_name")
        or raw.get("buyer")
        or raw.get("procuringEntity")
        or raw.get("publisher")
        or ""
    )

    closing_date = (
        raw.get("closing_date")
        or raw.get("closingDate")
        or raw.get("tender_closing_date")
        or raw.get("bidClosingDate")
        or raw.get("bid_closing_date")
        or ""
    )

    published_date = (
        raw.get("published_date")
        or raw.get("date")
        or raw.get("releaseDate")
        or ""
    )

    source_url = (
        raw.get("source_url")
        or raw.get("url")
        or raw.get("uri")
        or raw.get("tender_url")
        or None
    )

    source = raw.get("source") or "etenders"

    return {
        "external_id": str(tender_id).strip(),
        "title": str(title).strip(),
        "description": str(description).strip(),
        "category": str(category).strip(),
        "buyer_name": str(buyer_name).strip(),
        "closing_date": str(closing_date).strip() if closing_date else "",
        "published_date": str(published_date).strip() if published_date else "",
        "source": str(source).strip(),
        "source_url": source_url,
    }


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ["data", "results", "records", "releases", "items", "value"]:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def fetch_etenders_page(page: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
    base = ETENDERS_OCDS_BASE_URL.rstrip("/")
    endpoint = ETENDERS_OCDS_RELEASES_ENDPOINT.lstrip("/")
    url = f"{base}/{endpoint}"

    params = {
        "page": page,
        "pageSize": page_size,
    }

    response = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    return extract_records(payload)


def fetch_live_opportunities() -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []

    for page in range(1, ETENDERS_OCDS_MAX_PAGES + 1):
        records = fetch_etenders_page(page=page, page_size=ETENDERS_OCDS_PAGE_SIZE)

        if not records:
            break

        for record in records:
            normalized = normalize_opportunity(record)
            if normalized["title"]:
                all_items.append(normalized)

        if len(records) < ETENDERS_OCDS_PAGE_SIZE:
            break

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in all_items:
        key = item.get("external_id") or f'{item.get("title", "")}::{item.get("buyer_name", "")}'
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


def upsert_opportunities(db: Session, items: list[dict[str, Any]]) -> dict[str, int]:
    inserted = 0
    updated = 0

    for item in items:
        external_id = item.get("external_id")
        if not external_id:
            external_id = f'{item.get("title", "")}::{item.get("buyer_name", "")}'
            item["external_id"] = external_id

        existing = (
            db.query(Opportunity)
            .filter(Opportunity.external_id == external_id)
            .first()
        )

        if existing:
            existing.title = item.get("title")
            existing.description = item.get("description")
            existing.category = item.get("category")
            existing.buyer_name = item.get("buyer_name")
            existing.source = item.get("source")
            existing.source_url = item.get("source_url")
            existing.closing_date = item.get("closing_date")
            existing.published_date = item.get("published_date")
            updated += 1
        else:
            db.add(
                Opportunity(
                    external_id=item.get("external_id"),
                    title=item.get("title"),
                    description=item.get("description"),
                    buyer_name=item.get("buyer_name"),
                    category=item.get("category"),
                    source=item.get("source"),
                    source_url=item.get("source_url"),
                    closing_date=item.get("closing_date"),
                    published_date=item.get("published_date"),
                )
            )
            inserted += 1

    db.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "total_processed": len(items),
    }


def sync_opportunities_to_db(db: Session) -> dict[str, Any]:
    source = "etenders-live"
    warning = None

    try:
        live_items = fetch_live_opportunities()
        filtered_items = filter_open_opportunities(live_items)

        if not filtered_items:
            source = "sample-fallback"
            filtered_items = filter_open_opportunities(
                [normalize_opportunity(item) for item in sample_opportunities()]
            )
    except Exception as exc:
        source = "sample-fallback"
        warning = str(exc)
        filtered_items = filter_open_opportunities(
            [normalize_opportunity(item) for item in sample_opportunities()]
        )

    stats = upsert_opportunities(db, filtered_items)

    response = {
        "status": "ok",
        "source": source,
        "count": len(filtered_items),
        "inserted": stats["inserted"],
        "updated": stats["updated"],
        "total_processed": stats["total_processed"],
    }

    if warning:
        response["warning"] = warning

    return response


def list_opportunities_from_db(db: Session) -> list[Opportunity]:
    return (
        db.query(Opportunity)
        .order_by(Opportunity.created_at.desc())
        .all()
    )
