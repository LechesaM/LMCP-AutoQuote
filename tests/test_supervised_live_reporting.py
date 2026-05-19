from __future__ import annotations

from pathlib import Path

from app.dashboard import dashboard_service
from app.monitoring import reporting_service
from app.pilot import pilot_readiness_report


def _docs_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "docs"


def _canned_qualification() -> dict:
    return {
        "recommendation": "GO",
        "readiness_state": "READY",
        "supplier_match_score": 82.0,
        "supplier_evidence_score": 88.0,
        "pricing_confidence": {"overall_pricing_confidence": 91.0},
        "pricing_validation": {"validation_passed": True},
        "quote_aging": {"risk_level": "low"},
        "pricing_traceability_summary": {"quote_count": 1, "advisory_only": True},
        "manual_pricing_review_required": False,
        "stale_quote_warning": False,
        "manual_review_triggers": [],
        "detected_language_patterns": [],
        "next_operator_action": "proceed with governed approval steps",
        "risk_breakdown": {},
    }


def _sample_quality_context() -> dict:
    return {
        "rfq_payload": {
            "tender_id": "RFQ-U-001",
            "title": "Household products",
            "buyer_name": "IDT",
            "category": "household_products",
            "submission_instructions": "Submit by email to bids@example.com",
            "supplier_quote": {"supplier_name": "Sample Supplier"},
        },
        "quote_pack_payload": {"artifacts": []},
        "supplier_quotes": [{"supplier_name": "Sample Supplier"}],
        "schedule_payload": {"rows": []},
    }


def test_reporting_docs_capture_governance_preservation() -> None:
    docs = _docs_dir()
    governance_audit = (docs / "supervised_live_governance_audit.md").read_text(encoding="utf-8").lower()
    pilot_report = (docs / "supervised_live_pilot_execution_report.md").read_text(encoding="utf-8").lower()
    final_recommendation = (docs / "supervised_live_final_recommendation.md").read_text(encoding="utf-8").lower()

    assert "manual approval" in governance_audit
    assert "proof capture" in governance_audit
    assert "no autonomous submission" in governance_audit
    assert "manual-only" in pilot_report
    assert "no autonomous submission occurred" in pilot_report
    assert "conditional_go" in final_recommendation
    assert "human-governed" in final_recommendation
    assert "manual-only" in final_recommendation


def test_incident_and_pricing_confidence_reports_include_required_sections() -> None:
    docs = _docs_dir()
    incident = (docs / "supervised_live_incident_analysis.md").read_text(encoding="utf-8")
    pricing = (docs / "supervised_live_pricing_confidence_report.md").read_text(encoding="utf-8")
    batch1 = (docs / "supervised_live_batch1_summary.md").read_text(encoding="utf-8")
    batch2 = (docs / "supervised_live_batch2_summary.md").read_text(encoding="utf-8")

    assert "Extraction Incidents" in incident
    assert "Pricing Incidents" in incident
    assert "Supplier Pricing Issues" in incident
    assert "Pricing Confidence Averages" in pricing
    assert "Supplier Evidence Quality" in pricing
    assert "RFQ_001" in batch1
    assert "RFQ_003" in batch1
    assert "RFQ_004" in batch2
    assert "RFQ_005" in batch2


def test_pilot_and_dashboard_summaries_surface_supervised_live_fields(monkeypatch) -> None:
    sample_context = _sample_quality_context()
    canned_qualification = _canned_qualification()

    monkeypatch.setattr(pilot_readiness_report, "get_metrics_snapshot", lambda: {"metrics": {}})
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_summary", lambda limit=100: {})
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_failures", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_successes", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_runs", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_signoffs", lambda limit=100: [])
    monkeypatch.setattr(pilot_readiness_report, "build_quality_context", lambda limit=100: sample_context)
    monkeypatch.setattr(pilot_readiness_report, "build_quote_pack_quality_report", lambda payload: {"quality_score": 1.0})
    monkeypatch.setattr(pilot_readiness_report, "build_supplier_comparison_summary", lambda quotes: {
        "pricing_evidence_summary": {"quote_count": 1, "average_evidence_completeness": 95.0},
        "pricing_validation_summary": {"quote_count": 1},
        "pricing_traceability_summary": {"quote_count": 1},
        "quote_aging_summary": {"quote_count": 1},
        "pricing_confidence_summary": {"quote_count": 1},
    })
    monkeypatch.setattr(pilot_readiness_report, "qualify_rfq", lambda payload: canned_qualification)
    monkeypatch.setattr(pilot_readiness_report, "build_tender_success_analytics", lambda limit=100: {"quote_conversion_rate": 0.0})
    monkeypatch.setattr(pilot_readiness_report, "calculate_readiness_score", lambda: 100.0)
    monkeypatch.setattr(pilot_readiness_report, "calculate_success_rate", lambda: 1.0)
    monkeypatch.setattr(pilot_readiness_report, "get_pilot_execution_metadata", lambda: {"pilot_mode": "supervised_live", "pilot_enabled": True})

    pilot = pilot_readiness_report.build_pilot_readiness_report(limit=5)
    pilot_text = pilot_readiness_report.render_pilot_readiness_text(pilot)
    assert pilot["supervised_live_pilot_metrics"]["rfqs_processed"] == 0
    assert pilot["governance_audit_summary"]["no_autonomous_submission"] is True
    assert pilot["incident_summary"]["recovery_events"] == 0
    assert "Supervised-live RFQs processed" in pilot_text
    assert "Governance audit no autonomous submission" in pilot_text

    monkeypatch.setattr(dashboard_service, "build_quality_context", lambda limit=100: sample_context)
    monkeypatch.setattr(dashboard_service, "get_workflow_summary", lambda limit=100: {"stage_counts": {}, "approvals_pending": 0, "review_ready_pending": 0, "proof_capture_pending": 0})
    monkeypatch.setattr(dashboard_service, "get_queue_overview", lambda limit=100: {"summary": {}, "health": {}})
    monkeypatch.setattr(dashboard_service, "build_operational_report", lambda limit=100: {
        "runtime_diagnostics": {"warnings": []},
        "pilot": {
            "qualification_result": canned_qualification,
            "qualification_summary": {"recommendation_counts": {"GO": 1, "MANUAL_REVIEW": 0, "REJECT": 0}},
            "governance_compliance_score": 100.0,
            "manual_governance_integrity_score": 100.0,
            "supervised_live_governance_summary": {"manual_only_final_submission": True},
            "supervised_live_pilot_metrics": {"rfqs_processed": 5},
            "governance_audit_summary": {"no_autonomous_submission": True},
            "incident_summary": {"recovery_events": 0},
            "operational_reliability_summary": {"workflow_correctness_score": 100.0},
        },
        "metrics": {"metrics": {}},
        "system_health": {"status": "ok"},
        "supervised_live_pilot_metrics": {"rfqs_processed": 5},
        "governance_audit_summary": {"no_autonomous_submission": True},
        "incident_summary": {"recovery_events": 0},
        "operational_reliability_summary": {"workflow_correctness_score": 100.0},
        "supplier_pricing_summary": {
            "pricing_evidence_summary": {"quote_count": 1, "average_evidence_completeness": 95.0},
            "pricing_validation_summary": {"quote_count": 1},
            "pricing_traceability_summary": {"quote_count": 1},
            "quote_aging_summary": {"quote_count": 1},
            "pricing_confidence_summary": {"quote_count": 1},
        },
        "qualification_result": canned_qualification,
        "qualification_summary": {"recommendation_counts": {"GO": 1, "MANUAL_REVIEW": 0, "REJECT": 0}},
        "tender_success_analytics": {"quote_conversion_rate": 0.0},
        "operator_recommendations": {"advisory_only": True},
    })
    monkeypatch.setattr(dashboard_service, "build_tender_success_analytics", lambda limit=100: {"quote_conversion_rate": 0.0})
    monkeypatch.setattr(dashboard_service, "build_pilot_readiness_report", lambda limit=100: {
        "pilot_readiness_score": 100.0,
        "governance_compliance_score": 100.0,
        "manual_governance_integrity_score": 100.0,
        "supervised_live_governance_summary": {"manual_only_final_submission": True},
        "supervised_live_pilot_metrics": {"rfqs_processed": 5},
        "governance_audit_summary": {"no_autonomous_submission": True},
        "incident_summary": {"recovery_events": 0},
        "operational_reliability_summary": {"workflow_correctness_score": 100.0},
        "warnings": [],
        "quality_summary": {"supplier_pricing": {"pricing_evidence_summary": {"quote_count": 1}}},
        "qualification_result": canned_qualification,
        "qualification_summary": {"recommendation_counts": {"GO": 1, "MANUAL_REVIEW": 0, "REJECT": 0}},
    })
    monkeypatch.setattr(dashboard_service, "get_pilot_metrics", lambda: {})
    monkeypatch.setattr(dashboard_service, "build_rfq_extraction_quality_report", lambda payload: {})
    monkeypatch.setattr(dashboard_service, "build_pricing_schedule_quality_report", lambda payload: {})
    monkeypatch.setattr(dashboard_service, "build_quote_pack_quality_report", lambda payload: {"quality_score": 1.0})
    monkeypatch.setattr(dashboard_service, "build_supplier_comparison_summary", lambda quotes: {
        "pricing_evidence_summary": {"quote_count": 1, "average_evidence_completeness": 95.0},
        "pricing_validation_summary": {"quote_count": 1},
        "pricing_traceability_summary": {"quote_count": 1},
        "quote_aging_summary": {"quote_count": 1},
        "pricing_confidence_summary": {"quote_count": 1},
    })
    monkeypatch.setattr(dashboard_service, "qualify_rfq", lambda payload: canned_qualification)
    monkeypatch.setattr(dashboard_service, "generate_operator_recommendations", lambda **kwargs: {"advisory_only": True})
    monkeypatch.setattr(dashboard_service, "get_persistence_health", lambda: {})
    monkeypatch.setattr(dashboard_service, "get_recent_refusals", lambda limit=25: [])

    dashboard = dashboard_service.get_dashboard_summary(limit=5)
    assert dashboard["supervised_live_pilot_metrics"]["rfqs_processed"] == 5
    assert dashboard["governance_audit_summary"]["no_autonomous_submission"] is True
    assert dashboard["incident_summary"]["recovery_events"] == 0
    assert dashboard["operational_reliability_summary"]["workflow_correctness_score"] == 100.0
    assert dashboard["pricing_evidence_summary"]["quote_count"] == 1

    monkeypatch.setattr(reporting_service, "get_metrics_snapshot", lambda: {"metrics": {}})
    monkeypatch.setattr(reporting_service, "build_pilot_readiness_report", lambda limit=100: {
        "pilot_mode": {"pilot_mode": "supervised_live"},
        "pilot_metrics": {},
        "pilot_failures": [],
        "pilot_readiness_score": 100.0,
        "quality_summary": {"supplier_pricing": {"pricing_evidence_summary": {"quote_count": 1}}},
        "qualification_result": canned_qualification,
        "qualification_summary": {"recommendation_counts": {"GO": 1, "MANUAL_REVIEW": 0, "REJECT": 0}},
        "governance_compliance_score": 100.0,
        "manual_governance_integrity_score": 100.0,
        "supervised_live_governance_summary": {"manual_only_final_submission": True},
        "supervised_live_pilot_metrics": {"rfqs_processed": 5},
        "governance_audit_summary": {"no_autonomous_submission": True},
        "incident_summary": {"recovery_events": 0},
        "operational_reliability_summary": {"workflow_correctness_score": 100.0},
    })
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
    monkeypatch.setattr(reporting_service, "build_supplier_comparison_summary", lambda quotes: {
        "pricing_evidence_summary": {"quote_count": 1, "average_evidence_completeness": 95.0},
        "pricing_validation_summary": {"quote_count": 1},
        "pricing_traceability_summary": {"quote_count": 1},
        "quote_aging_summary": {"quote_count": 1},
        "pricing_confidence_summary": {"quote_count": 1},
    })

    operational = reporting_service.build_operational_report(limit=5)
    operational_text = reporting_service.render_operational_report_text(operational)
    assert operational["supervised_live_pilot_metrics"]["rfqs_processed"] == 5
    assert operational["governance_audit_summary"]["no_autonomous_submission"] is True
    assert operational["incident_summary"]["recovery_events"] == 0
    assert operational["operational_reliability_summary"]["workflow_correctness_score"] == 100.0
    assert "Supervised-live RFQs processed" in operational_text
    assert "Governance audit no autonomous submission" in operational_text
    assert "advisory only" in operational_text.lower()
