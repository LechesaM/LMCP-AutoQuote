from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.services.websocket_broker import publish_dashboard_event

logger = logging.getLogger(__name__)

DEFAULT_RUNTIME_DIR = Path("runtime")


def _runtime_dir(runtime_dir: Optional[str] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _action_dir(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_dir(runtime_dir) / "operator_actions"


def _action_history_file(runtime_dir: Optional[str] = None) -> Path:
    return _action_dir(runtime_dir) / "operator_action_history.json"


def _rejection_file(runtime_dir: Optional[str] = None) -> Path:
    return _action_dir(runtime_dir) / "operator_rejections.json"


def _paused_sources_file(runtime_dir: Optional[str] = None) -> Path:
    return _action_dir(runtime_dir) / "paused_sources.json"


_action_dir().mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_actions(runtime_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    history_file = _action_history_file(runtime_dir)
    if not history_file.exists():
        return []
    try:
        data = json.loads(history_file.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_actions(items: List[Dict[str, Any]], runtime_dir: Optional[str] = None) -> None:
    history_file = _action_history_file(runtime_dir)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(items[-1000:], indent=2, default=str))


async def record_operator_action(
    action: str,
    payload: Dict[str, Any],
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
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

    history = load_actions(runtime_dir=runtime_dir)
    history.append(item)
    save_actions(history, runtime_dir=runtime_dir)
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


def get_operator_action_summary(limit: int = 30, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    history = load_actions(runtime_dir=runtime_dir)
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
        "history_file": str(_action_history_file(runtime_dir)),
        "updated_at": _now_iso(),
    }


def is_opportunity_rejected(buyer_rfq_number: str, runtime_dir: Optional[str] = None) -> bool:
    try:
        rejection_file = _rejection_file(runtime_dir)
        data = json.loads(rejection_file.read_text()) if rejection_file.exists() else []
        return any(str(x.get("buyer_rfq_number") or "") == str(buyer_rfq_number) for x in data)
    except Exception:
        return False


def is_source_paused(source_name: str, runtime_dir: Optional[str] = None) -> bool:
    try:
        paused_sources_file = _paused_sources_file(runtime_dir)
        data = json.loads(paused_sources_file.read_text()) if paused_sources_file.exists() else []
        return any(str(x.get("source_name") or "") == str(source_name) for x in data)
    except Exception:
        return False
