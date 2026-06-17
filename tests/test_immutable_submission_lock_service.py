from __future__ import annotations

import json
from pathlib import Path

from app.services import immutable_submission_lock_service as lock_service


def test_immutable_submission_lock_chain_verifies_and_detects_tampering(tmp_path, monkeypatch) -> None:
    lock_dir = tmp_path / "runtime" / "locks" / "immutable_submission"
    log_file = lock_dir / "immutable_submission_chain.jsonl"
    manifest_file = lock_dir / "immutable_submission_manifest.json"
    lock_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(lock_service, "IMMUTABLE_SUBMISSION_DIR", lock_dir)
    monkeypatch.setattr(lock_service, "IMMUTABLE_SUBMISSION_LOG_FILE", log_file)
    monkeypatch.setattr(lock_service, "IMMUTABLE_SUBMISSION_MANIFEST_FILE", manifest_file)

    first = lock_service.append_immutable_submission_record(
        {
            "kind": "manual_approval",
            "actor": "Operator A",
            "source_service": "manual_approval_service",
            "source_log": "approvals.jsonl",
            "tender_id": "T-001",
            "status": "recorded",
            "payload": {"tender_id": "T-001", "approved": True},
        }
    )
    second = lock_service.append_immutable_submission_record(
        {
            "kind": "submission_review",
            "actor": "Reviewer B",
            "source_service": "submission_review_service",
            "source_log": "submission_reviews.jsonl",
            "tender_id": "T-001",
            "status": "review_ready",
            "payload": {"tender_id": "T-001", "review_ready": True},
        }
    )

    status = lock_service.get_submission_lock_status(limit=10)
    assert status["summary"]["total_records"] == 2
    assert status["summary"]["valid"] is True
    assert first["previous_hash"] == ""
    assert second["previous_hash"] == first["record_hash"]

    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    records[0]["status"] = "tampered"
    log_file.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in records) + "\n", encoding="utf-8")

    tampered = lock_service.verify_submission_chain()
    assert tampered["valid"] is False
    assert tampered["invalid_entries"]

