from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_operator_shortcut_catalog() -> Dict[str, Any]:
    shortcuts = [
        {"label": "Jump to urgent", "key": "g u", "action": "filter_urgent"},
        {"label": "Jump to overdue", "key": "g o", "action": "filter_overdue"},
        {"label": "Mark reviewed", "key": "m r", "action": "mark_reviewed"},
        {"label": "Request clarification", "key": "m c", "action": "request_clarification"},
        {"label": "Archive stale", "key": "m a", "action": "archive_reviewed"},
        {"label": "Toggle evidence panel", "key": "g e", "action": "toggle_evidence"},
    ]
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "shortcuts": shortcuts,
        "quick_actions": [
            "assign_operator",
            "acknowledge_alert",
            "mark_evidence_missing",
            "archive_reviewed",
        ],
        "filter_presets": ["urgent", "overdue", "high_value", "stale_evidence"],
        "advisory_only": True,
    }

