from __future__ import annotations

from enum import Enum


class ProductionMode(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    MANUAL_PRODUCTION = "manual_production"
    SEMI_AUTONOMOUS = "semi_autonomous"
    LOCKED_PRODUCTION = "locked_production"

    @classmethod
    def parse(cls, value: str) -> "ProductionMode":
        text = str(value or "").strip().lower()
        mapping = {
            "development": cls.DEVELOPMENT,
            "staging": cls.STAGING,
            "manual_production": cls.MANUAL_PRODUCTION,
            "semi_autonomous": cls.SEMI_AUTONOMOUS,
            "locked_production": cls.LOCKED_PRODUCTION,
        }
        return mapping.get(text, cls.MANUAL_PRODUCTION)

    @property
    def manual_production_enforced(self) -> bool:
        return self in {self.MANUAL_PRODUCTION, self.LOCKED_PRODUCTION}

