from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import math


# ============================================================
# Procurement Heatmap Engine
# ------------------------------------------------------------
# Purpose:
# Turn portal health + harvesting intelligence into a ranked
# crawl plan so the harvester prioritizes the most productive
# government / SOE portals first.
#
# This module is intentionally defensive:
# - Works even if some radar fields are missing
# - Works even if no database metrics exist yet
# - Produces stable output for API + dashboard + harvester
# ============================================================


UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return _clamp((value / max_value) * 100.0, 0.0, 100.0)


def _hours_since(iso_dt: Optional[str]) -> float:
    if not iso_dt:
        return 9999.0
    try:
        dt = datetime.fromisoformat(iso_dt.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta = _utcnow() - dt.astimezone(UTC)
        return max(delta.total_seconds() / 3600.0, 0.0)
    except Exception:
        return 9999.0


def _freshness_score(last_success_at: Optional[str]) -> float:
    """
    Higher score for more recently successful portals.
    """
    hours = _hours_since(last_success_at)

    if hours <= 1:
        return 100.0
    if hours <= 3:
        return 90.0
    if hours <= 6:
        return 80.0
    if hours <= 12:
        return 70.0
    if hours <= 24:
        return 55.0
    if hours <= 48:
        return 35.0
    if hours <= 72:
        return 20.0
    return 5.0


def _latency_score(avg_latency_seconds: float) -> float:
    """
    Lower latency => higher score
    """
    latency = max(avg_latency_seconds, 0.0)

    if latency <= 1:
        return 100.0
    if latency <= 2:
        return 90.0
    if latency <= 4:
        return 75.0
    if latency <= 6:
        return 60.0
    if latency <= 10:
        return 40.0
    if latency <= 15:
        return 20.0
    return 5.0


def _health_score(health_status: str) -> float:
    status = (health_status or "").strip().lower()

    if status == "healthy":
        return 100.0
    if status == "slow":
        return 65.0
    if status == "degraded":
        return 45.0
    if status == "blocked":
        return 15.0
    if status == "broken":
        return 5.0
    return 25.0


def _portal_temperature(priority_score: float) -> str:
    if priority_score >= 80:
        return "hot"
    if priority_score >= 60:
        return "warm"
    if priority_score >= 35:
        return "cool"
    return "cold"


def _recommended_crawl_interval_minutes(priority_score: float) -> int:
    if priority_score >= 90:
        return 10
    if priority_score >= 80:
        return 15
    if priority_score >= 70:
        return 20
    if priority_score >= 60:
        return 30
    if priority_score >= 45:
        return 45
    if priority_score >= 30:
        return 60
    return 120


@dataclass
class PortalHeatmapRow:
    portal_name: str
    portal_slug: str
    base_url: str
    category: str
    region: str
    health_status: str
    avg_latency_seconds: float
    recent_hits: int
    total_hits: int
    recent_failures: int
    success_rate: float
    last_success_at: Optional[str]
    health_score: float
    speed_score: float
    activity_score: float
    freshness_score: float
    reliability_score: float
    priority_score: float
    temperature: str
    recommended_crawl_interval_minutes: int
    recommended_priority_rank: int = 0


# ------------------------------------------------------------
# Optional dependency hooks
# These imports are wrapped so this file does not break startup
# if one related service is temporarily missing.
# ------------------------------------------------------------
def _load_portal_registry() -> List[Dict[str, Any]]:
    """
    Try to load registry from app.services.portal_registry.
    Fallback to empty list if unavailable.
    """
    try:
        from app.services.portal_registry import get_portal_registry  # type: ignore

        data = get_portal_registry()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _load_portal_radar_report() -> Dict[str, Any]:
    """
    Try to load live radar report from existing radar service.
    Fallback to empty report if unavailable.
    """
    try:
        from app.services.portal_radar_service import build_portal_radar_report  # type: ignore

        report = build_portal_radar_report()
        if isinstance(report, dict):
            return report
        return {}
    except Exception:
        return {}


def _extract_radar_rows(radar_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Supports several possible structures so it survives refactors.
    """
    if not radar_report:
        return []

    for key in ("portals", "results", "radar", "items", "portal_results"):
        value = radar_report.get(key)
        if isinstance(value, list):
            return value

    return []


def _merge_registry_and_radar(
    registry_rows: List[Dict[str, Any]],
    radar_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge registry portal definitions with live radar metrics.
    """
    merged: Dict[str, Dict[str, Any]] = {}

    for row in registry_rows:
        slug = (
            row.get("slug")
            or row.get("portal_slug")
            or row.get("name", "")
        )
        if not slug:
            continue
        merged[str(slug)] = dict(row)

    for row in radar_rows:
        slug = (
            row.get("slug")
            or row.get("portal_slug")
            or row.get("name", "")
        )
        if not slug:
            continue

        slug = str(slug)

        if slug not in merged:
            merged[slug] = {}

        merged[slug].update(row)

    return list(merged.values())


def _build_heatmap_rows(portal_rows: List[Dict[str, Any]]) -> List[PortalHeatmapRow]:
    """
    Calculate weighted priority per portal.
    """
    max_recent_hits = max([_safe_int(x.get("recent_hits", 0)) for x in portal_rows] or [1])
    max_total_hits = max([_safe_int(x.get("total_hits", 0)) for x in portal_rows] or [1])

    heatmap_rows: List[PortalHeatmapRow] = []

    for row in portal_rows:
        portal_name = row.get("portal_name") or row.get("name") or "Unknown Portal"
        portal_slug = row.get("portal_slug") or row.get("slug") or portal_name.lower().replace(" ", "-")
        base_url = row.get("base_url") or row.get("url") or ""
        category = row.get("category") or row.get("portal_type") or "government"
        region = row.get("region") or row.get("province") or "national"
        health_status = row.get("health_status") or row.get("status") or "unknown"

        avg_latency_seconds = _safe_float(
            row.get("avg_latency_seconds", row.get("latency_seconds", row.get("response_time_seconds", 0.0))),
            0.0,
        )
        recent_hits = _safe_int(row.get("recent_hits", row.get("opportunities_last_24h", row.get("hits_24h", 0))), 0)
        total_hits = _safe_int(row.get("total_hits", row.get("all_time_hits", 0)), 0)
        recent_failures = _safe_int(row.get("recent_failures", row.get("failures_24h", 0)), 0)
        success_rate = _safe_float(row.get("success_rate", 0.0), 0.0)
        last_success_at = row.get("last_success_at") or row.get("last_seen_at") or row.get("last_active_at")

        # Core component scores
        health_score = _health_score(health_status)
        speed_score = _latency_score(avg_latency_seconds)

        # Activity score combines recent + historic volume, weighted to recent
        recent_activity_norm = _normalize(recent_hits, max_recent_hits)
        total_activity_norm = _normalize(total_hits, max_total_hits)
        activity_score = _clamp((recent_activity_norm * 0.75) + (total_activity_norm * 0.25))

        freshness_score = _freshness_score(last_success_at)

        # Reliability: success rate minus penalties for recent failures
        failure_penalty = min(recent_failures * 7.5, 40.0)
        reliability_score = _clamp((success_rate * 100.0) - failure_penalty)

        # Final weighted score
        priority_score = _clamp(
            (health_score * 0.28)
            + (speed_score * 0.18)
            + (activity_score * 0.30)
            + (freshness_score * 0.14)
            + (reliability_score * 0.10)
        )

        temperature = _portal_temperature(priority_score)
        interval = _recommended_crawl_interval_minutes(priority_score)

        heatmap_rows.append(
            PortalHeatmapRow(
                portal_name=portal_name,
                portal_slug=portal_slug,
                base_url=base_url,
                category=category,
                region=region,
                health_status=health_status,
                avg_latency_seconds=round(avg_latency_seconds, 2),
                recent_hits=recent_hits,
                total_hits=total_hits,
                recent_failures=recent_failures,
                success_rate=round(success_rate, 4),
                last_success_at=last_success_at,
                health_score=round(health_score, 2),
                speed_score=round(speed_score, 2),
                activity_score=round(activity_score, 2),
                freshness_score=round(freshness_score, 2),
                reliability_score=round(reliability_score, 2),
                priority_score=round(priority_score, 2),
                temperature=temperature,
                recommended_crawl_interval_minutes=interval,
            )
        )

    heatmap_rows.sort(key=lambda x: (-x.priority_score, x.avg_latency_seconds, -x.recent_hits))

    for idx, row in enumerate(heatmap_rows, start=1):
        row.recommended_priority_rank = idx

    return heatmap_rows


def build_procurement_heatmap() -> Dict[str, Any]:
    """
    Public entrypoint for API + dashboard.
    """
    registry_rows = _load_portal_registry()
    radar_report = _load_portal_radar_report()
    radar_rows = _extract_radar_rows(radar_report)

    merged_rows = _merge_registry_and_radar(registry_rows, radar_rows)
    heatmap_rows = _build_heatmap_rows(merged_rows)

    hot = [r for r in heatmap_rows if r.temperature == "hot"]
    warm = [r for r in heatmap_rows if r.temperature == "warm"]
    cool = [r for r in heatmap_rows if r.temperature == "cool"]
    cold = [r for r in heatmap_rows if r.temperature == "cold"]

    recommended_crawl_order = [
        {
            "rank": row.recommended_priority_rank,
            "portal_slug": row.portal_slug,
            "portal_name": row.portal_name,
            "priority_score": row.priority_score,
            "temperature": row.temperature,
            "crawl_every_minutes": row.recommended_crawl_interval_minutes,
        }
        for row in heatmap_rows
    ]

    summary = {
        "generated_at": _utcnow().isoformat(),
        "total_portals": len(heatmap_rows),
        "hot_portals": len(hot),
        "warm_portals": len(warm),
        "cool_portals": len(cool),
        "cold_portals": len(cold),
        "average_priority_score": round(
            sum(r.priority_score for r in heatmap_rows) / len(heatmap_rows), 2
        ) if heatmap_rows else 0.0,
    }

    return {
        "summary": summary,
        "recommended_crawl_order": recommended_crawl_order,
        "heatmap": [asdict(row) for row in heatmap_rows],
        "top_10": [asdict(row) for row in heatmap_rows[:10]],
    }


def get_priority_portal_slugs(limit: Optional[int] = None) -> List[str]:
    """
    Harvester helper:
    returns portal slugs in best-first order.
    """
    heatmap = build_procurement_heatmap()
    rows = heatmap.get("recommended_crawl_order", [])
    slugs = [row["portal_slug"] for row in rows if row.get("portal_slug")]

    if limit is not None:
        return slugs[:limit]
    return slugs


def get_priority_portals(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Harvester helper:
    returns full heatmap portal rows in best-first order.
    """
    heatmap = build_procurement_heatmap()
    rows = heatmap.get("heatmap", [])
    if limit is not None:
        return rows[:limit]
    return rows


def get_procurement_heatmap():
    """
    Temporary fallback heatmap generator
    """
    return {
        "status": "ok",
        "heatmap": [],
        "message": "Heatmap service active (fallback mode)"
    }
