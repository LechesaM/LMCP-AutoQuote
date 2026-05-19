from __future__ import annotations

from typing import List

from pydantic import Field

from app.domain.base import StrictBaseModel, normalize_amount

try:
    from pydantic import model_validator
    PYDANTIC_V2 = True
except ImportError:  # pragma: no cover
    from pydantic import root_validator

    PYDANTIC_V2 = False


class PricingLineItem(StrictBaseModel):
    description: str
    quantity: float = 0.0
    unit_cost: float = 0.0
    markup_ratio: float = 0.25
    vat_rate: float = 0.15
    delivery_cost: float = 0.0
    gross_margin_ratio: float = 0.0
    profit_amount: float = 0.0


class PricingSchedule(StrictBaseModel):
    tender_id: str = ""
    line_items: List[PricingLineItem] = Field(default_factory=list)
    currency: str = "ZAR"


class PricingDecision(StrictBaseModel):
    tender_id: str = ""
    quantity: float = 0.0
    unit_cost: float = 0.0
    markup_ratio: float = 0.25
    vat_rate: float = 0.15
    delivery_cost: float = 0.0
    gross_margin_ratio: float = 0.0
    profit_amount: float = 0.0
    minimum_profit_required: float = 30000.0
    minimum_supply_margin_ratio: float = 0.25
    refusal_blocker_reasons: List[str] = Field(default_factory=list)
    approved: bool = True

    if PYDANTIC_V2:

        @model_validator(mode="before")
        @classmethod
        def _enforce_thresholds(cls, values):
            data = dict(values or {})
            data["unit_cost"] = normalize_amount(data.get("unit_cost"))
            data["delivery_cost"] = normalize_amount(data.get("delivery_cost"))
            data["profit_amount"] = normalize_amount(data.get("profit_amount"))
            blockers = list(data.get("refusal_blocker_reasons") or [])
            if data.get("profit_amount", 0.0) < data.get("minimum_profit_required", 30000.0):
                blockers.append("minimum profit R30,000 not met")
            if data.get("gross_margin_ratio", 0.0) < data.get("minimum_supply_margin_ratio", 0.25):
                blockers.append("minimum supply margin 25% not met")
            deduped = []
            for blocker in blockers:
                if blocker not in deduped:
                    deduped.append(blocker)
            data["refusal_blocker_reasons"] = deduped
            data["approved"] = not bool(deduped)
            return data

    else:  # pragma: no cover

        @root_validator
        def _enforce_thresholds_v1(cls, values):
            values["unit_cost"] = normalize_amount(values.get("unit_cost"))
            values["delivery_cost"] = normalize_amount(values.get("delivery_cost"))
            values["profit_amount"] = normalize_amount(values.get("profit_amount"))
            blockers = list(values.get("refusal_blocker_reasons") or [])
            if values.get("profit_amount", 0.0) < values.get("minimum_profit_required", 30000.0):
                blockers.append("minimum profit R30,000 not met")
            if values.get("gross_margin_ratio", 0.0) < values.get("minimum_supply_margin_ratio", 0.25):
                blockers.append("minimum supply margin 25% not met")
            deduped = []
            for blocker in blockers:
                if blocker not in deduped:
                    deduped.append(blocker)
            values["refusal_blocker_reasons"] = deduped
            values["approved"] = not bool(deduped)
            return values

    def passes_thresholds(self) -> bool:
        return self.approved and not self.refusal_blocker_reasons
