from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import pipeline_enforcement_service as enforcement
from app.services import proof_center_service as proof_center
from app.services import submission_proof_service as submission_proof


def test_proof_center_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    result = proof_center.scan_proof_center(runtime_dir=str(runtime_dir))
    index = proof_center.get_proof_center(runtime_dir=str(runtime_dir))

    assert result["files"]["index"] == str(runtime_dir / "proof_center" / "proof_index.json")
    assert index["last_scan"]["status"] == "ok"
    assert (runtime_dir / "proof_center" / "proof_index.json").exists()


def test_submission_proof_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    review_dir = runtime_dir / "manual_production"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_file = review_dir / "submission_reviews.jsonl"
    review_file.write_text("", encoding="utf-8")

    record = submission_proof.append_submission_proof({"tender_id": "T-1"}, runtime_dir=str(runtime_dir))
    listing = submission_proof.list_recent_submission_proofs(runtime_dir=str(runtime_dir))

    assert record["timestamp"]
    assert listing["log_file"] == str(runtime_dir / "manual_production" / "submission_proofs.jsonl")
    assert (runtime_dir / "manual_production" / "submission_proofs.jsonl").exists()


def test_pipeline_enforcement_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    result = asyncio.run(
        enforcement.enforce_before_rfq_processing(
            {"buyer_rfq_number": "RFQ-1", "runtime_dir": str(runtime_dir)}
        )
    )
    summary = enforcement.get_enforcement_summary(runtime_dir=str(runtime_dir))

    assert result["status"] == "ok"
    assert summary["history_file"] == str(runtime_dir / "pipeline_enforcement" / "enforcement_events.json")
    assert (runtime_dir / "pipeline_enforcement" / "enforcement_events.json").exists()
