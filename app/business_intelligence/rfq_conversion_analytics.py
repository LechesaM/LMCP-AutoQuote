from __future__ import annotations

from typing import Any, Dict, List

from app.analytics.tender_success_analytics import build_tender_success_analytics
from app.monitoring.workflow_monitor import get_workflow_summary
from ._shared import now_iso, safe_float, safe_int


def build_rfq_conversion_analytics(limit: int = 100) -> Dict[str, Any]:
    tender = build_tender_success_analytics(limit=limit)
    workflow = get_workflow_summary(limit=limit)
    summary = tender.get("tender_outcome_summary", {})
    harvested = safe_int(summary.get("processed", 0) or workflow.get("total_workflows", 0))
    qualified = safe_int(summary.get("eligible", 0))
    reviewed = safe_int(summary.get("reviewed_packs", 0))
    submission_ready = safe_int(workflow.get("review_ready_pending", 0) + workflow.get("proof_capture_pending", 0))
    blocked = safe_int(summary.get("refused", 0))
    stale_loss_rate = round(blocked / max(1, harvested), 4)
    manual_review_frequency = safe_float(summary.get("refusal_rate", 0.0)) * 100.0
    governance_blocked_frequency = safe_float(summary.get("refusal_rate", 0.0)) * 100.0
    conversion_rates = {
        "harvested_to_qualified": round(qualified / max(1, harvested), 4),
        "qualified_to_reviewed": round(reviewed / max(1, qualified), 4),
        "reviewed_to_submission_ready": round(submission_ready / max(1, reviewed), 4),
    }
    priority_groups = [
        {"group": "harvested", "count": harvested},
        {"group": "qualified", "count": qualified},
        {"group": "reviewed", "count": reviewed},
        {"group": "submission_ready", "count": submission_ready},
        {"group": "governance_blocked", "count": blocked},
    ]
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if harvested else "fallback",
        "summary": {
            "harvested": harvested,
            "qualified": qualified,
            "reviewed": reviewed,
            "submission_ready": submission_ready,
            "manual_review_frequency": manual_review_frequency,
            "governance_blocked_frequency": governance_blocked_frequency,
            "stale_rfq_loss_rate": stale_loss_rate,
        },
        "conversion_rates": conversion_rates,
        "priority_groups": priority_groups,
        "overdue_reviews": safe_int(workflow.get("review_ready_pending", 0) + workflow.get("proof_capture_pending", 0)),
        "manual_review_frequency": manual_review_frequency,
        "governance_blocked_frequency": governance_blocked_frequency,
        "stale_rfq_loss_rate": stale_loss_rate,
    }

