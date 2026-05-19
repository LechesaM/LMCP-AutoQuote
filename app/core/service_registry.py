from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from pydantic import Field

from app.core.service_contracts import ServiceStatus
from app.domain.base import StrictBaseModel


class ServiceRecord(StrictBaseModel):
    name: str
    module: str
    status: ServiceStatus = ServiceStatus.PRODUCTION
    description: str = ""
    workflow_aware: bool = False
    runtime_centralized: bool = False
    domain_schemas: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    legacy_service: bool = False


SERVICE_REGISTRY: List[ServiceRecord] = [
    ServiceRecord(
        name="audit_trail_service",
        module="app.services.audit_trail_service",
        status=ServiceStatus.PRODUCTION,
        description="Append-only audit event storage.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="manual_approval_service",
        module="app.services.manual_approval_service",
        status=ServiceStatus.PRODUCTION,
        description="Manual approval capture for production workflows.",
        workflow_aware=True,
        runtime_centralized=True,
        domain_schemas=["ApprovalRecord"],
    ),
    ServiceRecord(
        name="submission_review_service",
        module="app.services.submission_review_service",
        status=ServiceStatus.PRODUCTION,
        description="Manual review readiness and pack validation.",
        workflow_aware=True,
        runtime_centralized=True,
        domain_schemas=["SubmissionReview", "ApprovalRecord"],
    ),
    ServiceRecord(
        name="submission_proof_service",
        module="app.services.submission_proof_service",
        status=ServiceStatus.PRODUCTION,
        description="Manual proof capture after review readiness.",
        workflow_aware=True,
        runtime_centralized=True,
        domain_schemas=["SubmissionProof"],
    ),
    ServiceRecord(
        name="pilot_run_log_service",
        module="app.services.pilot_run_log_service",
        status=ServiceStatus.PRODUCTION,
        description="Manual-production pilot run logging.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="workflow_state_engine",
        module="app.core.workflow_state_engine",
        status=ServiceStatus.PRODUCTION,
        description="Append-only workflow state and event engine.",
        workflow_aware=True,
        runtime_centralized=True,
        domain_schemas=["WorkflowEvent", "WorkflowState", "WorkflowTransition"],
    ),
    ServiceRecord(
        name="pricing_engine",
        module="app.services.pricing_engine",
        status=ServiceStatus.PRODUCTION,
        description="Primary pricing and eligibility engine.",
        domain_schemas=["PricingDecision", "PricingSchedule"],
    ),
    ServiceRecord(
        name="real_profit_pricing_service",
        module="app.services.real_profit_pricing_service",
        status=ServiceStatus.PRODUCTION,
        description="Runtime pricing fallback and profitability enrichment.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="pricing_engine_v2_realistic",
        module="app.services.pricing_engine_v2_realistic",
        status=ServiceStatus.EXPERIMENTAL,
        description="Versioned pricing implementation retained for compatibility.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="quote_pack_service",
        module="app.services.quote_pack_service",
        status=ServiceStatus.PRODUCTION,
        description="Production quote pack generation.",
    ),
    ServiceRecord(
        name="quote_pack_builder_service",
        module="app.services.quote_pack_builder_service",
        status=ServiceStatus.PRODUCTION,
        description="PDF quote pack output builder.",
    ),
    ServiceRecord(
        name="quote_engine_service",
        module="app.services.quote_engine_service",
        status=ServiceStatus.PRODUCTION,
        description="Primary quote engine entrypoint.",
    ),
    ServiceRecord(
        name="quote_review_service",
        module="app.services.quote_review_service",
        status=ServiceStatus.PRODUCTION,
        description="Manual quote review support service.",
    ),
    ServiceRecord(
        name="quote_compilation_service",
        module="app.services.quote_compilation_service",
        status=ServiceStatus.PRODUCTION,
        description="Quote compilation and archival service.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="auto_quote_trigger_engine",
        module="app.services.auto_quote_trigger_engine",
        status=ServiceStatus.PRODUCTION,
        description="Eligibility and trigger engine for quote preparation.",
    ),
    ServiceRecord(
        name="submission_pipeline",
        module="app.services.submission_pipeline",
        status=ServiceStatus.PRODUCTION,
        description="Manual submission pipeline.",
        workflow_aware=True,
    ),
    ServiceRecord(
        name="tender_pipeline",
        module="app.services.tender_pipeline",
        status=ServiceStatus.PRODUCTION,
        description="Main tender processing pipeline.",
        workflow_aware=True,
    ),
    ServiceRecord(
        name="rfq_lifecycle_service",
        module="app.services.rfq_lifecycle_service",
        status=ServiceStatus.PRODUCTION,
        description="RFQ lifecycle and readiness management.",
    ),
    ServiceRecord(
        name="submission_history_service",
        module="app.services.submission_history_service",
        status=ServiceStatus.PRODUCTION,
        description="Submission history view and storage helper.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="submission_history_recent_service",
        module="app.services.submission_history_recent_service",
        status=ServiceStatus.PRODUCTION,
        description="Recent submission history reader.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="submission_history_pipeline_sync_service",
        module="app.services.submission_history_pipeline_sync_service",
        status=ServiceStatus.PRODUCTION,
        description="Submission history synchronization helper.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="submission_history_proof_enrichment_service",
        module="app.services.submission_history_proof_enrichment_service",
        status=ServiceStatus.PRODUCTION,
        description="Submission history proof enrichment helper.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="production_lock_service",
        module="app.services.production_lock_service",
        status=ServiceStatus.PRODUCTION,
        description="Production lock and governance guard.",
        runtime_centralized=True,
    ),
    ServiceRecord(
        name="auto_submission_v46_service",
        module="app.services.auto_submission_v46_service",
        status=ServiceStatus.LEGACY,
        description="Legacy auto-submission implementation kept for compatibility.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="final_submission_v47_5_service",
        module="app.services.final_submission_v47_5_service",
        status=ServiceStatus.LEGACY,
        description="Legacy final submission implementation retained for compatibility.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="full_autonomous_cycle_service",
        module="app.services.full_autonomous_cycle_service",
        status=ServiceStatus.LEGACY,
        description="Legacy autonomous cycle implementation.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="full_autonomous_v48_service",
        module="app.services.full_autonomous_v48_service",
        status=ServiceStatus.LEGACY,
        description="Versioned autonomous flow retained for compatibility.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="portal_submission_v47_service",
        module="app.services.portal_submission_v47_service",
        status=ServiceStatus.LEGACY,
        description="Legacy portal submission path.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="proof_of_submission_service",
        module="app.services.proof_of_submission_service",
        status=ServiceStatus.LEGACY,
        description="Legacy proof of submission helper.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="auto_proof_after_submission_service",
        module="app.services.auto_proof_after_submission_service",
        status=ServiceStatus.LEGACY,
        description="Legacy post-submission proof helper.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="auto_proof_after_submission_v2",
        module="app.services.auto_proof_after_submission_v2",
        status=ServiceStatus.LEGACY,
        description="Versioned legacy post-submission proof helper.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="quote_pack_v44_service",
        module="app.services.quote_pack_v44_service",
        status=ServiceStatus.LEGACY,
        description="Legacy quote pack implementation.",
        legacy_service=True,
    ),
    ServiceRecord(
        name="pricing_table_extraction_v42_service",
        module="app.services.pricing_table_extraction_v42_service",
        status=ServiceStatus.LEGACY,
        description="Legacy pricing table extraction implementation.",
        legacy_service=True,
    ),
]

_SERVICE_BY_NAME = {record.name: record for record in SERVICE_REGISTRY}
_SERVICE_BY_MODULE = {record.module: record for record in SERVICE_REGISTRY}


def get_production_services() -> List[ServiceRecord]:
    return [record for record in SERVICE_REGISTRY if record.status is ServiceStatus.PRODUCTION]


def get_legacy_services() -> List[ServiceRecord]:
    return [record for record in SERVICE_REGISTRY if record.status in {ServiceStatus.LEGACY, ServiceStatus.DEPRECATED}]


def get_service(name: str) -> Optional[ServiceRecord]:
    key = str(name or "").strip()
    if not key:
        return None
    return _SERVICE_BY_NAME.get(key) or _SERVICE_BY_MODULE.get(key)


def validate_unique_service_names() -> None:
    names = [record.name for record in SERVICE_REGISTRY]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate service names found: {', '.join(duplicates)}")

