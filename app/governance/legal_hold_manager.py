from __future__ import annotations

import uuid
from typing import Any, Dict, List

from ._shared import governance_path, now_iso, read_json, write_json


LEGAL_HOLDS_FILE = governance_path("legal_holds.json")


def _load_holds() -> List[Dict[str, Any]]:
    payload = read_json(LEGAL_HOLDS_FILE, [])
    return payload if isinstance(payload, list) else []


def _save_holds(holds: List[Dict[str, Any]]) -> None:
    write_json(LEGAL_HOLDS_FILE, holds)


def get_legal_holds() -> Dict[str, Any]:
    holds = _load_holds()
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "holds": holds,
        "active_count": len([hold for hold in holds if hold.get("active")]),
    }


def register_legal_hold(*, scope: str, reason: str, case_reference: str = "", operator_id: str = "", note: str = "") -> Dict[str, Any]:
    holds = _load_holds()
    hold = {
        "hold_id": f"hold-{uuid.uuid4().hex[:12]}",
        "scope": str(scope or "").strip(),
        "reason": str(reason or "").strip(),
        "case_reference": str(case_reference or "").strip(),
        "operator_id": str(operator_id or "").strip(),
        "note": str(note or "").strip(),
        "created_at": now_iso(),
        "released_at": "",
        "active": True,
    }
    holds.append(hold)
    _save_holds(holds)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "hold": hold,
        "holds": holds,
    }


def release_legal_hold(hold_id: str, *, operator_id: str = "", note: str = "") -> Dict[str, Any]:
    holds = _load_holds()
    updated = None
    for hold in holds:
        if hold.get("hold_id") == hold_id:
            hold["active"] = False
            hold["released_at"] = now_iso()
            hold["released_by"] = str(operator_id or "").strip()
            hold["release_note"] = str(note or "").strip()
            updated = hold
            break
    _save_holds(holds)
    return {
        "status": "ok" if updated else "not_found",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "hold": updated or {},
        "holds": holds,
    }


def build_legal_hold_summary() -> Dict[str, Any]:
    holds = _load_holds()
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "holds": holds,
        "active_holds": len([hold for hold in holds if hold.get("active")]),
        "released_holds": len([hold for hold in holds if not hold.get("active")]),
    }

