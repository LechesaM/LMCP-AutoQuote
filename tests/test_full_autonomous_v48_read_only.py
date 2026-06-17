from __future__ import annotations

import importlib
from pathlib import Path


def _reload_api(monkeypatch, tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("V48_AUTONOMOUS_API_ENABLED", "false")
    monkeypatch.setenv("V48_AUTONOMOUS_EXECUTION_ENABLED", "false")

    from app.services import full_autonomous_v48_service as service
    importlib.reload(service)

    from app.api import full_autonomous_v48_api as api
    return importlib.reload(api)


def test_v48_service_is_disabled_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("V48_AUTONOMOUS_EXECUTION_ENABLED", "false")

    from app.services import full_autonomous_v48_service as service
    service = importlib.reload(service)

    status = service.get_v48_status()
    policy = service.set_v48_autonomous_policy(enabled=True, mode="controlled")
    run_pdf = service.run_v48_from_pdf(
        input_pdf="/tmp/input.pdf",
        buyer_rfq_number="RFQ-1",
    )
    run_ws = service.run_v48_from_v45_workspace(
        v45_workspace="/tmp/v45",
        buyer_rfq_number="RFQ-2",
    )

    assert status["execution_enabled"] is False
    assert policy["status"] == "disabled"
    assert policy["execution_enabled"] is False
    assert "proposed_policy" in policy
    assert run_pdf["status"] == "disabled"
    assert run_pdf["action"] == "run-from-pdf"
    assert run_ws["status"] == "disabled"
    assert run_ws["action"] == "run-from-v45-workspace"


def test_v48_api_is_read_only_by_default(monkeypatch, tmp_path: Path) -> None:
    api = _reload_api(monkeypatch, tmp_path)

    status = api.status()
    policy = api.update_policy(api.PolicyRequest(enabled=True, mode="controlled"))
    run_pdf = api.api_run_from_pdf(
        api.RunFromPdfRequest(input_pdf="/tmp/input.pdf", buyer_rfq_number="RFQ-1")
    )
    run_ws = api.api_run_from_v45_workspace(
        api.RunFromV45WorkspaceRequest(v45_workspace="/tmp/v45", buyer_rfq_number="RFQ-2")
    )

    assert status["api_enabled"] is False
    assert status["execution_enabled"] is False
    assert policy["status"] == "disabled"
    assert policy["action"] == "policy"
    assert run_pdf["status"] == "disabled"
    assert run_pdf["action"] == "run-from-pdf"
    assert run_ws["status"] == "disabled"
    assert run_ws["action"] == "run-from-v45-workspace"
