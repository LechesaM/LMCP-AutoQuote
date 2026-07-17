from __future__ import annotations

from collections import Counter


def _route_records(app):
    records = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        operation_id = getattr(route, "operation_id", None) or getattr(route, "name", "")
        for method in methods:
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                records.append((method, path, operation_id))
    return records


def test_sbd_intelligence_has_single_canonical_owner():
    from app.main import app

    records = _route_records(app)
    counts = Counter((method, path) for method, path, _operation_id in records)

    assert counts[("GET", "/sbd-intelligence/status")] == 1
    assert counts[("POST", "/sbd-intelligence/complete")] == 1
    assert counts[("GET", "/tender-form-intelligence/status")] == 1
    assert counts[("POST", "/tender-form-intelligence/complete")] == 1
    assert not [pair for pair, count in counts.items() if count > 1]


def test_sbd_operation_ids_remain_canonical():
    from app.main import app

    openapi = app.openapi()
    assert (
        openapi["paths"]["/sbd-intelligence/status"]["get"]["operationId"]
        == "sbd_intelligence_status_sbd_intelligence_status_get"
    )
    assert (
        openapi["paths"]["/sbd-intelligence/complete"]["post"]["operationId"]
        == "sbd_intelligence_complete_sbd_intelligence_complete_post"
    )
    assert "/tender-form-intelligence/status" in openapi["paths"]
    assert "/tender-form-intelligence/complete" in openapi["paths"]
