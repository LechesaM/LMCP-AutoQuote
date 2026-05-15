"""
LMCP V50.8.6 API - eTenders Local Structured Filter + Deduplication

This can replace:
    app/api/etenders_local_filter_v50_8_5_api.py

Route is kept the same:
    /v50-8-5-etenders-local-filter

So existing frontend/tests will continue working, while service_version reports V50.8.6.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_local_filter_v50_8_5_service import (
    filter_etenders_locally,
    get_v50_8_5_status,
)

router = APIRouter(
    prefix="/v50-8-5-etenders-local-filter",
    tags=["V50.8.6 eTenders Local Filter Dedup"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_8_5_status()


@router.post("/filter")
def filter_local(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return filter_etenders_locally(payload or {})
