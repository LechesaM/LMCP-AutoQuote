from __future__ import annotations

import json

from app.api.observability_contracts import build_observability_anomalies_response
from app.observability.runtime_anomaly_detector import build_runtime_anomaly_report


def test_runtime_anomaly_detection_is_safe() -> None:
    payload = build_runtime_anomaly_report(limit=5)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert payload["advisory_only"] is True
    assert set(payload["severity_counts"].keys()).issubset({"info", "warning", "critical"})
    json.dumps(payload, default=str)


def test_runtime_anomaly_contract_is_json_safe() -> None:
    payload = build_observability_anomalies_response(limit=5)
    assert payload["anomaly_count"] >= 0
    assert isinstance(payload["anomalies"], list)
    json.dumps(payload, default=str)
