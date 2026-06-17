from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.services import audit_trail_service


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_operator_notifications(limit: int = 20) -> Dict[str, Any]:
    events = audit_trail_service.get_audit_events(limit=limit)
    return {
        "status": "ok",
        "events": events.get("items", []),
        "count": len(events.get("items", [])),
        "updated_at": _now_iso(),
    }

