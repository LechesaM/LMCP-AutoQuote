from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
SBD_DIR = RUNTIME_DIR / "sbd_completion"
SBD_DIR.mkdir(parents=True, exist_ok=True)

SBD_STATUS_FILE = SBD_DIR / "sbd_completion_status.json"
SBD_HISTORY_FILE = SBD_DIR / "sbd_completion_history.json"

REQUIRED_FIELDS = [
    "buyer_rfq_number",
    "company_name",
    "registration_number",
    "tax_number",
    "csd_number",
    "director_name",
    "director_capacity",
    "signature_present",
    "date_signed",
    "bid_price",
    "vat_included",
    "pricing_schedule_completed",
    "validity_days",
    "sbd_1_completed",
    "sbd_4_completed",
    "sbd_6_1_completed",
    "sbd_8_completed",
    "sbd_9_completed",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str))


def evaluate_sbd_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = []
    for field in REQUIRED_FIELDS:
        value = payload.get(field)
        if value is None or value == "" or value is False:
            missing.append(field)

    total = len(REQUIRED_FIELDS)
    done = total - len(missing)
    ready = len(missing) == 0

    return {
        "status": "ok",
        "buyer_rfq_number": payload.get("buyer_rfq_number") or payload.get("rfq_number") or "",
        "sbd_ready": ready,
        "completion_percent": round((done / total) * 100, 1),
        "missing_fields": missing,
        "message": "SBD/buyer forms are ready for submission." if ready else "SBD/buyer forms are incomplete.",
        "evaluated_at": _now_iso(),
        "payload": payload,
    }


async def record_sbd_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = evaluate_sbd_completion(payload)

    status = _load_dict(SBD_STATUS_FILE)
    key = result["buyer_rfq_number"] or f"UNKNOWN-{datetime.now().timestamp()}"
    status[key] = result
    _save(SBD_STATUS_FILE, status)

    history = _load_list(SBD_HISTORY_FILE)
    history.append(result)
    _save(SBD_HISTORY_FILE, history[-1000:])

    return result


def get_sbd_completion_summary(limit: int = 50) -> Dict[str, Any]:
    status = _load_dict(SBD_STATUS_FILE)
    history = _load_list(SBD_HISTORY_FILE)

    ready = [x for x in status.values() if x.get("sbd_ready")]
    incomplete = [x for x in status.values() if not x.get("sbd_ready")]

    return {
        "status": "ok",
        "summary": {
            "tracked_rfqs": len(status),
            "ready": len(ready),
            "incomplete": len(incomplete),
            "history_total": len(history),
        },
        "ready_items": ready[-limit:],
        "incomplete_items": incomplete[-limit:],
        "recent_history": list(reversed(history[-limit:])),
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
