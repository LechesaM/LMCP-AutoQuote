from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import tender_harvester
from app.services.verified_rfq_promotion_gate_v50_7_service import evaluate_verified_rfq_for_promotion


SMOKE_SOURCE_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "smoke_harvest_sources.json"


def test_controlled_mode_rejects_non_fixture_source_file(tmp_path, monkeypatch) -> None:
    source_file = tmp_path / "controlled_sources.json"
    source_file.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Live Portal",
                        "url": "https://example.com/live",
                        "type": "web",
                        "enabled": True,
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="controlled_mode requires a bundled fixture source file"):
        tender_harvester.run_national_tender_radar(
            max_total=1,
            max_per_source=1,
            max_sources_per_cycle=1,
            source_file=str(source_file),
            controlled_mode=True,
            persist_to_live_store=False,
        )


def test_controlled_smoke_fixture_output_is_stable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", tmp_path / "source_health.json")

    result = tender_harvester.run_national_tender_radar(
        max_total=2,
        max_per_source=1,
        max_sources_per_cycle=1,
        source_file=str(SMOKE_SOURCE_FILE),
        controlled_mode=True,
        persist_to_live_store=False,
        enable_auto_quote=False,
        true_autonomous=False,
    )

    assert result["status"] == "ok"
    assert result["controlled_mode"] is True
    assert result["persist_to_live_store"] is False
    assert result["source_count"] == 1
    assert result["selected_source_count"] == 1
    assert result["harvested_total"] == 1
    assert result["eligible_total"] == 1
    assert result["quote_ready_total"] == 1
    assert result["source_health_overview"]["ready_count"] == 1
    assert result["source_health_overview"]["watch_count"] == 0
    assert result["source_health_overview"]["quarantined_count"] == 0
    assert result["source_health_overview"]["zero_yield_count"] == 1
    assert result["source_runs"][0]["source_operator_action"] == "watch"
    assert result["source_runs"][0]["source_next_action"].startswith("Keep monitored")


def test_controlled_promotion_reports_detail_navigation_stall() -> None:
    item = {
        "eligible": True,
        "quote_ready": False,
        "estimated_profit": 50000,
        "ai_score": 85,
        "confidence": 0.9,
        "quantity_safety_status": "verified_buyer_docx_quantities",
        "submission_method": "email",
        "pipeline_status": "detail_navigation_required",
        "v50_7_navigation_status": "detail_navigation_required",
        "v50_7_navigation_blockers": ["no_tender_specific_document_link", "no_tender_specific_detail_link"],
        "v50_7_navigation_reasons": {"recommended_action": "manual_review", "candidate_count": 1},
        "v50_8_extended_resolution_status": "no_verified_resolution",
        "v50_8_extended_resolution_summary": {
            "attempt_count": 2,
            "verified_document": False,
            "verified_detail": True,
            "resolved_status": "no_verified_resolution",
        },
    }

    result = evaluate_verified_rfq_for_promotion(item, {"minimum_profit_required": 30000, "min_confidence": 0.35})

    assert result["stalled_stage"] == "detail_navigation"
    assert "detail_navigation_required" in result["blockers"]
    assert "no_verified_detail_or_document_link" in result["blockers"]
    assert result["extended_resolution_status"] == "no_verified_resolution"
    assert result["extended_resolution_summary"]["attempt_count"] == 2
