from __future__ import annotations

from typing import Any, Dict, List


def build_policy_registry() -> Dict[str, Any]:
    policies: List[Dict[str, Any]] = [
        {"id": "manual-submission-only", "label": "Manual submission only"},
        {"id": "final-submit-locked", "label": "Final submit locked"},
        {"id": "review-ready-gate", "label": "Review-ready gate enforced"},
        {"id": "proof-capture-required", "label": "Proof capture required"},
        {"id": "local-evidence-only", "label": "Local evidence accumulation only"},
        {"id": "immutable-audit-chain", "label": "Immutable audit chain required"},
    ]
    return {
        "policies": policies,
        "summary": {
            "manualEnforcementOnly": True,
            "policy_count": len(policies),
        },
    }
