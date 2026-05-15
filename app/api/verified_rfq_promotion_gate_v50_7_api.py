"""
LMCP V50.7 API - Verified RFQ Promotion Gate

Drop-in file:
    app/api/verified_rfq_promotion_gate_v50_7_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.verified_rfq_promotion_gate_v50_7_service import (
    batch_evaluate_verified_rfqs,
    evaluate_verified_rfq_for_promotion,
    get_v50_7_promotion_status,
)

router = APIRouter(prefix="/v50-7-promotion-gate", tags=["V50.7 Promotion Gate"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_7_promotion_status()


@router.post("/evaluate")
def evaluate(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    return evaluate_verified_rfq_for_promotion(
        item=payload.get("item") or payload,
        policy=payload.get("policy") or {},
    )


@router.post("/batch-evaluate")
def batch_evaluate(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    return batch_evaluate_verified_rfqs(
        items=payload.get("items") or [],
        policy=payload.get("policy") or {},
    )
