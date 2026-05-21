from __future__ import annotations

from app.recovery_main import app


def test_recovery_main_exposes_incremental_read_only_runtime_routes() -> None:
    paths = {getattr(route, "path", None) for route in app.routes if getattr(route, "path", None)}

    assert "/health/system" in paths
    assert "/health/workflows" in paths
    assert "/health/operational-report" in paths
    assert "/dashboard/workflows" in paths
    assert "/dashboard/refusals" in paths
    assert "/dashboard/health" in paths
    assert "/dashboard/queues" in paths
    assert "/pilot/summary" in paths
    assert "/pilot/readiness" in paths
    assert "/pilot/signoffs" in paths

    assert "/dashboard/summary" in paths
    assert "/auth/login" in paths
    assert "/operator-auth/status" in paths
