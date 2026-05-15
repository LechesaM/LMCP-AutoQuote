"""
LMCP V50.7 API - eTenders Real Detail Navigation

Drop-in file:
    app/api/etenders_real_detail_navigation_v50_7_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_real_detail_navigation_v50_7_service import (
    analyse_etenders_detail_navigation,
    get_v50_7_status,
)

router = APIRouter(prefix="/v50-7-etenders-navigation", tags=["V50.7 eTenders Navigation"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_7_status()


@router.post("/analyse")
def analyse(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return analyse_etenders_detail_navigation(payload or {})
