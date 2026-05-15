"""Step 16 — Portal Health Radar Live Events.

Safe helper functions for publishing portal health events through the existing
websocket broker.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.websocket_broker import publish_dashboard_event


async def publish_portal_health_update(
    source_name: str,
    url: str = "",
    status: str = "healthy",
    response_time_ms: Optional[int] = None,
    failure_count: int = 0,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_health_update",
        payload={
            "source_name": source_name,
            "url": url,
            "status": status,
            "response_time_ms": response_time_ms,
            "failure_count": failure_count,
            "message": message,
            "metadata": metadata or {},
        },
        source="portal-radar",
    )


async def publish_portal_blocked(
    source_name: str,
    url: str = "",
    message: str = "Portal access appears blocked.",
    failure_count: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_blocked",
        payload={
            "source_name": source_name,
            "url": url,
            "status": "blocked",
            "message": message,
            "failure_count": failure_count,
            "metadata": metadata or {},
        },
        source="portal-radar",
    )


async def publish_portal_broken(
    source_name: str,
    url: str = "",
    message: str = "Portal parser or fetch failed.",
    failure_count: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_broken",
        payload={
            "source_name": source_name,
            "url": url,
            "status": "broken",
            "message": message,
            "failure_count": failure_count,
            "metadata": metadata or {},
        },
        source="portal-radar",
    )


async def publish_portal_slow(
    source_name: str,
    url: str = "",
    response_time_ms: Optional[int] = None,
    message: str = "Portal is responding slowly.",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_slow",
        payload={
            "source_name": source_name,
            "url": url,
            "status": "slow",
            "response_time_ms": response_time_ms,
            "message": message,
            "metadata": metadata or {},
        },
        source="portal-radar",
    )


async def publish_portal_recovered(
    source_name: str,
    url: str = "",
    message: str = "Portal recovered.",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_recovered",
        payload={
            "source_name": source_name,
            "url": url,
            "status": "healthy",
            "message": message,
            "metadata": metadata or {},
        },
        source="portal-radar",
    )


async def publish_portal_isolated(
    source_name: str,
    url: str = "",
    message: str = "Portal isolated to protect harvest cycle.",
    failure_count: int = 0,
    retry_after_seconds: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_isolated",
        payload={
            "source_name": source_name,
            "url": url,
            "status": "blocked",
            "message": message,
            "failure_count": failure_count,
            "retry_after_seconds": retry_after_seconds,
            "metadata": metadata or {},
        },
        source="portal-radar",
    )


async def publish_portal_retry_scheduled(
    source_name: str,
    url: str = "",
    retry_after_seconds: int = 300,
    message: str = "Portal retry scheduled.",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_retry_scheduled",
        payload={
            "source_name": source_name,
            "url": url,
            "status": "recovering",
            "message": message,
            "retry_after_seconds": retry_after_seconds,
            "metadata": metadata or {},
        },
        source="portal-radar",
    )
