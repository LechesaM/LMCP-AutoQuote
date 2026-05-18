from __future__ import annotations

import json
from pathlib import Path

from app.services import manual_approval_service, submission_proof_service, submission_review_service
from scripts import record_manual_submission_proof, review_submission_pack


def _patch_manual_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(manual_approval_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(manual_approval_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(manual_approval_service, "APPROVAL_LOG_FILE", manual_dir / "approvals.jsonl")

    monkeypatch.setattr(submission_review_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(submission_review_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(submission_review_service, "SUBMISSION_REVIEW_LOG_FILE", manual_dir / "submission_reviews.jsonl")

    monkeypatch.setattr(submission_proof_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(submission_proof_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(submission_proof_service, "SUBMISSION_PROOF_LOG_FILE", manual_dir / "submission_proofs.jsonl")
    return runtime_dir


def test_record_manual_submission_proof_records_proof_after_review_ready(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()

    pricing_file = tender_root / "pricing.json"
    pricing_file.write_text("{}", encoding="utf-8")
    proof_file = tender_root / "proof.pdf"
    proof_file.write_text("proof", encoding="utf-8")
    (tender_root / "tender-003__quote_pack.pdf").write_text("quote pack", encoding="utf-8")
    (tender_root / "tender-003_submission_pack_manifest.txt").write_text("submission pack", encoding="utf-8")
    (tender_root / "rfq.pdf").write_text("rfq", encoding="utf-8")

    manual_approval_service.append_manual_approval(
        {
            "tender_id": "tender-003",
            "tender_root": str(tender_root),
            "pricing_file": str(pricing_file),
            "submission_ready": True,
            "final_submission_attempted": False,
            "status": "recorded",
        }
    )
    review_submission_pack.review_submission_pack(
        tender_id="tender-003",
        tender_root=str(tender_root),
    )

    record = record_manual_submission_proof.record_manual_submission_proof(
        tender_id="tender-003",
        tender_root=str(tender_root),
        portal_name="eTenders",
        submission_reference="SUB-123",
        submitted_by="Operator A",
        proof_file=str(proof_file),
    )

    assert record["status"] == "recorded"
    assert record["manual_submission_recorded"] is True
    assert record["proof_file_present"] is True
    assert submission_proof_service.SUBMISSION_PROOF_LOG_FILE.exists()
    lines = submission_proof_service.SUBMISSION_PROOF_LOG_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["submission_reference"] == "SUB-123"


def test_record_manual_submission_proof_refuses_without_review_ready_record(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()

    record = record_manual_submission_proof.record_manual_submission_proof(
        tender_id="tender-004",
        tender_root=str(tender_root),
        portal_name="eTenders",
        submission_reference="SUB-456",
        submitted_by="Operator B",
    )

    assert record["status"] == "refused"
    assert "submission review record missing" in record["blockers"]
