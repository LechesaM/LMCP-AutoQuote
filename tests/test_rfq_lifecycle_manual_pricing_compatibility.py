from __future__ import annotations

from collections import Counter

from fastapi import FastAPI


EXPECTED_OPERATION_IDS = {
    ("GET", "/rfq-lifecycle/manual-pricing/{rfq_id}"): "manual_pricing_rfq_lifecycle_manual_pricing__rfq_id__get",
    ("POST", "/rfq-lifecycle/manual-pricing/{rfq_id}"): "save_manual_pricing_rfq_lifecycle_manual_pricing__rfq_id__post",
    ("POST", "/rfq-lifecycle/reject-terminal-review-items"): "reject_terminal_review_items_rfq_lifecycle_reject_terminal_review_items_post",
    ("POST", "/rfq-lifecycle/validate-visible-opportunities"): "validate_visible_opportunities_rfq_lifecycle_validate_visible_opportunities_post",
}


class FakeLifecycleService:
    def __init__(self) -> None:
        self.calls = []

    def get_manual_pricing(self, rfq_id):
        self.calls.append(("get_manual_pricing", rfq_id))
        return {"status": "ok", "rfq_id": rfq_id, "manual_pricing": {}, "saved": False}

    def save_manual_pricing(self, rfq_id, payload):
        self.calls.append(("save_manual_pricing", rfq_id, payload))
        return {"status": "needs_review", "rfq_id": rfq_id, "safety": {"live_rfq_store_modified": False}}

    def reject_terminal_review_items(self, limit=100):
        self.calls.append(("reject_terminal_review_items", limit))
        return {"status": "ok", "processed_count": 0}

    def validate_visible_opportunities(
        self,
        limit=250,
        timeout_seconds=8,
        max_concurrent_downloads=4,
        retry_backoff_seconds=0.75,
        generate_local_pack=False,
        dry_run=True,
    ):
        self.calls.append(
            (
                "validate_visible_opportunities",
                limit,
                timeout_seconds,
                max_concurrent_downloads,
                retry_backoff_seconds,
                generate_local_pack,
                dry_run,
            )
        )
        return {
            "status": "ok",
            "dry_run": dry_run,
            "generate_local_pack_requested": generate_local_pack,
            "live_rfq_store_modified": False,
            "lifecycle_store_modified": False,
        }


def _isolated_app(monkeypatch):
    from app.api import rfq_lifecycle_api

    fake = FakeLifecycleService()
    monkeypatch.setattr(rfq_lifecycle_api, "service", lambda: fake)
    app = FastAPI()
    app.include_router(rfq_lifecycle_api.router)
    return app, fake, rfq_lifecycle_api


def _method_path_counts(app):
    counts = Counter()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        for method in methods:
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                counts[(method, path)] += 1
    return counts


def test_compatibility_routes_exist_once_with_historical_operation_ids(monkeypatch):
    app, _fake, _api = _isolated_app(monkeypatch)
    counts = _method_path_counts(app)
    openapi = app.openapi()

    for method_path, operation_id in EXPECTED_OPERATION_IDS.items():
        method, path = method_path
        assert counts[(method, path)] == 1
        assert openapi["paths"][path][method.lower()]["operationId"] == operation_id


def test_compatibility_routes_delegate_to_current_service(monkeypatch):
    _app, fake, api = _isolated_app(monkeypatch)

    assert api.manual_pricing("RFQ-1")["status"] == "ok"
    assert api.save_manual_pricing("RFQ-1", {"line_items": []})["status"] == "needs_review"
    assert api.reject_terminal_review_items({"limit": 7})["processed_count"] == 0
    validate = api.validate_visible_opportunities(
        {"limit": 3, "timeout_seconds": 2, "max_concurrent_downloads": 1, "retry_backoff_seconds": 0.1}
    )

    assert validate["dry_run"] is True
    assert validate["generate_local_pack_requested"] is False
    assert validate["live_rfq_store_modified"] is False
    assert validate["lifecycle_store_modified"] is False
    assert fake.calls == [
        ("get_manual_pricing", "RFQ-1"),
        ("save_manual_pricing", "RFQ-1", {"line_items": []}),
        ("reject_terminal_review_items", 7),
        ("validate_visible_opportunities", 3, 2, 1, 0.1, False, True),
    ]


def test_manual_pricing_service_uses_temporary_store_and_reports_safe_defaults(tmp_path, monkeypatch):
    from app.services import rfq_lifecycle_service
    from app.services import rfq_state_store
    from app.services.rfq_lifecycle_service import RfqLifecycleService
    from app.services.rfq_state_store import RfqStateStore

    manual_dir = tmp_path / "manual_pricing"
    audit_file = tmp_path / "rfq_lifecycle" / "audit_events.json"
    store = RfqStateStore(tmp_path / "rfqs.json")
    store.upsert_item(
        {
            "rfq_id": "RFQ-1",
            "title": "Office stationery supply",
            "buyer_name": "Test Buyer",
            "current_state": "DOCUMENTS_PARSED",
            "audit": [],
        }
    )
    monkeypatch.setattr(rfq_lifecycle_service, "MANUAL_PRICING_DIR", manual_dir)
    monkeypatch.setattr(rfq_state_store, "RFQ_AUDIT_FILE", audit_file)
    service = RfqLifecycleService(store=store)
    assert service._manual_pricing_path("RFQ-1", create=True).parent == manual_dir.resolve()

    result = service.save_manual_pricing(
        "RFQ-1",
        {
            "line_items": [
                {"description": "Pens", "quantity": 0, "unit_cost": 10, "selling_price": 0},
            ],
        },
    )

    assert result["status"] == "needs_review"
    assert result["safety"]["live_rfq_store_modified"] is False
    assert "line_1_invalid_quantity" in result["blockers"]
    assert (manual_dir / "RFQ-1.json").exists()
    assert audit_file.exists()
    assert not (tmp_path / "runtime" / "live_rfqs.json").exists()


def test_validate_visible_opportunities_is_read_only_by_default(tmp_path, monkeypatch):
    from app.services.rfq_lifecycle_service import RfqLifecycleService
    from app.services.rfq_state_store import RfqStateStore

    store = RfqStateStore(tmp_path / "rfqs.json")
    service = RfqLifecycleService(store=store)
    monkeypatch.setattr(
        service,
        "_live_store_index",
        lambda: {
            "RFQ-2": {
                "rfq_id": "RFQ-2",
                "title": "Supply and delivery of paper",
                "document_paths": ["/tmp/doc.pdf"],
                "pricing_verification_status": "verified",
            }
        },
    )

    result = service.validate_visible_opportunities()

    assert result["status"] == "ok"
    assert result["dry_run"] is True
    assert result["external_validation_executed"] is False
    assert result["live_rfq_store_modified"] is False
    assert result["lifecycle_store_modified"] is False
    assert store.list_items() == []


def test_autonomous_submission_remains_disabled():
    from app import autonomous_api
    from app.api import autonomous_api as legacy_autonomous_api

    assert autonomous_api.AUTONOMOUS_STATE["enabled"] is False
    assert legacy_autonomous_api._AUTONOMOUS_STATE["enabled"] is False
