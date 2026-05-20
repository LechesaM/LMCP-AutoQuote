from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.persistence_ops_contracts import (
    build_backup_status_response,
    build_dead_letter_queue_response,
    build_manual_backup_response,
    build_migration_plan_response,
    build_persistence_health_response,
    build_queue_dlq_archive_response,
    build_queue_dlq_retry_response,
    build_queue_durability_response,
    build_queue_recovery_response,
    build_retention_dry_run_response,
    build_retention_policy_response,
    build_restore_readiness_response,
    build_worker_supervision_response,
)
from app.auth.auth_service import require_permission


router = APIRouter(tags=["persistence-ops"])


def _confirm(payload: Dict[str, Any]) -> None:
    if not bool(payload.get("confirmed", False)):
        raise HTTPException(status_code=400, detail="Explicit confirmation is required.")


@router.get("/persistence/health", dependencies=[Depends(require_permission("view_audit"))])
def get_health() -> dict:
    return build_persistence_health_response()


@router.get("/persistence/migration-plan", dependencies=[Depends(require_permission("view_audit"))])
def get_migration_plan() -> dict:
    return build_migration_plan_response()


@router.get("/persistence/retention-policy", dependencies=[Depends(require_permission("view_audit"))])
def get_retention_policy() -> dict:
    return build_retention_policy_response()


@router.get("/persistence/backup-status", dependencies=[Depends(require_permission("view_audit"))])
def get_backup_status() -> dict:
    return build_backup_status_response()


@router.get("/persistence/restore-readiness", dependencies=[Depends(require_permission("view_audit"))])
def get_restore_readiness() -> dict:
    return build_restore_readiness_response()


@router.get("/queue/durability", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_queue_durability() -> dict:
    return build_queue_durability_response()


@router.get("/queue/dead-letter", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_dead_letter_queue() -> dict:
    return build_dead_letter_queue_response()


@router.get("/queue/recovery", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_queue_recovery() -> dict:
    return build_queue_recovery_response()


@router.get("/queue/workers", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_worker_supervision() -> dict:
    return build_worker_supervision_response()


@router.post("/persistence/backup/manual", dependencies=[Depends(require_permission("manage_sources"))])
def post_manual_backup(payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    data = payload or {}
    _confirm(data)
    operator_id = str(data.get("operator_id") or "").strip()
    label = str(data.get("label") or "manual").strip()
    return JSONResponse(content=build_manual_backup_response(operator_id=operator_id, label=label))


@router.post("/persistence/retention/dry-run", dependencies=[Depends(require_permission("manage_sources"))])
def post_retention_dry_run(payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    data = payload or {}
    _confirm(data)
    return JSONResponse(content=build_retention_dry_run_response(confirmed=True))


@router.post("/queue/dead-letter/retry", dependencies=[Depends(require_permission("manage_sources"))])
def post_dlq_retry(payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    data = payload or {}
    _confirm(data)
    dlq_id = str(data.get("dlq_id") or "").strip()
    if not dlq_id:
        raise HTTPException(status_code=400, detail="dlq_id is required.")
    return JSONResponse(content=build_queue_dlq_retry_response(dlq_id))


@router.post("/queue/dead-letter/archive", dependencies=[Depends(require_permission("manage_sources"))])
def post_dlq_archive(payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    data = payload or {}
    _confirm(data)
    dlq_id = str(data.get("dlq_id") or "").strip()
    if not dlq_id:
        raise HTTPException(status_code=400, detail="dlq_id is required.")
    return JSONResponse(content=build_queue_dlq_archive_response(dlq_id))
