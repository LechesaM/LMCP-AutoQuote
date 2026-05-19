from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import Optional


class HarvestTier(str, Enum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    TIER_4 = "tier_4"

    @classmethod
    def from_value(cls, value: str | "HarvestTier" | None) -> "HarvestTier":
        if isinstance(value, HarvestTier):
            return value
        normalized = str(value or "").strip().lower()
        for tier in cls:
            if normalized in {tier.value, tier.name.lower(), tier.name.replace("_", "")}:
                return tier
        return cls.TIER_4


def is_passive_tier(tier: str | HarvestTier | None) -> bool:
    return HarvestTier.from_value(tier) == HarvestTier.TIER_4


def max_active_sources_for_tier(tier: str | HarvestTier | None) -> int:
    resolved = HarvestTier.from_value(tier)
    if resolved == HarvestTier.TIER_1:
        return 40
    if resolved == HarvestTier.TIER_2:
        return 150
    if resolved == HarvestTier.TIER_3:
        return 600
    return 0


def default_harvest_interval_for_tier(tier: str | HarvestTier | None) -> Optional[timedelta]:
    resolved = HarvestTier.from_value(tier)
    if resolved == HarvestTier.TIER_1:
        return timedelta(hours=2)
    if resolved == HarvestTier.TIER_2:
        return timedelta(days=1)
    if resolved == HarvestTier.TIER_3:
        return timedelta(weeks=1)
    return None
