from __future__ import annotations

import json

from app.api.observability_contracts import build_observability_sla_response
from app.observability.sla_monitor import build_sla_monitoring_report


def test_sla_states_are_valid() -> None:
    payload = build_sla_monitoring_report(limit=5)
    states = {metric["state"] for metric in payload["sla_metrics"]}
    assert states.issubset({"healthy", "degraded", "failing"})
    assert payload["status"] in {"healthy", "degraded", "failing"}
    json.dumps(payload, default=str)


def test_sla_summary_is_json_safe() -> None:
    payload = build_observability_sla_response(limit=5)
    assert "sla" in payload
    assert payload["sla"]["summary"]["healthy"] >= 0
    assert payload["sla"]["summary"]["degraded"] >= 0
    assert payload["sla"]["summary"]["failing"] >= 0
    json.dumps(payload, default=str)
