from __future__ import annotations

from app.harvest.seed_sources import load_seed_sources
from app.harvest.startup_scope import get_harvest_startup_scope, should_activate_seed_source
from app.harvest.source_tiers import HarvestTier


def test_startup_scope_limits_initial_harvest() -> None:
    scope = get_harvest_startup_scope().to_jsonable_dict()
    assert scope["tier_1_target_range"] == [10, 20]
    assert scope["tier_2_target_range"] == [20, 40]
    assert scope["tier_3_initially_active"] is False
    assert scope["tier_4_mode"] == "passive_only"
    assert "National Treasury eTender Portal" in scope["active_source_names"]
    assert "SITA" in scope["staged_source_names"]


def test_seed_sources_start_small_and_stable() -> None:
    seeds = load_seed_sources()
    active = [seed for seed in seeds if seed.is_active]
    inactive = [seed for seed in seeds if not seed.is_active]
    assert len(active) == 5
    assert {seed.source_tier.value for seed in active} == {"tier_1", "tier_2"}
    assert all(seed.source_tier.value != "tier_3" for seed in active)
    assert all(not seed.is_active for seed in seeds if seed.source_tier.value == "tier_4")
    assert any(seed.name == "SITA" and not seed.is_active for seed in inactive)


def test_seed_activation_helper_respects_tier_policy() -> None:
    assert should_activate_seed_source("National Treasury eTender Portal", HarvestTier.TIER_1) is True
    assert should_activate_seed_source("Eskom", HarvestTier.TIER_2) is True
    assert should_activate_seed_source("SANRAL", HarvestTier.TIER_2) is True
    assert should_activate_seed_source("SITA", HarvestTier.TIER_3) is False
    assert should_activate_seed_source("Selected Municipality", HarvestTier.TIER_4) is False
