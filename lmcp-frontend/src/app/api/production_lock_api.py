from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Query

from app.services.production_lock_service import (
    assert_production_submission_allowed,
    evaluate_production_lock,
    get_production_lock_status,
    get_production_policy,
    save_production_policy,
)

router = APIRouter(prefix="/production-lock", tags=["production-lock"])


@router.get("/status")
def production_lock_status(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    return get_production_lock_status(limit=limit)


@router.get("/policy")
def production_lock_policy() -> Dict[str, Any]:
    return get_production_policy()


@router.post("/policy")
def production_lock_update_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    return save_production_policy(payload)


@router.post("/evaluate")
def production_lock_evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    return evaluate_production_lock(payload)


@router.post("/assert")
def production_lock_assert(payload: Dict[str, Any]) -> Dict[str, Any]:
    return assert_production_submission_allowed(payload)
