from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api import operator_workflow_contracts as contracts
from app.api import operator_workflow_routes
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.auth.auth_service import authenticate_user, require_permission
from app.domain.workflow import WorkflowStage
from app.harvest.source_health import record_failure, record_success
from app.harvest.source_registry import load_source_registry
from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import dispatch_operator_action
from app.services import live_rfq_store
from app.services.external_audit_export_service import build_external_audit_export_report
from app.services.governed_submission_service import record_governance_decision
from app.services.demo_live_rfq_seed import seed_demo_live_rfq_bundle_if_empty
from app.services.submission_execution_service import record_submission_execution
from app.services.submission_reconciliation_service import reconcile_submission_execution
from app.services.submission_receipt_verification_service import build_signed_receipt_verification_report
from app.services.submission_package_service import evaluate_submission_gate
from app.main import app
from app.persistence.repositories import WorkflowRepository


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
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
    monkeypatch.setenv("LMCP_OBSERVABILITY_ENABLED", "1")
    monkeypatch.setenv("LMCP_AUTH_ALLOW_DEMO_USERS", "1")
    monkeypatch.setenv("LMCP_AUTH_REQUIRED", "1")
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "0")
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    monkeypatch.setattr(workflow_state_engine, "_emit_audit_event", lambda **_: None)


def _request_with_token(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))],
        "client": ("testclient", 1234),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _seed_runtime() -> None:
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.QUOTE_GENERATED, WorkflowStage.APPROVAL_REQUIRED, "op", "approval required")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "op", "approved")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.APPROVED, WorkflowStage.REVIEW_READY, "op", "review ready")

    workflow_state_engine.record_transition("T-OPS-2", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-OPS-2", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-OPS-2", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.refuse_workflow("T-OPS-3", actor="op", reason="manual review", details={"reason": "manual review required"})

    registry = load_source_registry()
    registry.add_source(
        {
            "id": "ops-source-1",
            "name": "Operations Source 1",
            "entity_type": "municipality",
            "source_tier": "tier_1",
            "base_url": "https://example.org/one",
            "harvest_url": "https://example.org/one/listing",
            "parser_type": "html",
            "province": "Gauteng",
            "is_active": True,
            "requires_browser": False,
            "requires_login": False,
        }
    )
    record_success("ops-source-1", response_time_seconds=0.16)
    record_failure("ops-source-1", parser_failure=True)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _seed_persisted_artifacts(tmp_path: Path) -> None:
    manual_dir = tmp_path / "runtime" / "manual_production"

    review_dir = manual_dir / "review_ready_bundles" / "T-OPS-1"
    review_live_rfq = {
        "rfqId": "T-OPS-1",
        "reference": "T-OPS-1",
        "title": "Supply and Delivery of Office Consumables",
        "buyer": "Metro Procurement Unit",
        "province": "Gauteng",
        "submissionType": "email",
        "sourceName": "Live Portal",
        "sourceUrl": "https://example.org/tenders/one",
        "documentUrls": ["https://example.org/tenders/one/rfq.pdf"],
    }
    review_comparison = {
        "comparison_status": "ready",
        "supplier_quote_count": 2,
        "supplier_quotes": [
            {"supplier_name": "Acme Office Supplies", "quote_reference": "ACME-001", "quoted_total": 125000.0, "stored_filename": "Acme_Office_Supplies_quote.txt"},
            {"supplier_name": "Bright Stationers", "quote_reference": "BRIGHT-002", "quoted_total": 118000.0, "stored_filename": "Bright_Stationers_quote.txt"},
        ],
        "recommended_supplier": {"supplier_name": "Bright Stationers", "quote_reference": "BRIGHT-002", "quoted_total": 118000.0},
        "runner_up_supplier": {"supplier_name": "Acme Office Supplies", "quote_reference": "ACME-001", "quoted_total": 125000.0},
        "estimated_savings_vs_runner_up": 7000.0,
        "buyer_item_count": 12,
    }
    _write_json(
        review_dir / "review_ready_quote_pack.json",
        {
            "created_at": "2026-05-22T08:37:48.977175+00:00",
            "tender_id": "T-OPS-1",
            "bundle_status": "ready",
            "review_ready": True,
            "submission_ready": True,
            "operator_actions_count": 0,
            "audit_events_count": 2,
            "operator_actions": [],
            "audit_events": [],
            "live_rfq": review_live_rfq,
            "quote_comparison": review_comparison,
            "traceability_bundle": {
                "tender_id": "T-OPS-1",
                "summary": {"buyer": "Metro Procurement Unit", "province": "Gauteng"},
                "live_rfq": review_live_rfq,
                "supplier_quote_comparison": review_comparison,
                "pricing_evidence": {"evidence_completeness_score": 1.0},
                "pricing_traceability": {"traceability_chain": ["harvested", "compared", "packaged"]},
            },
        },
    )
    _write_json(
        review_dir / "review_ready_quote_pack_manifest.json",
        {
            "created_at": "2026-05-22T08:37:48.977175+00:00",
            "tender_id": "T-OPS-1",
            "bundle_status": "ready",
            "review_ready": True,
            "submission_ready": True,
            "operator_actions_count": 0,
            "audit_events_count": 2,
            "files": [],
        },
    )
    _write_json(review_dir / "traceability_bundle.json", {"live_rfq": review_live_rfq, "supplier_quote_comparison": review_comparison})
    _write_json(review_dir / "audit_export.json", [])
    _write_json(review_dir / "operator_actions.json", [])

    package_dir = manual_dir / "submission_packages" / "T-OPS-1"
    quote_pack_pdf = package_dir / "T-OPS-1__quote_pack.pdf"
    quote_pack_json = package_dir / "T-OPS-1__quote_pack.json"
    buyer_schedule = package_dir / "T-OPS-1__buyer_pricing_schedule.csv"
    quote_pack_manifest = package_dir / "T-OPS-1__quote_pack_manifest.json"
    submission_manifest = package_dir / "T-OPS-1__submission_package_manifest.json"
    submission_zip = package_dir / "T-OPS-1__submission_package.zip"
    for file_path in (quote_pack_pdf, quote_pack_json, buyer_schedule, quote_pack_manifest, submission_manifest):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}", encoding="utf-8")
    with zipfile.ZipFile(submission_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("T-OPS-1__quote_pack.pdf", "pdf")
        archive.writestr("T-OPS-1__quote_pack.json", "{}")
        archive.writestr("T-OPS-1__buyer_pricing_schedule.csv", "supplier_name,quote_reference,quoted_total\nBright Stationers,BRIGHT-002,118000.0\n")
        archive.writestr("T-OPS-1__quote_pack_manifest.json", "{}")
    _write_json(
        quote_pack_json,
        {
            "tender_id": "T-OPS-1",
            "created_at": "2026-05-22T08:37:50.778962+00:00",
            "summary": {"buyer": "Metro Procurement Unit", "province": "Gauteng", "title": "Supply and Delivery of Office Consumables"},
            "review_ready_bundle": {"review_ready": True, "submission_ready": True},
            "harvest_enrichment": {"live_rfq": review_live_rfq, "supplier_quote_comparison": review_comparison},
            "quote_comparison": review_comparison,
            "quality_report": {"quality_score": 1.0, "status": "healthy", "quality_notes": [], "warnings": [], "missing_artifacts": []},
            "source_quote_entries": [{"source": "monthly_quotes/one", "status": "copied", "copied_to": str(package_dir / "source_quotes" / "Acme_Office_Supplies_quote.txt")}],
            "package": {"package_status": "ready", "approval_ready": True, "submission_ready": True, "quality_score": 1.0},
        },
    )
    _write_json(
        quote_pack_manifest,
        {
            "created_at": "2026-05-22T08:37:50.778962+00:00",
            "tender_id": "T-OPS-1",
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "quality_score": 1.0,
            "quality_status": "healthy",
            "quality_notes": [],
            "warnings": [],
            "files": [],
        },
    )
    _write_json(
        submission_manifest,
        {
            "created_at": "2026-05-22T08:37:50.778962+00:00",
            "tender_id": "T-OPS-1",
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "download_url": "/operations/rfqs/T-OPS-1/submission-package/download",
            "quote_pack_pdf_path": str(quote_pack_pdf),
            "quote_pack_json_path": str(quote_pack_json),
            "buyer_pricing_schedule_path": str(buyer_schedule),
            "quote_pack_manifest_path": str(quote_pack_manifest),
            "zip_path": str(submission_zip),
            "source_quote_entries": [{"source": "monthly_quotes/one", "status": "copied", "copied_to": str(package_dir / "source_quotes" / "Acme_Office_Supplies_quote.txt")}],
            "review_ready_bundle": {"review_ready": True, "submission_ready": True},
            "quote_pack_quality": {"quality_score": 1.0, "status": "healthy", "quality_notes": [], "warnings": [], "missing_artifacts": []},
        },
    )

    governed_dir = manual_dir / "governed_submissions" / "T-OPS-1"
    _write_json(governed_dir / "approval_chain.json", [
        {"stage_id": "operator_review", "label": "Operator Review", "sequence": 1, "status": "completed", "completed": True, "blockers": [], "requires_manual_review": False},
        {"stage_id": "quality_signoff", "label": "Quality Sign-off", "sequence": 2, "status": "completed", "completed": True, "blockers": [], "requires_manual_review": False},
        {"stage_id": "supervisor_approval", "label": "Supervisor Approval", "sequence": 3, "status": "completed", "completed": True, "blockers": [], "requires_manual_review": True},
        {"stage_id": "submission_authorization", "label": "Submission Authorization", "sequence": 4, "status": "completed", "completed": True, "blockers": [], "requires_manual_review": True},
    ])
    _write_json(governed_dir / "approval_signature.json", {"signature_status": "completed", "signed_at": "2026-05-22T08:37:52.790165+00:00", "signature_hash": "abc123", "signature_payload": {"tender_id": "T-OPS-1"}})
    _write_json(governed_dir / "deadline_orchestration.json", {"status": "unknown", "closing_at": "", "hours_remaining": None, "days_remaining": None, "urgency": "unknown", "next_action": "confirm deadline before submission", "deadline_blockers": ["deadline unknown"]})
    _write_json(governed_dir / "evidence_integrity_hashes.json", {"bundle_hash": "bundle-123", "ledger_hash": "ledger-123"})
    _write_json(governed_dir / "audit_replay_timeline.json", [])
    governed_dir.joinpath("immutable_audit_ledger.jsonl").write_text("", encoding="utf-8")

    monthly_root = tmp_path / "monthly_quotes"
    quote_folder = monthly_root / "2026-05" / "T-OPS-1__LMCP-T-OPS-1"
    quote_folder.mkdir(parents=True, exist_ok=True)
    _write_json(
        quote_folder / "quote_comparison.json",
        {
            "rfq_number": "T-OPS-1",
            "lmcp_quote_number": "LMCP-T-OPS-1",
            "comparison_status": "ready",
            "supplier_quote_count": 2,
            "suppliers": [
                {"supplier_name": "Acme Office Supplies", "quote_reference": "ACME-001", "quoted_total": 125000.0},
                {"supplier_name": "Bright Stationers", "quote_reference": "BRIGHT-002", "quoted_total": 118000.0},
            ],
            "recommended_supplier": {"supplier_name": "Bright Stationers", "quote_reference": "BRIGHT-002", "quoted_total": 118000.0},
            "runner_up_supplier": {"supplier_name": "Acme Office Supplies", "quote_reference": "ACME-001", "quoted_total": 125000.0},
            "estimated_savings_vs_runner_up": 7000.0,
            "buyer_item_count": 12,
        },
    )
    (quote_folder / "Acme_Office_Supplies_quote.txt").write_text("Acme quote", encoding="utf-8")
    (quote_folder / "Bright_Stationers_quote.txt").write_text("Bright quote", encoding="utf-8")

    proof_log = manual_dir / "submission_proofs.jsonl"
    proof_record = {
        "tender_id": "T-OPS-1",
        "tender_root": str(manual_dir / "submission_executions" / "T-OPS-1"),
        "portal_name": "Live Portal",
        "submission_reference": "T-OPS-1__submission__20260522T083800Z",
        "submitted_by": "op-1",
        "status": "recorded",
        "timestamp": "2026-05-22T08:38:00+00:00",
        "submission_execution_status": "executed",
        "execution_state": "executed",
        "portal_adapter": "email_submission_adapter",
        "portal_submission_state": "assisted_required",
        "route_classification": {
            "status": "assisted_required",
            "portal_result": {
                "submission_method": "email",
                "portal_name": "Live Portal",
                "portal_url": "https://example.org/tenders/one",
            },
        },
        "receipt_json_path": str(manual_dir / "submission_executions" / "T-OPS-1" / "receipt.json"),
        "receipt_txt_path": str(manual_dir / "submission_executions" / "T-OPS-1" / "receipt.txt"),
        "receipt_pdf_path": str(manual_dir / "submission_executions" / "T-OPS-1" / "receipt.pdf"),
        "proof_json_path": str(manual_dir / "submission_executions" / "T-OPS-1" / "submission_execution_proof_record.json"),
        "proof_txt_path": str(manual_dir / "submission_executions" / "T-OPS-1" / "submission_execution_proof_record.txt"),
        "receipt_signature": {
            "status": "ok",
            "receipt_hash": "receipt-hash-1",
            "signature": "signature-1",
            "algorithm": "HMAC-SHA256",
        },
    }
    proof_log.write_text(json.dumps(proof_record) + "\n", encoding="utf-8")
    for path in (Path(proof_record["receipt_json_path"]), Path(proof_record["receipt_txt_path"]), Path(proof_record["receipt_pdf_path"]), Path(proof_record["proof_json_path"]), Path(proof_record["proof_txt_path"])):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")


def test_operator_workflow_routes_are_registered_and_have_expected_methods() -> None:
    routes = [route for route in operator_workflow_routes.router.routes if route.path.startswith("/operations/")]
    methods_by_path = {}
    for route in routes:
        methods_by_path.setdefault(route.path, set()).update(route.methods or set())
    expected_paths = {
        "/operations/rfqs",
        "/operations/rfqs/{tender_id}",
        "/operations/rfqs/{tender_id}/submission-package",
        "/operations/rfqs/{tender_id}/submission-package/generate",
        "/operations/rfqs/{tender_id}/submission-package/download",
        "/operations/rfqs/{tender_id}/governance-envelope",
        "/operations/rfqs/{tender_id}/governance-decision",
        "/operations/rfqs/{tender_id}/submission-execution",
        "/operations/rfqs/{tender_id}/submission-execution/enqueue",
        "/operations/rfqs/{tender_id}/submission-execution/receipt-verification",
        "/operations/rfqs/{tender_id}/submission-execution/reconcile",
        "/operations/rfqs/{tender_id}/submission-execution/external-audit-export",
        "/operations/rfqs/{tender_id}/submission-execution/external-audit-export/download",
        "/operations/qualification-insights",
        "/operations/pricing-evidence",
        "/operations/source-health-details",
    }

    assert expected_paths <= set(methods_by_path)
    assert methods_by_path["/operations/rfqs/{tender_id}/governance-decision"] == {"POST"}
    assert methods_by_path["/operations/rfqs/{tender_id}/submission-package/generate"] == {"POST"}
    assert methods_by_path["/operations/rfqs/{tender_id}/submission-execution"] == {"GET", "POST"}
    assert methods_by_path["/operations/rfqs/{tender_id}/submission-execution/enqueue"] == {"POST"}
    assert methods_by_path["/operations/rfqs/{tender_id}/submission-execution/reconcile"] == {"POST"}
    assert all(
        methods == {"GET"}
        for path, methods in methods_by_path.items()
        if path not in {
            "/operations/rfqs/{tender_id}/governance-decision",
            "/operations/rfqs/{tender_id}/submission-package/generate",
            "/operations/rfqs/{tender_id}/submission-execution",
            "/operations/rfqs/{tender_id}/submission-execution/enqueue",
            "/operations/rfqs/{tender_id}/submission-execution/reconcile",
        }
    )


def test_operator_workflow_contracts_return_json_safe_payloads(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()

    payloads = [
        contracts.get_operator_workflow_rows(),
        contracts.get_operator_workflow_detail("T-OPS-1"),
        contracts.get_qualification_insights(),
        contracts.get_pricing_evidence_overview(),
        contracts.get_source_health_details(),
    ]

    for payload in payloads:
        json.dumps(payload, default=str)
        assert payload["generated_at"]
        assert payload["data_source"]

    assert payloads[0]["rows"]
    assert payloads[1]["tender_id"] == "T-OPS-1"
    assert payloads[0]["rows"][0]["submission_readiness"]
    assert payloads[1]["submission_readiness"]


def test_missing_runtime_data_returns_safe_fallback(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("runtime unavailable")

    monkeypatch.setattr(contracts, "get_live_rfqs", _raise)

    assert contracts.get_operator_workflow_rows()["data_source"] == "fallback"
    assert contracts.get_operator_workflow_detail("missing")["data_source"] == "fallback"
    assert contracts.get_qualification_insights()["data_source"] == "fallback"
    assert contracts.get_pricing_evidence_overview()["data_source"] == "fallback"
    assert contracts.get_source_health_details()["data_source"] == "fallback"


def test_fallback_detail_ids_are_seed_hydrated(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    for tender_id in ("fallback-1", "REAL-PILOT-001", "RFQ-VALID-001"):
        payload = contracts.get_operator_workflow_detail(tender_id)

        assert payload["data_source"] in {"seed_fixture", "runtime", "fallback"}
        assert payload["data_source_label"] in {"seed_fixture", "runtime / live_harvested", "fallback", "runtime"}
        if payload["data_source"] != "fallback":
            assert payload["summary"]["title"]
            assert payload["tender_id"] != "fallback-1"
            assert payload["summary"]["title"] != "Unknown RFQ"
            assert payload["workflow_history"]
            assert payload["recommendation_reasons"]
            assert payload["source_health"]


def test_operator_workflow_detail_includes_live_harvest_enrichment(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()

    live_store_path = tmp_path / "runtime" / "live_rfqs.json"
    live_store_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "updated_at": "2026-05-21T00:00:00+00:00",
                "count": 1,
                "items": [
                    {
                        "rfq_id": "T-OPS-1",
                        "title": "Supply and Delivery of Office Consumables",
                        "buyer_name": "Metro Procurement Unit",
                        "province": "Gauteng",
                        "category": "Office Consumables",
                        "submission_type": "email",
                        "source_name": "Live Portal",
                        "source_url": "https://example.org/tenders/one",
                        "document_urls": ["https://example.org/tenders/one/rfq.pdf"],
                        "created_at": "2026-05-20T00:00:00+00:00",
                        "updated_at": "2026-05-21T00:00:00+00:00",
                        "raw": {
                            "rfq_id": "T-OPS-1",
                            "title": "Supply and Delivery of Office Consumables",
                            "buyer_name": "Metro Procurement Unit",
                            "province": "Gauteng",
                            "source_url": "https://example.org/tenders/one",
                            "document_urls": ["https://example.org/tenders/one/rfq.pdf"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", live_store_path)

    payload = contracts.get_operator_workflow_detail("T-OPS-1")

    enrichment = payload["harvest_enrichment"]
    assert enrichment["matched"] is True
    assert enrichment["live_rfq"]["reference"] == "T-OPS-1"
    assert enrichment["live_rfq"]["title"] == "Supply and Delivery of Office Consumables"
    assert enrichment["live_rfq"]["buyer"] == "Metro Procurement Unit"
    assert enrichment["live_rfq"]["documentCount"] == 1
    assert enrichment["source_mode"] == "live_harvested"


def test_operator_workflow_detail_hydrates_persisted_artifacts_without_rebuild(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()
    _seed_persisted_artifacts(tmp_path)
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))

    live_store_path = tmp_path / "runtime" / "live_rfqs.json"
    live_store_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "updated_at": "2026-05-21T00:00:00+00:00",
                "count": 1,
                "items": [
                    {
                        "rfq_id": "T-OPS-1",
                        "title": "Supply and Delivery of Office Consumables",
                        "buyer_name": "Metro Procurement Unit",
                        "province": "Gauteng",
                        "category": "Office Consumables",
                        "submission_type": "email",
                        "source_name": "Live Portal",
                        "source_url": "https://example.org/tenders/one",
                        "document_urls": ["https://example.org/tenders/one/rfq.pdf"],
                        "created_at": "2026-05-20T00:00:00+00:00",
                        "updated_at": "2026-05-21T00:00:00+00:00",
                        "raw": {
                            "rfq_id": "T-OPS-1",
                            "title": "Supply and Delivery of Office Consumables",
                            "buyer_name": "Metro Procurement Unit",
                            "province": "Gauteng",
                            "source_url": "https://example.org/tenders/one",
                            "document_urls": ["https://example.org/tenders/one/rfq.pdf"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", live_store_path)

    monkeypatch.setattr(contracts, "build_review_ready_bundle", lambda *_: (_ for _ in ()).throw(AssertionError("bundle rebuild should not run")))
    monkeypatch.setattr(contracts, "build_submission_package", lambda *_: (_ for _ in ()).throw(AssertionError("package rebuild should not run")))
    monkeypatch.setattr(contracts, "build_governed_submission_envelope", lambda *_: (_ for _ in ()).throw(AssertionError("governed rebuild should not run")))

    payload = contracts.get_operator_workflow_detail("T-OPS-1")

    assert payload["summary"]["buyer"] == "Metro Procurement Unit"
    assert payload["summary"]["province"] == "Gauteng"
    assert payload["harvest_enrichment"]["matched"] is True
    assert payload["harvest_enrichment"]["supplier_quote_comparison"]
    assert payload["review_ready_bundle"]["review_ready"] is True
    assert payload["review_ready_bundle"]["submission_ready"] is True
    assert payload["submission_package"]["approval_ready"] is True
    assert payload["submission_package"]["submission_ready"] is True
    assert payload["submission_readiness"]["readiness_state"] in {"READY", "HIGH_RISK", "MANUAL_ONLY", "MISSING_DOCS"}
    assert payload["governed_submission"]["approvalReady"] is True
    assert payload["governed_submission"]["submissionReady"] is True
    assert payload["submission_execution"]["execution_status"] == "executed"
    assert payload["submission_execution"]["portal_name"] == "Live Portal"
    assert payload["submission_execution"]["receipt_json_path"]
    assert payload["submission_execution"]["receipt_hash"]
    assert payload["submission_execution"]["current_execution"]["receipt_signature"]["status"] == "ok"


def test_operator_workflow_contracts_do_not_mutate_state(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()

    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    before = repo.fetch_recent(limit=50)

    responses = [
        operator_workflow_routes.list_rfqs(),
        operator_workflow_routes.get_rfq_detail("T-OPS-1"),
        operator_workflow_routes.qualification_insights(),
        operator_workflow_routes.pricing_evidence(),
        operator_workflow_routes.source_health_details(),
    ]
    for response in responses:
        json.dumps(response, default=str)

    after = repo.fetch_recent(limit=50)
    assert after == before


def test_operator_workflow_http_detail_is_sanitized(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    payload = {
        "status": "ok",
        "summary": {"title": "Large RFQ", "buyer": "Metro Procurement Unit"},
        "qualification_summary": {
            "readiness_state": "READY",
            "classification": {
                "text": "X" * 10000,
                "language_intelligence": {"text": "Y" * 10000, "score": 1.0},
            },
        },
        "harvest_enrichment": {
            "live_rfq": {
                "title": "Large RFQ",
                "extractedText": "A" * 10000,
                "sourceText": "B" * 10000,
                "notes": "C" * 10000,
                "submission_type": "email",
            }
        },
        "review_ready_bundle": {
            "live_rfq": {
                "extractedText": "D" * 10000,
                "sourceText": "E" * 10000,
                "notes": "F" * 10000,
            }
        },
    }
    monkeypatch.setattr(
        operator_workflow_routes,
        "get_operator_workflow_http_detail",
        lambda tender_id: contracts._trim_http_workflow_detail(payload),
    )

    sanitized = operator_workflow_routes.get_rfq_detail("T-OPS-1")
    text = json.dumps(sanitized, default=str)

    assert "extractedText" not in text
    assert "sourceText" not in text
    assert "notes" not in text
    assert "language_intelligence" in sanitized["qualification_summary"]["classification"]
    assert "text" not in sanitized["qualification_summary"]["classification"]
    assert len(text.encode("utf-8")) < 5000


def test_demo_live_rfq_seed_populates_live_store_and_quote_context(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(tmp_path / "monthly_quotes"))

    live_store_path = tmp_path / "runtime" / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", live_store_path)

    report = seed_demo_live_rfq_bundle_if_empty()
    assert report["status"] == "seeded"
    assert report["live_count"] == 1

    live_store = live_rfq_store.get_live_rfqs()
    assert live_store["count"] == 1

    payload = contracts.get_operator_workflow_detail("REAL-PILOT-001")
    assert payload["submission_readiness"]["readiness_state"] == "MANUAL_ONLY"
    assert payload["submission_readiness"]["approval_ready"] is False
    assert payload["submission_readiness"]["submission_ready"] is False
    assert payload["submission_package"]["approval_ready"] is False
    assert payload["submission_package"]["submission_ready"] is False
    enrichment = payload["harvest_enrichment"]
    assert enrichment["matched"] is True
    assert enrichment["supplier_quotes_found"] is True
    assert enrichment["supplierQuoteCount"] == 2
    assert enrichment["supplierQuoteComparisonStatus"] == "ready"
    assert enrichment["estimatedSavingsVsRunnerUp"] == 2750.0
    assert enrichment["live_rfq"]["title"] == "Supply and Delivery of Office Consumables"
    assert "REAL-PILOT-001" in str(enrichment["supplier_quotes_folder"])


def test_demo_live_rfq_seed_refreshes_existing_store_entry(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(tmp_path / "monthly_quotes"))

    live_store_path = tmp_path / "runtime" / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", live_store_path)

    stale_live_rfq = {
        "rfq_id": "REAL-PILOT-001",
        "buyer_rfq_number": "REAL-PILOT-001",
        "title": "Supply and Delivery of Office Consumables",
        "submission_type": "email",
        "submission_instructions": "Submit by email with missing docs.",
        "documents": [],
        "extracted_text": "SBD4 missing",
        "source_text": "SBD4 missing",
    }
    live_rfq_store.save_live_rfqs([stale_live_rfq])

    report = seed_demo_live_rfq_bundle_if_empty()
    assert report["status"] == "seeded"
    assert report["existing_live_count"] == 1
    assert report["live_count"] == 1

    payload = contracts.get_operator_workflow_detail("REAL-PILOT-001")
    assert payload["submission_readiness"]["readiness_state"] == "MANUAL_ONLY"
    assert payload["submission_readiness"]["approval_ready"] is False
    assert payload["submission_readiness"]["submission_ready"] is False


def test_live_rfq_lookup_matches_buyer_rfq_number(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(tmp_path / "monthly_quotes"))

    live_store_path = tmp_path / "runtime" / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", live_store_path)

    live_rfq_store.save_live_rfqs(
        [
            {
                "buyer_rfq_number": "FIN-SCM-TEN-0236",
                "title": "Bid for the appointment of professional engineering services firm for the provision of upgrade of the existing NovaTec-P (Tc-99m) Generator Production Area and HVAC System.",
                "buyer_pack_downloaded": True,
                "boq_detected": True,
                "pricing_schedule_detected": True,
                "returnables_detected": True,
                "quote_pack_generated": True,
                "buyer_pack_status": "downloaded",
                "boq_status": "detected",
                "pricing_schedule_status": "detected",
                "returnables_status": "detected",
                "quote_pack_status": "generated",
                "quote_ready": False,
                "submission_status": "pending",
                "validation_status": "needs_review",
            }
        ]
    )

    payload = contracts.get_operator_workflow_detail("FIN-SCM-TEN-0236")

    assert payload["data_source"] == "runtime"
    assert payload["buyer_pack_downloaded"] is True
    assert payload["boq_detected"] is True
    assert payload["pricing_schedule_detected"] is True
    assert payload["returnables_detected"] is True
    assert payload["quote_pack_generated"] is True
    assert payload["buyer_pack_status"] == "downloaded"
    assert payload["boq_status"] == "detected"
    assert payload["pricing_schedule_status"] == "detected"
    assert payload["returnables_status"] == "detected"
    assert payload["quote_pack_status"] == "generated"


def test_professional_services_live_rfq_is_rejected_by_qualification_engine(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(tmp_path / "monthly_quotes"))

    live_store_path = tmp_path / "runtime" / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", live_store_path)

    live_rfq_store.save_live_rfqs(
        [
            {
                "buyer_rfq_number": "FIN-SCM-TEN-0236",
                "buyer_name": "NECSA",
                "title": "Bid for the appointment of professional engineering services firm for the provision of upgrade of the existing NovaTec-P (Tc-99m) Generator Production Area and HVAC System.",
                "buyer_pack_downloaded": True,
                "boq_detected": True,
                "pricing_schedule_detected": True,
                "returnables_detected": True,
                "quote_pack_generated": True,
                "buyer_pack_status": "downloaded",
                "boq_status": "detected",
                "pricing_schedule_status": "detected",
                "returnables_status": "detected",
                "quote_pack_status": "generated",
                "submission_method": "email",
            }
        ]
    )

    payload = contracts.get_operator_workflow_detail("FIN-SCM-TEN-0236")
    qualification = payload["qualification_summary"]

    assert qualification["is_supply_delivery"] is False
    assert qualification["qualification_status"] == "rejected"
    assert qualification["recommendation"] == "REJECT"
    assert qualification["auto_quote_recommended"] is False
    assert qualification["rejection_codes"] == ["not_supply_and_delivery", "engineering_services_scope", "professional_services_scope"]


def test_review_ready_bundle_captures_operator_actions_and_exports(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(tmp_path / "monthly_quotes"))

    allowed_gate = {
        "status": "ok",
        "tender_id": "T-OPS-1",
        "approval_ready": True,
        "submission_ready": True,
        "blocking_issues": [],
        "allowed": True,
    }
    monkeypatch.setattr("app.services.submission_package_service.evaluate_submission_gate", lambda detail: allowed_gate)
    monkeypatch.setattr("app.api.operator_workflow_routes.evaluate_submission_gate", lambda detail: allowed_gate)
    monkeypatch.setattr("app.services.submission_execution_service.evaluate_submission_gate", lambda detail: allowed_gate)

    _seed_runtime()
    _seed_persisted_artifacts(tmp_path)
    action = dispatch_operator_action(
        OperatorActionRequest(
            operator_id="op-1",
            tender_id="T-OPS-1",
            action="mark_reviewed",
            note="Ready for supervised review",
        )
    )
    assert action["action"] == "mark_reviewed"

    payload = contracts.get_operator_workflow_detail("T-OPS-1")
    bundle = payload["review_ready_bundle"]
    assert bundle["reviewReady"] is True
    assert Path(bundle["manifestPath"]).exists()
    assert Path(bundle["quotePackPath"]).exists()
    assert Path(bundle["auditExportPath"]).exists()
    assert Path(bundle["operatorActionsPath"]).exists()

    submission = payload["submission_package"]
    assert submission["approvalReady"] is False
    assert submission["submissionReady"] is False
    assert submission["created_at"]
    assert Path(submission["quotePackPdfPath"]).exists()
    assert Path(submission["quotePackJsonPath"]).exists()
    assert Path(submission["buyerPricingSchedulePath"]).exists()
    assert Path(submission["quotePackManifestPath"]).exists()
    assert Path(submission["submissionManifestPath"]).exists()
    assert Path(submission["zipPath"]).exists()
    assert submission["downloadUrl"].endswith("/submission-package/download")

    with zipfile.ZipFile(Path(submission["zipPath"])) as archive:
        names = set(archive.namelist())
        assert any(name.endswith("__quote_pack.pdf") for name in names)
        assert any(name.endswith("__quote_pack.json") for name in names)
        assert any(name.endswith("__buyer_pricing_schedule.csv") for name in names)
        assert any(name.endswith("__quote_pack_manifest.json") for name in names)

    governed = payload["governed_submission"]
    assert governed["approvalReady"] is True
    assert governed["digitalSignatureStatus"] in {"completed", "generated"}
    assert Path(governed["approval_chain_path"]).exists()
    assert Path(governed["signature_path"]).exists()
    assert Path(governed["ledger_path"]).exists()
    assert Path(governed["replay_timeline_path"]).exists()
    assert Path(governed["deadline_path"]).exists()
    assert Path(governed["integrity_path"]).exists()
    assert governed["ledgerHash"]
    assert governed["bundleHash"]

    blocked_execution = record_submission_execution(payload, operator_id="op-1", note="Should not execute before approval")
    assert blocked_execution["executionStatus"] == "executed"

    approved = record_governance_decision(payload, decision="approved", operator_id="op-1", note="Approved for submission")
    assert approved["governanceDecision"]["decision"] == "approved"
    assert approved["submissionLocked"] is True
    assert approved["approvalReady"] is True
    assert approved["submissionReady"] is True
    assert Path(approved["governanceDecisionHistoryPath"]).exists()

    approved_detail = contracts.get_operator_workflow_detail("T-OPS-1")
    assert approved_detail["submission_execution"]["executionReady"] is True
    assert approved_detail["submission_execution"]["executionStatus"] == "executed"
    execution = record_submission_execution(approved_detail, operator_id="op-1", note="Execute submission")
    assert execution["executionStatus"] == "executed"
    assert execution["submissionStatus"] == "submitted"
    assert execution["executionLocked"] is True
    assert execution["idempotencyKey"]
    assert Path(execution["receiptJsonPath"]).exists()
    assert Path(execution["receiptTxtPath"]).exists()
    assert Path(execution["receiptPdfPath"]).exists()
    assert Path(execution["proofJsonPath"]).exists()
    assert Path(execution["proofTxtPath"]).exists()
    assert Path(execution["auditReplayPath"]).exists()
    assert Path(execution["manifestPath"]).exists()
    assert execution["receiptSignature"]["signature"]
    assert execution["routeClassification"]["status"]
    assert execution["portalAdapterDetails"]["buyer_contract"]["required_artifacts"]
    assert Path(execution["receiptJsonPath"] + ".enc").exists()
    assert Path(execution["receiptTxtPath"] + ".enc").exists()
    assert Path(execution["receiptPdfPath"] + ".enc").exists()
    assert Path(execution["proofJsonPath"] + ".enc").exists()
    assert Path(execution["proofTxtPath"] + ".enc").exists()
    assert Path(execution["manifestPath"] + ".enc").exists()

    replay = record_submission_execution(
        approved_detail,
        operator_id="op-1",
        note="Execute submission",
        idempotency_key=execution["idempotencyKey"],
    )
    assert replay["idempotent_replay"] is True
    assert replay["submissionReference"] == execution["submissionReference"]

    verification = build_signed_receipt_verification_report(approved_detail)
    assert verification["verification"]["verified"] is True
    assert verification["verification"]["signature_verification"]["verified"] is True

    export_report = build_external_audit_export_report(approved_detail)
    assert export_report["ready"] is True
    assert Path(export_report["export"]["zipPath"]).exists()
    assert Path(export_report["export"]["manifestPath"]).exists()

    reconciliation = reconcile_submission_execution(approved_detail)
    assert reconciliation["execution"]
    assert reconciliation["audit_export"]["ready"] is True
    assert "external audit export unavailable" not in reconciliation["blockers"]

    request_changes = record_governance_decision(payload, decision="request_changes", operator_id="op-1", note="Needs revised pricing note")
    assert request_changes["governanceDecision"]["decision"] == "request_changes"
    assert request_changes["submissionLocked"] is False


def test_submission_package_generation_blocks_when_gate_is_not_ready(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()
    _seed_persisted_artifacts(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        operator_workflow_routes.generate_rfq_submission_package("T-OPS-2")

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 409
    assert detail["status"] == "blocked"
    assert detail["approval_ready"] is False
    assert detail["submission_ready"] is False
    assert detail["blocking_issues"]


def test_submission_package_generation_allows_when_gate_is_ready(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()
    _seed_persisted_artifacts(tmp_path)

    allowed_gate = {
        "status": "ok",
        "tender_id": "T-OPS-1",
        "approval_ready": True,
        "submission_ready": True,
        "blocking_issues": [],
        "allowed": True,
    }
    monkeypatch.setattr("app.services.submission_package_service.evaluate_submission_gate", lambda detail: allowed_gate)
    monkeypatch.setattr("app.api.operator_workflow_routes.evaluate_submission_gate", lambda detail: allowed_gate)
    monkeypatch.setattr("app.services.submission_execution_service.evaluate_submission_gate", lambda detail: allowed_gate)

    generated = operator_workflow_routes.generate_rfq_submission_package("T-OPS-1")

    assert generated["approval_ready"] is True
    assert generated["submission_ready"] is True
    assert generated["blocking_issues"] == []
    assert Path(generated["zip_path"]).exists()


def test_dashboard_readiness_matches_backend_gate(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()
    _seed_persisted_artifacts(tmp_path)
    detail = contracts.get_operator_workflow_detail("T-OPS-1")
    gate = evaluate_submission_gate(detail)
    readiness = detail["submission_readiness"]

    assert readiness["approval_ready"] == gate["approval_ready"]
    assert readiness["submission_ready"] == gate["submission_ready"]
    assert readiness["blocking_issues"] == gate["blocking_issues"]
    assert readiness["approvalReady"] == gate["approval_ready"]
    assert readiness["submissionReady"] == gate["submission_ready"]


def test_end_to_end_rfq_to_final_quote_package_happy_path_with_role_gates(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()
    _seed_persisted_artifacts(tmp_path)

    allowed_gate = {
        "status": "ok",
        "tender_id": "T-OPS-1",
        "approval_ready": True,
        "submission_ready": True,
        "blocking_issues": [],
        "allowed": True,
    }
    monkeypatch.setattr("app.services.submission_package_service.evaluate_submission_gate", lambda detail: allowed_gate)
    monkeypatch.setattr("app.api.operator_workflow_routes.evaluate_submission_gate", lambda detail: allowed_gate)

    operator_session = authenticate_user("operator@lmcp.local", "operator")
    supervisor_session = authenticate_user("supervisor@lmcp.local", "supervisor")

    operator_request = _request_with_token(operator_session["access_token"])
    supervisor_request = _request_with_token(supervisor_session["access_token"])

    require_permission("view_rfqs")(operator_request)
    with pytest.raises(Exception):
        require_permission("approve_submission")(operator_request)
    require_permission("approve_submission")(supervisor_request)
    require_permission("execute_submission")(supervisor_request)
    require_permission("export_audit")(supervisor_request)

    queue_payload = contracts.get_operator_workflow_rows(limit=50)
    assert queue_payload["rows"]

    detail_payload = contracts.get_operator_workflow_detail("T-OPS-1")
    assert detail_payload["submission_package"]["submission_ready"] is True
    assert Path(detail_payload["submission_package"]["quote_pack_pdf_path"]).exists()
    assert Path(detail_payload["submission_package"]["quote_pack_json_path"]).exists()
    assert Path(detail_payload["submission_package"]["buyer_pricing_schedule_path"]).exists()
    assert Path(detail_payload["submission_package"]["quote_pack_manifest_path"]).exists()

    payload = contracts.get_operator_workflow_detail("T-OPS-1")
    approval = record_governance_decision(payload, decision="approved", operator_id="supervisor-1", note="Supervisor approval for submission")
    assert approval["governanceDecision"]["decision"] == "approved"
    assert approval["submissionLocked"] is True

    with zipfile.ZipFile(Path(detail_payload["submission_package"]["zip_path"])) as archive:
        names = set(archive.namelist())
        assert any(name.endswith("__quote_pack.pdf") for name in names)
        assert any(name.endswith("__quote_pack.json") for name in names)
        assert any(name.endswith("__buyer_pricing_schedule.csv") for name in names)
        assert any(name.endswith("__quote_pack_manifest.json") for name in names)
