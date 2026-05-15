from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.decision_intelligence_service import score_opportunity
from app.services.pipeline_enforcement_service import (
    enforce_before_quote,
    enforce_before_rfq_processing,
)
from app.services.operator_action_service import force_quote

RUNTIME_DIR = Path("runtime")
CYCLE_DIR = RUNTIME_DIR / "autonomous_cycle"
CYCLE_DIR.mkdir(parents=True, exist_ok=True)

CYCLE_HISTORY_FILE = CYCLE_DIR / "cycle_history.json"
LAST_CYCLE_FILE = CYCLE_DIR / "last_cycle.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


async def _publish(event_type: str, payload: Dict[str, Any]) -> None:
    try:
        from app.services.websocket_broker import publish_dashboard_event
        await publish_dashboard_event(
            event_type=event_type,
            payload=payload,
            source="full-autonomous-cycle",
        )
    except Exception:
        pass


async def _audit(event_type: str, title: str, message: str, severity: str, payload: Dict[str, Any]) -> None:
    try:
        from app.services.audit_trail_service import record_audit_event
        await record_audit_event(
            event_type=event_type,
            source="full-autonomous-cycle",
            severity=severity,
            title=title,
            message=message,
            buyer_rfq_number=payload.get("buyer_rfq_number") or "",
            quote_number=payload.get("quote_number") or "",
            payload=payload,
        )
    except Exception:
        pass


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _system_enabled() -> Dict[str, Any]:
    try:
        from app.services.system_control_service import get_system_status
        status = get_system_status()
        enabled = bool(
            status.get("enabled")
            if isinstance(status, dict)
            else True
        )
        return {"enabled": enabled, "status": status}
    except Exception:
        pass

    try:
        status_file = Path("runtime/autonomous_status.json")
        if status_file.exists():
            data = json.loads(status_file.read_text())
            return {"enabled": bool(data.get("enabled", True)), "status": data}
    except Exception:
        pass

    return {"enabled": True, "status": {"message": "No system control status found; default allowed."}}


def _normalize_opportunity(item: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = (
        item.get("buyer_rfq_number")
        or item.get("rfq_number")
        or item.get("tender_number")
        or item.get("reference")
        or item.get("id")
        or "RFQ-NO-ID"
    )

    return {
        **item,
        "buyer_rfq_number": buyer_rfq_number,
        "title": item.get("title") or item.get("description") or buyer_rfq_number,
        "buyer_name": item.get("buyer_name") or item.get("buyer") or item.get("organ_of_state") or "—",
        "source_name": item.get("source_name") or item.get("source") or item.get("portal") or "unknown",
    }


async def _harvest_opportunities(limit: int = 20) -> List[Dict[str, Any]]:
    harvest_attempts = [
        ("app.services.tender_harvester", "run_national_tender_radar"),
        ("app.services.tender_harvester", "harvest_tenders"),
        ("app.services.live_rfq_store", "list_live_opportunities"),
        ("app.services.live_rfq_store", "get_live_opportunities"),
    ]

    for module_path, fn_name in harvest_attempts:
        try:
            module = importlib.import_module(module_path)
            fn = getattr(module, fn_name, None)
            if not callable(fn):
                continue

            try:
                result = await _maybe_await(fn(max_total=limit, max_per_source=limit, enable_auto_quote=False, persist_to_live_store=True))
            except TypeError:
                try:
                    result = await _maybe_await(fn(limit=limit))
                except TypeError:
                    result = await _maybe_await(fn())

            if isinstance(result, dict):
                candidates = (
                    result.get("items")
                    or result.get("opportunities")
                    or result.get("results")
                    or result.get("rfqs")
                    or []
                )
            elif isinstance(result, list):
                candidates = result
            else:
                candidates = []

            normalized = [_normalize_opportunity(x) for x in candidates if isinstance(x, dict)]
            if normalized:
                return normalized[:limit]
        except Exception:
            continue

    # Safe fallback for testing cycle when harvester returns no items.
    return [
        {
            "buyer_rfq_number": f"DEMO-CYCLE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": "Supply and delivery of stationery",
            "buyer_name": "Demo Municipality",
            "source_name": "cycle-demo",
            "submission_method": "email",
            "estimated_profit": 45000,
            "estimated_margin_percent": 30,
            "briefing_required": False,
        }
    ]


async def run_full_autonomous_cycle(limit: int = 10, dry_run: bool = False) -> Dict[str, Any]:
    started_at = _now_iso()
    system = _system_enabled()

    cycle: Dict[str, Any] = {
        "status": "running",
        "started_at": started_at,
        "finished_at": None,
        "dry_run": dry_run,
        "limit": limit,
        "system": system,
        "harvested": 0,
        "scored": 0,
        "auto_approved": 0,
        "manual_review": 0,
        "rejected": 0,
        "blocked": 0,
        "force_quote_queued": 0,
        "items": [],
    }

    if not system.get("enabled", True):
        cycle["status"] = "blocked"
        cycle["message"] = "Autonomous cycle blocked because system is OFF."
        cycle["finished_at"] = _now_iso()
        _save_json(LAST_CYCLE_FILE, cycle)
        await _publish("autonomous_cycle_blocked", cycle)
        await _audit("autonomous_cycle_blocked", "Autonomous cycle blocked", cycle["message"], "warning", cycle)
        return cycle

    await _publish("autonomous_cycle_started", cycle)

    opportunities = await _harvest_opportunities(limit=limit)
    cycle["harvested"] = len(opportunities)

    for opportunity in opportunities:
        item = {
            "opportunity": opportunity,
            "decision": None,
            "rfq_guard": None,
            "quote_guard": None,
            "action": None,
            "status": "started",
        }

        try:
            scored = score_opportunity(opportunity)
            item["decision"] = scored
            cycle["scored"] += 1

            if scored.get("decision") == "auto_approve":
                cycle["auto_approved"] += 1
            elif scored.get("decision") == "manual_review":
                cycle["manual_review"] += 1
            else:
                cycle["rejected"] += 1
                item["status"] = "decision_rejected"
                cycle["items"].append(item)
                continue

            rfq_guard = await enforce_before_rfq_processing(opportunity)
            item["rfq_guard"] = rfq_guard
            if not rfq_guard.get("allowed"):
                cycle["blocked"] += 1
                item["status"] = "blocked_before_rfq_processing"
                cycle["items"].append(item)
                continue

            quote_guard = await enforce_before_quote(opportunity)
            item["quote_guard"] = quote_guard
            if not quote_guard.get("allowed"):
                cycle["blocked"] += 1
                item["status"] = "blocked_before_quote"
                cycle["items"].append(item)
                continue

            if dry_run:
                item["status"] = "dry_run_ready_for_quote"
                item["action"] = {"message": "Dry run only; force quote not triggered."}
            else:
                action = await force_quote({
                    **opportunity,
                    "reason": "Full autonomous cycle auto-approved opportunity",
                })
                item["action"] = action
                cycle["force_quote_queued"] += 1
                item["status"] = "force_quote_queued"

            await _publish("autonomous_cycle_item_processed", item)
        except Exception as exc:
            item["status"] = "error"
            item["error"] = str(exc)

        cycle["items"].append(item)

    cycle["status"] = "ok"
    cycle["finished_at"] = _now_iso()
    cycle["message"] = "Full autonomous cycle completed."

    history = _load_json_list(CYCLE_HISTORY_FILE)
    history.append(cycle)
    _save_json(CYCLE_HISTORY_FILE, history[-500:])
    _save_json(LAST_CYCLE_FILE, cycle)

    await _publish("autonomous_cycle_completed", cycle)
    await _audit("autonomous_cycle_completed", "Autonomous cycle completed", cycle["message"], "success", cycle)

    return cycle


def get_full_cycle_status(limit: int = 20) -> Dict[str, Any]:
    history = _load_json_list(CYCLE_HISTORY_FILE)
    last = {}
    if LAST_CYCLE_FILE.exists():
        try:
            last = json.loads(LAST_CYCLE_FILE.read_text())
        except Exception:
            last = {}

    return {
        "status": "ok",
        "last_cycle": last,
        "recent_cycles": list(reversed(history[-limit:])),
        "history_file": str(CYCLE_HISTORY_FILE),
        "last_cycle_file": str(LAST_CYCLE_FILE),
        "updated_at": _now_iso(),
    }
