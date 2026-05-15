"""
LMCP V50.9.6 API - Hidden API Discovery + DownloadSpec Replay
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_hidden_api_discovery_v50_9_6_service import (
    discover_hidden_api,
    get_v50_9_6_status,
    replay_download,
)

router = APIRouter(
    prefix="/v50-9-6-hidden-api-discovery",
    tags=["V50.9.6 eTenders Hidden API Discovery"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_6_status()


@router.post("/discover")
def discover(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return discover_hidden_api(payload or {})


@router.post("/replay-download")
def replay(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return replay_download(payload or {})
