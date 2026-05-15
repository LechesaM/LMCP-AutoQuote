"""
LMCP V50.9.1 API - TenderDetails JSON Parser + Download Bridge
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_tenderdetails_json_v50_9_1_service import (
    download_from_tenderdetails_json,
    get_v50_9_1_status,
    inspect_tenderdetails_json,
)

router = APIRouter(
    prefix="/v50-9-1-tenderdetails-json",
    tags=["V50.9.1 eTenders TenderDetails JSON"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_1_status()


@router.post("/inspect")
def inspect(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return inspect_tenderdetails_json(payload or {})


@router.post("/download")
def download(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return download_from_tenderdetails_json(payload or {})
