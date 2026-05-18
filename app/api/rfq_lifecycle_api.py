from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from app.services.rfq_lifecycle_service import RfqLifecycleService


router = APIRouter(prefix="/rfq-lifecycle", tags=["RFQ Lifecycle"])


def service() -> RfqLifecycleService:
    return RfqLifecycleService()


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
