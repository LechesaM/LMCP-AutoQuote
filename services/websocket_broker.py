from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WebSocketConnectionManager:
    """In-memory websocket broker for LMCP live dashboard events."""

    active_connections: Set[WebSocket] = field(default_factory=set)
    connection_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self.connection_lock:
            self.active_connections.add(websocket)
        logger.info("WebSocket connected. Total clients=%s", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.connection_lock:
            self.active_connections.discard(websocket)
        logger.info("WebSocket disconnected. Total clients=%s", len(self.active_connections))

    async def broadcast(self, payload: Dict[str, Any]) -> int:
        """Broadcast JSON payload to all connected clients.

        Returns number of successful sends.
        """
        async with self.connection_lock:
            connections: List[WebSocket] = list(self.active_connections)

        if not connections:
            return 0

        successful = 0
        stale: List[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(payload)
                successful += 1
            except Exception:
                logger.exception("Failed sending websocket payload; dropping stale client")
                stale.append(websocket)

        if stale:
            async with self.connection_lock:
                for websocket in stale:
                    self.active_connections.discard(websocket)

        return successful

    async def send_system_snapshot(self, websocket: WebSocket, snapshot: Dict[str, Any]) -> None:
        await websocket.send_json(
            {
                "type": "system_snapshot",
                "timestamp": utc_now_iso(),
                "payload": snapshot,
            }
        )

    async def heartbeat(self) -> int:
        return await self.broadcast(
            {
                "type": "heartbeat",
                "timestamp": utc_now_iso(),
                "payload": {"connected_clients": len(self.active_connections)},
            }
        )


websocket_broker = WebSocketConnectionManager()


async def publish_dashboard_event(
    event_type: str,
    payload: Dict[str, Any] | None = None,
    source: str = "lmcp-backend",
) -> int:
    message = {
        "type": event_type,
        "timestamp": utc_now_iso(),
        "source": source,
        "payload": payload or {},
    }
    return await websocket_broker.broadcast(message)


async def publish_opportunity_event(opportunity: Dict[str, Any]) -> int:
    return await publish_dashboard_event("opportunity_update", opportunity, source="opportunities")


async def publish_submission_event(submission: Dict[str, Any]) -> int:
    return await publish_dashboard_event("submission_update", submission, source="submission-pipeline")


async def publish_autonomous_status_event(status: Dict[str, Any]) -> int:
    return await publish_dashboard_event("autonomous_status", status, source="autonomous-engine")


async def publish_pipeline_event(snapshot: Dict[str, Any]) -> int:
    return await publish_dashboard_event("pipeline_update", snapshot, source="pipeline")


def serialize_for_log(payload: Dict[str, Any]) -> str:
    try:
        return json.dumps(payload, default=str)
    except Exception:
        return str(payload)

