from __future__ import annotations

import json
from pathlib import Path

from app.core.runtime_paths import get_runtime_paths
from app.services.simulation_harness_service import run_simulation_harness


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fixture(path: Path, *, tender_id: str, title: str, category: str, expected_exclusion_status: str, expected_minimum_profit_result: str, expected_submission_ready: bool) -> None:
    source_dir = path.parent / "source_files"
    pdf_name = f"{path.stem}.pdf"
    xlsx_name = f"{path.stem}_pricing.xlsx"
    _write(source_dir / pdf_name, "pdf")
    _write(source_dir / xlsx_name, "xlsx")
    path.write_text(
        json.dumps(
            {
                "tender_id": tender_id,
                "title": title,
                "buyer_name": "Test Buyer",
                "category": category,
                "source_files": [f"source_files/{pdf_name}"],
                "pricing_file": f"source_files/{xlsx_name}",
                "line_items": [{"line_number": 1, "description": "A4 paper", "quantity": 10, "unit": "Box"}],
                "expected_exclusion_status": expected_exclusion_status,
                "expected_minimum_profit_result": expected_minimum_profit_result,
                "expected_submission_ready": expected_submission_ready,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _seed_compliance_sources(project_root: Path) -> None:
    compliance_root = project_root / "runtime" / "compliance"
    _write(compliance_root / "tax_compliance.pdf", "tax")
    _write(compliance_root / "company_registration.pdf", "cipc")
    _write(compliance_root / "bbbee_certificate.pdf", "bbbee")
    _write(compliance_root / "bank_confirmation.pdf", "bank")


def test_simulation_harness_creates_artifacts_and_preserves_approval_gate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(tmp_path / "runtime" / "manual_production"))
    get_runtime_paths.cache_clear()

    _seed_compliance_sources(tmp_path)
    fixtures_root = tmp_path / "fixtures"
    valid = fixtures_root / "valid_supply_delivery_rfq.json"
    blocked = fixtures_root / "incomplete_schedule_rfq.json"
    rejected = fixtures_root / "excluded_catering_rfq.json"
    _fixture(valid, tender_id="RFQ-VALID-001", title="Supply and Delivery of Office Consumables", category="supply and delivery", expected_exclusion_status="eligible", expected_minimum_profit_result="above_margin", expected_submission_ready=True)
    _fixture(blocked, tender_id="RFQ-BLOCKED-001", title="Supply and Delivery of Consumables", category="supply and delivery", expected_exclusion_status="eligible", expected_minimum_profit_result="above_margin", expected_submission_ready=False)
    _fixture(rejected, tender_id="RFQ-REJECTED-001", title="Catering Services for Event", category="catering", expected_exclusion_status="excluded", expected_minimum_profit_result="above_margin", expected_submission_ready=False)

    result = run_simulation_harness(
        max_rfqs=3,
        fixture_paths=[valid, blocked, rejected],
        run_label="test-sim",
    )

    run_root = Path(result["run_root"])
    manifest = json.loads((run_root / "simulation_manifest.json").read_text(encoding="utf-8"))
    outputs = {
        "results": json.loads((run_root / "simulation_results.json").read_text(encoding="utf-8")),
        "metrics": json.loads((run_root / "simulation_metrics.json").read_text(encoding="utf-8")),
        "audit": json.loads((run_root / "simulation_audit.json").read_text(encoding="utf-8")),
    }

    assert manifest["selected_rfqs"] == 3
    assert len(outputs["results"]) == 3
    assert outputs["metrics"]["qualified_count"] == 2
    assert outputs["metrics"]["rejected_count"] == 1
    assert outputs["metrics"]["submission_packs_generated"] == 2
    assert outputs["metrics"]["submission_pack_success_rate"] == 50.0
    assert outputs["metrics"]["submission_pack_block_rate"] == 50.0
    assert outputs["metrics"]["approval_gate_bypass_count"] == 0
    assert outputs["metrics"]["submission_ready_without_approval_count"] == 0
    assert outputs["metrics"]["duplicate_audit_events"] == 0
    assert outputs["metrics"]["orphaned_audit_events"] == 0
    assert outputs["audit"]["audit_events_missing"] == 0

    valid_result = next(item for item in outputs["results"] if item["base_tender_id"] == "RFQ-VALID-001")
    blocked_result = next(item for item in outputs["results"] if item["base_tender_id"] == "RFQ-BLOCKED-001")

    assert valid_result["approval_ready"] is True
    assert valid_result["submission_ready"] is False
    assert valid_result["submission_pack_status"] == "approval_ready"
    assert valid_result["audit_integrity"] is True
    assert all(count == 1 for count in valid_result["audit_event_counts"].values())

    assert blocked_result["approval_ready"] is False
    assert blocked_result["submission_ready"] is False
    assert blocked_result["submission_pack_status"] == "blocked"
    assert "missing_bank_confirmation" in blocked_result["blocking_codes"]

    get_runtime_paths.cache_clear()


def test_simulation_harness_allows_explicit_approval_injection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(tmp_path / "runtime" / "manual_production"))
    get_runtime_paths.cache_clear()

    _seed_compliance_sources(tmp_path)
    fixture_path = tmp_path / "fixtures" / "valid_supply_delivery_rfq.json"
    _fixture(fixture_path, tender_id="RFQ-VALID-001", title="Supply and Delivery of Office Consumables", category="supply and delivery", expected_exclusion_status="eligible", expected_minimum_profit_result="above_margin", expected_submission_ready=True)

    result = run_simulation_harness(
        max_rfqs=1,
        fixture_paths=[fixture_path],
        inject_approvals_for=["RFQ-VALID-001"],
        run_label="test-approved",
    )

    run_root = Path(result["run_root"])
    outputs = json.loads((run_root / "simulation_results.json").read_text(encoding="utf-8"))
    approved = outputs[0]

    assert approved["approval_ready"] is True
    assert approved["submission_ready"] is True
    assert approved["submission_pack_status"] == "ready"
    assert approved["human_approval_injected"] is True

    get_runtime_paths.cache_clear()
