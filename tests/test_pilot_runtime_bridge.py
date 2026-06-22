from __future__ import annotations

from app.api.operator_workflow_contracts import get_operator_workflow_detail
from app.services.submission_package_service import evaluate_submission_gate


def test_pilot_workspace_exposes_blocked_submission_pack_when_compliance_docs_are_missing() -> None:
    detail = get_operator_workflow_detail("018_QUOTE_-_Stationary_Extra")

    review_bundle = detail["review_ready_bundle"]
    submission_package = detail["submission_package"]
    submission_pack = detail["submission_pack"]
    governed_submission = detail["governed_submission"]
    submission_execution = detail["submission_execution"]
    gate = evaluate_submission_gate(detail)

    assert submission_package["approval_ready"] is False
    assert submission_package["submission_ready"] is False
    assert submission_package["package_status"] == "blocked"
    assert submission_pack["status"] == "blocked"
    assert submission_pack["approval_ready"] is False
    assert submission_pack["submission_ready"] is False
    assert submission_pack["blocking_codes"] == [
        "missing_tax_compliance",
        "missing_company_registration",
        "missing_bbbee",
        "missing_bank_confirmation",
    ]
    assert governed_submission["approvalReady"] is True
    assert governed_submission["submissionReady"] is True
    assert governed_submission["submissionLocked"] is True
    assert gate["allowed"] is False
    assert gate["blocking_issues"] == submission_pack["blocking_codes"]
    assert gate["submission_ready"] is False
    assert submission_execution["status"] in {"ok", "ready"}
