from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.models import Opportunity

logger = logging.getLogger(__name__)


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """
    Read from dataclass/object or dict safely.
    """
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(attr, default)

    return getattr(obj, attr, default)


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _find_existing_opportunity(
    db: Session,
    external_url: Optional[str],
    reference_number: Optional[str],
    title: Optional[str],
) -> Optional[Opportunity]:
    """
    Try to find an existing opportunity using the safest available identifiers.
    Priority:
    1. external_url
    2. reference_number
    3. title
    """
    if external_url:
        existing = (
            db.query(Opportunity)
            .filter(Opportunity.external_url == external_url)
            .first()
        )
        if existing:
            return existing

    if reference_number:
        existing = (
            db.query(Opportunity)
            .filter(Opportunity.reference_number == reference_number)
            .first()
        )
        if existing:
            return existing

    if title:
        existing = (
            db.query(Opportunity)
            .filter(Opportunity.title == title)
            .first()
        )
        if existing:
            return existing

    return None


def _assign_if_exists(model: Opportunity, field_name: str, value: Any) -> None:
    """
    Only assign fields that actually exist on the SQLAlchemy model.
    This keeps the persistence layer safe even if your Opportunity model
    differs slightly from the harvested payload.
    """
    if hasattr(model, field_name):
        setattr(model, field_name, value)


def _upsert_single_opportunity(db: Session, harvested: Any) -> dict:
    """
    Upsert one harvested opportunity into the Opportunity table.
    Accepts either:
    - HarvestedOpportunity object
    - dict payload
    """
    title = _normalize_str(_safe_get(harvested, "title"))
    description = _normalize_str(_safe_get(harvested, "description"))
    external_url = _normalize_str(
        _safe_get(harvested, "external_url") or _safe_get(harvested, "url")
    )
    buyer_name = _normalize_str(
        _safe_get(harvested, "buyer_name") or _safe_get(harvested, "buyer")
    )
    reference_number = _normalize_str(_safe_get(harvested, "reference_number"))
    province = _normalize_str(_safe_get(harvested, "province"))
    category = _normalize_str(_safe_get(harvested, "category"))
    published_date = _safe_get(harvested, "published_date")
    closing_date = _safe_get(harvested, "closing_date")
    is_supply = bool(_safe_get(harvested, "is_supply", False))
    intelligence_score = int(_safe_get(harvested, "intelligence_score", 0) or 0)
    quote_ready = bool(_safe_get(harvested, "quote_ready", False))
    source_name = _normalize_str(_safe_get(harvested, "source_name"))
    source_type = _normalize_str(_safe_get(harvested, "source_type"))
    source_url = _normalize_str(_safe_get(harvested, "source_url"))
    is_national = bool(_safe_get(harvested, "is_national", False))
    raw_payload = _safe_get(harvested, "raw")

    if not title and not description:
        return {"status": "skipped", "reason": "missing_title_and_description"}

    existing = _find_existing_opportunity(
        db=db,
        external_url=external_url,
        reference_number=reference_number,
        title=title,
    )

    if existing:
        _assign_if_exists(existing, "title", title)
        _assign_if_exists(existing, "description", description)
        _assign_if_exists(existing, "external_url", external_url)
        _assign_if_exists(existing, "buyer", buyer_name)
        _assign_if_exists(existing, "buyer_name", buyer_name)
        _assign_if_exists(existing, "reference_number", reference_number)
        _assign_if_exists(existing, "province", province)
        _assign_if_exists(existing, "category", category)
        _assign_if_exists(existing, "published_date", published_date)
        _assign_if_exists(existing, "closing_date", closing_date)
        _assign_if_exists(existing, "is_supply", is_supply)
        _assign_if_exists(existing, "intelligence_score", intelligence_score)
        _assign_if_exists(existing, "quote_ready", quote_ready)
        _assign_if_exists(existing, "source_name", source_name)
        _assign_if_exists(existing, "source_type", source_type)
        _assign_if_exists(existing, "source_url", source_url)
        _assign_if_exists(existing, "is_national", is_national)
        _assign_if_exists(existing, "raw_payload", raw_payload)
        _assign_if_exists(existing, "raw", raw_payload)

        return {
            "status": "updated",
            "id": getattr(existing, "id", None),
            "title": title,
            "quote_ready": quote_ready,
            "intelligence_score": intelligence_score,
        }

    created = Opportunity()

    _assign_if_exists(created, "title", title)
    _assign_if_exists(created, "description", description)
    _assign_if_exists(created, "external_url", external_url)
    _assign_if_exists(created, "buyer", buyer_name)
    _assign_if_exists(created, "buyer_name", buyer_name)
    _assign_if_exists(created, "reference_number", reference_number)
    _assign_if_exists(created, "province", province)
    _assign_if_exists(created, "category", category)
    _assign_if_exists(created, "published_date", published_date)
    _assign_if_exists(created, "closing_date", closing_date)
    _assign_if_exists(created, "is_supply", is_supply)
    _assign_if_exists(created, "intelligence_score", intelligence_score)
    _assign_if_exists(created, "quote_ready", quote_ready)
    _assign_if_exists(created, "source_name", source_name)
    _assign_if_exists(created, "source_type", source_type)
    _assign_if_exists(created, "source_url", source_url)
    _assign_if_exists(created, "is_national", is_national)
    _assign_if_exists(created, "raw_payload", raw_payload)
    _assign_if_exists(created, "raw", raw_payload)

    db.add(created)

    return {
        "status": "created",
        "title": title,
        "quote_ready": quote_ready,
        "intelligence_score": intelligence_score,
    }


def persist_harvested_opportunities(db: Session, harvested_results: Iterable[Any]) -> dict:
    """
    Persist a batch of harvested opportunities into the database safely.

    Returns a summary like:
    {
        "created": 10,
        "updated": 4,
        "skipped": 2,
        "errors": 0,
        "quote_ready_count": 7,
        "results": [...]
    }
    """
    created = 0
    updated = 0
    skipped = 0
    errors = 0
    quote_ready_count = 0
    results = []

    for harvested in harvested_results:
        try:
            outcome = _upsert_single_opportunity(db, harvested)
            results.append(outcome)

            status = outcome.get("status")
            if status == "created":
                created += 1
            elif status == "updated":
                updated += 1
            elif status == "skipped":
                skipped += 1

            if outcome.get("quote_ready"):
                quote_ready_count += 1

        except Exception as exc:
            errors += 1
            logger.exception("Failed to persist harvested opportunity: %s", exc)
            db.rollback()
            results.append(
                {
                    "status": "error",
                    "error": str(exc),
                }
            )

    db.commit()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "quote_ready_count": quote_ready_count,
        "results": results,
    }
