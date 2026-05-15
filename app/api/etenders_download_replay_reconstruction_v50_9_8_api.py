"""
LMCP V50.9.8 API - Download Replay Reconstruction
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_download_replay_reconstruction_v50_9_8_service import (
    get_v50_9_8_status,
    reconstruct_download_replay,
    replay_one,
)

router = APIRouter(
    prefix="/v50-9-8-download-replay-reconstruction",
    tags=["V50.9.8 eTenders Download Replay Reconstruction"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_8_status()


@router.post("/reconstruct")
def reconstruct(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return reconstruct_download_replay(payload or {})


@router.post("/replay")
def replay(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return replay_one(payload or {})
