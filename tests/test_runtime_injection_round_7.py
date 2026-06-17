from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import portal_health_dashboard as portal_health
from app.services import submission_engine as submission_engine
from app.services import system_state_service as system_state


def test_portal_health_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"

    portal_health.register_portal(
        "test-portal",
        portal_name="Test Portal",
        runtime_dir=str(runtime_dir),
    )
    portal_health.record_portal_success(
        "test-portal",
        portal_name="Test Portal",
        duration_seconds=4.2,
        opportunities_seen=3,
        runtime_dir=str(runtime_dir),
    )
    dashboard = portal_health.build_portal_health_dashboard(runtime_dir=str(runtime_dir))

    portal_row = next(
        row for row in dashboard["portals"] if row["portal_slug"] == "test-portal"
    )

    assert dashboard["source_file"] == str(runtime_dir / "portal_health_state.json")
    assert portal_row["status"] == "healthy"
    assert (runtime_dir / "portal_health_state.json").exists()


def test_system_state_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"

    state = system_state.save_system_state(
        harvest_paused=True,
        reason="testing pause",
        runtime_dir=str(runtime_dir),
    )
    loaded = system_state.get_system_state(runtime_dir=str(runtime_dir))

    assert state["harvest_paused"] is True
    assert loaded["harvest_paused"] is True
    assert system_state.get_block_reason("harvest", runtime_dir=str(runtime_dir)) == "harvest_paused"
    assert (runtime_dir / "system_state" / "system_state.json").exists()


def test_submission_engine_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"

    record = submission_engine.mark_submission_status(
        "RFQ-1",
        "submitted",
        runtime_dir=str(runtime_dir),
    )
    summary = submission_engine.get_submission_summary(runtime_dir=str(runtime_dir))
    pack = submission_engine.build_submission_pack(
        rfq={
            "rfq_id": "RFQ-1",
            "title": "Supply and delivery of stationery",
            "submission_email": "buyer@example.com",
            "portal_url": "https://example.com/portal",
            "deadline": "2026-06-30",
        },
        classification={
            "excluded_category": None,
            "is_construction": False,
            "supply_only": True,
            "has_compulsory_briefing": False,
            "eligible": True,
            "submission_mode": "email",
            "category": "stationery",
            "delivery_location": "Pretoria",
        },
        quote={
            "can_quote": True,
            "profit_floor_passed": True,
            "selected_supplier": {"supplier_name": "Test Supplier"},
            "cost_breakdown": {
                "quote_total_excl_vat": 1000.0,
                "quote_total_incl_vat": 1150.0,
                "gross_profit": 150.0,
            },
        },
        score_result={
            "recommended_action": "SUBMIT",
            "score": 92.5,
            "priority": "HIGH",
        },
        runtime_dir=str(runtime_dir),
    )

    assert record["rfq_id"] == "RFQ-1"
    assert summary["submitted"] == 1
    assert pack["ready"] is True
    assert pack["generated_pack_path"] == str(
        runtime_dir / "generated_submission_packs" / "RFQ-1_submission_pack.txt"
    )
    assert Path(pack["generated_pack_path"]).exists()
