from __future__ import annotations

"""
LMCP AutoQuote - SBD Auto Completion Pipeline Service

Drop-in path:
    app/services/sbd_auto_completion_service.py

Purpose:
    Connect the stable tender_form_intelligence_engine.py into the quote /
    submission pipeline without rewriting the whole tender_pipeline.py.

Stable target engine:
    V22.7.4_COMPANY_NAME_RECOVERY_LOCK_ENGINE or later.

Usage from pipeline:
    from app.services.sbd_auto_completion_service import complete_sbd_for_pipeline

    result = complete_sbd_for_pipeline({
        "buyer_rfq_number": buyer_rfq_number,
        "input_pdf": rfq_pdf_path,
        "signature_image": "runtime/handwriting_simulation/sample_signature.png",
        "entity_type": "pty_ltd",
        "debug": True,
    })

    if result["status"] == "ok":
        completed_pdf = result["completed_pdf"]
        # attach completed_pdf to quote pack / submission pack
"""

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.services import tender_form_intelligence_engine as sbd_engine

SERVICE_VERSION = "SBD_AUTO_COMPLETION_PIPELINE_SERVICE_V1"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOCAL_PROJECT_ROOT = Path.cwd().resolve()

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "sbd_auto_completion"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = RUNTIME_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _safe_str(value: Any, fallback: str = "") -> str:
    value = "" if value is None else str(value)
    return value.strip() or fallback


def _safe_filename(value: Any, fallback: str = "RFQ") -> str:
    import re

    raw = _safe_str(value, fallback)
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw[:90] or fallback


def _resolve_path(path_value: Union[str, Path, None]) -> Optional[Path]:
    if not path_value:
        return None

    raw = str(path_value).strip()
    if not raw:
        return None

    candidates: List[Path] = []
    p = Path(raw)
    candidates.append(p)

    if raw.startswith("/app/"):
        candidates.append(PROJECT_ROOT / raw.replace("/app/", "", 1))

    if not p.is_absolute():
        candidates.append(PROJECT_ROOT / raw)
        candidates.append(LOCAL_PROJECT_ROOT / raw)

    if "/runtime/" in raw:
        tail = raw.split("/runtime/", 1)[1]
        candidates.append(PROJECT_ROOT / "runtime" / tail)
        candidates.append(LOCAL_PROJECT_ROOT / "runtime" / tail)

    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except Exception:
            continue

    try:
        return candidates[0].resolve()
    except Exception:
        return candidates[0]


def _default_signature_image() -> Optional[str]:
    runtime_root = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
    candidates = [
        runtime_root / "handwriting_simulation" / "sample_signature.png",
        runtime_root / "handwriting_simulation" / "sample_signature_real.png",
        runtime_root / "handwriting_simulation" / "sample_signature.jpg",
        runtime_root / "handwriting_simulation" / "signature.png",
        PROJECT_ROOT / "app" / "assets" / "signatures" / "director.png",
        LOCAL_PROJECT_ROOT / "runtime" / "handwriting_simulation" / "sample_signature.png",
        LOCAL_PROJECT_ROOT / "runtime" / "handwriting_simulation" / "sample_signature_real.png",
        LOCAL_PROJECT_ROOT / "runtime" / "handwriting_simulation" / "sample_signature.jpg",
        LOCAL_PROJECT_ROOT / "runtime" / "handwriting_simulation" / "signature.png",
        LOCAL_PROJECT_ROOT / "app" / "assets" / "signatures" / "director.png",
    ]

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                # Prefer runtime-relative path where possible.
                try:
                    rel = candidate.relative_to(PROJECT_ROOT)
                    return str(rel)
                except Exception:
                    return str(candidate)
        except Exception:
            continue

    return None


def _write_log(buyer_rfq_number: str, data: Dict[str, Any]) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_path = LOG_DIR / f"{_safe_filename(buyer_rfq_number)}__{stamp}.json"
    try:
        log_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return str(log_path)


def get_sbd_auto_completion_status() -> Dict[str, Any]:
    engine_status: Dict[str, Any]
    try:
        if hasattr(sbd_engine, "get_tender_form_intelligence_status"):
            engine_status = sbd_engine.get_tender_form_intelligence_status()
        elif hasattr(sbd_engine, "status"):
            engine_status = sbd_engine.status()
        else:
            engine_status = {
                "status": "unknown",
                "engine_version": getattr(sbd_engine, "ENGINE_VERSION", "unknown"),
            }
    except Exception as exc:
        engine_status = {
            "status": "error",
            "message": str(exc),
            "engine_version": getattr(sbd_engine, "ENGINE_VERSION", "unknown"),
        }

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "message": "SBD auto-completion pipeline service is available.",
        "runtime_dir": str(RUNTIME_DIR),
        "log_dir": str(LOG_DIR),
        "default_signature_image": _default_signature_image(),
        "engine": engine_status,
    }


def complete_sbd_for_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main pipeline entry point.

    Required:
      - input_pdf or pdf_path

    Recommended:
      - buyer_rfq_number
      - signature_image
      - entity_type='pty_ltd'
      - ink_color='black'
      - debug=True

    Returns:
      - status
      - completed_pdf/output_pdf when successful
      - attach_to_quote_pack flag
      - attach_to_submission_pack flag
    """
    payload = dict(payload or {})

    buyer_rfq_number = _safe_str(
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("reference_number"),
        "RFQ",
    )

    input_pdf = payload.get("input_pdf") or payload.get("pdf_path") or payload.get("source_pdf")
    resolved_pdf = _resolve_path(input_pdf)

    if not resolved_pdf or not resolved_pdf.exists():
        result = {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "engine_version": getattr(sbd_engine, "ENGINE_VERSION", "unknown"),
            "buyer_rfq_number": buyer_rfq_number,
            "message": "Input PDF not found for SBD auto-completion.",
            "input_pdf": str(input_pdf),
            "resolved_input_pdf": str(resolved_pdf) if resolved_pdf else None,
            "attach_to_quote_pack": False,
            "attach_to_submission_pack": False,
        }
        result["log_json"] = _write_log(buyer_rfq_number, result)
        return result

    signature_image = payload.get("signature_image") or _default_signature_image()

    engine_payload = {
        **payload,
        "buyer_rfq_number": buyer_rfq_number,
        "input_pdf": str(resolved_pdf),
        "signature_image": signature_image,
        "ink_color": payload.get("ink_color") or "black",
        "entity_type": payload.get("entity_type") or "pty_ltd",
        "debug": bool(payload.get("debug", True)),
    }

    try:
        if hasattr(sbd_engine, "complete_tender_form"):
            result = sbd_engine.complete_tender_form(engine_payload)
        elif hasattr(sbd_engine, "complete_tender_form_intelligence"):
            result = sbd_engine.complete_tender_form_intelligence(engine_payload)
        elif hasattr(sbd_engine, "complete_sbd_form"):
            result = sbd_engine.complete_sbd_form(engine_payload)
        else:
            result = {
                "status": "error",
                "message": "No compatible SBD completion function found.",
                "engine_version": getattr(sbd_engine, "ENGINE_VERSION", "unknown"),
            }

        result = dict(result or {})
        result.setdefault("service_version", SERVICE_VERSION)
        result.setdefault("buyer_rfq_number", buyer_rfq_number)
        result.setdefault("engine_version", getattr(sbd_engine, "ENGINE_VERSION", "unknown"))

        if result.get("status") == "ok":
            completed_pdf = result.get("completed_pdf") or result.get("output_pdf")
            result["sbd_completed"] = True
            result["completed_pdf"] = completed_pdf
            result["output_pdf"] = completed_pdf
            result["attach_to_quote_pack"] = bool(completed_pdf)
            result["attach_to_submission_pack"] = bool(completed_pdf)
            result["submission_attachment_type"] = "completed_sbd_form"
            result["message"] = result.get("message") or "SBD/tender form completed and ready for pack attachment."
        else:
            result["sbd_completed"] = False
            result["attach_to_quote_pack"] = False
            result["attach_to_submission_pack"] = False

        result["log_json"] = _write_log(buyer_rfq_number, result)
        return result

    except Exception as exc:
        result = {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "engine_version": getattr(sbd_engine, "ENGINE_VERSION", "unknown"),
            "buyer_rfq_number": buyer_rfq_number,
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "input_pdf": str(resolved_pdf),
            "attach_to_quote_pack": False,
            "attach_to_submission_pack": False,
        }
        result["log_json"] = _write_log(buyer_rfq_number, result)
        return result


def complete_sbd_from_pipeline_result(pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience wrapper for existing tender pipeline result dicts.
    It tries common PDF keys without requiring the caller to reshape data.
    """
    pipeline_result = dict(pipeline_result or {})

    pdf_candidates = [
        pipeline_result.get("input_pdf"),
        pipeline_result.get("rfq_pdf"),
        pipeline_result.get("source_pdf"),
        pipeline_result.get("downloaded_pdf"),
        pipeline_result.get("tender_document_path"),
        pipeline_result.get("document_path"),
        pipeline_result.get("original_pdf"),
    ]

    input_pdf = next((p for p in pdf_candidates if p), None)

    payload = {
        **pipeline_result,
        "input_pdf": input_pdf,
        "buyer_rfq_number": (
            pipeline_result.get("buyer_rfq_number")
            or pipeline_result.get("rfq_number")
            or pipeline_result.get("reference_number")
            or pipeline_result.get("quote_number")
            or "RFQ"
        ),
        "entity_type": pipeline_result.get("entity_type") or "pty_ltd",
        "signature_image": pipeline_result.get("signature_image") or _default_signature_image(),
        "ink_color": pipeline_result.get("ink_color") or "black",
        "debug": bool(pipeline_result.get("debug", True)),
    }

    return complete_sbd_for_pipeline(payload)


def merge_sbd_result_into_pipeline_result(
    pipeline_result: Dict[str, Any],
    sbd_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Safely merge completed SBD output into a pipeline result dict.

    This does not overwrite existing quote PDFs. It only adds SBD-specific keys
    and appends the completed SBD to attachment lists.
    """
    merged = dict(pipeline_result or {})
    sbd_result = dict(sbd_result or {})

    merged["sbd_auto_completion"] = sbd_result
    merged["sbd_completed"] = sbd_result.get("status") == "ok"

    completed_pdf = sbd_result.get("completed_pdf") or sbd_result.get("output_pdf")
    if completed_pdf:
        merged["completed_sbd_pdf"] = completed_pdf

        attachments = list(merged.get("attachments") or [])
        if completed_pdf not in attachments:
            attachments.append(completed_pdf)
        merged["attachments"] = attachments

        submission_attachments = list(merged.get("submission_attachments") or [])
        if completed_pdf not in submission_attachments:
            submission_attachments.append(completed_pdf)
        merged["submission_attachments"] = submission_attachments

        quote_pack_attachments = list(merged.get("quote_pack_attachments") or [])
        if completed_pdf not in quote_pack_attachments:
            quote_pack_attachments.append(completed_pdf)
        merged["quote_pack_attachments"] = quote_pack_attachments

    return merged


def run_sbd_auto_completion_for_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Alias used by some API/router naming styles.
    """
    return complete_sbd_for_pipeline(payload)


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_sbd_for_pipeline(payload)


if __name__ == "__main__":
    print(json.dumps(get_sbd_auto_completion_status(), indent=2, default=str))
