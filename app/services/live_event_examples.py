"""Examples of how to publish LMCP live websocket events from your existing backend.

Import these patterns inside your real services after key actions complete.
"""

from __future__ import annotations

from typing import Any, Dict

from app.services.websocket_broker import (
    publish_autonomous_status_event,
    publish_opportunity_event,
    publish_pipeline_event,
    publish_submission_event,
)


async def on_new_opportunity(opportunity: Dict[str, Any]) -> None:
    await publish_opportunity_event(opportunity)


async def on_submission_update(result: Dict[str, Any]) -> None:
    await publish_submission_event(result)


async def on_autonomous_status_change(status: Dict[str, Any]) -> None:
    await publish_autonomous_status_event(status)


async def on_pipeline_snapshot(snapshot: Dict[str, Any]) -> None:
    await publish_pipeline_event(snapshot)

