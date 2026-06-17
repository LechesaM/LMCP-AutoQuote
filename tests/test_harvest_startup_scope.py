from __future__ import annotations

from pathlib import Path

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.harvest.seed_sources import load_seed_sources, seed_source_registry_if_empty
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


def test_seed_source_registry_if_empty_populates_runtime_registry(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()

    report = seed_source_registry_if_empty()

    assert report["status"] == "seeded"
    assert report["seeded"] >= 5
    assert len(load_seed_sources()) >= 5
