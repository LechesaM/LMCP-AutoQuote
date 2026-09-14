from __future__ import annotations

import pytest

from app.governance.thazat import (
    build_outcome_learning,
    calculate_readiness,
    commercial_gate,
    evaluate_opportunity,
    run_red_team,
)


def test_commercial_gate_uses_25k_minimum() -> None:
    result = commercial_gate(estimated_profit=25_000, gross_margin_ratio=0.25)
    assert result["state"] == "PASS"
    assert result["minimum_profit"] == 25_000
    assert result["required_margin_percent"] == 25.0


def test_commercial_gate_escalates_sub_25k_case_to_35_percent() -> None:
    result = commercial_gate(estimated_profit=20_000, gross_margin_ratio=0.25)
    assert result["state"] == "REPRICE"
    assert result["requires_margin_escalation"] is True
    assert result["required_margin_percent"] == 35.0
    assert "MARGIN_ESCALATION_REQUIRED" in result["reason_codes"]


def test_go_triggers_supplier_outreach_when_quote_coverage_is_incomplete() -> None:
    assessment = evaluate_opportunity(
        {
            "eligibility_ok": True,
            "mandatory_evidence_obtainable": True,
            "delivery_ok": True,
            "supply_route_ok": True,
            "critical_information_complete": True,
            "estimated_profit": 40_000,
            "gross_margin_ratio": 0.30,
            "supplier_quotes_received": 1,
            "supplier_target": 3,
        }
    )
    assert assessment.decision.value == "GO"
    assert assessment.supplier_outreach_required is True
    assert "START_SUPPLIER_OUTREACH" in assessment.actions


def test_hard_governance_failure_is_no_go() -> None:
    assessment = evaluate_opportunity(
        {
            "eligibility_ok": False,
            "mandatory_evidence_obtainable": True,
            "delivery_ok": True,
            "supply_route_ok": True,
            "critical_information_complete": True,
            "estimated_profit": 50_000,
            "gross_margin_ratio": 0.30,
        }
    )
    assert assessment.decision.value == "NO_GO"
    assert "ELIGIBILITY_FAILED" in assessment.reason_codes


def test_unknown_or_recoverable_information_holds_instead_of_false_reject() -> None:
    assessment = evaluate_opportunity(
        {
            "eligibility_ok": True,
            "mandatory_evidence_obtainable": True,
            "delivery_ok": True,
            "supply_route_ok": False,
            "critical_information_complete": False,
            "estimated_profit": 20_000,
            "gross_margin_ratio": 0.25,
        }
    )
    assert assessment.decision.value == "HOLD"
    assert "SUPPLY_ROUTE_GAP" in assessment.reason_codes
    assert "COMMERCIAL_REPRICING_REQUIRED" in assessment.reason_codes


def test_blocker_requires_owner_and_deadline() -> None:
    with pytest.raises(ValueError, match="owner and due_at"):
        calculate_readiness(
            {
                "issues": [{"id": "B1", "title": "OEM letter", "status": "BLOCKER"}],
                "opportunity_decision": "GO",
            }
        )


def test_submission_ready_requires_full_evidence_red_team_and_no_blockers() -> None:
    readiness = calculate_readiness(
        {
            "requirements": [
                {"id": "R1", "description": "OEM letter", "mandatory": True, "status": "PROVEN"},
                {"id": "R2", "description": "Warranty", "mandatory": True, "status": "PROVEN"},
            ],
            "issues": [],
            "supplier_quotes_received": 3,
            "supplier_target": 3,
            "priced_items": 10,
            "total_items": 10,
            "completed_documents": 5,
            "required_documents": 5,
            "red_team_status": "PASSED",
            "opportunity_decision": "GO",
            "landed_cost": 300_000,
            "bid_price": 420_000,
        }
    )
    assert readiness.submission_ready is True
    assert readiness.execution_decision.value == "SUBMIT"
    assert readiness.blocker_count == 0
    assert readiness.mandatory_evidence_percent == 100.0
    assert readiness.overall_readiness_percent == 100.0
    assert readiness.expected_gp == 120_000.0


def test_red_team_failure_blocks_submission_gate() -> None:
    result = run_red_team(
        {
            "mandatory_documents": True,
            "signatures": True,
            "pricing_arithmetic": False,
            "technical_evidence": True,
        }
    )
    assert result["status"] == "FAILED"
    assert result["submission_gate_passed"] is False
    assert result["failed_checks"] == ["pricing_arithmetic"]


def test_outcome_learning_calculates_price_gap_and_signal() -> None:
    learning = build_outcome_learning(
        {
            "result": "LOST",
            "loss_reason": "PRICE",
            "bid_price": 425_000,
            "winning_price": 397_500,
        }
    ).as_dict()
    assert learning["price_delta_value"] == 27_500.0
    assert learning["price_delta_percent"] == 6.92
    assert "BID_PRICE_ABOVE_WINNER" in learning["signals"]
    assert "LOSS_REASON_PRICE" in learning["signals"]
