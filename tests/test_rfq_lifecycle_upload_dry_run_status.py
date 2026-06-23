from __future__ import annotations

from app.api import rfq_lifecycle_api


def test_upload_dry_run_status_route_exposes_latest_status(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.upload_dry_run_service.latest_upload_dry_run_status",
        lambda: {"status": "ok", "dry_run": True, "mode": "controlled_upload_dry_run_no_submission"},
    )

    payload = rfq_lifecycle_api.upload_dry_run_status()

    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert payload["mode"] == "controlled_upload_dry_run_no_submission"
