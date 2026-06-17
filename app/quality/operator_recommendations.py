from __future__ import annotations

from typing import Any, Dict


def generate_operator_recommendations(*, workflow_summary: Dict[str, Any], quality_summary: Dict[str, Any], queue_summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "advisory_only": True,
        "recommendations": [
            {"action": "manual_review", "mutates_workflow": False},
            {"action": "escalate_to_operator", "mutates_workflow": False},
        ],
        "workflow_summary": workflow_summary,
        "quality_summary": quality_summary,
        "queue_summary": queue_summary,
    }
