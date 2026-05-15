from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_temperature(value: Optional[str]) -> str:
    if not value:
        return "cold"
    value = str(value).strip().lower()
    if value in {"hot", "warm", "cold"}:
        return value
    return "cold"


def _temperature_interval_minutes(temperature: str) -> int:
    temperature = _normalize_temperature(temperature)
    if temperature == "hot":
        return 10
    if temperature == "warm":
        return 30
    return 120


def _parse_last_crawled_at(value: Any) -> Optional[datetime]:
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    text = str(value).strip()
    if not text:
        return None

    # Handle common ISO forms, including trailing Z
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_due(last_crawled_at: Optional[datetime], interval_minutes: int, now: datetime) -> bool:
    if last_crawled_at is None:
        return True
    return last_crawled_at <= now - timedelta(minutes=interval_minutes)


def build_adaptive_crawl_schedule(portals: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Returns a structured crawl schedule based on portal temperature.
    Hot portals: every 10 minutes
    Warm portals: every 30 minutes
    Cold portals: every 120 minutes
    """
    portals = portals or []
    now = _utc_now()

    schedule_items: List[Dict[str, Any]] = []

    for portal in portals:
        slug = portal.get("portal_slug") or portal.get("slug") or portal.get("name") or "unknown-portal"
        name = portal.get("portal_name") or portal.get("name") or slug
        temperature = _normalize_temperature(portal.get("temperature"))
        priority_score = portal.get("priority_score", 0)
        interval_minutes = _temperature_interval_minutes(temperature)
        last_crawled_at = _parse_last_crawled_at(
            portal.get("last_crawled_at") or portal.get("last_crawl_at")
        )

        next_due_at = now if last_crawled_at is None else last_crawled_at + timedelta(minutes=interval_minutes)
        due = _is_due(last_crawled_at, interval_minutes, now)

        schedule_items.append(
            {
                "portal_slug": slug,
                "portal_name": name,
                "temperature": temperature,
                "priority_score": priority_score,
                "crawl_interval_minutes": interval_minutes,
                "last_crawled_at": last_crawled_at.isoformat() if last_crawled_at else None,
                "next_due_at": next_due_at.isoformat(),
                "due_now": due,
            }
        )

    schedule_items.sort(
        key=lambda item: (
            not item["due_now"],
            {"hot": 0, "warm": 1, "cold": 2}.get(item["temperature"], 3),
            -(item.get("priority_score") or 0),
            item["portal_slug"],
        )
    )

    return {
        "generated_at": now.isoformat(),
        "total_portals": len(schedule_items),
        "due_now_count": sum(1 for item in schedule_items if item["due_now"]),
        "schedule": schedule_items,
    }


def get_due_portals_for_crawl(
    portals: Optional[List[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Returns only portals that are due for crawl right now.
    """
    result = build_adaptive_crawl_schedule(portals=portals)
    due_items = [item for item in result["schedule"] if item["due_now"]]

    if limit is not None:
        try:
            limit = int(limit)
            if limit >= 0:
                due_items = due_items[:limit]
        except Exception:
            pass

    return due_items
