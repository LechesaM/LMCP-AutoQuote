from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNTIME_DIR = Path("runtime")
SBD_DIR = RUNTIME_DIR / "sbd_completion"
SBD_DIR.mkdir(parents=True, exist_ok=True)

SBD_STATUS_FILE = SBD_DIR / "sbd_completion_status.json"
SBD_HISTORY_FILE = SBD_DIR / "sbd_completion_history.json"

REQUIRED_CORE_FIELDS = [
    "buyer_rfq_number",
    "company_name",
    "registration_number",
    "tax_number",
    "csd_number",
    "director_name",
    "director_capacity",
    "signature_present",
    "date_signed",
]

REQUIRED_BID_FIELDS = [
    "bid_price",
    "vat_included",
    "pricing_schedule_completed",
    "validity_days",
]

REQUIRED_DECLARATION_FIELDS = [
    "sbd_1_completed",
    "sbd_4_completed",
    "sbd_6_1_completed",
    "sbd_8_completed",
    "sbd_9_completed",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _load_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def _missing_fields(data: Dict[str, Any], fields: List[str]) -> List[str]:
    missing = []
    for field in fields:
        value = data.get(field)
        if value is None or value == "" or value is False:
            missing.append(field)
    return missing


def evaluate_sbd_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = str(payload.get("buyer_rfq_number") or payload.get("rfq_number") or "").strip()

    missing_core = _missing_fields(payload, REQUIRED_CORE_FIELDS)
    missing_bid = _missing_fields(payload, REQUIRED_BID_FIELDS)
    missing_declarations = _missing_fields(payload, REQUIRED_DECLARATION_FIELDS)

    missing_all = missing_core + missing_bid + missing_declarations
    total_required = len(REQUIRED_CORE_FIELDS) + len(REQUIRED_BID_FIELDS) + len(REQUIRED_DECLARATION_FIELDS)
    completed_count = total_required - len(missing_all)
    completed = len(missing_all) == 0

    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "sbd_ready": completed,
        "completion_percent": round((completed_count / total_required) * 100, 1),
        "missing": {
            "core": missing_core,
            "bid": missing_bid,
            "declarations": missing_declarations,
            "all": missing_all,
        },
        "checks": {
            "signature_present": bool(payload.get("signature_present")),
            "pricing_schedule_completed": bool(payload.get("pricing_schedule_completed")),
            "sbd_1_completed": bool(payload.get("sbd_1_completed")),
            "sbd_4_completed": bool(payload.get("sbd_4_completed")),
            "sbd_6_1_completed": bool(payload.get("sbd_6_1_completed")),
            "sbd_8_completed": bool(payload.get("sbd_8_completed")),
            "sbd_9_completed": bool(payload.get("sbd_9_completed")),
        },
        "message": "SBD/buyer forms are ready for submission." if completed else "SBD/buyer forms are incomplete. Missing fields must be completed before submission.",
        "evaluated_at": _now_iso(),
        "payload": payload,
    }


async def record_sbd_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = evaluate_sbd_completion(payload)

    status_data = _load_dict(SBD_STATUS_FILE)
    key = result["buyer_rfq_number"] or f"UNKNOWN-{datetime.now().timestamp()}"
    status_data[key] = result
    _save_json(SBD_STATUS_FILE, status_data)

    history = _load_list(SBD_HISTORY_FILE)
    history.append(result)
    _save_json(SBD_HISTORY_FILE, history[-1000:])

    try:
        from app.services.websocket_broker import publish_dashboard_event
        await publish_dashboard_event(
            event_type="sbd_completion_evaluated",
            payload=result,
            source="sbd-completion-engine",
        )
    except Exception:
        pass

    try:
        from app.services.audit_trail_service import record_audit_event
        await record_audit_event(
            event_type="sbd_completion_ready" if result["sbd_ready"] else "sbd_completion_incomplete",
            source="sbd-completion-engine",
            severity="success" if result["sbd_ready"] else "warning",
            title="SBD completion evaluated",
            message=result["message"],
            buyer_rfq_number=result["buyer_rfq_number"],
            payload=result,
        )
    except Exception:
        pass

    return result


def get_sbd_completion_summary(limit: int = 50) -> Dict[str, Any]:
    status_data = _load_dict(SBD_STATUS_FILE)
    history = _load_list(SBD_HISTORY_FILE)

    ready = [x for x in status_data.values() if x.get("sbd_ready")]
    incomplete = [x for x in status_data.values() if not x.get("sbd_ready")]

    return {
        "status": "ok",
        "summary": {
            "tracked_rfqs": len(status_data),
            "ready": len(ready),
            "incomplete": len(incomplete),
            "history_total": len(history),
        },
        "ready_items": ready[-limit:],
        "incomplete_items": incomplete[-limit:],
        "recent_history": list(reversed(history[-limit:])),
        "files": {
            "status": str(SBD_STATUS_FILE),
            "history": str(SBD_HISTORY_FILE),
        },
        "updated_at": _now_iso(),
    }


def build_lmcp_default_sbd_payload(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = {
        "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "registration_number": "",
        "tax_number": "",
        "csd_number": "",
        "director_name": "Lechesa Manaba",
        "director_capacity": "Director",
        "signature_present": False,
        "date_signed": datetime.now().strftime("%Y-%m-%d"),
        "bid_price": None,
        "vat_included": True,
        "pricing_schedule_completed": False,
        "validity_days": 30,
        "sbd_1_completed": False,
        "sbd_4_completed": False,
        "sbd_6_1_completed": False,
        "sbd_8_completed": False,
        "sbd_9_completed": False,
    }

    if overrides:
        data.update(overrides)

    return data
