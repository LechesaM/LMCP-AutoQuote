from __future__ import annotations

from typing import Any, Dict

from .compliance_controls import build_compliance_controls
from .policy_registry import build_policy_registry


def build_compliance_report() -> Dict[str, Any]:
    return {
        "manualGovernanceOnly": True,
        "export_ready": True,
        "controls": build_compliance_controls(),
        "policies": build_policy_registry(),
    }
