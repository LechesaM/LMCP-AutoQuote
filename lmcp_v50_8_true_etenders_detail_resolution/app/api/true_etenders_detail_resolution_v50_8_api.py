"""
LMCP V50.8 API - True eTenders Detail Resolution

Drop-in:
    app/api/true_etenders_detail_resolution_v50_8_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.true_etenders_detail_resolution_v50_8_service import (
    get_v50_8_status,
    resolve_true_etenders_detail,
)

router = APIRouter(prefix="/v50-8-etenders-detail", tags=["V50.8 eTenders Detail Resolution"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_8_status()


@router.post("/resolve")
def resolve(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return resolve_true_etenders_detail(payload or {})
