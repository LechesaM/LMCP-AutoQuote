from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class OperatorCapacityConfig:
    team_size: int = 10
    max_reviews_per_operator_per_day: int = 100

    @property
    def total_daily_review_capacity(self) -> int:
        return self.team_size * self.max_reviews_per_operator_per_day


@dataclass(frozen=True)
class ReviewCapacitySnapshot:
    team_size: int
    max_reviews_per_operator_per_day: int
    total_daily_review_capacity: int
    already_promoted_count: int
    remaining_capacity: int
    utilization_rate: float
    can_promote_more: bool


DEFAULT_OPERATOR_CAPACITY = OperatorCapacityConfig()


def get_daily_review_capacity(config: OperatorCapacityConfig | None = None) -> int:
    selected = config or DEFAULT_OPERATOR_CAPACITY
    return selected.total_daily_review_capacity


def calculate_remaining_capacity(already_promoted_count: int, config: OperatorCapacityConfig | None = None) -> int:
    total = get_daily_review_capacity(config)
    return max(0, total - max(0, int(already_promoted_count)))


def can_promote_more(already_promoted_count: int, config: OperatorCapacityConfig | None = None) -> bool:
    return calculate_remaining_capacity(already_promoted_count, config) > 0


def estimate_operator_load(candidate_count: int, config: OperatorCapacityConfig | None = None) -> Dict[str, int | float | bool]:
    selected = config or DEFAULT_OPERATOR_CAPACITY
    remaining = calculate_remaining_capacity(candidate_count, selected)
    utilization = 0.0 if selected.total_daily_review_capacity <= 0 else min(1.0, max(0.0, candidate_count / selected.total_daily_review_capacity))
    return {
        "team_size": selected.team_size,
        "max_reviews_per_operator_per_day": selected.max_reviews_per_operator_per_day,
        "total_daily_review_capacity": selected.total_daily_review_capacity,
        "candidate_count": max(0, int(candidate_count)),
        "remaining_capacity": remaining,
        "utilization_rate": utilization,
        "can_promote_more": remaining > 0,
    }


def capacity_status(already_promoted_count: int = 0, config: OperatorCapacityConfig | None = None) -> ReviewCapacitySnapshot:
    selected = config or DEFAULT_OPERATOR_CAPACITY
    remaining = calculate_remaining_capacity(already_promoted_count, selected)
    total = selected.total_daily_review_capacity
    utilization = 0.0 if total <= 0 else min(1.0, max(0.0, already_promoted_count / total))
    return ReviewCapacitySnapshot(
        team_size=selected.team_size,
        max_reviews_per_operator_per_day=selected.max_reviews_per_operator_per_day,
        total_daily_review_capacity=total,
        already_promoted_count=max(0, int(already_promoted_count)),
        remaining_capacity=remaining,
        utilization_rate=utilization,
        can_promote_more=remaining > 0,
    )
