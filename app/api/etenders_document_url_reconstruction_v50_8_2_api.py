"""
LMCP V50.8.2 API - eTenders Document URL Reconstruction

Drop-in:
    app/api/etenders_document_url_reconstruction_v50_8_2_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_document_url_reconstruction_v50_8_2_service import (
    get_v50_8_2_status,
    reconstruct_etenders_document_urls,
)

router = APIRouter(prefix="/v50-8-2-etenders-docurl", tags=["V50.8.2 eTenders Document URL Reconstruction"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_8_2_status()


@router.post("/reconstruct")
def reconstruct(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return reconstruct_etenders_document_urls(payload or {})
