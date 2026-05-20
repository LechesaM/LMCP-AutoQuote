from __future__ import annotations

import pytest

from app.productivity.bulk_review_actions import bulk_acknowledge_alerts, bulk_archive_reviewed, bulk_assign_operators


def test_bulk_actions_require_confirmation():
    with pytest.raises(ValueError):
        bulk_assign_operators(operator_id="op-1", tender_ids=["RFQ-1"], target_operator_id="op-2", confirmed=False)


def test_each_rfq_audited_individually():
    payload = bulk_acknowledge_alerts(operator_id="op-1", tender_ids=["RFQ-1", "RFQ-2"], confirmed=True)
    assert payload["item_count"] == len(payload["items"])
    assert all("audit" in item for item in payload["items"])


def test_no_bulk_approval_exists():
    from app.api.operator_productivity_routes import router
    paths = {route.path for route in router.routes}
    assert "/productivity/bulk/approve" not in paths


def test_no_bulk_submission_exists():
    from app.api.operator_productivity_routes import router
    paths = {route.path for route in router.routes}
    assert "/productivity/bulk/submit" not in paths


def test_no_governance_bypass_exists():
    payload = bulk_archive_reviewed(operator_id="op-1", tender_ids=["RFQ-1"], confirmed=True)
    assert payload["action"] == "archive_rfq"


def test_bulk_routes_are_limited():
    from app.api.operator_productivity_routes import router

    paths = {route.path for route in router.routes}
    assert "/productivity/bulk/assign" in paths
    assert "/productivity/bulk/acknowledge-alert" in paths
    assert "/productivity/bulk/archive-reviewed" in paths
    assert "/productivity/bulk/approve" not in paths
    assert "/productivity/bulk/submit" not in paths
