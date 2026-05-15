"""
LMCP V50.9.7 API - Tender Document Mapping Resolver
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_document_mapping_resolver_v50_9_7_service import (
    download_mapped,
    get_v50_9_7_status,
    resolve_mapping,
)

router = APIRouter(
    prefix="/v50-9-7-document-mapping-resolver",
    tags=["V50.9.7 eTenders Document Mapping Resolver"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_7_status()


@router.post("/resolve")
def resolve(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return resolve_mapping(payload or {})


@router.post("/download-mapped")
def download(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return download_mapped(payload or {})
