from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.runtime_paths import get_runtime_paths

RUNTIME_DIR = get_runtime_paths().runtime_root
PRODUCTION_LOCK_DIR = RUNTIME_DIR / "production_lock"
PRODUCTION_LOCK_DIR.mkdir(parents=True, exist_ok=True)

LAST_DECISION_FILE = PRODUCTION_LOCK_DIR / "last_decision.json"
DECISION_HISTORY_FILE = PRODUCTION_LOCK_DIR / "decision_history.json"
POLICY_FILE = PRODUCTION_LOCK_DIR / "production_policy.json"

MIN_PROFIT_REQUIRED = float(os.getenv("LMCP_MIN_PROFIT_REQUIRED", "30000"))
MIN_MARGIN_PERCENT = float(os.getenv("LMCP_MIN_MARGIN_PERCENT", "25"))


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative

EXCLUDED_CATEGORY_KEYWORDS = [
    "medical", "pharmaceutical", "medicine", "clinic", "hospital consumable",
    "medical consumable", "surgical", "syringe", "bandage", "glucose", "drug",
    "it equipment", "laptop", "desktop", "computer", "printer", "server",
    "monitor", "router", "switch", "ups", "software", "scanner", "tablet",
    "petrol", "diesel", "fuel", "catering", "food", "refreshment",
]

BRIEFING_KEYWORDS = [
    "compulsory briefing", "mandatory briefing", "compulsory site briefing",
    "mandatory site briefing", "site inspection is compulsory",
    "briefing session is compulsory",
]

SAFE_BRIEFING_NEGATIONS = [
    "no compulsory briefing", "not compulsory", "non-compulsory",
    "not mandatory", "briefing session: no", "briefing required: no",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("R", "").replace(",", "").replace("%", "").strip()
        return float(value)
    except Exception:
        return default


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _append_json(path: Path, item: Dict[str, Any]) -> None:
    data = _read_json(path, [])
    if not isinstance(data, list):
        data = []
    data.append(item)
    _write_json(path, data[-2000:])


def _payload_text(payload: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in [
        "buyer_rfq_number", "rfq_number", "reference_number", "quote_number",
        "title", "description", "buyer_name", "category", "tender_category",
        "submission_method", "briefing_details", "briefing", "notes",
    ]:
        value = payload.get(key)
        if value:
            parts.append(str(value))

    items = payload.get("items") or payload.get("line_items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                parts.extend([str(v) for v in item.values() if v is not None])
            else:
                parts.append(str(item))
    return " ".join(parts)


def _is_test_or_demo(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    text = _safe_lower(_payload_text(payload))
    markers = ["test", "demo", "dummy", "sample", "sandbox", "q-live-001", "sedcol-test", "live-portal-test"]
    hits = [m for m in markers if m in text]
    return bool(hits), hits


def _is_expired(payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    date_keys = ["closing_date", "closing_datetime", "closing_at", "deadline", "submission_deadline", "tender_closing_date"]
    checked: Dict[str, Any] = {}
    for key in date_keys:
        raw = payload.get(key)
        if not raw:
            continue
        text = _safe_str(raw)
        checked[key] = text
        for candidate in [text, text.replace("Z", "+00:00"), text.split(" ")[0]]:
            try:
                dt = datetime.fromisoformat(candidate)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                return dt < now, {"key": key, "value": text, "parsed": dt.isoformat(), "now": now.isoformat()}
            except Exception:
                continue
    return False, {"checked": checked, "message": "No parseable closing date found."}


def _has_compulsory_briefing(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    if payload.get("briefing_required") is True:
        return True, ["briefing_required=true"]
    text = _safe_lower(_payload_text(payload))
    for safe in SAFE_BRIEFING_NEGATIONS:
        if safe in text:
            return False, [f"safe_negation:{safe}"]
    hits = [kw for kw in BRIEFING_KEYWORDS if kw in text]
    return bool(hits), hits


def _has_excluded_category(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    text = _safe_lower(_payload_text(payload))
    hits = [kw for kw in EXCLUDED_CATEGORY_KEYWORDS if kw in text]
    return bool(hits), hits


def _extract_profit_margin(payload: Dict[str, Any]) -> Dict[str, Any]:
    pricing = payload.get("pricing") or payload.get("pricing_summary") or payload.get("quote_pricing") or {}
    if not isinstance(pricing, dict):
        pricing = {}
    profit = (
        payload.get("estimated_profit") or payload.get("total_profit") or payload.get("profit")
        or pricing.get("total_profit") or pricing.get("estimated_profit") or pricing.get("profit")
    )
    margin = (
        payload.get("estimated_margin_percent") or payload.get("achieved_margin_percent")
        or payload.get("margin_percent") or pricing.get("achieved_margin_percent")
        or pricing.get("minimum_margin_percent") or pricing.get("margin_percent")
    )
    return {
        "profit": _to_float(profit, 0.0),
        "margin_percent": _to_float(margin, 0.0),
        "raw_profit": profit,
        "raw_margin": margin,
    }


def _load_policy(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    default = {
        "enabled": True,
        "mode": "production_locked",
        "block_test_demo": True,
        "block_expired": True,
        "block_compulsory_briefing": True,
        "block_excluded_categories": True,
        "enforce_profit": True,
        "minimum_profit_required": MIN_PROFIT_REQUIRED,
        "minimum_margin_percent": MIN_MARGIN_PERCENT,
        "excluded_category_keywords": EXCLUDED_CATEGORY_KEYWORDS,
        "updated_at": _now(),
    }
    policy_file = _resolve_runtime_path(POLICY_FILE, runtime_dir)
    existing = _read_json(policy_file, None)
    if not isinstance(existing, dict):
        _write_json(policy_file, default)
        return default
    return {**default, **existing}


def save_production_policy(policy: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    current = _load_policy(runtime_dir=runtime_dir)
    updated = {**current, **(policy if isinstance(policy, dict) else {})}
    updated["updated_at"] = _now()
    policy_file = _resolve_runtime_path(POLICY_FILE, runtime_dir)
    _write_json(policy_file, updated)
    return {"status": "ok", "policy": updated, "policy_file": str(policy_file)}


def get_production_policy(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    policy_file = _resolve_runtime_path(POLICY_FILE, runtime_dir)
    return {"status": "ok", "policy": _load_policy(runtime_dir=runtime_dir), "policy_file": str(policy_file), "updated_at": _now()}


def evaluate_production_lock(payload: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    policy = _load_policy(runtime_dir=runtime_dir)
    reasons: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not policy.get("enabled", True):
        decision = {"status": "allowed", "allowed": True, "production_locked": False, "message": "Production lock is disabled by policy.", "policy": policy, "checked_at": _now()}
        last_file = _resolve_runtime_path(LAST_DECISION_FILE, runtime_dir)
        history_file = _resolve_runtime_path(DECISION_HISTORY_FILE, runtime_dir)
        _write_json(last_file, decision)
        _append_json(history_file, decision)
        return decision

    is_test, test_hits = _is_test_or_demo(payload)
    if policy.get("block_test_demo", True) and is_test:
        reasons.append({"code": "TEST_OR_DEMO_BLOCKED", "message": "TEST/DEMO/SAMPLE RFQs are blocked in production mode.", "hits": test_hits})

    expired, expired_info = _is_expired(payload)
    if policy.get("block_expired", True) and expired:
        reasons.append({"code": "EXPIRED_TENDER_BLOCKED", "message": "Tender appears expired or past closing date.", "details": expired_info})
    elif expired_info.get("message"):
        warnings.append({"code": "NO_CLOSING_DATE", "message": "No parseable closing date found.", "details": expired_info})

    briefing, briefing_hits = _has_compulsory_briefing(payload)
    if policy.get("block_compulsory_briefing", True) and briefing:
        reasons.append({"code": "COMPULSORY_BRIEFING_BLOCKED", "message": "Compulsory briefing/site inspection detected.", "hits": briefing_hits})

    excluded, excluded_hits = _has_excluded_category(payload)
    if policy.get("block_excluded_categories", True) and excluded:
        reasons.append({"code": "EXCLUDED_CATEGORY_BLOCKED", "message": "Excluded category detected.", "hits": excluded_hits})

    profit_info = _extract_profit_margin(payload)
    min_profit = _to_float(policy.get("minimum_profit_required"), MIN_PROFIT_REQUIRED)
    min_margin = _to_float(policy.get("minimum_margin_percent"), MIN_MARGIN_PERCENT)

    if policy.get("enforce_profit", True):
        if profit_info["profit"] < min_profit:
            reasons.append({"code": "LOW_PROFIT_BLOCKED", "message": f"Estimated profit is below required minimum of R{min_profit:,.2f}.", "actual_profit": profit_info["profit"], "required_profit": min_profit})
        if profit_info["margin_percent"] < min_margin:
            reasons.append({"code": "LOW_MARGIN_BLOCKED", "message": f"Estimated margin is below required minimum of {min_margin:.2f}%.", "actual_margin_percent": profit_info["margin_percent"], "required_margin_percent": min_margin})

    allowed = len(reasons) == 0
    decision = {
        "status": "allowed" if allowed else "blocked",
        "allowed": allowed,
        "production_locked": True,
        "submission_allowed": allowed,
        "message": "Submission allowed by production lock." if allowed else "Submission blocked by production lock.",
        "reasons": reasons,
        "warnings": warnings,
        "profit_check": profit_info,
        "policy": policy,
        "payload_keys": sorted(list(payload.keys())),
        "checked_at": _now(),
    }
    last_file = _resolve_runtime_path(LAST_DECISION_FILE, runtime_dir)
    history_file = _resolve_runtime_path(DECISION_HISTORY_FILE, runtime_dir)
    _write_json(last_file, decision)
    _append_json(history_file, decision)
    return decision


def assert_production_submission_allowed(payload: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    decision = evaluate_production_lock(payload, runtime_dir=runtime_dir)
    if decision.get("allowed"):
        return decision
    return {**decision, "status": "blocked", "allowed": False, "submitted": False, "portal_auto_submitted": False, "submission_status": "blocked_by_production_lock"}


def get_production_lock_status(limit: int = 50, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    history_file = _resolve_runtime_path(DECISION_HISTORY_FILE, runtime_dir)
    last_file = _resolve_runtime_path(LAST_DECISION_FILE, runtime_dir)
    policy_file = _resolve_runtime_path(POLICY_FILE, runtime_dir)
    history = _read_json(history_file, [])
    if not isinstance(history, list):
        history = []
    last = _read_json(last_file, {})
    blocked_total = len([d for d in history if isinstance(d, dict) and not d.get("allowed")])
    allowed_total = len([d for d in history if isinstance(d, dict) and d.get("allowed")])
    return {
        "status": "ok",
        "service_version": "LMCP_PRODUCTION_LOCK_V1",
        "summary": {"history_total": len(history), "allowed_total": allowed_total, "blocked_total": blocked_total, "minimum_profit_required": MIN_PROFIT_REQUIRED, "minimum_margin_percent": MIN_MARGIN_PERCENT},
        "last_decision": last,
        "recent_decisions": history[-limit:],
        "policy": _load_policy(runtime_dir=runtime_dir),
        "files": {"policy": str(policy_file), "last_decision": str(last_file), "history": str(history_file)},
        "updated_at": _now(),
    }
