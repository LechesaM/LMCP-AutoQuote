from __future__ import annotations

from app.harvest.source_tiers import HarvestTier
from app.orchestration.job_models import QueueJobType
from app.orchestration.queue_manager import enqueue_job


def enqueue_harvest_source(source_id: str, *, actor: str = "harvest", operator: str = "system") -> dict:
    return enqueue_job(
        tender_id=str(source_id),
        job_type=QueueJobType.INTEGRITY_CHECK,
        actor=actor,
        operator=operator,
        workflow_stage="harvest_source",
        payload={"action": "harvest_source", "source_id": str(source_id)},
    )


def enqueue_harvest_tier(tier: str | HarvestTier, *, actor: str = "harvest", operator: str = "system") -> dict:
    resolved = HarvestTier.from_value(tier)
    return enqueue_job(
        tender_id=f"tier-{resolved.value}",
        job_type=QueueJobType.INTEGRITY_CHECK,
        actor=actor,
        operator=operator,
        workflow_stage="harvest_tier",
        payload={"action": "harvest_tier", "tier": resolved.value},
    )


def enqueue_source_health_refresh(*, actor: str = "harvest", operator: str = "system") -> dict:
    return enqueue_job(
        tender_id="source-health-refresh",
        job_type=QueueJobType.INTEGRITY_CHECK,
        actor=actor,
        operator=operator,
        workflow_stage="source_health",
        payload={"action": "refresh_source_health"},
    )
