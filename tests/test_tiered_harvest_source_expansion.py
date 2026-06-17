from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.api.router_registry import iter_router_specs
from app.harvest.controlled_harvester import ControlledHarvester
from app.harvest.deduplication import annotate_possible_duplicates, find_possible_duplicates
from app.harvest.filtering import evaluate_prequalification
from app.harvest.operator_capacity import (
    OperatorCapacityConfig,
    can_promote_more,
    calculate_remaining_capacity,
    capacity_status,
    estimate_operator_load,
    get_daily_review_capacity,
)
from app.harvest.parsers import HtmlTenderParser, JsonApiParser
from app.harvest.promotion_policy import prioritize_promotions
from app.harvest.seed_sources import import_sources_from_json, load_seed_sources
from app.harvest.source_health import get_source_health, record_failure, record_success, should_disable_source
from app.harvest.source_models import ProcurementSourceRecord, TenderOpportunityRecord
from app.harvest.source_registry import SourceRegistry, normalize_urls
from app.harvest.source_tiers import HarvestTier, default_harvest_interval_for_tier, is_passive_tier, max_active_sources_for_tier


def test_url_normalization() -> None:
    assert normalize_urls("HTTPS://Example.com/path/", "https://example.com/path") == ("https://example.com/path", "https://example.com/path")


def test_duplicate_url_prevention(tmp_path: Path) -> None:
    registry = SourceRegistry(storage_path=tmp_path / "sources.jsonl")
    registry.add_source({"id": "a", "name": "A", "source_tier": "tier_1", "base_url": "https://example.com/a/", "harvest_url": "https://example.com/a", "is_active": True})
    with pytest.raises(ValueError):
        registry.add_source({"id": "b", "name": "B", "source_tier": "tier_1", "base_url": "https://example.com/a", "harvest_url": "https://example.com/a", "is_active": True})


def test_tier_classification_helpers() -> None:
    assert max_active_sources_for_tier(HarvestTier.TIER_1) == 40
    assert max_active_sources_for_tier(HarvestTier.TIER_2) == 150
    assert max_active_sources_for_tier(HarvestTier.TIER_3) == 600
    assert max_active_sources_for_tier(HarvestTier.TIER_4) == 0
    assert is_passive_tier(HarvestTier.TIER_4) is True
    assert default_harvest_interval_for_tier(HarvestTier.TIER_1) == timedelta(hours=2)


def test_tier_four_passive_behavior(tmp_path: Path) -> None:
    registry = SourceRegistry(storage_path=tmp_path / "sources.jsonl")
    with pytest.raises(ValueError):
        registry.add_source({"id": "t4", "name": "T4", "source_tier": "tier_4", "base_url": "https://example.com", "harvest_url": "https://example.com/tenders", "is_active": True})


def test_active_source_limits(tmp_path: Path) -> None:
    registry = SourceRegistry(storage_path=tmp_path / "sources.jsonl")
    for index in range(40):
        registry.add_source({"id": f"src-{index}", "name": f"Src {index}", "source_tier": "tier_1", "base_url": f"https://example.com/{index}", "harvest_url": f"https://example.com/{index}/tenders", "is_active": True})
    with pytest.raises(ValueError):
        registry.add_source({"id": "src-over", "name": "Overflow", "source_tier": "tier_1", "base_url": "https://example.com/overflow", "harvest_url": "https://example.com/overflow/tenders", "is_active": True})


def test_operator_capacity_model() -> None:
    assert get_daily_review_capacity() == 1000
    assert calculate_remaining_capacity(250) == 750
    assert can_promote_more(999) is True
    assert capacity_status(1000).can_promote_more is False
    assert estimate_operator_load(1000)["total_daily_review_capacity"] == 1000


def test_cannot_promote_beyond_capacity() -> None:
    candidates = [
        {"recommendation": "GO", "qualification_score": 95, "automation_suitability_score": 95, "risk_level": "low", "source_tier": "tier_1"},
        {"recommendation": "GO", "qualification_score": 94, "automation_suitability_score": 94, "risk_level": "low", "source_tier": "tier_1"},
    ]
    summary = prioritize_promotions(candidates, already_promoted_count=999)
    assert summary["total_promoted"] == 1
    assert summary["remaining_capacity"] == 0


def test_go_candidates_prioritized_first() -> None:
    summary = prioritize_promotions([
        {"recommendation": "MANUAL_REVIEW", "qualification_score": 80, "automation_suitability_score": 60, "risk_level": "medium", "source_tier": "tier_1"},
        {"recommendation": "GO", "qualification_score": 70, "automation_suitability_score": 90, "risk_level": "low", "source_tier": "tier_1"},
    ])
    assert summary["promoted"][0]["recommendation"] == "GO"


def test_reject_and_low_confidence_suppressed() -> None:
    summary = prioritize_promotions([
        {"recommendation": "REJECT", "qualification_score": 10, "automation_suitability_score": 5, "risk_level": "blocked", "source_tier": "tier_1"},
        {"recommendation": "MANUAL_REVIEW", "qualification_score": 20, "automation_suitability_score": 20, "risk_level": "high", "source_tier": "tier_1", "low_confidence": True},
    ])
    assert len(summary["suppressed"]) == 2


def test_source_import_works(tmp_path: Path) -> None:
    payload = [{"id": "x1", "name": "X1", "source_tier": "tier_2", "base_url": "https://example.org", "harvest_url": "https://example.org/tenders", "is_active": False}]
    path = tmp_path / "sources.json"
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    result = import_sources_from_json(path, registry=SourceRegistry(storage_path=tmp_path / "sources.jsonl"))
    assert result["imported_count"] == 1


def test_parser_normalized_output() -> None:
    output = HtmlTenderParser().parse({"html": "<html><title>Sample Tender</title><body>Buyer: ABC Reference: RFQ1 <a href='/docs/a.pdf'>doc</a></body></html>", "source_url": "https://example.com"})
    assert output["title"] == "Sample Tender"
    assert output["documents"]


def test_filtering_rejects_excluded_categories() -> None:
    result = evaluate_prequalification({"title": "IT equipment tender", "description": "laptops", "reference": "RFQ-1", "closing_date": datetime.now(timezone.utc), "documents": [{}]})
    assert result["eligible"] is False


def test_compulsory_briefing_rejected() -> None:
    result = evaluate_prequalification({"title": "Supply", "description": "Compulsory briefing session required", "reference": "RFQ-2", "closing_date": datetime.now(timezone.utc), "documents": [{}], "briefing_required": True})
    assert result["eligible"] is False


def test_deduplication_detects_duplicate_reference() -> None:
    reasons = find_possible_duplicates({"reference": "RFQ-1", "title": "A", "buyer": "B", "closing_date": "2026-01-01", "source_url": "https://a", "documents": []}, [{"reference": "RFQ-1", "title": "B", "buyer": "C", "closing_date": "2026-02-01", "source_url": "https://b", "documents": []}])
    assert "reference match" in reasons


def test_health_logging_records_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    record_failure("src-1", parser_failure=True)
    health = get_source_health("src-1")
    assert health.failure_count == 1
    assert should_disable_source("src-1") is False
    record_success("src-1")
    assert get_source_health("src-1").status in {"healthy", "degraded", "failing"}


def test_controlled_harvester_handoff_and_no_quote_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = SourceRegistry(storage_path=tmp_path / "sources.jsonl")
    registry.add_source({"id": "src-1", "name": "Source 1", "source_tier": "tier_1", "base_url": "https://example.com", "harvest_url": "https://example.com/tenders", "parser_type": "html", "is_active": True})

    async def fake_fetch(source):
        return {"source_url": source["harvest_url"], "html": "<html><title>Supply tender</title><body>Buyer: ABC Reference: RFQ1</body></html>", "text": "Supply tender Buyer: ABC Reference: RFQ1", "content_type": "text/html"}

    harvester = ControlledHarvester(registry=registry, fetcher=fake_fetch)
    result = asyncio.run(harvester.harvest_source("src-1"))
    assert "qualification" in result
    assert result["qualification"]["recommendation"] in {"GO", "MANUAL_REVIEW", "REJECT"}
    assert "submission" not in result.get("run", {})


def test_harvest_routes_do_not_duplicate_existing_routers() -> None:
    specs = list(iter_router_specs(include_legacy=False))
    names = [spec.name for spec in specs]
    assert len(names) == len(set(names))
    assert any(spec.module_path == "app.api.harvest_routes" for spec in specs)
