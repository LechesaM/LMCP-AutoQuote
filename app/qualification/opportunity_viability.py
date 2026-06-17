from __future__ import annotations

from typing import Any, Dict


def assess_opportunity_viability(opportunity: Dict[str, Any], metadata: Dict[str, Any], compliance: Dict[str, Any], method_meta: Dict[str, Any]) -> Dict[str, Any]:
    profit_gate = float(opportunity.get("estimated_profit", 0) or 0) >= 30000
    margin_gate = float(opportunity.get("gross_margin_ratio", 0) or 0) >= 0.25
    return {"profit_gate": profit_gate, "margin_gate": margin_gate, "final_recommendation": "REJECT" if not (profit_gate and margin_gate) else "GO"}
