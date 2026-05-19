from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.dashboard import dashboard_service
from app.monitoring import reporting_service
from app.pilot import pilot_readiness_report
from app.pricing_evidence import (
    assess_pricing_confidence,
    assess_quote_aging,
    build_pricing_traceability,
    build_supplier_quote_evidence,
    build_supplier_quote_evidence_summary,
    validate_pricing_evidence,
)
from app.qualification.qualification_engine import qualify_rfq
from app.quality.supplier_pricing_quality import assess_supplier_pricing_quality


def _sample_quote(**overrides):
    base = {
        "supplier_name": "Sample Supplier",
        "supplier_contact": "sample@example.com",
        "quote_reference": "SQ-001",
        "quote_received_date": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "quote_valid_until": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "quotation_source_type": "emailed quote",
        "delivery_assumptions": ["delivery included"],
        "vat_clarity": "VAT included at 15%",
        "stock_availability_notes": ["in stock"],
        "lead_time_notes": ["5 days"],
        "lines": [
            {"description": "Item A", "quantity": 2, "unit_price": 100.0, "delivery_cost": 20.0, "vat_amount": 18.0, "line_total": 238.0},
        ],
        "subtotal": 200.0,
        "vat_total": 18.0,
        "delivery_total": 20.0,
        "total": 238.0,
    }
    base.update(overrides)
    return base


def _sample_quality_context():
    return {
        "rfq_payload": {
            "tender_id": "RFQ-EVIDENCE",
            "title": "Household products",
            "buyer_name": "IDT",
            "category": "household_products",
            "submission_instructions": "Submit by email to bids@example.com",
            "estimated_profit": 55000.0,
            "gross_margin_ratio": 0.32,
            "supplier_quote": _sample_quote(),
        },
        "quote_pack_payload": {"artifacts": []},
        "supplier_quotes": [_sample_quote()],
        "schedule_payload": {"rows": []},
    }


def test_supplier_evidence_completeness_scoring() -> None:
    evidence = build_supplier_quote_evidence(_sample_quote())

    assert evidence["evidence_completeness_score"] > 80
    assert evidence["pricing_defensibility_score"] >= 70
    assert not evidence["evidence_warnings"]


def test_manual_estimated_pricing_lowers_confidence() -> None:
    payload = _sample_quote(quotation_source_type="estimated/manual", vat_clarity="", delivery_assumptions=[])
    evidence = build_supplier_quote_evidence(payload)
    validation = validate_pricing_evidence(payload)
    aging = assess_quote_aging(payload)
    confidence = assess_pricing_confidence(payload, evidence_report=evidence, validation_report=validation, quote_aging_report=aging)

    assert "estimated or manual pricing lowers confidence" in evidence["evidence_warnings"]
    assert confidence["overall_pricing_confidence"] < 80


def test_missing_vat_and_delivery_warnings() -> None:
    evidence = build_supplier_quote_evidence(_sample_quote(vat_clarity="", delivery_assumptions=[]))

    assert "missing VAT clarity lowers confidence" in evidence["evidence_warnings"]
    assert "missing delivery assumptions lowers confidence" in evidence["evidence_warnings"]


def test_pricing_validation_catches_common_errors() -> None:
    validation = validate_pricing_evidence(
        {
            "lines": [
                {"description": "Item A", "quantity": 1, "unit_price": 0.0, "vat_amount": 0.0, "delivery_cost": 0.0, "line_total": 0.0},
                {"description": "Item B", "quantity": 1, "unit_price": -10.0, "vat_amount": 0.0, "delivery_cost": 0.0, "line_total": -10.0},
            ],
            "subtotal": 100.0,
            "vat_total": 10.0,
            "delivery_total": 5.0,
            "total": 200.0,
        }
    )

    assert validation["manual_review_required"] is True
    assert "zero price" in validation["validation_errors"]
    assert "negative price" in validation["validation_errors"]
    assert "subtotal mismatch" in validation["validation_errors"]
    assert "VAT mismatch" in validation["validation_errors"]


def test_stale_quote_detection_and_expired_high_risk() -> None:
    stale = assess_quote_aging(_sample_quote(quote_received_date=(datetime.now(timezone.utc) - timedelta(days=45)).isoformat()))
    expired = assess_quote_aging(_sample_quote(quote_valid_until=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()))

    assert stale["aging_severity"] in {"medium", "high"}
    assert "stale pricing warning" in stale["stale_pricing_warnings"]
    assert expired["risk_level"] == "HIGH_RISK"
    assert "expired quote" in expired["stale_pricing_warnings"]


def test_pricing_traceability_generation() -> None:
    payload = _sample_quote()
    evidence = build_supplier_quote_evidence(payload)
    validation = validate_pricing_evidence(payload)
    aging = assess_quote_aging(payload)
    traceability = build_pricing_traceability(payload, evidence_report=evidence, validation_report=validation, quote_aging_report=aging)

    assert traceability["traceability_chain"]
    assert traceability["pricing_traceability_summary"]["append_only_friendly"] is True
    assert "audit_friendly_summary" in traceability


def test_supplier_evidence_summary_generation() -> None:
    summary = build_supplier_quote_evidence_summary([_sample_quote(), _sample_quote(quote_reference="SQ-002", quotation_source_type="phone confirmation")])

    assert summary["quote_count"] == 2
    assert summary["average_evidence_completeness"] > 0
    assert isinstance(summary["supplier_evidence_gaps"], dict)


def test_supplier_pricing_quality_surfaces_evidence_summaries() -> None:
    report = assess_supplier_pricing_quality({"supplier_quotes": [_sample_quote()]})

    assert report["pricing_evidence_summary"]["quote_count"] == 1
    assert report["pricing_validation_summary"]["quote_count"] == 1
    assert report["pricing_traceability_summary"]["quote_count"] == 1
    assert report["quote_aging_summary"]["quote_count"] == 1
    assert report["pricing_confidence_summary"]["quote_count"] == 1


def test_dashboard_reporting_and_pilot_surface_evidence_summaries(monkeypatch) -> None:
    sample_context = _sample_quality_context()
    canned_qualification = {
        "recommendation": "GO",
        "readiness_state": "READY",
        "supplier_match_score": 82.0,
        "supplier_evidence_score": 88.0,
        "pricing_confidence": {"overall_pricing_confidence": 91.0},
        "pricing_validation": {"validation_passed": True},
        "quote_aging": {"stale_pricing_warnings": []},
        "pricing_traceability_summary": {"quote_count": 1, "advisory_only": True},
        "manual_pricing_review_required": False,
        "stale_quote_warning": False,
        "manual_review_triggers": [],
        "detected_language_patterns": [],
        "next_operator_action": "proceed with governed approval steps",
        "risk_breakdown": {},
    }

    monkeypatch.setattr(dashboard_service, "build_quality_context", lambda limit=100: sample_context)
    monkeypatch.setattr(dashboard_service, "get_workflow_summary", lambda limit=100: {"stage_counts": {}, "approvals_pending": 0, "review_ready_pending": 0, "proof_capture_pending": 0})
    monkeypatch.setattr(dashboard_service, "get_queue_overview", lambda limit=100: {"summary": {}, "health": {}})
    monkeypatch.setattr(dashboard_service, "build_operational_report", lambda limit=100: {"runtime_diagnostics": {"warnings": []}, "pilot": {"qualification_result": canned_qualification, "qualification_summary": {"recommendation_counts": {"GO": 1, "MANUAL_REVIEW": 0, "REJECT": 0}}, "governance_compliance_score": 100.0, "manual_governance_integrity_score": 100.0, "supervised_live_governance_summary": {}}, "metrics": {"metrics": {}}, "system_health": {"status": "ok"}})
    monkeypatch.setattr(dashboard_service, "build_tender_success_analytics", lambda limit=100: {"quote_conversion_rate": 0.0})
    monkeypatch.setattr(dashboard_service, "build_pilot_readiness_report", lambda limit=100: {"pilot_readiness_score": 100.0, "governance_compliance_score": 100.0, "manual_governance_integrity_score": 100.0, "supervised_live_governance_summary": {}, "warnings": [], "quality_summary": {"supplier_pricing": {"pricing_evidence_summary": {"quote_count": 1}, "pricing_validation_summary": {"quote_count": 1}, "pricing_traceability_summary": {"quote_count": 1}, "quote_aging_summary": {"quote_count": 1}, "pricing_confidence_summary": {"quote_count": 1}}}, "qualification_result": canned_qualification, "qualification_summary": {"recommendation_counts": {"GO": 1, "MANUAL_REVIEW": 0, "REJECT": 0}}})
    monkeypatch.setattr(dashboard_service, "get_pilot_metrics", lambda: {})
    monkeypatch.setattr(dashboard_service, "build_rfq_extraction_quality_report", lambda payload: {})
    monkeypatch.setattr(dashboard_service, "build_pricing_schedule_quality_report", lambda payload: {})
    monkeypatch.setattr(dashboard_service, "build_quote_pack_quality_report", lambda payload: {"quality_score": 1.0})
    monkeypatch.setattr(dashboard_service, "build_supplier_comparison_summary", lambda quotes: assess_supplier_pricing_quality({"supplier_quotes": quotes}))
    monkeypatch.setattr(dashboard_service, "qualify_rfq", lambda payload: canned_qualification)
    monkeypatch.setattr(dashboard_service, "generate_operator_recommendations", lambda **kwargs: {"advisory_only": True})
    monkeypatch.setattr(dashboard_service, "get_persistence_health", lambda: {})
    monkeypatch.setattr(dashboard_service, "get_recent_refusals", lambda limit=25: [])

    dashboard = dashboard_service.get_dashboard_summary(limit=5)
    assert dashboard["pricing_evidence_summary"]["quote_count"] == 1
    assert dashboard["pricing_validation_summary"]["quote_count"] == 1
    assert dashboard["pricing_traceability_summary"]["quote_count"] == 1
    assert dashboard["qualification_result"]["manual_pricing_review_required"] is False

    monkeypatch.setattr(reporting_service, "get_metrics_snapshot", lambda: {"metrics": {}})
    monkeypatch.setattr(reporting_service, "build_pilot_readiness_report", lambda limit=100: {"pilot_mode": {"pilot_mode": "supervised_live"}, "pilot_metrics": {}, "pilot_failures": [], "pilot_readiness_score": 100.0, "quality_summary": {"supplier_pricing": {"pricing_evidence_summary": {"quote_count": 1}, "pricing_validation_summary": {"quote_count": 1}, "pricing_traceability_summary": {"quote_count": 1}, "quote_aging_summary": {"quote_count": 1}, "pricing_confidence_summary": {"quote_count": 1}}}, "qualification_result": canned_qualification, "qualification_summary": {"recommendation_counts": {"GO": 1, "MANUAL_REVIEW": 0, "REJECT": 0}}, "governance_compliance_score": 100.0, "manual_governance_integrity_score": 100.0, "supervised_live_governance_summary": {}})
    monkeypatch.setattr(reporting_service, "build_tender_success_analytics", lambda limit=100: {"quote_conversion_rate": 0.0})
    monkeypatch.setattr(reporting_service, "build_quality_context", lambda limit=100: sample_context)
    monkeypatch.setattr(reporting_service, "build_quote_pack_quality_report", lambda payload: {"quality_score": 1.0})
    monkeypatch.setattr(reporting_service, "qualify_rfq", lambda payload: canned_qualification)
    monkeypatch.setattr(reporting_service, "generate_operator_recommendations", lambda **kwargs: {"advisory_only": True})
    monkeypatch.setattr(reporting_service, "get_system_health", lambda: {"status": "ok"})
    monkeypatch.setattr(reporting_service, "find_stuck_workflows", lambda stuck_after_minutes=240, limit=100: [])
    monkeypatch.setattr(reporting_service, "find_invalid_workflows", lambda limit=100: [])
    monkeypatch.setattr(reporting_service, "get_workflow_summary", lambda limit=100: {})
    monkeypatch.setattr(reporting_service, "get_persistence_health", lambda: {})
    monkeypatch.setattr(reporting_service, "get_runtime_diagnostics", lambda: {"warnings": []})

    operational = reporting_service.build_operational_report(limit=5)
    assert operational["pricing_evidence_summary"]["quote_count"] == 1
    assert operational["pricing_validation_summary"]["quote_count"] == 1
    assert operational["pricing_traceability_summary"]["quote_count"] == 1

    monkeypatch.setattr(pilot_readiness_report, "get_metrics_snapshot", lambda: {"metrics": {}})
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_summary", lambda limit=100: {})
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_failures", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_successes", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_runs", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_signoffs", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "build_quality_context", lambda limit=100: sample_context)
    monkeypatch.setattr(pilot_readiness_report, "build_quote_pack_quality_report", lambda payload: {"quality_score": 1.0})
    monkeypatch.setattr(pilot_readiness_report, "build_supplier_comparison_summary", lambda quotes: assess_supplier_pricing_quality({"supplier_quotes": quotes}))
    monkeypatch.setattr(pilot_readiness_report, "qualify_rfq", lambda payload: canned_qualification)
    monkeypatch.setattr(pilot_readiness_report, "build_tender_success_analytics", lambda limit=100: {"quote_conversion_rate": 0.0})
    monkeypatch.setattr(pilot_readiness_report, "calculate_readiness_score", lambda: 100.0)
    monkeypatch.setattr(pilot_readiness_report, "calculate_success_rate", lambda: 1.0)
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_execution_metadata", lambda: {"pilot_mode": "supervised_live", "pilot_enabled": True})

    pilot = pilot_readiness_report.build_pilot_readiness_report(limit=5)
    assert pilot["pricing_evidence_summary"]["quote_count"] == 1
    assert pilot["pricing_validation_summary"]["quote_count"] == 1
    assert pilot["pricing_traceability_summary"]["quote_count"] == 1


def test_no_workflow_bypass_or_autonomous_submission() -> None:
    result = qualify_rfq(
        {
            "tender_id": "RFQ-NO-AUTO",
            "title": "Household products",
            "buyer_name": "IDT",
            "category": "household_products",
            "submission_instructions": "Submit by email to bids@example.com",
            "estimated_profit": 55000.0,
            "gross_margin_ratio": 0.32,
            "pricing_evidence": _sample_quote(quotation_source_type="estimated/manual"),
        }
    )

    assert result["manual_pricing_review_required"] is True
    assert "autonomous" not in " ".join(result.get("warnings", [])).lower()
    assert result["pricing_traceability_summary"]["advisory_only"] is True
