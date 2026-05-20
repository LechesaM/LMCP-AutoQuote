from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.governance_contracts import (
    build_access_review_response,
    build_attestation_generate_response,
    build_attestations_response,
    build_audit_integrity_response,
    build_compliance_controls_response,
    build_compliance_report_response,
    build_legal_hold_register_response,
    build_legal_hold_release_response,
    build_legal_holds_response,
    build_policies_response,
    build_regulatory_export_response,
    build_retention_status_response,
    build_risk_register_response,
)
from app.auth.auth_service import AuthError, get_current_auth_context, require_permission
from app.operations.structured_logging import log_operation_event
from app.services.audit_trail_service import append_audit_event

from app.governance import build_governance_attestation, register_legal_hold, release_legal_hold


router = APIRouter(prefix="/governance", tags=["governance"])


def _require_any_role(*roles: str):
    allowed = {str(role or "").lower() for role in roles}

    def dependency(request: Request):
        user = get_current_auth_context(request)
        if str(user.role or "").lower() not in allowed:
            raise AuthError(f"Role '{', '.join(sorted(allowed))}' required.", status_code=403)
        return user

    return dependency


def _confirm(payload: Dict[str, Any]) -> None:
    if not bool(payload.get("confirmed", False)):
        raise HTTPException(status_code=400, detail="Explicit confirmation is required.")


@router.get("/policies", dependencies=[Depends(require_permission("view_governance"))])
def get_policies() -> dict:
    return build_policies_response()


@router.get("/compliance-controls", dependencies=[Depends(require_permission("view_governance"))])
def get_compliance_controls() -> dict:
    return build_compliance_controls_response()


@router.get("/access-review", dependencies=[Depends(require_permission("view_audit"))])
def get_access_review() -> dict:
    return build_access_review_response()


@router.get("/attestations", dependencies=[Depends(require_permission("view_governance"))])
def get_attestations() -> dict:
    return build_attestations_response()


@router.get("/audit-integrity", dependencies=[Depends(require_permission("view_audit"))])
def get_audit_integrity() -> dict:
    return build_audit_integrity_response()


@router.get("/retention-status", dependencies=[Depends(require_permission("view_audit"))])
def get_retention_status() -> dict:
    return build_retention_status_response()


@router.get("/legal-holds", dependencies=[Depends(require_permission("view_governance"))])
def get_legal_holds() -> dict:
    return build_legal_holds_response()


@router.get("/risk-register", dependencies=[Depends(require_permission("view_governance"))])
def get_risk_register() -> dict:
    return build_risk_register_response()


@router.get("/compliance-report", dependencies=[Depends(require_permission("view_governance"))])
def get_compliance_report() -> dict:
    return build_compliance_report_response()


@router.get("/regulatory-export", dependencies=[Depends(require_permission("view_audit"))])
def get_regulatory_export() -> dict:
    return build_regulatory_export_response()


@router.post("/legal-hold/register", dependencies=[Depends(_require_any_role("supervisor", "admin", "governance"))])
def post_legal_hold_register(
    user=Depends(_require_any_role("supervisor", "admin", "governance")),
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> JSONResponse:
    data = payload or {}
    _confirm(data)
    scope = str(data.get("scope") or "").strip()
    reason = str(data.get("reason") or "").strip()
    if not scope or not reason:
        raise HTTPException(status_code=400, detail="scope and reason are required.")
    result = register_legal_hold(
        scope=scope,
        reason=reason,
        case_reference=str(data.get("case_reference") or "").strip(),
        operator_id=str(data.get("operator_id") or getattr(user, "user_id", "")).strip(),
        note=str(data.get("note") or "").strip(),
    )
    append_audit_event(
        "governance_legal_hold_registered",
        source="governance",
        severity="info",
        title="Legal hold registered",
        message=f"Legal hold registered for {scope}.",
        payload={"scope": scope, "reason": reason, "result": result},
    )
    log_operation_event("governance", "legal_hold_registered", severity="info", operator_id=str(getattr(user, "user_id", "")), details={"scope": scope})
    return JSONResponse(content=build_legal_hold_register_response(result))


@router.post("/legal-hold/release", dependencies=[Depends(_require_any_role("supervisor", "admin", "governance"))])
def post_legal_hold_release(
    user=Depends(_require_any_role("supervisor", "admin", "governance")),
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> JSONResponse:
    data = payload or {}
    _confirm(data)
    hold_id = str(data.get("hold_id") or "").strip()
    if not hold_id:
        raise HTTPException(status_code=400, detail="hold_id is required.")
    result = release_legal_hold(
        hold_id,
        operator_id=str(data.get("operator_id") or getattr(user, "user_id", "")).strip(),
        note=str(data.get("note") or "").strip(),
    )
    append_audit_event(
        "governance_legal_hold_released",
        source="governance",
        severity="info",
        title="Legal hold released",
        message=f"Legal hold released: {hold_id}.",
        payload={"hold_id": hold_id, "result": result},
    )
    log_operation_event("governance", "legal_hold_released", severity="info", operator_id=str(getattr(user, "user_id", "")), details={"hold_id": hold_id})
    return JSONResponse(content=build_legal_hold_release_response(result))


@router.post("/attestation/generate", dependencies=[Depends(_require_any_role("supervisor", "admin", "governance"))])
def post_attestation_generate(
    user=Depends(_require_any_role("supervisor", "admin", "governance")),
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> JSONResponse:
    data = payload or {}
    _confirm(data)
    note = str(data.get("note") or "").strip()
    result = build_governance_attestation(operator_id=str(getattr(user, "user_id", "")), note=note)
    append_audit_event(
        "governance_attestation_generated",
        source="governance",
        severity="info",
        title="Governance attestation generated",
        message="Governance attestation generated for enterprise compliance review.",
        payload={"result": result},
    )
    log_operation_event("governance", "attestation_generated", severity="info", operator_id=str(getattr(user, "user_id", "")), details={"note": note})
    return JSONResponse(content=build_attestation_generate_response(result))

