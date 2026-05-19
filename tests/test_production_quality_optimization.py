from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.analytics.tender_success_analytics import TenderOutcomeStatus, build_tender_success_analytics, record_tender_outcome
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.dashboard import dashboard_service
from app.domain.workflow import WorkflowStage
from app.pilot import build_pilot_readiness_report, get_pilot_metrics, record_pilot_run, record_signoff
from app.pilot.pilot_metrics import reset_pilot_metrics
from app.persistence import db as persistence_db
from app.persistence.repositories import reset_persistence_health
from app.quality.extraction_quality import assess_rfq_extraction_quality
from app.quality.operator_recommendations import generate_operator_recommendations
from app.quality.pricing_schedule_quality import assess_pricing_schedule_quality
from app.quality.quote_pack_quality import assess_quote_pack_quality
from app.quality.supplier_pricing_quality import assess_supplier_pricing_quality, build_supplier_comparison_summary
from app.services import audit_trail_service


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "rfqs"


def _prepare_runtime(monkeypatch, tmp_path: Path, pilot_mode: str = "supervised_live") -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audit_trail").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_PILOT_MODE", pilot_mode)
    monkeypatch.setenv("LMCP_OBSERVABILITY_ENABLED", "1")

    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    reset_pilot_metrics()
    reset_persistence_health()
    persistence_db._INITIALIZED = False
    persistence_db._INITIALIZED_PATH = None

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    monkeypatch.setattr(workflow_state_engine, "_emit_audit_event", lambda **_: None)

    monkeypatch.setattr(audit_trail_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", runtime_dir / "audit_trail")
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", runtime_dir / "audit_trail" / "audit_events.json")
    audit_trail_service.AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    async def _noop_publish_dashboard_event(**_: object) -> None:
        return None

    monkeypatch.setattr(audit_trail_service, "publish_dashboard_event", _noop_publish_dashboard_event)
    return runtime_dir


def _seed_quality_workflow() -> None:
    rfq_payload = {
        "tender_id": "Q-001",
        "title": "Supply and Delivery of Office Consumables",
        "buyer_name": "City of Example",
        "province": "Gauteng",
        "category": "supply and delivery",
        "closing_date": "2026-12-31T12:00:00+00:00",
        "line_items": [{"description": "Paper", "quantity": 10, "unit": "Box"}],
    }
    schedule_payload = {
        "completed_buyer_schedule_path": "/tmp/schedule.xlsx",
        "rows": [
            {
                "item_description": "Paper",
                "quantity": 10,
                "unit": "Box",
                "unit_price": 100.0,
                "total": 1000.0,
                "vat_applicable": True,
                "vat_amount": 150.0,
                "delivery_applicable": True,
                "delivery_cost": 50.0,
            }
        ],
    }
    quote_pack_payload = {
        "tender_id": "Q-001",
        "generated_pdf_path": "/tmp/Q-001__quote_pack.pdf",
        "generated_json_path": "/tmp/Q-001__quote_pack.json",
        "completed_buyer_schedule_path": schedule_payload["completed_buyer_schedule_path"],
        "company_details_present": True,
        "buyer_details_present": True,
        "tender_reference_present": True,
        "pricing_schedule_present": True,
        "vat_treatment_shown": True,
        "validity_period_present": True,
        "delivery_terms_present": True,
        "signature_placeholder_present": True,
        "artifacts": [
            {"artifact_type": "pdf", "path": "/tmp/Q-001__quote_pack.pdf", "present": True},
            {"artifact_type": "json", "path": "/tmp/Q-001__quote_pack.json", "present": True},
        ],
    }
    supplier_quotes = [
        {
            "supplier_name": "Supplier A",
            "quote_reference": "A-001",
            "vat_registered": True,
            "lines": [
                {
                    "description": "Paper",
                    "quantity": 10,
                    "unit_price": 100.0,
                    "delivery_cost": 50.0,
                    "vat_amount": 150.0,
                }
            ],
        }
    ]

    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.DISCOVERED,
        WorkflowStage.EXTRACTED,
        "tester",
        "extract",
        {"rfq_record": rfq_payload},
    )
    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.EXTRACTED,
        WorkflowStage.EVALUATED,
        "tester",
        "evaluate",
        {"rfq_record": rfq_payload},
    )
    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.EVALUATED,
        WorkflowStage.PRICED,
        "tester",
        "price",
        {"buyer_pricing_schedule_completion": schedule_payload},
    )
    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.PRICED,
        WorkflowStage.QUOTE_GENERATED,
        "tester",
        "quote",
        {"quote_pack": quote_pack_payload, "supplier_quotes": supplier_quotes},
    )
    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        "tester",
        "approval required",
        {"quote_pack": quote_pack_payload},
    )
    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.APPROVAL_REQUIRED,
        WorkflowStage.APPROVED,
        "tester",
        "approved",
        {"quote_pack": quote_pack_payload},
    )
    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.APPROVED,
        WorkflowStage.REVIEW_READY,
        "tester",
        "review ready",
        {"quote_pack": quote_pack_payload},
    )
    workflow_state_engine.record_transition(
        "Q-001",
        WorkflowStage.REVIEW_READY,
        WorkflowStage.PROOF_RECORDED,
        "tester",
        "proof recorded",
        {"quote_pack": quote_pack_payload},
    )


def test_rfq_extraction_score_and_warnings() -> None:
    payload = json.loads((FIXTURES_DIR / "messy_missing_fields_rfq.json").read_text(encoding="utf-8"))
    report = assess_rfq_extraction_quality(payload)

    assert report["extraction_quality_score"] < 1
    assert "missing buyer" in report["warnings"]
    assert "missing closing date" in report["warnings"]
    assert "missing line items" in report["warnings"]
    assert "ambiguous category" in report["warnings"]


def test_exclusion_confidence_detects_briefing_requirement() -> None:
    payload = json.loads((FIXTURES_DIR / "ambiguous_category_rfq.json").read_text(encoding="utf-8"))
    report = assess_rfq_extraction_quality(payload)

    assert report["exclusion_confidence"] >= 0.4
    assert "possible briefing requirement" in report["warnings"]
    assert "compulsory briefing sessions" in report["detected_exclusions"]


def test_pricing_schedule_completion_score() -> None:
    payload = json.loads((FIXTURES_DIR / "incomplete_schedule_rfq.json").read_text(encoding="utf-8"))
    report = assess_pricing_schedule_quality(payload["buyer_pricing_schedule"])

    assert report["completion_score"] < 1
    assert report["missing_fields"]
    assert report["warnings"]
    assert report["buyer_pricing_schedule_completion"]["completed"] is False


def test_quote_pack_readiness_score() -> None:
    report = assess_quote_pack_quality(
        {
            "tender_id": "Q-QUOTE-001",
            "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "company_contact_person": "Operator",
            "company_email": "ops@example.com",
            "company_phone": "+27-11-000-0000",
            "buyer_name": "City of Example",
            "tender_reference": "Q-QUOTE-001",
            "pricing_schedule_path": "/tmp/Q-QUOTE-001__buyer_pricing_schedule.csv",
            "generated_pdf_path": "/tmp/Q-QUOTE-001__quote_pack.pdf",
            "generated_json_path": "/tmp/Q-QUOTE-001__quote_pack.json",
            "completed_buyer_schedule_path": "/tmp/Q-QUOTE-001__buyer_pricing_schedule.csv",
            "manifest_path": "/tmp/Q-QUOTE-001__quote_pack_manifest.json",
            "validity_days": 30,
            "delivery_terms": "Standard delivery terms apply.",
            "vat_treatment": "VAT included at 15%",
            "company_details_present": True,
            "buyer_details_present": True,
            "tender_reference_present": True,
            "pricing_schedule_present": True,
            "vat_treatment_shown": True,
            "validity_period_present": True,
            "delivery_terms_present": True,
            "signature_placeholder_present": True,
            "artifacts": [
                {"artifact_type": "pdf", "path": "/tmp/Q-QUOTE-001__quote_pack.pdf", "present": True},
                {"artifact_type": "json", "path": "/tmp/Q-QUOTE-001__quote_pack.json", "present": True},
                {"artifact_type": "manifest", "path": "/tmp/Q-QUOTE-001__quote_pack_manifest.json", "present": True},
            ],
        }
    )

    assert report["quality_score"] >= 0.8
    assert report["quote_pack"]["quote_pack_ready"] is True
    assert report["missing_artifacts"] == []


def test_quote_pack_missing_fields_emit_warnings() -> None:
    report = assess_quote_pack_quality(
        {
            "tender_id": "Q-QUOTE-002",
            "generated_pdf_path": "",
            "generated_json_path": "",
            "completed_buyer_schedule_path": "",
            "manifest_path": "",
            "artifacts": [],
        }
    )

    assert report["quality_score"] < 0.8
    assert "missing_company_details" in report["warnings"]
    assert "missing_buyer_details" in report["warnings"]
    assert "missing_tender_reference" in report["warnings"]
    assert "missing_pricing_schedule" in report["warnings"]
    assert "missing_vat_treatment" in report["warnings"]
    assert "missing_validity_period" in report["warnings"]
    assert "missing_delivery_terms" in report["warnings"]
    assert "missing_signature_placeholder" in report["warnings"]
    assert "missing_artifacts" in report["warnings"]


def test_supplier_price_anomaly_detection_and_comparison_summary() -> None:
    report = assess_supplier_pricing_quality(
        {
            "supplier_quotes": [
                {
                    "supplier_name": "Supplier Low",
                    "quote_reference": "LOW-001",
                    "vat_registered": None,
                    "lines": [
                        {
                            "description": "Paper",
                            "quantity": 10,
                            "unit_price": 0,
                            "delivery_cost": 0,
                            "vat_amount": 0,
                        }
                    ],
                },
                {
                    "supplier_name": "Supplier High",
                    "quote_reference": "HIGH-001",
                    "vat_registered": True,
                    "lines": [
                        {
                            "description": "Paper",
                            "quantity": 10,
                            "unit_price": 1000,
                            "delivery_cost": 100,
                            "vat_amount": 150,
                        }
                    ],
                },
            ]
        }
    )

    assert report["comparison_rows"][0]["anomalies"]
    assert report["supplier_comparison_summary"]["quote_count"] == 2
    assert report["supplier_comparison_summary"]["recommended_supplier"]["supplier_name"] in {"Supplier Low", "Supplier High"}
    assert build_supplier_comparison_summary(report["comparison_rows"])["supplier_comparison_summary"]["quote_count"] == 2


def test_operator_recommendations_do_not_mutate_workflow(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    workflow_state_engine.record_transition("Q-RECO-001", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "tester", "extract", {})
    before = workflow_state_engine.get_current_state("Q-RECO-001").stage

    recommendations = generate_operator_recommendations(
        workflow_summary={"approvals_pending": 1, "review_ready_pending": 1, "proof_capture_pending": 1, "refused_workflows": 1},
        quality_summary={"missing_artifacts": ["quote_pack_pdf"]},
        queue_summary={"blocked_jobs": 1},
    )

    after = workflow_state_engine.get_current_state("Q-RECO-001").stage

    assert before == after
    assert recommendations["advisory_only"] is True
    assert all(not item["mutates_workflow"] for item in recommendations["recommendations"])


def test_tender_outcome_status_tracking(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    record_tender_outcome(
        {
            "tender_id": "OUT-001",
            "workflow_stage": "proof_recorded",
            "operator": "Operator A",
            "outcome_status": TenderOutcomeStatus.SUBMITTED,
            "quote_generated": True,
            "reviewed": True,
            "proof_captured": True,
            "submitted_manually": True,
            "manual_intervention": True,
            "blocked": False,
            "blockers": [],
        }
    )
    record_tender_outcome(
        {
            "tender_id": "OUT-002",
            "workflow_stage": "proof_recorded",
            "operator": "Operator A",
            "outcome_status": TenderOutcomeStatus.AWARDED,
            "quote_generated": True,
            "reviewed": True,
            "proof_captured": True,
            "submitted_manually": True,
            "manual_intervention": False,
            "blocked": False,
            "blockers": [],
        }
    )
    record_tender_outcome(
        {
            "tender_id": "OUT-003",
            "workflow_stage": "refused",
            "operator": "Operator A",
            "outcome_status": TenderOutcomeStatus.LOST,
            "quote_generated": False,
            "reviewed": False,
            "proof_captured": False,
            "submitted_manually": False,
            "manual_intervention": True,
            "blocked": True,
            "blockers": ["excluded category"],
        }
    )

    report = build_tender_success_analytics(limit=20)

    assert report["tender_outcome_summary"]["processed"] == 3
    assert report["tender_outcome_summary"]["submitted_manually"] == 2
    assert report["tender_outcome_summary"]["won"] == 1
    assert report["tender_outcome_summary"]["lost"] == 1
    assert report["refusal_rate"] > 0
    assert report["quote_conversion_rate"] > 0


def test_dashboard_includes_quality_summaries(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_quality_workflow()

    summary = dashboard_service.get_dashboard_summary(limit=50)

    assert "quality_summary" in summary
    assert "rfq_extraction" in summary["quality_summary"]
    assert "quote_pack" in summary["quality_summary"]
    assert summary["quality_summary"]["quote_pack"]["quality_score"] > 0
    assert summary["operator_recommendations"]["advisory_only"] is True


def test_pilot_report_includes_quality_analytics(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_quality_workflow()
    record_pilot_run(
        {
            "tender_id": "PILOT-Q-001",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Pilot Operator",
            "actor": "Pilot Operator",
            "outcome": "completed",
            "status": "recorded",
            "proof_confirmed": True,
        }
    )
    record_signoff(
        {
            "tender_id": "PILOT-Q-001",
            "workflow_stage": "approval_required",
            "signoff_type": "approval",
            "signoff_status": "signed",
            "operator": "Pilot Operator",
            "actor": "Pilot Operator",
            "note": "pilot signoff",
        }
    )
    record_tender_outcome(
        {
            "tender_id": "PILOT-Q-001",
            "workflow_stage": "proof_recorded",
            "operator": "Pilot Operator",
            "outcome_status": TenderOutcomeStatus.SUBMITTED,
            "quote_generated": True,
            "reviewed": True,
            "proof_captured": True,
            "submitted_manually": True,
            "manual_intervention": True,
            "blocked": False,
            "blockers": [],
        }
    )

    report = build_pilot_readiness_report(limit=50)

    assert "quality_summary" in report
    assert "tender_success_analytics" in report
    assert report["quality_summary"]["quality_score"] > 0
    assert report["tender_success_analytics"]["quote_conversion_rate"] >= 0
    assert get_pilot_metrics()["rfqs_processed"] == 1
