from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.services.proof_center_service import (
    get_proof_center,
    get_proof_record,
    resolve_download_path,
    scan_proof_center,
)

router = APIRouter(prefix="/proof-center", tags=["proof-center"])


@router.get("/health")
def proof_center_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "production-proof-center",
        "available_endpoints": {
            "scan": "/proof-center/scan",
            "list": "/proof-center",
            "record": "/proof-center/{record_id}",
            "download_proof": "/proof-center/{record_id}/download-proof",
            "download_screenshot": "/proof-center/{record_id}/download-screenshot?screenshot_index=0",
        },
    }


@router.post("/scan")
def proof_center_scan() -> Dict[str, Any]:
    return scan_proof_center()


@router.get("")
def proof_center_list(
    limit: int = Query(default=100, ge=1, le=500),
    submitted_only: bool = False,
    q: str = "",
) -> Dict[str, Any]:
    return get_proof_center(limit=limit, submitted_only=submitted_only, q=q)


@router.get("/")
def proof_center_list_slash(
    limit: int = Query(default=100, ge=1, le=500),
    submitted_only: bool = False,
    q: str = "",
) -> Dict[str, Any]:
    return get_proof_center(limit=limit, submitted_only=submitted_only, q=q)


@router.get("/{record_id}")
def proof_center_record(record_id: str) -> Dict[str, Any]:
    return get_proof_record(record_id)


@router.get("/{record_id}/download-proof")
def proof_center_download_proof(record_id: str) -> FileResponse:
    resolved = resolve_download_path(record_id, kind="proof")
    if resolved.get("status") != "ok":
        raise HTTPException(status_code=404, detail=resolved)
    return FileResponse(path=resolved["path"], filename=resolved["filename"], media_type=resolved["media_type"])


@router.get("/{record_id}/download-screenshot")
def proof_center_download_screenshot(record_id: str, screenshot_index: int = Query(default=0, ge=0)) -> FileResponse:
    resolved = resolve_download_path(record_id, kind="screenshot", screenshot_index=screenshot_index)
    if resolved.get("status") != "ok":
        raise HTTPException(status_code=404, detail=resolved)
    return FileResponse(path=resolved["path"], filename=resolved["filename"], media_type=resolved["media_type"])
