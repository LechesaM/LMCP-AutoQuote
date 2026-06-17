from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.core.supply_target_config import (
    SUPPLY_DAYS_IN_MONTH,
    SUPPLY_DEFAULT_WIN_RATE,
    SUPPLY_MIN_PROFIT_PER_WIN,
    SUPPLY_MONTHLY_PROFIT_TARGET,
    SUPPLY_WINS_TARGET_PER_MONTH,
)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def calculate_submission_requirements(target_wins: int, win_rate: float) -> Dict[str, Any]:
    if win_rate <= 0:
        return {
            "required_submissions": 0,
            "message": "Win rate must be greater than zero.",
        }

    required_submissions = int(round(target_wins / win_rate))
    required_daily_submissions = round(required_submissions / SUPPLY_DAYS_IN_MONTH, 2)

    return {
        "required_submissions": required_submissions,
        "required_daily_submissions": required_daily_submissions,
        "win_rate": win_rate,
    }


def build_target_control(actual_wins: int, actual_profit: float) -> Dict[str, Any]:
    now = datetime.utcnow()
    day_of_month = now.day
    days_elapsed = min(day_of_month, SUPPLY_DAYS_IN_MONTH)
    days_remaining = max(SUPPLY_DAYS_IN_MONTH - days_elapsed, 0)

    wins_gap = max(SUPPLY_WINS_TARGET_PER_MONTH - actual_wins, 0)
    profit_gap = max(SUPPLY_MONTHLY_PROFIT_TARGET - actual_profit, 0.0)

    required_daily_wins = round(SUPPLY_WINS_TARGET_PER_MONTH / SUPPLY_DAYS_IN_MONTH, 2)
    required_daily_profit = round(SUPPLY_MONTHLY_PROFIT_TARGET / SUPPLY_DAYS_IN_MONTH, 2)

    required_remaining_daily_wins = round(wins_gap / max(days_remaining, 1), 2) if wins_gap > 0 else 0.0
    required_remaining_daily_profit = round(profit_gap / max(days_remaining, 1), 2) if profit_gap > 0 else 0.0

    required_avg_profit_per_remaining_win = (
        round(profit_gap / wins_gap, 2) if wins_gap > 0 else 0.0
    )

    current_avg_profit_per_win = round(actual_profit / actual_wins, 2) if actual_wins > 0 else 0.0

    on_track_for_profit = actual_profit >= ((SUPPLY_MONTHLY_PROFIT_TARGET / SUPPLY_DAYS_IN_MONTH) * days_elapsed)
    on_track_for_wins = actual_wins >= ((SUPPLY_WINS_TARGET_PER_MONTH / SUPPLY_DAYS_IN_MONTH) * days_elapsed)

    submission_requirements = {
        "at_20_percent_win_rate": calculate_submission_requirements(SUPPLY_WINS_TARGET_PER_MONTH, 0.20),
        "at_10_percent_win_rate": calculate_submission_requirements(SUPPLY_WINS_TARGET_PER_MONTH, 0.10),
        "at_5_percent_win_rate": calculate_submission_requirements(SUPPLY_WINS_TARGET_PER_MONTH, 0.05),
        "at_2_percent_win_rate": calculate_submission_requirements(SUPPLY_WINS_TARGET_PER_MONTH, 0.02),
        "using_default_win_rate": calculate_submission_requirements(SUPPLY_WINS_TARGET_PER_MONTH, SUPPLY_DEFAULT_WIN_RATE),
    }

    return {
        "target_model": {
            "wins_target_per_month": SUPPLY_WINS_TARGET_PER_MONTH,
            "min_profit_per_win": SUPPLY_MIN_PROFIT_PER_WIN,
            "monthly_profit_target": SUPPLY_MONTHLY_PROFIT_TARGET,
            "days_in_month": SUPPLY_DAYS_IN_MONTH,
        },
        "actuals": {
            "actual_wins": actual_wins,
            "actual_profit": round(actual_profit, 2),
            "current_avg_profit_per_win": current_avg_profit_per_win,
        },
        "gaps": {
            "wins_gap": wins_gap,
            "profit_gap": round(profit_gap, 2),
        },
        "daily_requirements": {
            "required_daily_wins": required_daily_wins,
            "required_daily_profit": required_daily_profit,
            "required_remaining_daily_wins": required_remaining_daily_wins,
            "required_remaining_daily_profit": required_remaining_daily_profit,
            "required_avg_profit_per_remaining_win": required_avg_profit_per_remaining_win,
        },
        "tracking": {
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "on_track_for_profit": on_track_for_profit,
            "on_track_for_wins": on_track_for_wins,
        },
        "submission_requirements": submission_requirements,
    }
