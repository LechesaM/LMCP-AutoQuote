import inspect

import pytest

from app.services import harvest_entrypoint


def test_harvest_entrypoint_uses_current_radar_api_not_legacy_symbol():
    source = inspect.getsource(harvest_entrypoint)

    assert "harvest_tenders" not in source
    assert hasattr(harvest_entrypoint, "run_national_tender_radar")


def test_legacy_canonical_harvest_alias_points_to_current_entrypoint():
    assert (
        harvest_entrypoint.canonical_harvest
        is harvest_entrypoint.run_canonical_harvest
    )


def test_canonical_harvest_calls_radar_with_fail_closed_controls(monkeypatch):
    calls = []

    def fake_radar(**kwargs):
        calls.append(kwargs)
        return {
            "status": "success",
            "summary": {"items_found": 1},
            "sources": [{"name": "test-source"}],
            "items": [{"title": "test-rfq"}],
        }

    monkeypatch.setattr(
        harvest_entrypoint,
        "run_national_tender_radar",
        fake_radar,
    )

    result = harvest_entrypoint.run_canonical_harvest(
        max_total=7,
        max_per_source=2,
        persist_to_live_store=False,
    )

    assert len(calls) == 1
    assert calls[0] == {
        "max_total": 7,
        "max_per_source": 2,
        "enable_auto_quote": False,
        "persist_to_live_store": False,
        "persist_source_health": False,
        "headless": True,
        "true_autonomous": False,
    }
    assert result["status"] == "completed"
    assert result["persist_to_live_store"] is False
    assert result["persist_source_health"] is False
    assert result["auto_quote_enabled"] is False
    assert result["autonomous_downstream_enabled"] is False
    assert result["result"]["summary"]["items_found"] == 1


def test_canonical_harvest_returns_controlled_failure(monkeypatch):
    def fake_radar(**_kwargs):
        raise RuntimeError("source temporarily unavailable")

    monkeypatch.setattr(
        harvest_entrypoint,
        "run_national_tender_radar",
        fake_radar,
    )

    result = harvest_entrypoint.run_canonical_harvest(
        max_total=5,
        max_per_source=1,
        persist_to_live_store=False,
    )

    assert result["status"] == "failed"
    assert result["persist_to_live_store"] is False
    assert result["persist_source_health"] is False
    assert result["auto_quote_enabled"] is False
    assert result["autonomous_downstream_enabled"] is False
    assert "source temporarily unavailable" in result["error"]
