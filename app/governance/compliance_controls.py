from __future__ import annotations

from typing import Any, Dict


def build_compliance_controls(limit: int = 25) -> Dict[str, Any]:
    return {
        "manual_governance_only": True,
        "controls": {
            "manual_submission_only": True,
            "review_ready_enforced": True,
            "proof_capture_enforced": True,
            "final_submit_locked": True,
        },
        "limit": max(1, int(limit or 25)),
    }
