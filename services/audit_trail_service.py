from __future__ import annotations

import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.websocket_broker import publish_dashboard_event

logger = logging.getLogger(__name__)

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
AUDIT_DIR = RUNTIME_DIR / "audit_trail"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_FILE = AUDIT_DIR / "audit_events.json"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_audit_events() -> List[Dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    try:
        data = json.loads(AUDIT_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_audit_events(items: List[Dict[str, Any]]) -> None:
    AUDIT_FILE.write_text(json.dumps(items[-5000:], indent=2, default=str))

async def record_audit_event(
    event_type: str,
    source: str = "system",
    severity: str = "info",
    title: str = "",
    message: str = "",
    buyer_rfq_number: str = "",
    quote_number: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    item = {
        "id": f"audit-{datetime.now(timezone.utc).timestamp()}",
        "event_type": event_type,
        "source": source,
        "severity": severity,
        "title": title or event_type,
        "message": message,
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "payload": payload or {},
        "created_at": _now_iso(),
    }

    events = load_audit_events()
    events.append(item)
    save_audit_events(events)
    logger.info(
        "audit_event_recorded type=%s source=%s severity=%s buyer_rfq_number=%s quote_number=%s",
        event_type,
        source,
        severity,
        buyer_rfq_number,
        quote_number,
    )

    await publish_dashboard_event(
        event_type="audit_event_recorded",
        payload=item,
        source="audit-trail",
    )

    return item

def get_audit_events(limit: int = 80) -> Dict[str, Any]:
    events = load_audit_events()
    return {
        "status": "ok",
        "items": list(reversed(events[-limit:])),
        "total": len(events),
        "history_file": str(AUDIT_FILE),
        "updated_at": _now_iso(),
    }

def get_audit_summary() -> Dict[str, Any]:
    events = load_audit_events()

    def count_severity(severity: str) -> int:
        return len([x for x in events if str(x.get("severity") or "").lower() == severity])

    return {
        "status": "ok",
        "summary": {
            "total_events": len(events),
            "critical": count_severity("critical"),
            "warning": count_severity("warning"),
            "success": count_severity("success"),
            "info": count_severity("info"),
        },
        "history_file": str(AUDIT_FILE),
        "updated_at": _now_iso(),
    }
