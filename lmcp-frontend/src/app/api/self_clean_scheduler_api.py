from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

from app.services.self_clean_scheduler_service import (
    assert_disk_safe_or_block,
    enforce_disk_guard,
    get_disk_guard_status,
    get_self_clean_scheduler_status,
    resume_system_if_safe,
    run_scheduled_self_clean,
)

router = APIRouter(prefix="/self-clean-scheduler", tags=["self-clean-scheduler"])


@router.get("/status")
def scheduler_status() -> Dict[str, Any]:
    return get_self_clean_scheduler_status()


@router.get("/disk-guard")
def disk_guard_status() -> Dict[str, Any]:
    return get_disk_guard_status()


@router.post("/run")
def scheduler_run(dry_run: bool = False) -> Dict[str, Any]:
    return run_scheduled_self_clean(dry_run=dry_run)


@router.post("/enforce")
def disk_guard_enforce(auto_archive: bool = True, dry_run: bool = False) -> Dict[str, Any]:
    return enforce_disk_guard(auto_archive=auto_archive, dry_run=dry_run)


@router.post("/resume")
def disk_guard_resume(force: bool = Query(default=False)) -> Dict[str, Any]:
    return resume_system_if_safe(force=force)


@router.get("/allowed")
def disk_guard_allowed() -> Dict[str, Any]:
    return assert_disk_safe_or_block()
