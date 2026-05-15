from __future__ import annotations


class CostEstimator:
    @staticmethod
    def estimate_cost(item_name: str) -> float:
        if not item_name:
            return 500.0

        name = item_name.lower()

        if "chair" in name:
            return 700.0
        if "desk" in name:
            return 1500.0
        if "table" in name:
            return 1200.0
        if "paper" in name or "a4" in name:
            return 320.0
        if "pen" in name:
            return 12.0
        if "toner" in name or "cartridge" in name:
            return 950.0
        if "boots" in name:
            return 450.0
        if "helmet" in name:
            return 280.0
        if "vest" in name:
            return 95.0
        if "gloves" in name:
            return 60.0
        if "cement" in name:
            return 120.0
        if "brick" in name:
            return 8.5
        if "pipe" in name:
            return 180.0
        if "valve" in name:
            return 350.0
        if "laptop" in name or "computer" in name:
            return 8500.0

        return 500.0
