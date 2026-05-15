"""
LMCP V50.8.4 API - eTenders Status Enumerator

Drop-in:
    app/api/etenders_status_enumerator_v50_8_4_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_status_enumerator_v50_8_4_service import (
    enumerate_etenders_statuses,
    get_v50_8_4_status,
)

router = APIRouter(prefix="/v50-8-4-etenders-status", tags=["V50.8.4 eTenders Status Enumerator"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_8_4_status()


@router.post("/enumerate")
def enumerate_statuses(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return enumerate_etenders_statuses(payload or {})
