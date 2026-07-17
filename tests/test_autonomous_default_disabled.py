from __future__ import annotations


def test_active_autonomous_api_defaults_disabled():
    from app import autonomous_api

    assert autonomous_api.AUTONOMOUS_STATE["enabled"] is False


def test_legacy_autonomous_api_defaults_disabled():
    from app.api import autonomous_api

    assert autonomous_api._AUTONOMOUS_STATE["enabled"] is False
