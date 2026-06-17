from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.websocket_broker import publish_dashboard_event
from app.persistence import db as persistence_db

logger = logging.getLogger(__name__)

RUNTIME_DIR = Path("runtime")
AUDIT_DIR = RUNTIME_DIR / "audit_trail"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_FILE = AUDIT_DIR / "audit_events.json"


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_audit_events(runtime_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    audit_file = _resolve_runtime_path(AUDIT_FILE, runtime_dir)
    if not audit_file.exists():
        return []
    try:
        data = json.loads(audit_file.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_audit_events(items: List[Dict[str, Any]], runtime_dir: Optional[str] = None) -> None:
    audit_file = _resolve_runtime_path(AUDIT_FILE, runtime_dir)
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    audit_file.write_text(json.dumps(items[-5000:], indent=2, default=str))

async def record_audit_event(
    event_type: str,
    source: str = "system",
    severity: str = "info",
    title: str = "",
    message: str = "",
    buyer_rfq_number: str = "",
    quote_number: str = "",
    payload: Optional[Dict[str, Any]] = None,
    runtime_dir: Optional[str] = None,
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

    events = load_audit_events(runtime_dir=runtime_dir)
    events.append(item)
    save_audit_events(events, runtime_dir=runtime_dir)
    try:
        persistence_db.insert_json_record("audit_event_entities", item)
    except Exception:
        pass
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


def append_audit_event(
    event_type: str,
    source: str = "system",
    severity: str = "info",
    title: str = "",
    message: str = "",
    buyer_rfq_number: str = "",
    quote_number: str = "",
    payload: Optional[Dict[str, Any]] = None,
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Compatibility wrapper for older sync call sites."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            record_audit_event(
                event_type=event_type,
                source=source,
                severity=severity,
                title=title,
                message=message,
                buyer_rfq_number=buyer_rfq_number,
                quote_number=quote_number,
                payload=payload,
                runtime_dir=runtime_dir,
            )
        )

    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            record_audit_event(
                event_type=event_type,
                source=source,
                severity=severity,
                title=title,
                message=message,
                buyer_rfq_number=buyer_rfq_number,
                quote_number=quote_number,
                payload=payload,
                runtime_dir=runtime_dir,
            ),
            loop,
        )
        return future.result()

    return loop.run_until_complete(
        record_audit_event(
            event_type=event_type,
            source=source,
            severity=severity,
            title=title,
            message=message,
            buyer_rfq_number=buyer_rfq_number,
            quote_number=quote_number,
            payload=payload,
            runtime_dir=runtime_dir,
        )
    )

def get_audit_events(limit: int = 80, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    events = load_audit_events(runtime_dir=runtime_dir)
    return {
        "status": "ok",
        "items": list(reversed(events[-limit:])),
        "total": len(events),
        "history_file": str(_resolve_runtime_path(AUDIT_FILE, runtime_dir)),
        "updated_at": _now_iso(),
    }

def get_audit_summary(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    events = load_audit_events(runtime_dir=runtime_dir)

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
        "history_file": str(_resolve_runtime_path(AUDIT_FILE, runtime_dir)),
        "updated_at": _now_iso(),
    }
