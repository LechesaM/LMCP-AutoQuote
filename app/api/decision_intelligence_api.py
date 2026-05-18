from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from app.services.decision_intelligence_service import (
    get_decision_summary,
    score_and_publish,
    score_many_and_publish,
    score_opportunity,
)

router = APIRouter(prefix="/decision-intelligence", tags=["decision-intelligence"])


@router.get("/summary")
def decision_summary(limit: int = 20) -> Dict[str, Any]:
    return get_decision_summary(limit=limit)


@router.post("/score")
def score_single(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    return score_opportunity(opportunity)


@router.post("/score-and-publish")
async def score_single_and_publish(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    return await score_and_publish(opportunity)


@router.post("/score-many-and-publish")
async def score_many(payload: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    opportunities = payload.get("opportunities") or []
    results = await score_many_and_publish(opportunities)
    return {"status": "ok", "scored": len(results), "items": results}
