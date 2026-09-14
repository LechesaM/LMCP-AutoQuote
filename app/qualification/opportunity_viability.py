from __future__ import annotations

from typing import Any, Dict

from app.governance.thazat.service import commercial_gate


def assess_opportunity_viability(
    opportunity: Dict[str, Any],
    metadata: Dict[str, Any],
    compliance: Dict[str, Any],
    method_meta: Dict[str, Any],
) -> Dict[str, Any]:
    profit = float(opportunity.get("estimated_profit", 0) or 0)
    margin = float(opportunity.get("gross_margin_ratio", 0) or 0)
    commercial = commercial_gate(
        estimated_profit=profit,
        gross_margin_ratio=margin,
        recoverable=True,
    )

    if commercial["state"] == "PASS":
        final_recommendation = "GO"
    elif commercial["state"] == "REPRICE":
        final_recommendation = "HOLD"
    else:
        final_recommendation = "REJECT"

    return {
        "profit_gate": commercial["profit_ok"],
        "margin_gate": commercial["margin_ok"],
        "requires_margin_escalation": commercial["requires_margin_escalation"],
        "required_margin_percent": commercial["required_margin_percent"],
        "minimum_profit": commercial["minimum_profit"],
        "commercial_state": commercial["state"],
        "reason_codes": commercial["reason_codes"],
        "final_recommendation": final_recommendation,
    }
