from __future__ import annotations

import json
from pathlib import Path

from app.api.operator_workflow_routes import router as operator_workflow_router
from app.qualification.qualification_engine import qualify_fixture
from app.services import submission_quality_service as quality_service
from app.testing.rfq_fixture_loader import load_fixture


def test_submission_quality_report_is_json_safe(monkeypatch) -> None:
    detail = {
        "tender_id": "RFQ-QUALITY-001",
        "title": "Office supplies",
        "buyer_name": "LMCP Buyer",
        "pricing_evidence": {"lines": [{"quantity": 2, "unit_price": 10, "line_total": 20}]},
    }

    monkeypatch.setattr(
        quality_service,
        "qualify_rfq",
        lambda payload: {
            "recommendation": "GO",
            "readiness_state": "READY",
            "submission_readiness": {"readiness_state": "READY", "go_candidate": True, "manual_only": False, "warnings": [], "next_operator_action": "go"},
            "viability": {"final_recommendation": "GO", "profit_gate": True, "margin_gate": True, "estimated_profit": 45000.0, "gross_margin_ratio": 0.3, "manual_pricing_review_required": False, "automation_suitability_score": 92.0},
            "classification": {"excluded_category": False},
            "compliance_matrix": {"blockers": [], "missing_required_count": 0, "items": []},
            "pricing_validation": {"validation_errors": [], "validation_warnings": [], "manual_review_required": False},
            "warnings": [],
            "blockers": [],
            "supplier_match_intelligence": {"supplier_match_score": 88.0},
            "supplier_domain": {"supplier_domain": "office_supplies"},
            "submission_method": {"method": "email"},
            "risk_level": "low",
            "manual_pricing_review_required": False,
            "supplier_match_score": 88.0,
        },
    )
    monkeypatch.setattr(
        quality_service,
        "attach_supplier_quotes_to_result",
        lambda payload: {
            "supplier_quotes_found": True,
            "supplier_quotes_count": 2,
            "supplier_responses_count": 2,
            "supplier_quote_files": ["quote-1.pdf", "quote-2.pdf"],
            "supplier_quote_comparison": {"recommended_supplier": {"supplier_name": "Seeded"}},
        },
    )
    monkeypatch.setattr(
        quality_service,
        "build_submission_package",
        lambda payload: {
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "quality_score": 91.5,
            "quality_status": "ready",
            "quality_notes": [],
            "warnings": [],
            "missing_artifacts": [],
            "download_url": "/download",
            "metadata_url": "/metadata",
            "quote_pack_pdf_path": "/tmp/quote-pack.pdf",
            "buyer_pricing_schedule_path": "/tmp/pricing.csv",
            "zip_path": "/tmp/quote-pack.zip",
            "source_quote_file_count": 2,
        },
    )
    monkeypatch.setattr(
        quality_service,
        "build_review_ready_bundle",
        lambda payload: {"review_ready": True, "submission_ready": True, "warnings": [], "operator_actions_count": 1, "audit_events_count": 2},
    )

    report = quality_service.build_submission_quality_report(detail)

    assert report["status"] == "healthy"
    assert report["summary"]["submission_ready"] is True
    assert report["package_preview"]["submission_ready"] is True
    assert report["supplier_verification_checks"]["supplier_quotes_found"] is True
    json.dumps(report, default=str)


def test_operator_workflow_router_exposes_submission_quality_route() -> None:
    paths = {route.path for route in operator_workflow_router.routes}
    assert "/operations/rfqs/{tender_id}/submission-quality" in paths


def test_submission_quality_report_handles_real_pilot_fixture(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(tmp_path / "monthly_quotes"))
    fixture = load_fixture(Path("/Users/cash/Documents/tests/fixtures/real_pilot_rfqs/real_pilot_valid_office_consumables_001.json"))
    rfq_record = fixture["rfq_record"]
    detail = {
        "tender_id": fixture["tender_id"],
        "title": rfq_record["title"],
        "buyer_name": rfq_record["buyer_name"],
        "province": rfq_record["province"],
        "category": rfq_record["category"],
        "pricing_evidence": {"lines": [{"quantity": 120, "unit_price": 12.5, "line_total": 1500}, {"quantity": 60, "unit_price": 15, "line_total": 900}]},
        "summary": {"title": rfq_record["title"], "buyer": rfq_record["buyer_name"], "province": rfq_record["province"]},
        "qualificationSummary": {
            "recommendation": "GO",
            "readiness_state": "READY",
            "submission_readiness": {"readiness_state": "READY", "go_candidate": True, "manual_only": False, "warnings": [], "next_operator_action": "proceed with governed approval steps"},
            "viability": {"final_recommendation": "GO", "profit_gate": True, "margin_gate": True, "estimated_profit": 45000.0, "gross_margin_ratio": 0.3, "manual_pricing_review_required": False, "automation_suitability_score": 92.0},
            "classification": {"excluded_category": False},
            "compliance_matrix": {"blockers": [], "missing_required_count": 0, "items": []},
            "pricing_validation": {"validation_errors": [], "validation_warnings": [], "manual_review_required": False},
            "warnings": [],
            "blockers": [],
            "supplier_match_intelligence": {"supplier_match_score": 88.0},
            "supplier_domain": {"supplier_domain": "office_supplies"},
            "submission_method": {"method": "email"},
            "risk_level": "low",
            "manual_pricing_review_required": False,
            "supplier_match_score": 88.0,
        },
        "qualification_summary": {
            "recommendation": "GO",
            "readiness_state": "READY",
            "submission_readiness": {"readiness_state": "READY", "go_candidate": True, "manual_only": False, "warnings": [], "next_operator_action": "proceed with governed approval steps"},
            "viability": {"final_recommendation": "GO", "profit_gate": True, "margin_gate": True, "estimated_profit": 45000.0, "gross_margin_ratio": 0.3, "manual_pricing_review_required": False, "automation_suitability_score": 92.0},
            "classification": {"excluded_category": False},
            "compliance_matrix": {"blockers": [], "missing_required_count": 0, "items": []},
            "pricing_validation": {"validation_errors": [], "validation_warnings": [], "manual_review_required": False},
            "warnings": [],
            "blockers": [],
            "supplier_match_intelligence": {"supplier_match_score": 88.0},
            "supplier_domain": {"supplier_domain": "office_supplies"},
            "submission_method": {"method": "email"},
            "risk_level": "low",
            "manual_pricing_review_required": False,
            "supplier_match_score": 88.0,
        },
    }

    monkeypatch.setattr(
        quality_service,
        "attach_supplier_quotes_to_result",
        lambda payload: {
            "supplier_quotes_found": True,
            "supplier_quotes_count": 2,
            "supplier_responses_count": 2,
            "supplier_quote_files": ["quote-1.pdf", "quote-2.pdf"],
            "supplier_quote_comparison": {"recommended_supplier": {"supplier_name": "Seeded"}},
        },
    )
    monkeypatch.setattr(
        quality_service,
        "build_review_ready_bundle",
        lambda payload: {"review_ready": True, "submission_ready": True, "warnings": [], "operator_actions_count": 1, "audit_events_count": 2},
    )
    monkeypatch.setattr(
        quality_service,
        "build_submission_package",
        lambda payload: {
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "quality_score": 91.5,
            "quality_status": "ready",
            "quality_notes": [],
            "warnings": [],
            "missing_artifacts": [],
            "download_url": "/download",
            "metadata_url": "/metadata",
            "quote_pack_pdf_path": "/tmp/quote-pack.pdf",
            "buyer_pricing_schedule_path": "/tmp/pricing.csv",
            "zip_path": "/tmp/quote-pack.zip",
            "source_quote_file_count": 2,
        },
    )
    report = quality_service.build_submission_quality_report(detail)

    assert report["tender_id"] == "REAL-PILOT-001"
    assert report["review_ready_bundle"]["review_ready"] is True
    assert report["package_preview"]["download_url"] == "/download"
    assert report["supplier_verification_checks"]["supplier_quotes_found"] is True
    json.dumps(report, default=str)


def test_submission_quality_report_handles_below_margin_fixture(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(tmp_path / "monthly_quotes"))

    fixture_path = Path("/Users/cash/Documents/tests/fixtures/real_pilot_rfqs/real_pilot_below_margin_005.json")
    fixture = load_fixture(fixture_path)
    rfq_record = fixture["rfq_record"]
    detail = {
        "tender_id": fixture["tender_id"],
        "title": rfq_record["title"],
        "buyer_name": rfq_record["buyer_name"],
        "province": rfq_record["province"],
        "category": rfq_record["category"],
        "pricing_evidence": {"lines": [{"quantity": 1, "unit_price": 10, "line_total": 10}]},
        "qualificationSummary": fixture.get("qualification_summary", {}),
        "qualification_summary": fixture.get("qualification_summary", {}),
        "summary": {"title": rfq_record["title"], "buyer": rfq_record["buyer_name"], "province": rfq_record["province"]},
    }

    monkeypatch.setattr(
        quality_service,
        "attach_supplier_quotes_to_result",
        lambda payload: {
            "supplier_quotes_found": False,
            "supplier_quotes_count": 0,
            "supplier_responses_count": 0,
            "supplier_quote_files": [],
            "supplier_quote_comparison": {},
        },
    )
    monkeypatch.setattr(
        quality_service,
        "build_review_ready_bundle",
        lambda payload: {"review_ready": False, "submission_ready": False, "warnings": ["manual review required"], "operator_actions_count": 0, "audit_events_count": 0},
    )
    monkeypatch.setattr(
        quality_service,
        "build_submission_package",
        lambda payload: {
            "package_status": "review_required",
            "approval_ready": False,
            "submission_ready": False,
            "quality_score": 42.0,
            "quality_status": "degraded",
            "quality_notes": ["below margin"],
            "warnings": ["below margin"],
            "missing_artifacts": ["pricing schedule"],
            "download_url": "/download",
            "metadata_url": "/metadata",
            "quote_pack_pdf_path": "/tmp/quote-pack.pdf",
            "buyer_pricing_schedule_path": "/tmp/pricing.csv",
            "zip_path": "/tmp/quote-pack.zip",
            "source_quote_file_count": 0,
        },
    )

    report = quality_service.build_submission_quality_report(detail)

    assert report["summary"]["recommendation"] == "REJECT"
    assert report["status"] in {"degraded", "failing"}
    assert report["package_preview"]["submission_ready"] is False
    assert report["supplier_verification_checks"]["supplier_quotes_found"] is False
    json.dumps(report, default=str)
