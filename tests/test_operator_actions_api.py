from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
os.environ.setdefault("LMCP_ALLOW_DEGRADED_STARTUP", "true")

from app.main import app
from app.services import audit_trail_service
from app.services import operator_auth_service


def _prepare_audit_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    audit_dir = runtime_dir / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", audit_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", audit_dir / "audit_events.json")
    return audit_dir


def test_operator_audit_endpoint_writes_supervised_ui_action(monkeypatch, tmp_path: Path) -> None:
    audit_dir = _prepare_audit_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(operator_auth_service, "OPERATOR_AUTH_ALLOW_DEV_FALLBACK", True)

    payload = {
        "timestamp": "2026-06-18T10:15:00+00:00",
        "operator_action": "Mark Reviewed Locally",
        "rfq_reference": "RFQ-OPS-001",
        "quote_pack_id": "QCP-OPS-001",
        "workspace": "quote-pack-engine",
        "page": "QuotePackEngineWorkspace",
        "controlled_workflow_mode": "supervised",
        "safety_flags": {
            "no_submission": True,
            "no_upload": True,
            "no_email": True,
            "final_submit_locked": True,
        },
    }

    with TestClient(app) as client:
        response = client.post(
            "/operator-actions/audit",
            json=payload,
            headers={
                "X-LMCP-Operator-Role": "reviewer",
                "X-LMCP-Operator-Name": "Test Reviewer",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["item"]["event_type"] == "operator_supervised_ui_action"
    assert body["item"]["title"] == "Mark Reviewed Locally"
    assert body["item"]["buyer_rfq_number"] == "RFQ-OPS-001"
    assert body["item"]["quote_number"] == "QCP-OPS-001"

    audit_events = json.loads((audit_dir / "audit_events.json").read_text())
    assert len(audit_events) == 1
    event = audit_events[0]
    assert event["event_type"] == "operator_supervised_ui_action"
    assert event["title"] == "Mark Reviewed Locally"
    assert event["buyer_rfq_number"] == "RFQ-OPS-001"
    assert event["quote_number"] == "QCP-OPS-001"
    assert event["payload"]["workspace"] == "quote-pack-engine"
    assert event["payload"]["page"] == "QuotePackEngineWorkspace"
    assert event["payload"]["controlled_workflow_mode"] == "supervised"
    assert event["payload"]["operator_role"] == "reviewer"
    assert event["payload"]["operator_display_name"] == "Test Reviewer"
    assert event["payload"]["safety_flags"] == {
        "no_submission": True,
        "no_upload": True,
        "no_email": True,
        "final_submit_locked": True,
    }


def test_operator_audit_endpoint_defaults_safety_flags(monkeypatch, tmp_path: Path) -> None:
    audit_dir = _prepare_audit_runtime(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/operator-actions/audit",
            json={
                "operator_action": "Ready for Operator Approval",
                "rfq_reference": "RFQ-OPS-002",
                "workspace": "quote-pack-engine",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"

    audit_events = json.loads((audit_dir / "audit_events.json").read_text())
    assert len(audit_events) == 1
    event = audit_events[0]
    assert event["title"] == "Ready for Operator Approval"
    assert event["payload"]["auth_source"] == "anonymous"
    assert event["payload"]["safety_flags"] == {
        "no_submission": True,
        "no_upload": True,
        "no_email": True,
        "final_submit_locked": True,
    }
