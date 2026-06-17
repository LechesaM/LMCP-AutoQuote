from __future__ import annotations

from typing import Any, Dict, List


def build_governance_risk_register() -> Dict[str, Any]:
    risks: List[Dict[str, Any]] = [
        {"risk": "stale evidence", "severity": "medium", "mitigation": "controlled validation set"},
        {"risk": "audit tampering", "severity": "high", "mitigation": "immutable submission lock"},
        {"risk": "submission bypass", "severity": "high", "mitigation": "manual-only controls"},
    ]
    return {
        "risks": risks,
        "summary": {
            "count": len(risks),
            "manual_governance_only": True,
        },
    }
