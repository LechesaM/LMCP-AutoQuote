from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PriorityEngine:
    """
    Scores RFQs so the system processes the strongest opportunities first.

    Main scoring pillars:
    - Supply / delivery fit
    - Submission method preference
    - Estimated profit potential
    - Presence of structured line items
    - Buyer RFQ completeness
    - Briefing penalty
    - Exclusion penalties
    """

    HIGH_PRIORITY_KEYWORDS = [
        "supply and delivery",
        "supply",
        "delivery",
        "procurement of",
        "purchase of",
        "appointment for supply",
    ]

    EXCLUDED_KEYWORDS = [
        "medical",
        "pharmaceutical",
        "clinic",
        "hospital",
        "syringe",
        "bandage",
        "laptop",
        "computer",
        "printer",
        "server",
        "router",
        "monitor",
        "software",
        "ict",
        "petrol",
        "diesel",
        "fuel",
        "catering",
        "meals",
        "refreshments",
        "construction",
        "civil works",
        "building works",
        "renovation",
        "plumbing works",
        "electrical works",
        "painting works",
    ]

    EMAIL_METHODS = {"email"}
    PORTAL_METHODS = {"portal"}
    PHYSICAL_METHODS = {"physical", "physical_via_email"}

    @classmethod
    def score_batch(cls, rfqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scored: List[Dict[str, Any]] = []
        for rfq in rfqs or []:
            if not isinstance(rfq, dict):
                continue
            scored.append(cls.score_single(rfq))
        return scored

    @classmethod
    def score_single(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        rfq = dict(rfq or {})

        title = cls._clean(rfq.get("title"))
        description = cls._clean(rfq.get("description"))
        buyer_name = cls._clean(rfq.get("buyer_name"))
        buyer_rfq_number = cls._clean(
            rfq.get("buyer_rfq_number")
            or rfq.get("rfq_number")
            or rfq.get("reference_number")
        )
        submission_method = cls._clean(rfq.get("submission_method")).lower()
        briefing_required = cls._to_bool(rfq.get("briefing_required"))
        items = rfq.get("items") or rfq.get("line_items") or []
        estimated_value = cls._to_float(rfq.get("estimated_value"))

        searchable = " ".join([title, description, buyer_name]).lower()

        score = 0.0
        reasons: List[str] = []

        # ---------------------------------------------------------------
        # Supply fit
        # ---------------------------------------------------------------
        supply_hits = sum(
            1 for keyword in cls.HIGH_PRIORITY_KEYWORDS if keyword in searchable
        )
        if supply_hits > 0:
            score += min(30, supply_hits * 10)
            reasons.append(f"supply_fit:+{min(30, supply_hits * 10):.1f}")
        elif items:
            score += 10
            reasons.append("items_present:+10.0")
        else:
            score -= 20
            reasons.append("weak_supply_fit:-20.0")

        # ---------------------------------------------------------------
        # Submission method preference
        # ---------------------------------------------------------------
        if submission_method in cls.EMAIL_METHODS:
            score += 20
            reasons.append("submission_email:+20.0")
        elif submission_method in cls.PORTAL_METHODS:
            score += 12
            reasons.append("submission_portal:+12.0")
        elif submission_method in cls.PHYSICAL_METHODS:
            score += 5
            reasons.append("submission_physical:+5.0")
        elif submission_method == "unknown":
            score += 2
            reasons.append("submission_unknown:+2.0")
        else:
            score -= 10
            reasons.append("submission_unsupported:-10.0")

        # ---------------------------------------------------------------
        # Estimated value / profit
        # ---------------------------------------------------------------
        estimated_profit = cls._estimate_profit_floor(estimated_value)
        if estimated_profit >= 150000:
            score += 30
            reasons.append("profit_150k_plus:+30.0")
        elif estimated_profit >= 100000:
            score += 24
            reasons.append("profit_100k_plus:+24.0")
        elif estimated_profit >= 60000:
            score += 18
            reasons.append("profit_60k_plus:+18.0")
        elif estimated_profit >= 30000:
            score += 10
            reasons.append("profit_30k_plus:+10.0")
        else:
            score -= 35
            reasons.append("profit_below_floor:-35.0")

        # ---------------------------------------------------------------
        # Structured items
        # ---------------------------------------------------------------
        if isinstance(items, list):
            item_count = len(items)
            if item_count >= 10:
                score += 10
                reasons.append("items_10_plus:+10.0")
            elif item_count >= 3:
                score += 6
                reasons.append("items_3_plus:+6.0")
            elif item_count >= 1:
                score += 3
                reasons.append("items_1_plus:+3.0")

        # ---------------------------------------------------------------
        # RFQ completeness
        # ---------------------------------------------------------------
        if buyer_rfq_number and buyer_rfq_number != "RFQ-MISSING":
            score += 8
            reasons.append("rfq_number_present:+8.0")
        else:
            score -= 12
            reasons.append("rfq_number_missing:-12.0")

        if buyer_name:
            score += 4
            reasons.append("buyer_present:+4.0")

        # ---------------------------------------------------------------
        # Briefing penalty
        # ---------------------------------------------------------------
        if briefing_required:
            score -= 100
            reasons.append("briefing_required:-100.0")

        # ---------------------------------------------------------------
        # Hard exclusion keyword penalties
        # ---------------------------------------------------------------
        exclusion_hits = [kw for kw in cls.EXCLUDED_KEYWORDS if kw in searchable]
        if exclusion_hits:
            penalty = min(120, len(exclusion_hits) * 30)
            score -= penalty
            reasons.append(f"excluded_keywords:-{penalty:.1f}")

        # ---------------------------------------------------------------
        # Clamp and band
        # ---------------------------------------------------------------
        priority_score = round(score, 2)
        priority_band = cls._priority_band(priority_score)

        rfq["estimated_profit"] = round(estimated_profit, 2)
        rfq["priority_score"] = priority_score
        rfq["priority_band"] = priority_band
        rfq["priority_reasons"] = reasons

        return rfq

    @classmethod
    def sort_rfqs(cls, rfqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def sort_key(rfq: Dict[str, Any]) -> Any:
            return (
                float(rfq.get("priority_score", 0.0)),
                float(rfq.get("estimated_profit", 0.0)),
                cls._clean(rfq.get("buyer_rfq_number")),
            )

        return sorted(rfqs or [], key=sort_key, reverse=True)

    @staticmethod
    def _priority_band(score: float) -> str:
        if score >= 70:
            return "critical"
        if score >= 45:
            return "high"
        if score >= 20:
            return "medium"
        if score >= 0:
            return "low"
        return "blocked"

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y", "required", "mandatory"}

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            text = str(value or "").strip()
            text = text.replace("R", "").replace(",", "")
            if not text:
                return 0.0
            match = re.search(r"-?\d+(\.\d+)?", text)
            if not match:
                return 0.0
            return float(match.group(0))
        except Exception:
            return 0.0

    @staticmethod
    def _estimate_profit_floor(estimated_value: float) -> float:
        if estimated_value <= 0:
            return 30000.0
        return estimated_value * 0.25
