from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
MONTHLY_QUOTES_DIR = Path("monthly_quotes")
PORTAL_UPLOAD_DIR = RUNTIME_DIR / "portal_uploads"
PORTAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_HISTORY_FILE = PORTAL_UPLOAD_DIR / "portal_upload_history.json"
UPLOAD_ASSISTED_FILE = PORTAL_UPLOAD_DIR / "assisted_upload_required.json"
LATEST_QUOTE_DISCOVERY_FILE = PORTAL_UPLOAD_DIR / "latest_quote_discovery.json"


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


def _path_exists(path_value: str) -> bool:
    if not path_value:
        return False

    path = Path(path_value)
    candidates = [
        path,
        Path("/app") / path_value,
        Path.cwd() / path_value,
        Path("/Users/Shared/LMCP-AutoQuote-Server") / path_value,
    ]

    return any(candidate.exists() for candidate in candidates)


def _resolve_path(path_value: str) -> Optional[str]:
    if not path_value:
        return None

    candidates = [
        Path(path_value),
        Path("/app") / path_value,
        Path.cwd() / path_value,
        Path("/Users/Shared/LMCP-AutoQuote-Server") / path_value,
    ]

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        except Exception:
            continue

    return None


def _find_latest_generated_quote_pdf(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Finds the newest generated LMCP quote PDF.

    Priority:
    1. Match buyer RFQ number folder/name.
    2. Match quote number folder/name.
    3. Fallback to newest PDF under monthly_quotes/.
    """
    buyer_rfq = _buyer_rfq_number(payload)
    quote_number = _quote_number(payload)

    search_roots = [
        MONTHLY_QUOTES_DIR,
        Path("/app/monthly_quotes"),
        Path("/Users/Shared/LMCP-AutoQuote-Server/monthly_quotes"),
    ]

    pdfs: List[Path] = []
    for root in search_roots:
        try:
            if root.exists():
                pdfs.extend([p for p in root.rglob("*.pdf") if p.is_file()])
        except Exception:
            continue

    unique: Dict[str, Path] = {}
    for pdf in pdfs:
        unique[str(pdf)] = pdf
    pdfs = list(unique.values())

    if not pdfs:
        result = {
            "status": "not_found",
            "buyer_rfq_number": buyer_rfq,
            "quote_number": quote_number,
            "reason": "No PDF files found under monthly_quotes.",
            "checked_at": _now(),
        }
        _write_json(LATEST_QUOTE_DISCOVERY_FILE, result)
        return result

    def score(pdf: Path) -> int:
        haystack = str(pdf).lower()
        points = 0
        if buyer_rfq and buyer_rfq.lower() in haystack:
            points += 1000
        if quote_number and quote_number.lower() in haystack:
            points += 1000
        if "lmcp" in haystack:
            points += 100
        if "quote" in haystack or "rfq" in haystack:
            points += 50
        return points

    pdfs = sorted(
        pdfs,
        key=lambda p: (score(p), p.stat().st_mtime),
        reverse=True,
    )

    selected = pdfs[0]

    # Prefer relative path if inside current project.
    selected_str = str(selected)
    try:
        cwd = Path.cwd().resolve()
        selected_str = str(selected.resolve().relative_to(cwd))
    except Exception:
        pass

    result = {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq,
        "quote_number": quote_number,
        "selected_pdf": selected_str,
        "selected_pdf_absolute": str(selected.resolve()),
        "candidate_count": len(pdfs),
        "score": score(selected),
        "modified_at": datetime.fromtimestamp(selected.stat().st_mtime, timezone.utc).isoformat(),
        "checked_at": _now(),
    }
    _write_json(LATEST_QUOTE_DISCOVERY_FILE, result)
    return result


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
        for key in ["attachments", "submission_attachments", "supporting_documents"]:
            raw = submission_pack.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif raw:
                values.append(raw)

    for key in ["pdf_path", "final_pdf_path", "quote_pdf_path"]:
        if payload.get(key):
            values.append(payload.get(key))

    output: List[str] = []
    seen = set()
    for item in values:
        path = _safe_str(item)
        if not path or path in seen:
            continue
        seen.add(path)
        output.append(path)

    if not output:
        latest = _find_latest_generated_quote_pdf(payload)
        if latest.get("status") == "ok" and latest.get("selected_pdf"):
            output.append(latest["selected_pdf"])

    return output


def _validate_attachments(attachments: List[str]) -> Dict[str, Any]:
    checked = []
    missing = []

    for attachment in attachments:
        resolved = _resolve_path(attachment)
        exists = bool(resolved)
        row = {"path": attachment, "exists": exists, "resolved_path": resolved}
        checked.append(row)
        if not exists:
            missing.append(attachment)

    return {
        "status": "ok" if not missing else "missing_files",
        "checked": checked,
        "missing": missing,
        "count": len(attachments),
    }


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


def _looks_uploaded(result: Dict[str, Any]) -> bool:
    status = _safe_lower(result.get("status") or result.get("upload_status") or result.get("submission_status"))

    return (
        result.get("uploaded") is True
        or result.get("documents_uploaded") is True
        or result.get("attachments_uploaded") is True
        or result.get("portal_upload_complete") is True
        or status in {"ok", "uploaded", "success", "completed", "done"}
        and any(
            key in result
            for key in [
                "uploaded_files",
                "attachments_uploaded",
                "upload_result",
                "proof",
                "screenshot_path",
                "portal_session",
            ]
        )
    )


async def upload_submission_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Production portal upload bridge with automatic latest quote attachment.

    If no attachments are passed, it finds the latest generated LMCP quote PDF
    under monthly_quotes/ and sends that to the browser upload engine.
    """
    payload = deepcopy(payload if isinstance(payload, dict) else {})

    attachments = _normalise_attachments(payload)
    validation = _validate_attachments(attachments)

    buyer_rfq = _buyer_rfq_number(payload)
    quote_number = _quote_number(payload)
    portal_url = _safe_str(payload.get("portal_url") or payload.get("submission_url") or payload.get("url"))
    portal_domain = _safe_str(payload.get("portal_domain"))

    bridge_payload = {
        **payload,
        "buyer_rfq_number": buyer_rfq,
        "quote_number": quote_number,
        "portal_url": portal_url,
        "portal_domain": portal_domain,
        "attachments": attachments,
        "submission_attachments": attachments,
        "attachment_validation": validation,
        "latest_quote_auto_attached": bool(attachments),
    }

    attempts: List[Dict[str, Any]] = []

    candidate_calls = [
        ("app.services.smart_upload_v47_4_service", "run_smart_upload"),
        ("app.services.smart_upload_v47_4_service", "smart_upload_documents"),
        ("app.services.live_browser_attach_v47_3_service", "attach_documents_to_live_browser"),
        ("app.services.live_browser_attach_v47_3_service", "attach_documents"),
        ("app.services.assisted_browser_v47_2_service", "upload_documents"),
        ("app.services.portal_submission_v47_service", "upload_documents_to_portal"),
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
                "buyer_rfq_number": buyer_rfq,
                "quote_number": quote_number,
                "portal_url": portal_url,
                "portal_domain": portal_domain,
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
            _append_json(UPLOAD_HISTORY_FILE, result)
            return result

    result = {
        "status": "assisted_required",
        "uploaded": False,
        "documents_uploaded": False,
        "buyer_rfq_number": buyer_rfq,
        "quote_number": quote_number,
        "portal_url": portal_url,
        "portal_domain": portal_domain,
        "attachments": attachments,
        "attachment_validation": validation,
        "latest_quote_discovery": _read_json(LATEST_QUOTE_DISCOVERY_FILE, {}),
        "reason": "No existing V47/V48 browser upload bridge returned a confirmed upload success.",
        "attempts": attempts,
        "created_at": _now(),
    }

    _append_json(UPLOAD_ASSISTED_FILE, result)
    _append_json(UPLOAD_HISTORY_FILE, result)
    return result


async def run_portal_upload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await upload_submission_documents(payload)


async def upload_documents_to_portal(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await upload_submission_documents(payload)


def find_latest_generated_quote(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _find_latest_generated_quote_pdf(payload or {})


def get_portal_upload_status(limit: int = 50) -> Dict[str, Any]:
    history = _read_json(UPLOAD_HISTORY_FILE, [])
    assisted = _read_json(UPLOAD_ASSISTED_FILE, [])

    if not isinstance(history, list):
        history = []
    if not isinstance(assisted, list):
        assisted = []

    uploaded_count = len([x for x in history if isinstance(x, dict) and x.get("uploaded") is True])

    return {
        "status": "ok",
        "summary": {
            "history_total": len(history),
            "uploaded_total": uploaded_count,
            "assisted_required_total": len(assisted),
        },
        "latest_quote_discovery": _read_json(LATEST_QUOTE_DISCOVERY_FILE, {}),
        "recent_history": history[-limit:],
        "recent_assisted": assisted[-limit:],
        "files": {
            "history": str(UPLOAD_HISTORY_FILE),
            "assisted": str(UPLOAD_ASSISTED_FILE),
            "latest_quote_discovery": str(LATEST_QUOTE_DISCOVERY_FILE),
            "runtime_dir": str(PORTAL_UPLOAD_DIR),
        },
        "updated_at": _now(),
    }
