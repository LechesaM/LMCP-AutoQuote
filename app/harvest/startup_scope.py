from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.harvest.source_tiers import HarvestTier


@dataclass(frozen=True)
class HarvestStartupScope:
    tier_1_target_range: tuple[int, int] = (10, 20)
    tier_2_target_range: tuple[int, int] = (20, 40)
    tier_3_initially_active: bool = False
    tier_4_mode: str = "passive_only"
    active_source_names: tuple[str, ...] = (
        "National Treasury eTender Portal",
        "gCommerce",
        "Eskom",
        "Transnet",
        "SANRAL",
    )
    staged_source_names: tuple[str, ...] = (
        "SITA",
        "PRASA",
        "ACSA",
        "DBSA",
        "IDC",
        "Rand Water",
    )

    def to_jsonable_dict(self) -> Dict[str, object]:
        return {
            "tier_1_target_range": list(self.tier_1_target_range),
            "tier_2_target_range": list(self.tier_2_target_range),
            "tier_3_initially_active": self.tier_3_initially_active,
            "tier_4_mode": self.tier_4_mode,
            "active_source_names": list(self.active_source_names),
            "staged_source_names": list(self.staged_source_names),
            "recommended_tiers": {
                "Tier 1": "active",
                "Tier 2": "active",
                "Tier 3": "off initially",
                "Tier 4": "passive only",
            },
        }


def get_harvest_startup_scope() -> HarvestStartupScope:
    return HarvestStartupScope()


def should_activate_seed_source(name: str, source_tier: str | HarvestTier) -> bool:
    scope = get_harvest_startup_scope()
    tier = HarvestTier.from_value(source_tier)
    normalized_name = str(name or "").strip().lower()
    if tier == HarvestTier.TIER_4:
        return False
    if tier == HarvestTier.TIER_3:
        return False
    return normalized_name in {item.lower() for item in scope.active_source_names}

