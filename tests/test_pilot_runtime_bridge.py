from __future__ import annotations

from app.api.operator_workflow_contracts import get_operator_workflow_detail
from app.services.submission_package_service import evaluate_submission_gate


def test_approved_pilot_workspace_promotes_runtime_submission_state() -> None:
    detail = get_operator_workflow_detail("018_QUOTE_-_Stationary_Extra")

    review_bundle = detail["review_ready_bundle"]
    submission_package = detail["submission_package"]
    governed_submission = detail["governed_submission"]
    submission_execution = detail["submission_execution"]
    gate = evaluate_submission_gate(detail)

    assert review_bundle["review_ready"] is True
    assert review_bundle["submission_ready"] is True
    assert submission_package["approval_ready"] is True
    assert submission_package["submission_ready"] is True
    assert submission_package["package_status"] == "ready"
    assert governed_submission["approvalReady"] is True
    assert governed_submission["submissionReady"] is True
    assert governed_submission["submissionLocked"] is True
    assert gate["allowed"] is True
    assert not gate["blocking_issues"]
    assert submission_execution["status"] in {"ok", "ready"}
