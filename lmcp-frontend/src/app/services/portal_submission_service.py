from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNTIME_DIR = Path("runtime")
PORTAL_DIR = RUNTIME_DIR / "portal_submission"
PORTAL_DIR.mkdir(parents=True, exist_ok=True)

PORTAL_HISTORY_FILE = PORTAL_DIR / "portal_submission_history.json"
PORTAL_MANUAL_QUEUE_FILE = PORTAL_DIR / "manual_portal_queue.json"
PORTAL_PROOF_DIR = PORTAL_DIR / "proofs"
PORTAL_PROOF_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_AUTO_PORTAL_DOMAINS: List[str] = [
    # Keep empty until a portal has a stable, tested, non-CAPTCHA submission path.
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


def _save_list(path: Path, items: List[Dict[str, Any]], limit: int = 2000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[-limit:], indent=2, default=str))


def _normalise_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _portal_domain(url: str) -> str:
    value = str(url or "").strip().lower()
    value = value.replace("https://", "").replace("http://", "")
    return value.split("/")[0]


def classify_submission_route(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = _normalise_text(
        payload.get("submission_method")
        or payload.get("submission_channel")
        or payload.get("method")
        or ""
    )
    portal_url = str(
        payload.get("portal_url")
        or payload.get("submission_url")
        or payload.get("url")
        or ""
    ).strip()

    email = str(
        payload.get("recipient_email")
        or payload.get("submission_email")
        or payload.get("buyer_email")
        or ""
    ).strip()

    if "email" in method or email:
        route = "email"
        auto_supported = True
        reason = "Email submission route detected."
    elif "portal" in method or portal_url:
        route = "portal"
        domain = _portal_domain(portal_url)
        auto_supported = bool(domain and any(domain.endswith(x) for x in SUPPORTED_AUTO_PORTAL_DOMAINS))
        reason = (
            "Portal route detected and domain is auto-supported."
            if auto_supported
            else "Portal route detected but auto-submission is not enabled for this portal. Manual action/proof required."
        )
    elif "physical" in method or "hand" in method or "courier" in method:
        route = "physical"
        auto_supported = False
        reason = "Physical/manual submission route detected."
    else:
        route = "unknown"
        auto_supported = False
        reason = "Submission route could not be determined."

    return {
        "status": "ok",
        "route": route,
        "auto_supported": auto_supported,
        "reason": reason,
        "portal_url": portal_url,
        "portal_domain": _portal_domain(portal_url),
        "email": email,
        "method": method,
        "checked_at": _now_iso(),
    }


async def _publish(event_type: str, payload: Dict[str, Any]) -> None:
    try:
        from app.services.websocket_broker import publish_dashboard_event

        await publish_dashboard_event(
            event_type=event_type,
            payload=payload,
            source="portal-submission-fix",
        )
    except Exception:
        pass


async def _audit(event_type: str, title: str, message: str, severity: str, payload: Dict[str, Any]) -> None:
    try:
        from app.services.audit_trail_service import record_audit_event

        await record_audit_event(
            event_type=event_type,
            source="portal-submission-fix",
            severity=severity,
            title=title,
            message=message,
            buyer_rfq_number=payload.get("buyer_rfq_number") or "",
            quote_number=payload.get("quote_number") or "",
            payload=payload,
        )
    except Exception:
        pass


def _history_append(item: Dict[str, Any]) -> None:
    history = _load_list(PORTAL_HISTORY_FILE)
    history.append(item)
    _save_list(PORTAL_HISTORY_FILE, history)


def _manual_queue_append(item: Dict[str, Any]) -> None:
    queue = _load_list(PORTAL_MANUAL_QUEUE_FILE)
    queue.append(item)
    _save_list(PORTAL_MANUAL_QUEUE_FILE, queue)


async def prepare_portal_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    route = classify_submission_route(payload)
    buyer_rfq_number = str(payload.get("buyer_rfq_number") or payload.get("rfq_number") or "").strip()
    quote_number = str(payload.get("quote_number") or "").strip()

    item = {
        "status": "ok",
        "stage": "prepare_portal_submission",
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "route": route,
        "payload": payload,
        "created_at": _now_iso(),
    }

    if route["route"] == "portal" and not route["auto_supported"]:
        item["submission_status"] = "manual_portal_submission_required"
        item["message"] = "Portal submission requires manual action. The system will not mark it as submitted automatically."
        _manual_queue_append(item)
        await _publish("portal_manual_action_required", item)
        await _audit(
            "portal_manual_action_required",
            "Portal manual action required",
            item["message"],
            "warning",
            item,
        )
    elif route["route"] == "email":
        item["submission_status"] = "email_submission_route"
        item["message"] = "Email route detected. Continue through email submission pipeline."
        await _publish("portal_route_email_detected", item)
    elif route["route"] == "physical":
        item["submission_status"] = "physical_submission_required"
        item["message"] = "Physical submission required. Do not auto-submit."
        _manual_queue_append(item)
        await _publish("physical_submission_required", item)
    elif route["route"] == "portal" and route["auto_supported"]:
        item["submission_status"] = "portal_auto_supported"
        item["message"] = "Portal auto-submission route is supported. Proceed only if the portal adapter is wired."
        await _publish("portal_auto_supported", item)
    else:
        item["submission_status"] = "unknown_submission_route"
        item["message"] = "Unknown submission route. Manual review required."
        _manual_queue_append(item)
        await _publish("submission_route_unknown", item)

    _history_append(item)
    return item


async def mark_portal_submission_proof(payload: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = str(payload.get("buyer_rfq_number") or "").strip()
    quote_number = str(payload.get("quote_number") or "").strip()
    proof_note = str(payload.get("proof_note") or payload.get("note") or "").strip()
    proof_url = str(payload.get("proof_url") or "").strip()

    proof = {
        "status": "ok",
        "submission_status": "portal_submission_proof_recorded",
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "proof_note": proof_note,
        "proof_url": proof_url,
        "payload": payload,
        "recorded_at": _now_iso(),
    }

    proof_file = PORTAL_PROOF_DIR / f"{buyer_rfq_number or 'UNKNOWN'}__{quote_number or 'NOQUOTE'}__proof.json"
    proof_file.write_text(json.dumps(proof, indent=2, default=str))
    proof["proof_file"] = str(proof_file)

    _history_append(proof)
    await _publish("portal_submission_proof_recorded", proof)
    await _audit(
        "portal_submission_proof_recorded",
        "Portal submission proof recorded",
        "Portal/manual submission proof was recorded.",
        "success",
        proof,
    )

    return proof


def get_portal_submission_status(limit: int = 50) -> Dict[str, Any]:
    history = _load_list(PORTAL_HISTORY_FILE)
    queue = _load_list(PORTAL_MANUAL_QUEUE_FILE)

    return {
        "status": "ok",
        "summary": {
            "history_total": len(history),
            "manual_queue_total": len(queue),
            "proof_files_total": len(list(PORTAL_PROOF_DIR.glob("*_proof.json"))),
            "auto_supported_domains": SUPPORTED_AUTO_PORTAL_DOMAINS,
        },
        "recent_history": list(reversed(history[-limit:])),
        "manual_queue": list(reversed(queue[-limit:])),
        "files": {
            "history": str(PORTAL_HISTORY_FILE),
            "manual_queue": str(PORTAL_MANUAL_QUEUE_FILE),
            "proof_dir": str(PORTAL_PROOF_DIR),
        },
        "updated_at": _now_iso(),
    }
