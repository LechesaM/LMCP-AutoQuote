from __future__ import annotations

import importlib
import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.core.runtime_paths import get_runtime_paths
from app.services import etenders_persistent_session_service as session
from app.services import local_system_service as local_system
from app.services import live_rfq_store


def test_local_system_service_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    status_path = runtime_dir / "local_system" / "local_system_status.json"

    status = local_system.refresh_local_system_status(
        backend_url="http://127.0.0.1:8011",
        frontend_url="http://127.0.0.1:5175",
        status_path=status_path,
        backend_probe_fn=lambda url: {
            "available": True,
            "status": "healthy",
            "url": url,
            "health_url": f"{url}/health",
            "error": "",
            "payload": {"status": "healthy"},
        },
        frontend_probe_fn=lambda url: {
            "available": True,
            "status": "online",
            "url": url,
            "http_status": 200,
            "body_preview": "ok",
            "error": "",
        },
    )
    loaded = local_system.load_local_system_status(status_path)

    assert status["status"] == "ready"
    assert loaded["status"] == "ready"
    assert status["status_file"] == str(status_path)
    assert status_path.exists()


def test_etenders_session_service_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"

    result = session.probe_persistent_session(runtime_dir=str(runtime_dir))
    loaded = session.get_etenders_session_status(runtime_dir=str(runtime_dir))

    assert result["status"] == "ok"
    assert loaded["status"] == "ok"
    assert loaded["session"]["status"] == "ok"
    assert (runtime_dir / "etenders_session" / "status.json").exists()


def test_live_rfq_store_uses_live_rfqs_path_alias(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    live_store_path = runtime_dir / "custom" / "live_rfqs.json"
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LIVE_RFQS_PATH", str(live_store_path))
    get_runtime_paths.cache_clear()

    reloaded = importlib.reload(live_rfq_store)
    try:
        saved = reloaded.upsert_rfq(
            {
                "title": "Alias test RFQ",
                "source_url": "https://example.com/rfq/alias-test",
                "submission_type": "portal",
                "briefing_required": False,
            }
        )

        assert reloaded.LIVE_RFQ_STORE_PATH == live_store_path.resolve()
        assert saved["count"] == 1
        assert live_store_path.exists()
    finally:
        get_runtime_paths.cache_clear()
        importlib.reload(live_rfq_store)
