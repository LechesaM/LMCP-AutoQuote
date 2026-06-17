from __future__ import annotations

import importlib
import json
from pathlib import Path

def _load_service(monkeypatch, tmp_path: Path, allow_final_automation: bool = False):
    runtime_dir = tmp_path / "runtime"
    compliance_dir = runtime_dir / "compliance"
    final_automation_dir = runtime_dir / "final_automation"
    logs_dir = final_automation_dir / "logs"

    for path in (compliance_dir, final_automation_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    if allow_final_automation:
        monkeypatch.setenv("LMCP_ALLOW_FINAL_AUTOMATION", "true")
    else:
        monkeypatch.delenv("LMCP_ALLOW_FINAL_AUTOMATION", raising=False)

    service = importlib.import_module("app.services.final_automation_layer_service")
    service = importlib.reload(service)

    monkeypatch.setattr(service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(service, "COMPLIANCE_DIR", compliance_dir)
    monkeypatch.setattr(service, "FINAL_AUTOMATION_DIR", final_automation_dir)
    monkeypatch.setattr(service, "FINAL_AUTOMATION_LOGS", logs_dir)
    monkeypatch.setattr(service, "STANDARD_CSD_REPORT", compliance_dir / "CSD_Report.pdf")
    monkeypatch.setattr(
        service,
        "QUOTE_PACK_PROOF_CANDIDATES",
        [final_automation_dir / "clean_quote_pack_proof.json"],
    )
    return service, compliance_dir, final_automation_dir, logs_dir


def test_final_go_live_check_stays_blocked_without_quote_pack_proof(monkeypatch, tmp_path: Path) -> None:
    service, compliance_dir, _, _ = _load_service(monkeypatch, tmp_path)

    for name in ("CSD_Report.pdf", "tax_compliance.pdf", "bbbee_certificate.pdf"):
        (compliance_dir / name).write_bytes(b"%PDF-1.4 placeholder")

    result = service.final_go_live_check()

    assert result["status"] == "blocked"
    assert result["ready_for_live_automation"] is False
    assert result["compliance"]["status"] == "ready"
    assert result["quote_pack_proof"]["status"] == "blocked"
    assert any(blocker["area"] == "quote_pack_proof" for blocker in result["blockers"])
    assert any(blocker["area"] == "manual_guard" for blocker in result["blockers"])


def test_final_go_live_check_remains_guarded_with_clean_quote_pack_proof(monkeypatch, tmp_path: Path) -> None:
    service, compliance_dir, final_automation_dir, _ = _load_service(monkeypatch, tmp_path)

    for name in ("CSD_Report.pdf", "tax_compliance.pdf", "bbbee_certificate.pdf"):
        (compliance_dir / name).write_bytes(b"%PDF-1.4 placeholder")

    proof_path = final_automation_dir / "clean_quote_pack_proof.json"
    proof_path.write_text(
        json.dumps(
            {
                "status": "ready",
                "clean_quote_pack_generated": True,
                "checked_at": "2026-06-11T18:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = service.final_go_live_check()

    assert result["status"] == "blocked"
    assert result["ready_for_live_automation"] is False
    assert result["quote_pack_proof"]["status"] == "ready"
    assert any(blocker["area"] == "manual_guard" for blocker in result["blockers"])


def test_final_go_live_check_can_be_explicitly_enabled(monkeypatch, tmp_path: Path) -> None:
    service, compliance_dir, final_automation_dir, _ = _load_service(monkeypatch, tmp_path, allow_final_automation=True)

    for name in ("CSD_Report.pdf", "tax_compliance.pdf", "bbbee_certificate.pdf"):
        (compliance_dir / name).write_bytes(b"%PDF-1.4 placeholder")

    proof_path = final_automation_dir / "clean_quote_pack_proof.json"
    proof_path.write_text(
        json.dumps(
            {
                "status": "ready",
                "clean_quote_pack_generated": True,
                "checked_at": "2026-06-11T18:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = service.final_go_live_check()

    assert result["status"] == "ready"
    assert result["ready_for_live_automation"] is True
    assert result["quote_pack_proof"]["status"] == "ready"
