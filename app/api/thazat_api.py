from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.business_intelligence.thazat_outcomes import record_outcome, summarize_outcomes
from app.governance.thazat import (
    build_outcome_learning,
    calculate_readiness,
    commercial_gate,
    evaluate_opportunity,
    run_red_team,
)


router = APIRouter(prefix="/thazat", tags=["thazat-governance"])


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@router.post("/commercial-gate")
def thazat_commercial_gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    return commercial_gate(
        estimated_profit=float(payload.get("estimated_profit") or 0.0),
        gross_margin_ratio=float(payload.get("gross_margin_ratio") or 0.0),
        recoverable=_bool(payload.get("recoverable"), True),
    )


@router.post("/decision")
def thazat_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    return evaluate_opportunity(payload).as_dict()


@router.post("/readiness")
def thazat_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return calculate_readiness(payload).as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/red-team")
def thazat_red_team(payload: Dict[str, Any]) -> Dict[str, Any]:
    checks = payload.get("checks") if "checks" in payload else payload
    if not isinstance(checks, dict):
        raise HTTPException(status_code=422, detail="checks must be an object")
    return run_red_team(checks)


@router.post("/outcome-learning")
def thazat_outcome_learning(payload: Dict[str, Any]) -> Dict[str, Any]:
    return build_outcome_learning(payload).as_dict()


@router.post("/outcomes")
def thazat_record_outcome(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "recorded", "record": record_outcome(payload)}


@router.get("/outcomes/summary")
def thazat_outcome_summary() -> Dict[str, Any]:
    return summarize_outcomes()


@router.get("/policy")
def thazat_policy() -> Dict[str, Any]:
    return {
        "status": "active",
        "submission_authority": "human_authorised_only",
        "operating_sequence": [
            "IDENTITY",
            "STANDARDS",
            "SELECTIVITY",
            "ACTION",
            "EVIDENCE",
            "EXECUTION",
            "LEARNING",
        ],
        "issue_states": ["BLOCKER", "REQUIRED", "OPTIONAL", "CLOSED"],
        "evidence_states": ["PROVEN", "GAP", "DEVIATION", "NOT_APPLICABLE"],
        "opportunity_decisions": ["GO", "HOLD", "NO_GO"],
        "execution_decisions": ["SUBMIT", "WITHDRAW", "ESCALATE", "PENDING"],
        "note": "SUBMIT is a readiness recommendation only; this API never submits a bid.",
    }
