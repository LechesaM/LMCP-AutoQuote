from __future__ import annotations

import uuid
from typing import Any, Dict, List

from ._shared import append_jsonl, governance_path, now_iso, read_json, write_json


ACK_FILE = governance_path("policy_acknowledgements.json")
ACK_LOG_FILE = governance_path("policy_acknowledgements.jsonl")


def _load_acknowledgements() -> List[Dict[str, Any]]:
    payload = read_json(ACK_FILE, [])
    return payload if isinstance(payload, list) else []


def _save_acknowledgements(items: List[Dict[str, Any]]) -> None:
    write_json(ACK_FILE, items)


def record_policy_acknowledgement(policy_key: str, *, user_id: str = "", note: str = "", acknowledged: bool = True) -> Dict[str, Any]:
    item = {
        "ack_id": f"ack-{uuid.uuid4().hex[:12]}",
        "policy_key": str(policy_key or "").strip(),
        "user_id": str(user_id or "").strip(),
        "note": str(note or "").strip(),
        "acknowledged": bool(acknowledged),
        "created_at": now_iso(),
    }
    items = _load_acknowledgements()
    items.append(item)
    _save_acknowledgements(items)
    append_jsonl(ACK_LOG_FILE, item)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "acknowledgement": item,
        "acknowledgements": items,
    }


def build_policy_acknowledgement_report() -> Dict[str, Any]:
    items = _load_acknowledgements()
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "acknowledgements": items,
        "acknowledgement_count": len(items),
    }

