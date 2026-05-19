from __future__ import annotations

from typing import Any, Dict, List


def _recommend(action: str, reason: str, *, advisory_only: bool = True) -> Dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "advisory_only": advisory_only,
        "mutates_workflow": False,
    }


def generate_operator_recommendations(
    *,
    workflow_summary: Dict[str, Any] | None = None,
    quality_summary: Dict[str, Any] | None = None,
    queue_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    workflow_summary = workflow_summary or {}
    quality_summary = quality_summary or {}
    queue_summary = queue_summary or {}
    recommendations: List[Dict[str, Any]] = []
    next_action = "review workflow"
    current_blocker = ""
    required_step = "manual review"
    missing_artifacts: List[str] = []

    if workflow_summary.get("approvals_pending"):
        recommendations.append(_recommend("approve", "approval required before review-ready progression"))
        next_action = "approve"
        required_step = "approval"
        current_blocker = "approval pending"
    if workflow_summary.get("review_ready_pending"):
        recommendations.append(_recommend("review", "review-ready items require operator review"))
        next_action = "review"
        required_step = "review"
    if workflow_summary.get("proof_capture_pending"):
        recommendations.append(_recommend("capture proof", "proof capture must be recorded after review"))
        next_action = "capture proof"
        required_step = "proof capture"
    if workflow_summary.get("refused_workflows"):
        recommendations.append(_recommend("archive", "refused workflows may be archived by operator"))
        next_action = "archive"
        required_step = "archive"
        current_blocker = current_blocker or "refused workflow"

    missing_artifacts.extend(quality_summary.get("missing_artifacts", []))
    if missing_artifacts:
        recommendations.append(_recommend("rerun validation", "missing artifacts should be regenerated and rechecked"))
        current_blocker = current_blocker or "missing artifacts"
        next_action = "rerun validation"
        required_step = "validation rerun"

    if queue_summary.get("blocked_jobs") or queue_summary.get("retry_pending_jobs"):
        recommendations.append(_recommend("rerun validation", "queue backlog or blocked jobs need operator review"))

    if not recommendations:
        recommendations.append(_recommend("review workflow", "no immediate blocker identified"))

    return {
        "next_action_needed": next_action,
        "current_blocker": current_blocker,
        "required_operator_step": required_step,
        "missing_artifacts": list(dict.fromkeys(missing_artifacts)),
        "recommendations": recommendations,
        "advisory_only": True,
    }


def summarize_operator_next_steps(
    *,
    workflow_summary: Dict[str, Any] | None = None,
    quality_summary: Dict[str, Any] | None = None,
    queue_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return generate_operator_recommendations(
        workflow_summary=workflow_summary,
        quality_summary=quality_summary,
        queue_summary=queue_summary,
    )
