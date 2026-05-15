from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

from app.services.self_clean_archive_service import (
    get_self_clean_archive_status,
    run_self_clean_archive,
)

router = APIRouter(prefix="/self-clean", tags=["self-clean"])


@router.get("/status")
def self_clean_status(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return get_self_clean_archive_status(limit=limit)


@router.post("/archive")
def self_clean_archive(
    days_to_keep_live: int = Query(default=7, ge=1, le=365),
    keep_proofs_live_days: int = Query(default=30, ge=1, le=3650),
    min_free_gb: float = Query(default=10, ge=1, le=500),
    dry_run: bool = False,
) -> Dict[str, Any]:
    return run_self_clean_archive(
        days_to_keep_live=days_to_keep_live,
        keep_proofs_live_days=keep_proofs_live_days,
        min_free_gb=min_free_gb,
        dry_run=dry_run,
    )
