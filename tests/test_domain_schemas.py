from __future__ import annotations

from app.domain.audit import AuditActor, AuditEvent, AuditSeverity
from app.domain.pricing import PricingDecision
from app.domain.rfq import RFQDocument, RFQLineItem, RFQRecord
from app.domain.submission import ApprovalRecord, SubmissionProof, SubmissionReview
from app.domain.workflow import WorkflowStage


def test_valid_rfq_record() -> None:
    record = RFQRecord(
        tender_id="RFQ-001",
        buyer_name="Buyer",
        title="Supply and delivery of office chairs",
        documents=[RFQDocument(name="rfq.pdf", source_path="runtime/rfq.pdf")],
        line_items=[RFQLineItem(description="Office chair", quantity=10, unit="each")],
        eligible_for_quoting=True,
        extraction_confidence=0.91,
    )
    payload = record.to_jsonable_dict()
    assert payload["tender_id"] == "RFQ-001"
    assert payload["documents"][0]["name"] == "rfq.pdf"


def test_exclusion_detection_representation() -> None:
    record = RFQRecord(
        tender_id="RFQ-002",
        detected_exclusions=["medical consumables", "catering"],
        eligible_for_quoting=False,
    )
    assert record.detected_exclusions == ["medical consumables", "catering"]
    assert record.eligible_for_quoting is False


def test_pricing_decision_passes_minimum_thresholds() -> None:
    decision = PricingDecision(
        tender_id="RFQ-003",
        quantity=100,
        unit_cost=1000,
        gross_margin_ratio=0.30,
        profit_amount=50000,
    )
    assert decision.passes_thresholds() is True
    assert decision.refusal_blocker_reasons == []


def test_pricing_decision_refuses_below_threshold() -> None:
    decision = PricingDecision(
        tender_id="RFQ-004",
        quantity=10,
        unit_cost=100,
        gross_margin_ratio=0.10,
        profit_amount=1000,
    )
    assert decision.passes_thresholds() is False
    assert "minimum profit R30,000 not met" in decision.refusal_blocker_reasons
    assert "minimum supply margin 25% not met" in decision.refusal_blocker_reasons


def test_submission_review_requires_manual_approval_state_fields() -> None:
    approval = ApprovalRecord(
        tender_id="RFQ-005",
        tender_root="/tmp/rfq-005",
        manual_approval_recorded=True,
        approved_by_operator=True,
        submission_ready=True,
        final_submission_attempted=False,
        status="recorded",
    )
    review = SubmissionReview(
        tender_id="RFQ-005",
        tender_root="/tmp/rfq-005",
        submission_review_ready=True,
        approval_record_present=True,
        final_submission_still_false=True,
        submission_ready=True,
        final_submission_attempted=False,
        approval_record=approval,
        status="review_ready",
    )
    assert review.approval_record is not None
    assert review.approval_record.manual_approval_recorded is True
    assert review.final_submission_attempted is False


def test_submission_proof_preserves_final_submission_attempted_false() -> None:
    proof = SubmissionProof(
        tender_id="RFQ-006",
        tender_root="/tmp/rfq-006",
        portal_name="eTenders",
        submission_reference="SUB-123",
        submitted_by="Operator",
        manual_submission_recorded=True,
        final_submission_attempted=False,
        status="recorded",
    )
    assert proof.final_submission_attempted is False


def test_workflow_stage_enum_values() -> None:
    assert WorkflowStage.DISCOVERED.value == "discovered"
    assert WorkflowStage.REVIEW_READY.value == "review_ready"
    assert WorkflowStage.PROOF_RECORDED.value == "proof_recorded"


def test_audit_event_serialization() -> None:
    event = AuditEvent(
        actor=AuditActor(actor_type="operator", actor_id="op-1", display_name="Operator 1"),
        action="submission_review_completed",
        tender_id="RFQ-007",
        workflow_stage=WorkflowStage.REVIEW_READY,
        severity=AuditSeverity.SUCCESS,
        details={"status": "review_ready"},
    )
    payload = event.to_jsonable_dict()
    assert payload["actor"]["actor_id"] == "op-1"
    assert payload["workflow_stage"] == "review_ready"
    assert payload["severity"] == "success"


def test_json_dump_compatibility() -> None:
    review = SubmissionReview(
        tender_id="RFQ-008",
        tender_root="/tmp/rfq-008",
        submission_review_ready=False,
        review_blockers=["manual approval record missing"],
        status="refused",
    )
    payload = review.to_jsonable_dict()
    assert isinstance(payload, dict)
    assert payload["review_blockers"] == ["manual approval record missing"]
