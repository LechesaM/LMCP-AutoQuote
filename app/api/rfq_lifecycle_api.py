from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.operational_rehearsal_service import OperationalRehearsalService
from app.services.pilot_cadence_service import PilotCadenceService
from app.services.operational_exception_service import OperationalExceptionService
from app.services.operational_remediation_service import OperationalRemediationService
from app.services.pilot_progression_service import PilotProgressionService
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService
from app.services.pilot_operator_session_service import PilotOperatorSessionService
from app.services.recurring_pilot_cycle_service import RecurringPilotCycleService
from app.services.pilot_review_board_service import PilotReviewBoardService
from app.services.pilot_evidence_pack_service import PilotEvidencePackService
from app.services.pilot_operations_summary_service import PilotOperationsSummaryService
from app.services.operational_stability_service import OperationalStabilityService
from app.services.supervised_rfq_intake_service import SupervisedRfqIntakeService
from app.services.physical_submission_governance_service import PhysicalSubmissionGovernanceService
from app.services.submission_modality_governance_service import SubmissionModalityGovernanceService


router = APIRouter(prefix="/rfq-lifecycle", tags=["RFQ Lifecycle"])


def service() -> RfqLifecycleService:
    return RfqLifecycleService()


def rehearsal_service() -> OperationalRehearsalService:
    return OperationalRehearsalService()


def pilot_evidence_service() -> PilotEvidencePackService:
    return PilotEvidencePackService()


def cadence_service() -> PilotCadenceService:
    return PilotCadenceService()


def recurring_cycle_service() -> RecurringPilotCycleService:
    return RecurringPilotCycleService()


def exception_service() -> OperationalExceptionService:
    return OperationalExceptionService()


def remediation_service() -> OperationalRemediationService:
    return OperationalRemediationService()


def progression_service() -> PilotProgressionService:
    return PilotProgressionService()


def declaration_service() -> PilotReadinessDeclarationService:
    return PilotReadinessDeclarationService()


def operator_session_service() -> PilotOperatorSessionService:
    return PilotOperatorSessionService()


def intake_service() -> SupervisedRfqIntakeService:
    return SupervisedRfqIntakeService()


def physical_submission_service() -> PhysicalSubmissionGovernanceService:
    return PhysicalSubmissionGovernanceService()


def submission_modality_service() -> SubmissionModalityGovernanceService:
    return SubmissionModalityGovernanceService()


def review_board_service() -> PilotReviewBoardService:
    return PilotReviewBoardService()


def stability_service() -> OperationalStabilityService:
    return OperationalStabilityService()


def operations_summary_service() -> PilotOperationsSummaryService:
    return PilotOperationsSummaryService()


@router.get("/status")
def status() -> Dict[str, Any]:
    return service().status()


@router.get("/mission-control")
def mission_control() -> Dict[str, Any]:
    return service().mission_control_summary()


@router.get("/analytics")
def analytics() -> Dict[str, Any]:
    return service().analytics()


@router.get("/telemetry")
def telemetry() -> Dict[str, Any]:
    return service().telemetry()


@router.get("/health-report")
def health_report() -> Dict[str, Any]:
    return service().health_report()


@router.get("/audit/{rfq_id}")
def audit_trace(rfq_id: str) -> Dict[str, Any]:
    return service().audit_trace(rfq_id)


@router.get("/items")
def items(state: Optional[str] = Query(default=None), limit: int = Query(default=250, ge=1, le=1000)) -> Dict[str, Any]:
    return service().list_items(state=state, limit=limit)


@router.get("/items/{rfq_id}")
def item(rfq_id: str) -> Dict[str, Any]:
    return service().get_item(rfq_id)


@router.get("/manual-pricing/{rfq_id}")
def manual_pricing(rfq_id: str) -> Dict[str, Any]:
    return service().get_manual_pricing(rfq_id)


@router.post("/manual-pricing/{rfq_id}")
def save_manual_pricing(rfq_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().save_manual_pricing(rfq_id, payload)


@router.post("/ingest")
def ingest(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().ingest(payload)


@router.post("/ingest-discovered")
def ingest_discovered() -> Dict[str, Any]:
    return service().ingest_discovered()


@router.post("/advance/{rfq_id}")
def advance(rfq_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().advance(
        rfq_id=rfq_id,
        target_state=payload.get("target_state") or payload.get("state"),
        note=str(payload.get("note") or ""),
    )


@router.post("/advance-discovered")
def advance_discovered(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().advance_discovered(
        limit=int(payload.get("limit") or 50),
        timeout_seconds=int(payload.get("timeout_seconds") or 8),
        max_concurrent_downloads=int(payload.get("max_concurrent_downloads") or 4),
        retry_backoff_seconds=float(payload.get("retry_backoff_seconds") or 0.75),
    )


@router.post("/advance-parsed")
def advance_parsed(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().advance_parsed(
        limit=int(payload.get("limit") or 25),
    )


@router.post("/run-controlled-submission")
def run_controlled_submission(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().run_controlled_submission(
        limit=int(payload.get("limit") or 25),
    )


@router.post("/review-recovery")
def review_recovery(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().review_recovery(
        limit=int(payload.get("limit") or 50),
        timeout_seconds=int(payload.get("timeout_seconds") or 8),
        max_concurrent_downloads=int(payload.get("max_concurrent_downloads") or 4),
        retry_backoff_seconds=float(payload.get("retry_backoff_seconds") or 0.75),
    )


@router.post("/reject-terminal-review-items")
def reject_terminal_review_items(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().reject_terminal_review_items(
        limit=int(payload.get("limit") or 100),
    )


@router.post("/retry-ready")
def retry_ready(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().retry_ready(
        limit=int(payload.get("limit") or 50),
        timeout_seconds=int(payload.get("timeout_seconds") or 8),
        max_concurrent_downloads=int(payload.get("max_concurrent_downloads") or 4),
        retry_backoff_seconds=float(payload.get("retry_backoff_seconds") or 0.75),
    )


@router.post("/run-golden-validation")
def run_golden_validation(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().run_golden_validation(
        limit=int(payload.get("limit") or 50),
        timeout_seconds=int(payload.get("timeout_seconds") or 8),
        max_sources=int(payload.get("max_sources") or 8),
        max_per_source=int(payload.get("max_per_source") or 2),
        max_concurrent_downloads=int(payload.get("max_concurrent_downloads") or 4),
        retry_backoff_seconds=float(payload.get("retry_backoff_seconds") or 0.75),
    )


@router.post("/run-scale-simulation")
def run_scale_simulation(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().run_scale_simulation(
        target_rfqs=int(payload.get("target_rfqs") or 10),
    )


@router.post("/run-live-acquisition-validation")
def run_live_acquisition_validation(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().run_live_acquisition_validation(
        limit=int(payload.get("limit") or 25),
        timeout_seconds=int(payload.get("timeout_seconds") or 6),
    )


@router.post("/run-live-pilot")
def run_live_pilot(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().run_live_pilot(
        limit=int(payload.get("limit") or 5),
        timeout_seconds=int(payload.get("timeout_seconds") or 8),
        max_concurrent_downloads=int(payload.get("max_concurrent_downloads") or 4),
        retry_backoff_seconds=float(payload.get("retry_backoff_seconds") or 0.75),
    )


@router.post("/debug-etenders-acquisition")
def debug_etenders_acquisition(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().debug_etenders_acquisition(
        url=str(payload.get("url") or ""),
        timeout_seconds=int(payload.get("timeout_seconds") or 15),
    )


@router.post("/replay-dead-letters")
def replay_dead_letters(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().replay_dead_letters(
        limit=int(payload.get("limit") or 25),
        timeout_seconds=int(payload.get("timeout_seconds") or 4),
        max_concurrent_downloads=int(payload.get("max_concurrent_downloads") or 4),
        retry_backoff_seconds=float(payload.get("retry_backoff_seconds") or 0.25),
    )


@router.post("/cleanup-runtime")
def cleanup_runtime(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().cleanup_runtime(
        retention_days=int(payload.get("retention_days") or 14),
        allow_delete_submitted_proofs=bool(payload.get("allow_delete_submitted_proofs", False)),
        dry_run=bool(payload.get("dry_run", False)),
    )


@router.post("/retry-failed")
def retry_failed() -> Dict[str, Any]:
    return service().retry_failed()


@router.post("/recover-stuck")
def recover_stuck(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().recover_stuck(timeout_minutes=int(payload.get("timeout_minutes") or 120))


@router.post("/run-golden-cycle")
def run_golden_cycle(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().run_golden_cycle(
        limit=int(payload.get("limit") or 25),
        dry_run=bool(payload.get("dry_run", True)),
    )


@router.post("/run-discovery-cycle")
def run_discovery_cycle(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().run_discovery_cycle(
        max_total=int(payload.get("max_total") or 20),
        max_per_source=int(payload.get("max_per_source") or 3),
        max_sources=int(payload.get("max_sources") or 12),
    )


@router.post("/validate-visible-opportunities")
def validate_visible_opportunities(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return service().validate_visible_opportunities(
        limit=int(payload.get("limit") or 250),
        timeout_seconds=int(payload.get("timeout_seconds") or 8),
        max_concurrent_downloads=int(payload.get("max_concurrent_downloads") or 4),
        retry_backoff_seconds=float(payload.get("retry_backoff_seconds") or 0.75),
        generate_local_pack=bool(payload.get("generate_local_pack", True)),
    )


# ---------------------------------------------------------------------
# LMCP Upload Dry-Run Endpoint
# ---------------------------------------------------------------------
@router.post("/run-upload-dry-run")
def run_upload_dry_run_endpoint(payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    from app.services.upload_dry_run_service import run_upload_dry_run

    payload = payload or {}
    return run_upload_dry_run(
        limit=int(payload.get("limit") or 5),
        dry_run=bool(payload.get("dry_run", True)),
    )


@router.get("/upload-dry-run/status")
def upload_dry_run_status() -> Dict[str, Any]:
    from app.services.upload_dry_run_service import latest_upload_dry_run_status

    return latest_upload_dry_run_status()


@router.get("/rehearsals/history")
def rehearsal_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return rehearsal_service().list_rehearsals(limit=limit)


@router.get("/rehearsals/latest")
def rehearsal_latest() -> Dict[str, Any]:
    return rehearsal_service().latest_rehearsal()


@router.get("/rehearsals/readiness")
def rehearsal_readiness() -> Dict[str, Any]:
    return rehearsal_service().readiness_summary()


@router.get("/rehearsals/readiness/history")
def rehearsal_readiness_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return rehearsal_service().readiness_history(limit=limit)


@router.get("/rehearsals/{run_id}")
def rehearsal_run(run_id: str) -> Dict[str, Any]:
    return rehearsal_service().get_rehearsal(run_id)


@router.get("/pilot-evidence/history")
def pilot_evidence_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return pilot_evidence_service().list_packs(limit=limit)


@router.get("/pilot-evidence/latest")
def pilot_evidence_latest() -> Dict[str, Any]:
    return pilot_evidence_service().latest_pack()


@router.get("/pilot-evidence/governance-review")
def pilot_evidence_governance_review() -> Dict[str, Any]:
    return pilot_evidence_service().governance_review()


@router.get("/pilot-evidence/{pack_id}")
def pilot_evidence_pack(pack_id: str) -> Dict[str, Any]:
    return pilot_evidence_service().get_pack(pack_id)


@router.get("/stability")
def stability(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return stability_service().list_stability(limit=limit)


@router.get("/stability/latest")
def stability_latest() -> Dict[str, Any]:
    return stability_service().latest_stability()


@router.get("/stability/history")
def stability_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return stability_service().stability_history(limit=limit)


@router.get("/cadence")
def cadence(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return cadence_service().list_cadence(limit=limit)


@router.get("/cadence/latest")
def cadence_latest() -> Dict[str, Any]:
    return cadence_service().latest_cadence()


@router.get("/cadence/history")
def cadence_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return cadence_service().cadence_history(limit=limit)


@router.get("/review-board")
def review_board(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return review_board_service().list_review_board(limit=limit)


@router.get("/review-board/latest")
def review_board_latest() -> Dict[str, Any]:
    return review_board_service().latest_review_board()


@router.get("/review-board/history")
def review_board_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return review_board_service().review_board_history(limit=limit)


@router.get("/recurring-cycles")
def recurring_cycles(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return recurring_cycle_service().list_recurring_cycles(limit=limit)


@router.get("/recurring-cycles/latest")
def recurring_cycles_latest() -> Dict[str, Any]:
    return recurring_cycle_service().latest_recurring_cycles()


@router.get("/recurring-cycles/history")
def recurring_cycles_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return recurring_cycle_service().recurring_cycles_history(limit=limit)


@router.get("/exceptions")
def exceptions(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return exception_service().list_exceptions(limit=limit)


@router.get("/exceptions/latest")
def exceptions_latest() -> Dict[str, Any]:
    return exception_service().latest_exceptions()


@router.get("/exceptions/history")
def exceptions_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return exception_service().exceptions_history(limit=limit)


@router.get("/remediation")
def remediation(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return remediation_service().list_remediation(limit=limit)


@router.get("/remediation/latest")
def remediation_latest() -> Dict[str, Any]:
    return remediation_service().latest_remediation()


@router.get("/remediation/history")
def remediation_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return remediation_service().remediation_history(limit=limit)


@router.get("/progression")
def progression(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return progression_service().list_progression(limit=limit)


@router.get("/progression/latest")
def progression_latest() -> Dict[str, Any]:
    return progression_service().latest_progression()


@router.get("/progression/history")
def progression_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return progression_service().progression_history(limit=limit)


@router.get("/operations-summary")
def operations_summary(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return operations_summary_service().list_operations_summary(limit=limit)


@router.get("/operations-summary/latest")
def operations_summary_latest() -> Dict[str, Any]:
    return operations_summary_service().latest_operations_summary()


@router.get("/operations-summary/history")
def operations_summary_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return operations_summary_service().operations_summary_history(limit=limit)


@router.get("/declaration")
def declaration(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return declaration_service().list_declarations(limit=limit)


@router.get("/declaration/latest")
def declaration_latest() -> Dict[str, Any]:
    return declaration_service().latest_declaration()


@router.get("/declaration/history")
def declaration_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return declaration_service().declaration_history(limit=limit)


@router.get("/operator-sessions")
def operator_sessions(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return operator_session_service().list_operator_sessions(limit=limit)


@router.get("/operator-sessions/latest")
def operator_sessions_latest() -> Dict[str, Any]:
    return operator_session_service().latest_operator_session()


@router.get("/operator-sessions/history")
def operator_sessions_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return operator_session_service().operator_session_history(limit=limit)


@router.get("/intake")
def intake(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return intake_service().list_intake(limit=limit)


@router.get("/intake/latest")
def intake_latest() -> Dict[str, Any]:
    return intake_service().latest_intake()


@router.get("/intake/history")
def intake_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return intake_service().intake_history(limit=limit)


@router.get("/physical-submission")
def physical_submission(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return physical_submission_service().list_physical_submissions(limit=limit)


@router.get("/physical-submission/latest")
def physical_submission_latest() -> Dict[str, Any]:
    return physical_submission_service().latest_physical_submission()


@router.get("/physical-submission/history")
def physical_submission_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return physical_submission_service().physical_submission_history(limit=limit)


@router.get("/submission-modality")
def submission_modality(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return submission_modality_service().list_submission_modalities(limit=limit)


@router.get("/submission-modality/latest")
def submission_modality_latest() -> Dict[str, Any]:
    return submission_modality_service().latest_submission_modality()


@router.get("/submission-modality/history")
def submission_modality_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return submission_modality_service().submission_modality_history(limit=limit)
