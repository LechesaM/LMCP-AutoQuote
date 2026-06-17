"""Step 14 — Quote Engine Live Events

Safe helper functions that publish quote lifecycle websocket events through
the existing app.services.websocket_broker module.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.websocket_broker import publish_dashboard_event


async def publish_quote_started(
    buyer_rfq_number: str,
    title: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="quote_started",
        payload={
            "buyer_rfq_number": buyer_rfq_number,
            "title": title,
            "metadata": metadata or {},
        },
        source="quote-engine",
    )


async def publish_pricing_schedule_mapped(
    buyer_rfq_number: str,
    mapped_items: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="pricing_schedule_mapped",
        payload={
            "buyer_rfq_number": buyer_rfq_number,
            "mapped_items": mapped_items,
            "metadata": metadata or {},
        },
        source="quote-engine",
    )


async def publish_quote_pack_generated(
    buyer_rfq_number: str,
    quote_number: str = "",
    pdf_path: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="quote_pack_generated",
        payload={
            "buyer_rfq_number": buyer_rfq_number,
            "quote_number": quote_number,
            "pdf_path": pdf_path,
            "metadata": metadata or {},
        },
        source="quote-engine",
    )


async def publish_quote_submission_dispatched(
    buyer_rfq_number: str,
    quote_number: str = "",
    submission_channel: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="quote_submission_dispatched",
        payload={
            "buyer_rfq_number": buyer_rfq_number,
            "quote_number": quote_number,
            "submission_channel": submission_channel,
            "metadata": metadata or {},
        },
        source="quote-engine",
    )


async def publish_quote_failed(
    buyer_rfq_number: str,
    stage: str,
    error_message: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    return await publish_dashboard_event(
        event_type="quote_failed",
        payload={
            "buyer_rfq_number": buyer_rfq_number,
            "stage": stage,
            "error_message": error_message,
            "metadata": metadata or {},
        },
        source="quote-engine",
    )

