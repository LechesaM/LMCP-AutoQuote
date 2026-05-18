from __future__ import annotations

import json
from pathlib import Path

from app.services import manual_approval_service, submission_review_service
from scripts import review_submission_pack


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
    return runtime_dir


def test_review_submission_pack_records_review_ready_submission(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()

    pricing_file = tender_root / "pricing.json"
    pricing_file.write_text("{}", encoding="utf-8")
    (tender_root / "tender-001__quote_pack.pdf").write_text("quote pack", encoding="utf-8")
    (tender_root / "tender-001_submission_pack_manifest.txt").write_text("submission pack", encoding="utf-8")
    (tender_root / "rfq.pdf").write_text("rfq", encoding="utf-8")

    approval_record = {
        "tender_id": "tender-001",
        "tender_root": str(tender_root),
        "pricing_file": str(pricing_file),
        "submission_ready": True,
        "final_submission_attempted": False,
        "status": "recorded",
    }
    manual_approval_service.append_manual_approval(approval_record)

    record = review_submission_pack.review_submission_pack(
        tender_id="tender-001",
        tender_root=str(tender_root),
    )

    assert record["status"] == "review_ready"
    assert record["submission_review_ready"] is True
    assert record["approval_record_present"] is True
    assert submission_review_service.SUBMISSION_REVIEW_LOG_FILE.exists()
    lines = submission_review_service.SUBMISSION_REVIEW_LOG_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["tender_id"] == "tender-001"


def test_review_submission_pack_refuses_when_manual_approval_is_missing(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()
    (tender_root / "rfq.pdf").write_text("rfq", encoding="utf-8")

    record = review_submission_pack.review_submission_pack(
        tender_id="tender-002",
        tender_root=str(tender_root),
    )

    assert record["status"] == "refused"
    assert "manual approval record missing" in record["review_blockers"]
