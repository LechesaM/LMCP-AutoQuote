from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


RUNTIME_DIR = Path("runtime")
SMART_UPLOAD_DIR = RUNTIME_DIR / "smart_upload_v47_4"
SMART_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_HISTORY_FILE = SMART_UPLOAD_DIR / "smart_upload_history.json"
ASSISTED_QUEUE_FILE = SMART_UPLOAD_DIR / "assisted_upload_queue.json"
LAST_UPLOAD_FILE = SMART_UPLOAD_DIR / "last_upload.json"


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return deepcopy(default)
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _append_json(path: Path, item: Dict[str, Any]) -> None:
    data = _read_json(path, [])
    if not isinstance(data, list):
        data = []
    data.append(item)
    _write_json(path, data)


def _buyer_rfq_number(payload: Dict[str, Any]) -> str:
    return _safe_str(
        payload.get("_locked_buyer_rfq_number")
        or payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("reference_number")
        or payload.get("document_number")
        or payload.get("tender_number")
        or "UNKNOWN-RFQ"
    )


def _quote_number(payload: Dict[str, Any]) -> str:
    buyer_rfq = _buyer_rfq_number(payload)
    return _safe_str(payload.get("quote_number") or payload.get("lmcp_quote_number") or f"LMCP-{buyer_rfq}")


def _normalise_attachments(payload: Dict[str, Any]) -> List[str]:
    values: List[Any] = []

    for key in ["attachments", "submission_attachments", "supporting_documents", "documents"]:
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif raw:
            values.append(raw)

    submission_pack = payload.get("submission_pack")
    if isinstance(submission_pack, dict):
        for key in ["attachments", "submission_attachments", "supporting_documents", "supporting_docs"]:
            raw = submission_pack.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif raw:
                values.append(raw)

    for key in ["pdf_path", "final_pdf_path", "quote_pdf_path"]:
        raw = payload.get(key)
        if raw:
            values.append(raw)

    output: List[str] = []
    seen = set()

    for item in values:
        path = _safe_str(item)
        if not path or path in seen:
            continue
        seen.add(path)
        output.append(path)

    return output


def _resolve_path(path_value: str, runtime_dir: Optional[str] = None) -> Optional[str]:
    if not path_value:
        return None

    runtime_root = Path(runtime_dir).expanduser().resolve() if runtime_dir else None
    candidates = [
        Path(path_value),
        Path("/app") / path_value,
        Path.cwd() / path_value,
        Path("/Users/Shared/LMCP-AutoQuote-Server") / path_value,
    ]
    if runtime_root is not None:
        candidates.insert(1, runtime_root / path_value)

    for candidate in candidates:
        try:
            if candidate.exists():
                return str(candidate)
        except Exception:
            continue

    return None


def _validate_attachments(attachments: List[str], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    checked: List[Dict[str, Any]] = []
    missing: List[str] = []
    resolved: List[str] = []

    for attachment in attachments:
        resolved_path = _resolve_path(attachment, runtime_dir=runtime_dir)
        exists = bool(resolved_path)
        row = {
            "path": attachment,
            "exists": exists,
            "resolved_path": resolved_path,
        }
        checked.append(row)

        if exists and resolved_path:
            resolved.append(resolved_path)
        else:
            missing.append(attachment)

    return {
        "status": "ok" if not missing else "missing_files",
        "checked": checked,
        "missing": missing,
        "resolved": resolved,
        "count": len(attachments),
    }


def _looks_uploaded(result: Dict[str, Any]) -> bool:
    status_text = _safe_lower(
        result.get("status")
        or result.get("upload_status")
        or result.get("submission_status")
        or result.get("stage")
    )

    return (
        result.get("uploaded") is True
        or result.get("documents_uploaded") is True
        or result.get("attachments_uploaded") is True
        or result.get("portal_upload_complete") is True
        or (
            status_text in {"ok", "uploaded", "success", "completed", "done"}
            and any(
                key in result
                for key in [
                    "uploaded_files",
                    "uploaded_count",
                    "attachments_uploaded",
                    "upload_result",
                    "screenshot_path",
                    "proof",
                    "portal_session",
                ]
            )
        )
    )


async def _call_bridge(module_name: str, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        module = __import__(module_name, fromlist=[function_name])
        func = getattr(module, function_name, None)

        if not callable(func):
            return {
                "status": "skipped",
                "module": module_name,
                "function": function_name,
                "reason": "Function not found",
            }

        result = func(payload)

        if hasattr(result, "__await__"):
            result = await result

        if not isinstance(result, dict):
            result = {"raw_result": str(result)}

        return {
            "status": "called",
            "module": module_name,
            "function": function_name,
            "result": result,
        }

    except Exception as exc:
        return {
            "status": "error",
            "module": module_name,
            "function": function_name,
            "error": str(exc),
        }


def _assisted_upload_payload(payload: Dict[str, Any], attempts: List[Dict[str, Any]], validation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "assisted_required",
        "uploaded": False,
        "documents_uploaded": False,
        "stage": "smart_upload_v47_4",
        "buyer_rfq_number": _buyer_rfq_number(payload),
        "quote_number": _quote_number(payload),
        "portal_url": _safe_str(payload.get("portal_url")),
        "portal_domain": _safe_str(payload.get("portal_domain")),
        "attachments": _normalise_attachments(payload),
        "attachment_validation": validation,
        "reason": "No live browser upload implementation confirmed document upload.",
        "attempts": attempts,
        "created_at": _now(),
    }


async def run_smart_upload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    V47.4 Smart Upload Bridge.

    This layer connects portal_submission_service -> existing browser/session/upload helpers.

    It is intentionally truthful:
    - uploaded=True only when a downstream function confirms upload.
    - If browser helpers are missing, it returns assisted_required.
    - It records every attempt for debugging.
    """
    payload = deepcopy(payload if isinstance(payload, dict) else {})

    runtime_dir = _safe_str(payload.get("runtime_dir"))
    attachments = _normalise_attachments(payload)
    validation = _validate_attachments(attachments, runtime_dir=runtime_dir or None)

    bridge_payload = {
        **payload,
        "attachments": attachments,
        "submission_attachments": attachments,
        "attachment_validation": validation,
        "resolved_attachments": validation.get("resolved", []),
        "buyer_rfq_number": _buyer_rfq_number(payload),
        "quote_number": _quote_number(payload),
    }

    attempts: List[Dict[str, Any]] = []

    # Candidate bridge functions likely to exist in your V47 stack.
    candidate_calls = [
        ("app.services.live_browser_attach_v47_3_service", "attach_documents_to_live_browser"),
        ("app.services.live_browser_attach_v47_3_service", "attach_documents"),
        ("app.services.assisted_browser_v47_2_service", "upload_documents"),
        ("app.services.assisted_browser_v47_2_service", "attach_documents"),
        ("app.services.portal_submission_v47_service", "upload_documents_to_portal"),
        ("app.services.portal_submission_v47_service", "run_portal_upload"),
        ("app.services.final_submission_v47_5_service", "upload_documents"),
    ]

    for module_name, function_name in candidate_calls:
        call_result = await _call_bridge(module_name, function_name, bridge_payload)
        attempts.append(call_result)

        inner = call_result.get("result") if isinstance(call_result.get("result"), dict) else {}

        if isinstance(inner, dict) and _looks_uploaded(inner):
            result = {
                "status": "ok",
                "uploaded": True,
                "documents_uploaded": True,
                "stage": "smart_upload_v47_4",
                "buyer_rfq_number": _buyer_rfq_number(payload),
                "quote_number": _quote_number(payload),
                "portal_url": _safe_str(payload.get("portal_url")),
                "portal_domain": _safe_str(payload.get("portal_domain")),
                "attachments": attachments,
                "attachment_validation": validation,
                "bridge": {
                    "module": module_name,
                    "function": function_name,
                },
                "bridge_result": inner,
                "attempts": attempts,
                "uploaded_at": _now(),
            }

            last_upload_file = _resolve_runtime_path(LAST_UPLOAD_FILE, runtime_dir or None)
            history_file = _resolve_runtime_path(UPLOAD_HISTORY_FILE, runtime_dir or None)
            _write_json(last_upload_file, result)
            _append_json(history_file, result)
            return result

    result = _assisted_upload_payload(payload, attempts, validation)

    last_upload_file = _resolve_runtime_path(LAST_UPLOAD_FILE, runtime_dir or None)
    assisted_queue_file = _resolve_runtime_path(ASSISTED_QUEUE_FILE, runtime_dir or None)
    history_file = _resolve_runtime_path(UPLOAD_HISTORY_FILE, runtime_dir or None)
    _write_json(last_upload_file, result)
    _append_json(assisted_queue_file, result)
    _append_json(history_file, result)
    return result


async def smart_upload_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await run_smart_upload(payload)


async def upload_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await run_smart_upload(payload)


def get_smart_upload_status(limit: int = 50, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    history_file = _resolve_runtime_path(UPLOAD_HISTORY_FILE, runtime_dir)
    assisted_queue_file = _resolve_runtime_path(ASSISTED_QUEUE_FILE, runtime_dir)
    last_upload_file = _resolve_runtime_path(LAST_UPLOAD_FILE, runtime_dir)
    history = _read_json(history_file, [])
    assisted = _read_json(assisted_queue_file, [])
    last = _read_json(last_upload_file, {})

    if not isinstance(history, list):
        history = []
    if not isinstance(assisted, list):
        assisted = []

    uploaded_count = len([item for item in history if isinstance(item, dict) and item.get("uploaded") is True])

    return {
        "status": "ok",
        "service_version": "V47_4_SMART_UPLOAD_BRIDGE",
        "summary": {
            "history_total": len(history),
            "uploaded_total": uploaded_count,
            "assisted_required_total": len(assisted),
        },
        "last_upload": last,
        "recent_history": history[-limit:],
        "recent_assisted": assisted[-limit:],
        "files": {
            "history": str(history_file),
            "assisted_queue": str(assisted_queue_file),
            "last_upload": str(last_upload_file),
            "runtime_dir": str(_resolve_runtime_path(SMART_UPLOAD_DIR, runtime_dir)),
        },
        "updated_at": _now(),
    }


async def attach_and_smart_upload(
    autofill_plan_json=None,
    cdp_url="http://host.docker.internal:9222",
    output_dir=None,
    attachments=None,
    fill_visible_fields=True,
    capture_screenshots=True,
    stop_before_submit=True,
    payload=None,
    runtime_dir: Optional[str] = None,
):
    if payload is None:
        payload = {}

    # Load autofill plan metadata so downstream helpers receive buyer_rfq_number,
    # quote_number, portal_url, upload_files, and form_values.
    if autofill_plan_json:
        try:
            import json
            from pathlib import Path
            plan_path = Path(str(autofill_plan_json))
            if plan_path.exists():
                plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                if isinstance(plan_data, dict):
                    payload.update(plan_data)
                    if isinstance(plan_data.get("form_values"), dict):
                        payload.update({k: v for k, v in plan_data["form_values"].items() if v is not None})
        except Exception as exc:
            payload["autofill_plan_load_error"] = str(exc)

    payload.update({
        "autofill_plan_json": autofill_plan_json,
        "cdp_url": cdp_url,
        "output_dir": output_dir,
        "attachments": attachments or payload.get("attachments") or [],
        "fill_visible_fields": fill_visible_fields,
        "capture_screenshots": capture_screenshots,
        "stop_before_submit": stop_before_submit,
        "runtime_dir": runtime_dir,
    })

    return await run_smart_upload(payload)


def get_v47_4_status(limit: int = 50, runtime_dir: Optional[str] = None):
    return get_smart_upload_status(limit=limit, runtime_dir=runtime_dir)
