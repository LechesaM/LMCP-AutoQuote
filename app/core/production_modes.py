from __future__ import annotations

from enum import Enum


class ProductionMode(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    MANUAL_PRODUCTION = "manual_production"
    SEMI_AUTONOMOUS = "semi_autonomous"
    LOCKED_PRODUCTION = "locked_production"

    @classmethod
    def default(cls) -> "ProductionMode":
        return cls.MANUAL_PRODUCTION

    @classmethod
    def parse(cls, value: str | None) -> "ProductionMode":
        raw = str(value or "").strip().lower()
        if not raw:
            return cls.default()
        try:
            return cls(raw)
        except ValueError:
            return cls.default()

    @property
    def manual_production_enforced(self) -> bool:
        return self in {
            self.STAGING,
            self.MANUAL_PRODUCTION,
            self.SEMI_AUTONOMOUS,
            self.LOCKED_PRODUCTION,
        }

    @property
    def legacy_routers_allowed_by_default(self) -> bool:
        return False

    @property
    def is_locked(self) -> bool:
        return self is self.LOCKED_PRODUCTION

    @property
    def allows_background_automation(self) -> bool:
        return self in {self.DEVELOPMENT, self.SEMI_AUTONOMOUS}
