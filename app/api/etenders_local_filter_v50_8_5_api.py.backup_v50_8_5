"""
LMCP V50.8.5 API - eTenders Local Structured Filter Engine

Drop-in:
    app/api/etenders_local_filter_v50_8_5_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_local_filter_v50_8_5_service import (
    filter_etenders_locally,
    get_v50_8_5_status,
)

router = APIRouter(prefix="/v50-8-5-etenders-local-filter", tags=["V50.8.5 eTenders Local Filter"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_8_5_status()


@router.post("/filter")
def filter_local(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return filter_etenders_locally(payload or {})
