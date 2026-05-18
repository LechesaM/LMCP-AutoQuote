"""
LMCP V50.9.3 API - Browser Session Download Interceptor
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_browser_download_interceptor_v50_9_3_service import (
    capture_browser_download,
    get_v50_9_3_status,
)

router = APIRouter(
    prefix="/v50-9-3-browser-download-interceptor",
    tags=["V50.9.3 Browser Download Interceptor"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_3_status()


@router.post("/capture")
def capture(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return capture_browser_download(payload or {})
