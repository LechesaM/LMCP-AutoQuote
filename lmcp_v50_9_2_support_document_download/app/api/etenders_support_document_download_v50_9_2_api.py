"""
LMCP V50.9.2 API - SupportDocument Direct Download Probe
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_support_document_download_v50_9_2_service import (
    download_support_document,
    get_v50_9_2_status,
    probe_support_document,
)

router = APIRouter(
    prefix="/v50-9-2-support-document-download",
    tags=["V50.9.2 eTenders SupportDocument Download"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_2_status()


@router.post("/probe")
def probe(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return probe_support_document(payload or {})


@router.post("/download")
def download(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return download_support_document(payload or {})
