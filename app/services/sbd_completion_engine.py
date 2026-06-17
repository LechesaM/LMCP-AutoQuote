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


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


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
    path.parent.mkdir(parents=True, exist_ok=True)
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
    runtime_dir = str(payload.get("runtime_dir") or "").strip() or None

    status_file = _resolve_runtime_path(SBD_STATUS_FILE, runtime_dir)
    history_file = _resolve_runtime_path(SBD_HISTORY_FILE, runtime_dir)

    status = _load_dict(status_file)
    key = result["buyer_rfq_number"] or f"UNKNOWN-{datetime.now().timestamp()}"
    status[key] = result
    _save(status_file, status)

    history = _load_list(history_file)
    history.append(result)
    _save(history_file, history[-1000:])

    return result


def get_sbd_completion_summary(limit: int = 50, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    status_file = _resolve_runtime_path(SBD_STATUS_FILE, runtime_dir)
    history_file = _resolve_runtime_path(SBD_HISTORY_FILE, runtime_dir)
    status = _load_dict(status_file)
    history = _load_list(history_file)

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
        "files": {
            "status": str(status_file),
            "history": str(history_file),
            "runtime_dir": str(_resolve_runtime_path(SBD_DIR, runtime_dir)),
        },
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
