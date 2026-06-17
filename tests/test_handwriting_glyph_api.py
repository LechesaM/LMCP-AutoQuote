from __future__ import annotations

from app.api.handwriting_glyph_api import (
    handwriting_glyph_example_payload,
    handwriting_glyph_status,
    router,
)


def test_handwriting_glyph_router_smoke() -> None:
    route_paths = {route.path for route in router.routes}
    assert router.prefix == "/handwriting-glyph"
    assert "/handwriting-glyph/status" in route_paths
    assert "/handwriting-glyph/example-payload" in route_paths
    assert "/handwriting-glyph/build-cache" in route_paths
    assert "/handwriting-glyph/overlay-existing-pdf" in route_paths

    status_payload = handwriting_glyph_status()
    assert status_payload["status"] == "ok"
    assert status_payload["service"] == "handwriting_glyph_service"

    example_payload = handwriting_glyph_example_payload()
    assert example_payload["status"] == "ok"
    assert example_payload["payload"]["buyer_rfq_number"] == "TEST-GLYPH-HANDWRITING-001"
