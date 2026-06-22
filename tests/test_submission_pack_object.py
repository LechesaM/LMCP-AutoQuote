from __future__ import annotations

import json
from pathlib import Path

from app.core.runtime_paths import get_runtime_paths
from app.services import submission_package_service


def _setup_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    get_runtime_paths.cache_clear()
    monkeypatch.setattr(submission_package_service, "append_audit_event", lambda **kwargs: kwargs)
    return runtime_dir


def _write_file(path: Path, content: str = "x") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _build_detail(tender_id: str, docs: list[str], *, approved: bool = False) -> dict[str, object]:
    detail = {
        "tender_id": tender_id,
        "title": f"Submission pack for {tender_id}",
        "buyer_name": "NECSA",
        "review_ready_bundle": {"review_ready": True, "submission_ready": approved, "source_quote_entries": docs},
        "governed_submission": {"submissionLocked": True},
        "submission_execution": {"submissionLocked": True, "execution_status": "ready"},
        "compliance_document_paths": docs,
        "extra_submission_paths": docs,
    }
    if approved:
        detail.update(
            {
                "manual_approval_recorded": True,
                "approved_by_operator": True,
                "approved_by": "Operator",
                "approved_at": "2026-06-19T00:00:00+00:00",
                "approval_decision": "approved",
            }
        )
    return detail


def test_submission_pack_object_requires_human_approval_for_submission_ready(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _setup_runtime(monkeypatch, tmp_path)
    docs_dir = tmp_path / "docs"

    tax = _write_file(docs_dir / "tax_compliance.pdf")
    registration = _write_file(docs_dir / "company_registration.pdf")
    bbbee = _write_file(docs_dir / "bbbee_certificate.pdf")
    bank = _write_file(docs_dir / "bank_confirmation.pdf")

    result = submission_package_service.build_submission_package(
        _build_detail("PACK-001", [tax, registration, bbbee, bank])
    )
    pack = result["submission_pack"]

    assert pack["status"] == "approval_ready"
    assert pack["approval_ready"] is True
    assert pack["submission_ready"] is False
    assert pack["readiness_score"] == 100
    assert pack["blocking_codes"] == []
    assert pack["missing_artifacts"] == []
    assert pack["approval_decision"] == ""
    assert pack["approved_by"] == ""
    assert pack["approved_at"] == ""
    assert pack["human_approval_present"] is False
    assert all(pack["required_artifacts"][key] is True for key in [
        "buyer_pricing_schedule",
        "formal_quotation",
        "quote_pack_manifest",
        "submission_manifest",
        "tax_compliance",
        "company_registration",
        "bbbee",
        "bank_confirmation",
    ])
    assert pack["artifact_count"] >= 12

    event_log = runtime_dir / "manual_production" / "submission_pack_events.jsonl"
    assert event_log.exists()
    event = json.loads(event_log.read_text(encoding="utf-8").splitlines()[-1])
    assert event["event"] == "submission_pack_created"
    assert event["rfq"] == "PACK-001"
    assert event["artifact_count"] == pack["artifact_count"]
    assert event["readiness_score"] == 100

    metrics = submission_package_service.get_submission_pack_measurement_metrics(runtime_dir=str(runtime_dir))
    assert metrics["submission_pack_created_count"] == 1
    assert metrics["submission_pack_ready_count"] == 0
    assert metrics["submission_pack_blocked_count"] == 0
    assert metrics["submission_pack_success_rate"] == 0.0
    assert metrics["submission_pack_block_rate"] == 0.0
    assert metrics["average_readiness_score"] == 100.0
    assert metrics["top_blocking_codes"] == []
    get_runtime_paths.cache_clear()


def test_submission_pack_object_becomes_submission_ready_after_human_approval(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _setup_runtime(monkeypatch, tmp_path)
    docs_dir = tmp_path / "docs"

    tax = _write_file(docs_dir / "tax_compliance.pdf")
    registration = _write_file(docs_dir / "company_registration.pdf")
    bbbee = _write_file(docs_dir / "bbbee_certificate.pdf")
    bank = _write_file(docs_dir / "bank_confirmation.pdf")

    result = submission_package_service.build_submission_package(
        _build_detail("PACK-001A", [tax, registration, bbbee, bank], approved=True)
    )
    pack = result["submission_pack"]

    assert pack["status"] == "ready"
    assert pack["approval_ready"] is True
    assert pack["submission_ready"] is True
    assert pack["readiness_score"] == 100
    assert pack["blocking_codes"] == []
    assert pack["approved_by"] == "Operator"
    assert pack["approved_at"] == "2026-06-19T00:00:00+00:00"
    assert pack["approval_decision"] == "approved"
    assert pack["human_approval_present"] is True

    metrics = submission_package_service.get_submission_pack_measurement_metrics(runtime_dir=str(runtime_dir))
    assert metrics["submission_pack_created_count"] == 1
    assert metrics["submission_pack_ready_count"] == 1
    assert metrics["submission_pack_blocked_count"] == 0
    assert metrics["submission_pack_success_rate"] == 100.0
    assert metrics["submission_pack_block_rate"] == 0.0
    assert metrics["average_readiness_score"] == 100.0
    get_runtime_paths.cache_clear()


def test_submission_pack_object_blocks_when_tax_compliance_is_missing(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _setup_runtime(monkeypatch, tmp_path)
    docs_dir = tmp_path / "docs"

    registration = _write_file(docs_dir / "company_registration.pdf")
    bbbee = _write_file(docs_dir / "bbbee_certificate.pdf")
    bank = _write_file(docs_dir / "bank_confirmation.pdf")

    result = submission_package_service.build_submission_package(
        _build_detail("PACK-002", [registration, bbbee, bank])
    )
    pack = result["submission_pack"]

    assert pack["status"] == "blocked"
    assert pack["approval_ready"] is False
    assert pack["submission_ready"] is False
    assert pack["readiness_score"] < 100
    assert "missing_tax_compliance" in pack["blocking_codes"]
    assert "tax_compliance" in pack["missing_artifacts"]

    metrics = submission_package_service.get_submission_pack_measurement_metrics(runtime_dir=str(runtime_dir))
    assert metrics["submission_pack_created_count"] == 1
    assert metrics["submission_pack_ready_count"] == 0
    assert metrics["submission_pack_blocked_count"] == 1
    assert metrics["submission_pack_success_rate"] == 0.0
    assert metrics["submission_pack_block_rate"] == 100.0
    assert metrics["average_readiness_score"] < 100.0
    assert metrics["top_blocking_codes"][0]["code"] == "missing_tax_compliance"
    get_runtime_paths.cache_clear()


def test_submission_pack_object_detects_package_local_compliance_files(monkeypatch, tmp_path: Path) -> None:
    _setup_runtime(monkeypatch, tmp_path)
    tender_id = "PACK-003"
    workspace = tmp_path / "runtime" / "manual_production" / "submission_packages" / tender_id
    workspace.mkdir(parents=True, exist_ok=True)

    _write_file(workspace / "company_registration.pdf")
    _write_file(workspace / "tax_compliance.pdf")
    _write_file(workspace / "bbbee_certificate.pdf")
    _write_file(workspace / "bank_confirmation.pdf")

    result = submission_package_service.build_submission_package(
        {
            "tender_id": tender_id,
            "title": f"Submission pack for {tender_id}",
            "buyer_name": "NECSA",
            "review_ready_bundle": {"review_ready": True, "submission_ready": False},
            "governed_submission": {"submissionLocked": True},
            "submission_execution": {"submissionLocked": True, "execution_status": "ready"},
        }
    )
    pack = result["submission_pack"]

    assert pack["status"] == "approval_ready"
    assert pack["approval_ready"] is True
    assert pack["submission_ready"] is False
    assert pack["readiness_score"] == 100
    assert pack["blocking_codes"] == []
    assert pack["required_artifact_files"]["tax_compliance"].endswith("tax_compliance.pdf")
    assert pack["required_artifact_files"]["company_registration"].endswith("company_registration.pdf")
