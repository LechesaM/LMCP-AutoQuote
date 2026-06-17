from __future__ import annotations

from app.api.handwriting_stack_api import handwriting_stack_status, router


def test_handwriting_stack_router_smoke() -> None:
    route_paths = {route.path for route in router.routes}
    assert router.prefix == "/handwriting-stack"
    assert "/handwriting-stack/status" in route_paths
    assert "/handwriting-stack/example-payload" in route_paths

    status_payload = handwriting_stack_status()
    assert status_payload["status"] == "ok"
    assert status_payload["service"] == "handwriting_stack"
    assert status_payload["components"]["glyph"]["status"] == "ok"
    assert status_payload["components"]["line_ink"]["status"] == "ok"
    assert status_payload["components"]["simulation"]["status"] == "ok"
