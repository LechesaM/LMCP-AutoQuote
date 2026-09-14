from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.governance.thazat import build_outcome_learning


DEFAULT_RUNTIME_DIR = Path("runtime")
MAX_OUTCOME_RECORDS = 5_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _outcome_file(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_dir(runtime_dir) / "thazat" / "outcomes.json"


def _float(value: Any) -> float:
    try:
        return round(float(value or 0.0), 2)
    except Exception:
        return 0.0


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize_outcome_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the institutional bid-outcome record used by THAZAT learning."""

    bid_price = _float(payload.get("bid_price"))
    landed_cost = _float(payload.get("landed_cost"))
    expected_gp = _float(payload.get("expected_gp"))
    if not expected_gp and bid_price:
        expected_gp = round(bid_price - landed_cost, 2)

    expected_margin_percent = _float(payload.get("expected_margin_percent"))
    if not expected_margin_percent and bid_price:
        expected_margin_percent = round((expected_gp / bid_price) * 100.0, 2)

    learning_payload = dict(payload)
    learning_payload["result"] = payload.get("amiri_result") or payload.get("result") or "UNKNOWN"
    learning_payload["loss_reason"] = payload.get("loss_reason") or payload.get("reason_won_lost") or "UNKNOWN"
    learning_payload["bid_price"] = bid_price
    learning = build_outcome_learning(learning_payload).as_dict()

    return {
        "buyer": str(payload.get("buyer") or payload.get("buyer_name") or "").strip(),
        "rfq": str(
            payload.get("rfq")
            or payload.get("rfq_number")
            or payload.get("tender_number")
            or payload.get("reference")
            or ""
        ).strip(),
        "category": str(payload.get("category") or "").strip(),
        "closing_date": str(payload.get("closing_date") or "").strip(),
        "estimated_value": _float(payload.get("estimated_value") or payload.get("estimated_contract_value")),
        "suppliers": _string_list(payload.get("suppliers")),
        "supplier_cost": _float(payload.get("supplier_cost")),
        "landed_cost": landed_cost,
        "bid_price": bid_price,
        "expected_gp": expected_gp,
        "expected_margin_percent": expected_margin_percent,
        "compliance_status": str(payload.get("compliance_status") or "").strip(),
        "competitors": _string_list(payload.get("competitors")),
        "winner": str(payload.get("winner") or "").strip(),
        "winning_price": None if payload.get("winning_price") in (None, "") else _float(payload.get("winning_price")),
        "award_date": str(payload.get("award_date") or "").strip(),
        "amiri_result": str(payload.get("amiri_result") or payload.get("result") or "UNKNOWN").strip().upper(),
        "reason_won_lost": str(payload.get("reason_won_lost") or payload.get("loss_reason") or "UNKNOWN").strip().upper(),
        "learning": learning,
        "recorded_at": str(payload.get("recorded_at") or _now_iso()),
    }


def load_outcomes(runtime_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    path = _outcome_file(runtime_dir)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def record_outcome(payload: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    record = normalize_outcome_record(payload)
    records = load_outcomes(runtime_dir)
    records.append(record)
    records = records[-MAX_OUTCOME_RECORDS:]

    path = _outcome_file(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    return record


def summarize_outcomes(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    records = load_outcomes(runtime_dir)
    won = [item for item in records if item.get("amiri_result") == "WON"]
    lost = [item for item in records if item.get("amiri_result") == "LOST"]
    disqualified = [item for item in records if item.get("amiri_result") == "DISQUALIFIED"]
    known_price_losses = [
        item for item in lost
        if (item.get("learning") or {}).get("loss_reason") == "PRICE"
    ]
    total_expected_gp = round(sum(_float(item.get("expected_gp")) for item in records), 2)

    return {
        "status": "ok",
        "total_records": len(records),
        "won": len(won),
        "lost": len(lost),
        "disqualified": len(disqualified),
        "price_losses": len(known_price_losses),
        "recorded_expected_gp": total_expected_gp,
        "recent": list(reversed(records[-20:])),
        "data_source": str(_outcome_file(runtime_dir)),
    }
