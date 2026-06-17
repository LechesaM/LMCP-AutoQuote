from __future__ import annotations

import json
from pathlib import Path

from app.core.autonomous_supervisor import AutonomousSupervisor
from app.core.stability_guard import StabilityGuard
from app.services import proof_of_submission_service as proof_service


def test_stability_guard_uses_injected_runtime_dir(tmp_path: Path) -> None:
    guard = StabilityGuard(base_dir=str(tmp_path))

    payload = guard.heartbeat("test_component")

    assert guard.base_dir == tmp_path.resolve()
    assert (tmp_path / "health" / "test_component_heartbeat.json").exists()
    assert payload["component"] == "test_component"


def test_autonomous_supervisor_uses_injected_runtime_dir(tmp_path: Path) -> None:
    supervisor = AutonomousSupervisor(runtime_dir=str(tmp_path))

    payload = supervisor.write_status("healthy", "ok")

    assert supervisor.runtime_dir == tmp_path.resolve()
    assert (tmp_path / "supervisor" / "autonomous_supervisor_status.json").exists()
    assert payload["state"] == "healthy"


def test_proof_service_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    history_file = runtime_dir / "submission_history" / "submission_history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(
        json.dumps(
            [
                {
                    "buyer_rfq_number": "RFQ-123",
                    "quote_number": "Q-456",
                    "submitted_at": "2026-06-02T20:00:00+00:00",
                    "status": "submitted",
                }
            ]
        ),
        encoding="utf-8",
    )

    status = proof_service.get_proof_status(runtime_dir=str(runtime_dir))
    latest = proof_service.generate_latest_proof(runtime_dir=str(runtime_dir))

    assert status["history_file"] == str(history_file)
    assert status["history_available"] is True
    assert status["proof_dir"] == str(runtime_dir / "submission_proofs")
    assert latest["status"] == "ok"
    assert Path(latest["proof_pdf_path"]).exists()
    assert Path(latest["proof_metadata_path"]).exists()
