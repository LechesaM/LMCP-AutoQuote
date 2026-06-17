from __future__ import annotations

from app.api.handwriting_line_ink_v5_api import (
    handwriting_line_ink_example_payload,
    handwriting_line_ink_status,
    router,
)


def test_handwriting_line_ink_router_smoke() -> None:
    route_paths = {route.path for route in router.routes}
    assert router.prefix == "/handwriting-line-ink-v5"
    assert "/handwriting-line-ink-v5/status" in route_paths
    assert "/handwriting-line-ink-v5/example-payload" in route_paths
    assert "/handwriting-line-ink-v5/build-assets" in route_paths
    assert "/handwriting-line-ink-v5/normalize-job" in route_paths
    assert "/handwriting-line-ink-v5/resolve-asset" in route_paths

    status_payload = handwriting_line_ink_status()
    assert status_payload["status"] == "ok"
    assert status_payload["service"] == "handwriting_line_ink_v5"

    example_payload = handwriting_line_ink_example_payload()
    assert example_payload["status"] == "ok"
    assert example_payload["payload"]["job_id"] == "REAL-HANDWRITING"
