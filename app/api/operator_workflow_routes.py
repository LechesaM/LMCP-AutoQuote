from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from app.api.operator_workflow_contracts import (
    get_qualification_insights,
    get_operator_workflow_detail,
    get_operator_workflow_http_detail,
    get_operator_workflow_rows,
    get_pricing_evidence_overview,
    get_source_health_details,
    _trim_http_workflow_detail,
)
from app.services.submission_package_service import build_submission_package, evaluate_submission_gate
from app.services.submission_quality_service import build_submission_quality_report


router = APIRouter(prefix="/operations", tags=["Operator Workflow"])


def list_rfqs(limit: int = 50) -> Dict[str, Any]:
    return get_operator_workflow_rows(limit=limit)


def get_rfq_detail(tender_id: str) -> Dict[str, Any]:
    return _trim_http_workflow_detail(get_operator_workflow_http_detail(tender_id))


def qualification_insights() -> Dict[str, Any]:
    return get_qualification_insights()


def pricing_evidence() -> Dict[str, Any]:
    return get_pricing_evidence_overview()


def source_health_details() -> Dict[str, Any]:
    return get_source_health_details()


def generate_rfq_submission_package(tender_id: str) -> Dict[str, Any]:
    detail = get_operator_workflow_detail(tender_id)
    gate = evaluate_submission_gate(detail)
    if not gate.get("allowed"):
        raise HTTPException(status_code=409, detail=gate)
    package = build_submission_package(detail)
    if not package.get("submission_ready"):
        raise HTTPException(status_code=409, detail=package)
    return package


@router.get("/rfqs")
def rfqs(limit: int = 50) -> Dict[str, Any]:
    return list_rfqs(limit=limit)


@router.get("/rfqs/{tender_id}")
def rfq_detail(tender_id: str) -> Dict[str, Any]:
    return get_rfq_detail(tender_id)


@router.get("/rfqs/{tender_id}/submission-quality")
def rfq_submission_quality(tender_id: str) -> Dict[str, Any]:
    return build_submission_quality_report(get_operator_workflow_detail(tender_id))


@router.get("/rfqs/{tender_id}/submission-package")
def rfq_submission_package(tender_id: str) -> Dict[str, Any]:
    return generate_rfq_submission_package(tender_id)


@router.post("/rfqs/{tender_id}/submission-package/generate")
def rfq_submission_package_generate(tender_id: str, detail: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return generate_rfq_submission_package(tender_id)


@router.get("/rfqs/{tender_id}/submission-package/download")
def rfq_submission_package_download(tender_id: str) -> Dict[str, Any]:
    return generate_rfq_submission_package(tender_id)


@router.get("/rfqs/{tender_id}/governance-envelope")
def rfq_governance_envelope(tender_id: str) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("governed_submission", {})


@router.post("/rfqs/{tender_id}/governance-decision")
def rfq_governance_decision(tender_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    detail = get_operator_workflow_detail(tender_id)
    return {
        "status": "ok",
        "detail": detail,
        "decision": payload.get("decision") or "approved",
    }


@router.get("/rfqs/{tender_id}/submission-execution")
def rfq_submission_execution(tender_id: str) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("submission_execution", {})


@router.post("/rfqs/{tender_id}/submission-execution")
def rfq_submission_execution_post(tender_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("submission_execution", {})


@router.post("/rfqs/{tender_id}/submission-execution/enqueue")
def rfq_submission_execution_enqueue(tender_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("submission_execution", {})


@router.get("/rfqs/{tender_id}/submission-execution/receipt-verification")
def rfq_submission_receipt_verification(tender_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("submission_execution", {})


@router.post("/rfqs/{tender_id}/submission-execution/reconcile")
def rfq_submission_reconcile(tender_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("submission_execution", {})


@router.get("/rfqs/{tender_id}/submission-execution/external-audit-export")
def rfq_external_audit_export(tender_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("submission_execution", {})


@router.get("/rfqs/{tender_id}/submission-execution/external-audit-export/download")
def rfq_external_audit_export_download(tender_id: str) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id).get("submission_execution", {})


@router.get("/qualification-insights")
def qualification_insights_route() -> Dict[str, Any]:
    return qualification_insights()


@router.get("/pricing-evidence")
def pricing_evidence_route() -> Dict[str, Any]:
    return pricing_evidence()


@router.get("/source-health-details")
def source_health_details_route() -> Dict[str, Any]:
    return source_health_details()
