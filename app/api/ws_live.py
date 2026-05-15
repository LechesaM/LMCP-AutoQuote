from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_broker import (
    publish_dashboard_event,
    websocket_broker,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


def build_initial_snapshot() -> Dict[str, Any]:
    """Return a lightweight initial payload for newly connected dashboard clients.

    Keep this dependency-light so it can be added without breaking your current system.
    You can enrich it later by importing your real dashboard/services modules.
    """
    return {
        "status": "ok",
        "message": "LMCP websocket live feed connected",
        "connected_clients": len(websocket_broker.active_connections),
    }


async def _client_receive_loop(websocket: WebSocket) -> None:
    while True:
        data = await websocket.receive_json()
        action = str(data.get("action") or "").strip().lower()

        if action == "ping":
            await websocket.send_json(
                {
                    "type": "pong",
                    "timestamp": build_initial_snapshot().get("message"),
                    "payload": {"echo": data},
                }
            )
        elif action == "refresh":
            await publish_dashboard_event(
                event_type="manual_refresh_request",
                payload={"requested_by": "websocket_client", "data": data},
                source="ws-client",
            )
        else:
            await websocket.send_json(
                {
                    "type": "ack",
                    "payload": {
                        "message": "Message received",
                        "action": action or "none",
                    },
                }
            )


async def _heartbeat_loop(websocket: WebSocket, interval_seconds: int = 15) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        await websocket.send_json(
            {
                "type": "heartbeat",
                "payload": {
                    "connected_clients": len(websocket_broker.active_connections),
                    "interval_seconds": interval_seconds,
                },
            }
        )




@router.get("/ws/status")
async def websocket_status() -> dict:
    return {
        "status": "ok",
        "service": "LMCP_WEBSOCKET_LAYER",
        "connected_clients": len(websocket_broker.active_connections),
        "paths": [
            "/ws",
            "/ws/live",
            "/ws/dashboard",
            "/ws/tenders",
        ],
        "heartbeat_enabled": True,
        "reconnect_supported": True,
    }


@router.websocket("/ws")
async def websocket_root(websocket: WebSocket) -> None:
    await _handle_dashboard_socket(websocket)


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await _handle_dashboard_socket(websocket)


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket) -> None:
    await _handle_dashboard_socket(websocket)


@router.websocket("/ws/tenders")
async def websocket_tenders(websocket: WebSocket) -> None:
    await _handle_dashboard_socket(websocket)


async def _handle_dashboard_socket(websocket: WebSocket) -> None:
    await websocket_broker.connect(websocket)
    try:
        await websocket_broker.send_system_snapshot(websocket, build_initial_snapshot())

        receiver = asyncio.create_task(_client_receive_loop(websocket))
        heartbeat = asyncio.create_task(_heartbeat_loop(websocket))

        done, pending = await asyncio.wait(
            {receiver, heartbeat},
            return_when=asyncio.FIRST_EXCEPTION,
        )

        for task in pending:
            task.cancel()

        for task in done:
            exc = task.exception()
            if exc:
                raise exc

    except WebSocketDisconnect:
        logger.info("Dashboard websocket disconnected")
    except Exception:
        logger.exception("Unhandled websocket error")
    finally:
        await websocket_broker.disconnect(websocket)

