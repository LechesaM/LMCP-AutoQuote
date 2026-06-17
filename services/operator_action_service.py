from __future__ import annotations

import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.services.websocket_broker import publish_dashboard_event

logger = logging.getLogger(__name__)

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
ACTION_DIR = RUNTIME_DIR / "operator_actions"
ACTION_DIR.mkdir(parents=True, exist_ok=True)

ACTION_HISTORY_FILE = ACTION_DIR / "operator_action_history.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_actions() -> List[Dict[str, Any]]:
    if not ACTION_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(ACTION_HISTORY_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_actions(items: List[Dict[str, Any]]) -> None:
    ACTION_HISTORY_FILE.write_text(json.dumps(items[-1000:], indent=2, default=str))


async def record_operator_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    item = {
        "action": action,
        "status": "recorded",
        "buyer_rfq_number": payload.get("buyer_rfq_number") or "",
        "quote_number": payload.get("quote_number") or "",
        "source_name": payload.get("source_name") or "",
        "reason": payload.get("reason") or "",
        "created_at": _now_iso(),
        "payload": payload,
    }

    history = load_actions()
    history.append(item)
    save_actions(history)
    logger.info(
        "operator_action_recorded action=%s buyer_rfq_number=%s quote_number=%s source_name=%s reason=%s",
        action,
        item["buyer_rfq_number"],
        item["quote_number"],
        item["source_name"],
        item["reason"],
    )

    await publish_dashboard_event(
        event_type=f"operator_{action.replace('-', '_')}",
        payload=item,
        source="operator-action-center",
    )

    return item


async def force_quote(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = await record_operator_action("force_quote", payload)
    item["message"] = "Force quote action recorded. Wire this to tender pipeline trigger next."
    return item


async def retry_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = await record_operator_action("retry_submission", payload)
    item["message"] = "Retry submission action recorded. Wire this to retry service next."
    return item


async def reject_opportunity(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = await record_operator_action("reject_opportunity", payload)
    item["message"] = "Opportunity rejection recorded."
    return item


async def mark_review_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = await record_operator_action("mark_review_complete", payload)
    item["message"] = "Manual review completion recorded."
    return item


async def pause_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = await record_operator_action("pause_source", payload)
    item["message"] = "Source pause action recorded. Wire this to harvester source control next."
    return item


def get_operator_action_summary(limit: int = 30) -> Dict[str, Any]:
    history = load_actions()
    recent = list(reversed(history[-limit:]))

    def count(action: str) -> int:
        return len([x for x in history if x.get("action") == action])

    return {
        "status": "ok",
        "summary": {
            "total_actions": len(history),
            "force_quote": count("force_quote"),
            "retry_submission": count("retry_submission"),
            "reject_opportunity": count("reject_opportunity"),
            "mark_review_complete": count("mark_review_complete"),
            "pause_source": count("pause_source"),
        },
        "recent_actions": recent,
        "history_file": str(ACTION_HISTORY_FILE),
        "updated_at": _now_iso(),
    }

REJECTION_FILE = ACTION_DIR / "operator_rejections.json"
PAUSED_SOURCES_FILE = ACTION_DIR / "paused_sources.json"


def is_opportunity_rejected(buyer_rfq_number: str) -> bool:
    try:
        data = json.loads(REJECTION_FILE.read_text()) if REJECTION_FILE.exists() else []
        return any(str(x.get("buyer_rfq_number") or "") == str(buyer_rfq_number) for x in data)
    except Exception:
        return False


def is_source_paused(source_name: str) -> bool:
    try:
        data = json.loads(PAUSED_SOURCES_FILE.read_text()) if PAUSED_SOURCES_FILE.exists() else []
        return any(str(x.get("source_name") or "") == str(source_name) for x in data)
    except Exception:
        return False
