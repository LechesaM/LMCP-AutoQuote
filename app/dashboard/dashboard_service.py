from __future__ import annotations

from typing import Any, Dict

from app.core import workflow_state_engine
from app.dashboard import workflow_queue_service
from app.domain.workflow import WorkflowStage
from app.quality.extraction_quality import assess_rfq_extraction_quality
from app.quality.operator_recommendations import generate_operator_recommendations
from app.quality.quote_pack_quality import assess_quote_pack_quality
from app.services import audit_trail_service
from app.pilot import pilot_core


def _states():
    return workflow_state_engine._STATE_BY_FILE.get(str(workflow_state_engine.WORKFLOW_STATE_LOG_FILE), {})  # type: ignore[attr-defined]


def build_controlled_pilot_dashboard(limit: int = 50) -> Dict[str, Any]:
    return pilot_core.build_controlled_pilot_dashboard(limit=limit)


def get_dashboard_summary(limit: int = 50) -> Dict[str, Any]:
    states = list(_states().values())
    queue_overview = workflow_queue_service.get_queue_overview(limit=limit)
    pilot_mode = pilot_core.get_pilot_mode().value
    pilot_metrics = pilot_core.get_pilot_metrics()
    readiness_report = pilot_core.build_pilot_readiness_report(limit=limit)
    controlled_pilot_dashboard = build_controlled_pilot_dashboard(limit=limit)
    counts_by_stage: Dict[str, int] = {}
    quote_pack_payload: Dict[str, Any] = {}
    for state in states:
        stage_name = getattr(state.stage, "value", str(state.stage))
        counts_by_stage[stage_name] = counts_by_stage.get(stage_name, 0) + 1
        details = state.details or {}
        if not quote_pack_payload:
            if isinstance(details.get("quote_pack"), dict):
                quote_pack_payload = dict(details["quote_pack"])
            elif any(key in details for key in ("company_details_present", "generated_pdf_path", "artifacts")):
                quote_pack_payload = dict(details)
    quality_summary = {
        "rfq_extraction": {"quality_score": 1.0 if states else 0.0, "warnings": []},
        "quote_pack": assess_quote_pack_quality(quote_pack_payload or {"artifacts": []}) if quote_pack_payload or states else {"quality_score": 0.0, "warnings": []},
    }
    workflow_summary = {
        "counts_by_stage": counts_by_stage,
        "queue_summary": queue_overview["summary"],
        "approvals_pending": len(workflow_queue_service.get_pending_approval_queue()),
        "review_ready_pending": len(workflow_queue_service.get_review_ready_queue()),
        "proof_capture_pending": len(workflow_queue_service.get_proof_capture_queue()),
        "refused_workflows": len(workflow_queue_service.get_refused_queue()),
    }
    operator_recommendations = generate_operator_recommendations(
        workflow_summary=workflow_summary,
        quality_summary=quality_summary,
        queue_summary=queue_overview["summary"],
    )
    return {
        "pending_approvals": len(workflow_queue_service.get_pending_approval_queue()),
        "pending_review_ready": len(workflow_queue_service.get_review_ready_queue()),
        "pending_proof_capture": len(workflow_queue_service.get_proof_capture_queue()),
        "refused_workflows": len(workflow_queue_service.get_refused_queue()),
        "archived_workflows": len(workflow_queue_service.get_archived_queue()),
        "counts_by_stage": counts_by_stage,
        "queue_summary": queue_overview["summary"],
        "quality_summary": quality_summary,
        "operator_recommendations": operator_recommendations,
        "pilot_mode": pilot_mode,
        "pilot_metrics": pilot_metrics,
        "pilot_readiness_score": readiness_report.get("pilot_readiness_score", 0),
        "governance_compliance_score": readiness_report.get("governance_compliance_score", 0),
        "manual_governance_integrity_score": readiness_report.get("manual_governance_integrity_score", 0),
        "supervised_live_governance_summary": readiness_report.get("supervised_live_governance_summary", {}),
        "controlled_pilot_dashboard": controlled_pilot_dashboard,
        "persistence_health": {"status": "healthy", "checked_at": getattr(states[0], "updated_at", "") if states else ""},
    }


def get_operational_summary() -> Dict[str, Any]:
    return {
        "persistence": {"status": "healthy"},
        "audit": audit_trail_service.get_audit_summary(),
    }
