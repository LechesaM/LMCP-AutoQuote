"""Step 17 — Alerts & Notifications Live Events.

Helper functions for publishing operational alert events through the existing
websocket broker.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.websocket_broker import publish_dashboard_event


async def publish_alert(
    title: str,
    message: str,
    severity: str = "info",
    alert_type: str = "alert",
    recommended_action: str = "Review dashboard",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type=alert_type,
        payload={
            "title": title,
            "message": message,
            "severity": severity,
            "recommended_action": recommended_action,
            "metadata": metadata or {},
        },
        source="alert-engine",
    )


async def publish_critical_alert(
    title: str,
    message: str,
    recommended_action: str = "Immediate operator review required",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_alert(
        title=title,
        message=message,
        severity="critical",
        alert_type="critical_alert",
        recommended_action=recommended_action,
        metadata=metadata,
    )


async def publish_high_value_tender_alert(
    buyer_rfq_number: str,
    title: str,
    estimated_profit: float = 0.0,
    recommended_action: str = "Review and prioritize quotation",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="high_value_tender_alert",
        payload={
            "title": "High-value tender found",
            "message": title,
            "severity": "high",
            "buyer_rfq_number": buyer_rfq_number,
            "estimated_profit": estimated_profit,
            "recommended_action": recommended_action,
            "metadata": metadata or {},
        },
        source="alert-engine",
    )


async def publish_failed_submission_alert(
    buyer_rfq_number: str,
    quote_number: str = "",
    error_message: str = "",
    recommended_action: str = "Retry submission or inspect failure logs",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="failed_submission_alert",
        payload={
            "title": "Submission failed",
            "message": error_message or "A submission failed.",
            "severity": "critical",
            "buyer_rfq_number": buyer_rfq_number,
            "quote_number": quote_number,
            "recommended_action": recommended_action,
            "metadata": metadata or {},
        },
        source="alert-engine",
    )


async def publish_portal_blocked_alert(
    source_name: str,
    url: str = "",
    message: str = "Portal appears blocked.",
    recommended_action: str = "Pause or isolate portal and retry later",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="portal_blocked_alert",
        payload={
            "title": "Portal blocked",
            "message": message,
            "severity": "high",
            "source_name": source_name,
            "url": url,
            "recommended_action": recommended_action,
            "metadata": metadata or {},
        },
        source="alert-engine",
    )


async def publish_system_stopped_alert(
    message: str = "Autonomous engine has stopped.",
    recommended_action: str = "Check system control and restart if safe",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="system_stopped_alert",
        payload={
            "title": "System stopped",
            "message": message,
            "severity": "critical",
            "recommended_action": recommended_action,
            "metadata": metadata or {},
        },
        source="alert-engine",
    )


async def publish_quote_failure_alert(
    buyer_rfq_number: str,
    stage: str = "",
    error_message: str = "",
    recommended_action: str = "Review quote generation logs",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="quote_failure_alert",
        payload={
            "title": "Quote generation failed",
            "message": error_message or "Quote generation failed.",
            "severity": "high",
            "buyer_rfq_number": buyer_rfq_number,
            "stage": stage,
            "recommended_action": recommended_action,
            "metadata": metadata or {},
        },
        source="alert-engine",
    )


async def publish_profit_alert(
    buyer_rfq_number: str,
    title: str,
    estimated_profit: float,
    severity: str = "high",
    recommended_action: str = "Prioritize this opportunity",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="profit_alert",
        payload={
            "title": "Profit opportunity alert",
            "message": title,
            "severity": severity,
            "buyer_rfq_number": buyer_rfq_number,
            "estimated_profit": estimated_profit,
            "recommended_action": recommended_action,
            "metadata": metadata or {},
        },
        source="alert-engine",
    )
