"""
LMCP V50.9.9 API - Runtime Browser Download Interceptor
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_runtime_download_interceptor_v50_9_9 import (
    capture_runtime_downloads,
    get_v50_9_9_status,
)

router = APIRouter(
    prefix="/v50-9-9-runtime-download-interceptor",
    tags=["V50.9.9 Runtime Download Interceptor"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_9_status()


@router.post("/capture")
def capture(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return capture_runtime_downloads(payload or {})
