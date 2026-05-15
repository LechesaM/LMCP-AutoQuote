from __future__ import annotations


class MarginEngine:
    DEFAULT_MARGIN = 0.25  # 25%

    @staticmethod
    def apply_margin(cost: float, margin: float | None = None) -> float:
        selected_margin = margin if margin is not None else MarginEngine.DEFAULT_MARGIN
        return round(float(cost) * (1 + float(selected_margin)), 2)
