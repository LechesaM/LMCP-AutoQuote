"""
LMCP V50.9 API - eTenders Document Auto-Download Engine
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_document_download_v50_9_service import (
    download_etenders_document,
    get_v50_9_status,
)

router = APIRouter(
    prefix="/v50-9-document-download",
    tags=["V50.9 eTenders Document Download"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_status()


@router.post("/download")
def download(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return download_etenders_document(payload or {})
