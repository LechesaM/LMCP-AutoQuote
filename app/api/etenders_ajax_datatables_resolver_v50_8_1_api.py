"""
LMCP V50.8.1 API - eTenders Ajax/DataTables Resolver

Drop-in:
    app/api/etenders_ajax_datatables_resolver_v50_8_1_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_ajax_datatables_resolver_v50_8_1_service import (
    get_v50_8_1_status,
    resolve_etenders_ajax_datatables,
)

router = APIRouter(prefix="/v50-8-1-etenders-ajax", tags=["V50.8.1 eTenders Ajax Resolver"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_8_1_status()


@router.post("/resolve")
def resolve(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return resolve_etenders_ajax_datatables(payload or {})
