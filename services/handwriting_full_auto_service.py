"""
LMCP AutoQuote - V16 Full Auto Handwriting Form Completion

Drop-in target:
    app/services/handwriting_full_auto_service.py

Purpose:
    One-step form completion pipeline:

        PDF
          -> V15 auto-detect fields
          -> map LMCP/default values
          -> V14 signature handling
          -> V13.2 real-ink handwriting overlay
          -> final completed PDF

Dependencies:
    Existing working services:
      - app.services.handwriting_field_detector_service
      - app.services.handwriting_simulation_service

API companion:
    app/api/handwriting_full_auto_api.py
"""

from __future__ import annotations

import json
import os
import re
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_full_auto"
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
FULL_AUTO_DIR = HANDWRITING_DIR / "full_auto"
FULL_AUTO_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FullAutoResult:
    status: str
    engine_version: str
    buyer_rfq_number: str
    input_pdf: Optional[str]
    detected_count: int
    mapped_count: int
    output_pdf: Optional[str]
    output_png_preview: Optional[str]
    detection_preview: Optional[str]
    detection_manifest: Optional[str]
    handwriting_manifest: Optional[str]
    message: str
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _safe_slug(value: Any, fallback: str = "FULL-AUTO-FORM") -> str:
    raw = str(value or fallback).strip()
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-._")
    return raw[:100] or fallback


def _resolve_path(value: Any) -> Optional[Path]:
    if not value:
        return None
    p = Path(str(value))
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def _default_lmcp_values(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Conservative defaults. Payload values override these.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    defaults = {
        "company": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "name": "Lechesa Manaba",
        "capacity": "Director",
        "designation": "Director",
        "position": "Director",
        "date": today,
        "email": payload.get("email") or "lechesam@me.com",
        "telephone": payload.get("telephone") or "0826338492",
    }

    user_values = payload.get("values") or payload.get("field_values") or {}
    if isinstance(user_values, dict):
        defaults.update({k: v for k, v in user_values.items() if str(v).strip()})

    return defaults


def _add_signature_field_if_requested(handwriting_payload: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds one manual signature field only if the user requests it and V15 did not map one.
    Useful for blank-page testing and forms where signature line is not vector-detected.
    """
    auto_add = bool(payload.get("auto_add_signature", True))
    if not auto_add:
        return handwriting_payload

    fields = list(handwriting_payload.get("fields") or [])
    has_signature = any(
        "signature" in str(f.get("text", "")).lower()
        or "signature" in str(f.get("label_hint", "")).lower()
        or f.get("is_signature")
        for f in fields
        if isinstance(f, dict)
    )

    if has_signature:
        handwriting_payload["fields"] = fields
        return handwriting_payload

    signature_x = float(payload.get("signature_x") or 120)
    signature_y = float(payload.get("signature_y") or 620)
    signature_width = float(payload.get("signature_width") or 190)

    fields.append(
        {
            "page": int(payload.get("signature_page") or 1),
            "x": signature_x,
            "y": signature_y,
            "text": "SIGNATURE",
            "font_size": 13,
            "max_width": signature_width,
            "label_hint": "Signature",
            "detected_field_type": "v16_auto_signature",
            "confidence": 0.99,
        }
    )
    handwriting_payload["fields"] = fields
    return handwriting_payload


def run_full_auto_handwriting_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main V16 entrypoint.

    Example payload:
    {
      "buyer_rfq_number": "TEST-V16-001",
      "input_pdf": "/tmp/lmcp_runtime/test_tender_pack/form.pdf",
      "reference_image": "/tmp/lmcp_runtime/handwriting_simulation/clean_ink_cropped.png",
      "signature_image": "/tmp/lmcp_runtime/handwriting_simulation/signature.png",
      "ink_color": "black",
      "values": {
        "company": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "name": "Lechesa Manaba",
        "capacity": "Director",
        "date": "2026-04-26"
      }
    }
    """
    payload = payload or {}

    try:
        from app.services.handwriting_field_detector_service import build_handwriting_payload_from_detection
        from app.services.handwriting_simulation_service import complete_handwriting_form
    except Exception as exc:
        result = FullAutoResult(
            status="error",
            engine_version="V16_FULL_AUTO_HANDWRITING",
            buyer_rfq_number=_safe_slug(payload.get("buyer_rfq_number")),
            input_pdf=str(payload.get("input_pdf") or ""),
            detected_count=0,
            mapped_count=0,
            output_pdf=None,
            output_png_preview=None,
            detection_preview=None,
            detection_manifest=None,
            handwriting_manifest=None,
            message="Required handwriting services could not be imported.",
            error=f"{exc}\n{traceback.format_exc()}",
        )
        return asdict(result)

    buyer_rfq_number = _safe_slug(
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("quote_number")
        or f"FULL-AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    input_pdf = _resolve_path(payload.get("input_pdf") or payload.get("pdf_path") or payload.get("source_pdf"))
    if not input_pdf or not input_pdf.exists():
        result = FullAutoResult(
            status="error",
            engine_version="V16_FULL_AUTO_HANDWRITING",
            buyer_rfq_number=buyer_rfq_number,
            input_pdf=str(input_pdf) if input_pdf else None,
            detected_count=0,
            mapped_count=0,
            output_pdf=None,
            output_png_preview=None,
            detection_preview=None,
            detection_manifest=None,
            handwriting_manifest=None,
            message="Input PDF not found.",
            error=f"Input PDF not found: {input_pdf}",
        )
        return asdict(result)

    values = _default_lmcp_values(payload)

    detection_payload = dict(payload)
    detection_payload["buyer_rfq_number"] = buyer_rfq_number
    detection_payload["input_pdf"] = str(input_pdf)
    detection_payload["values"] = values
    detection_payload.setdefault("limit", int(payload.get("limit") or 80))
    detection_payload.setdefault("min_confidence", float(payload.get("min_confidence") or 0.50))

    detection_result = build_handwriting_payload_from_detection(detection_payload)
    if detection_result.get("status") != "ok":
        result = FullAutoResult(
            status="error",
            engine_version="V16_FULL_AUTO_HANDWRITING",
            buyer_rfq_number=buyer_rfq_number,
            input_pdf=str(input_pdf),
            detected_count=0,
            mapped_count=0,
            output_pdf=None,
            output_png_preview=None,
            detection_preview=None,
            detection_manifest=None,
            handwriting_manifest=None,
            message="V15 field detection failed.",
            error=json.dumps(detection_result, indent=2),
        )
        return asdict(result)

    handwriting_payload = dict(detection_result.get("handwriting_payload") or {})
    detection = detection_result.get("detection") or {}

    handwriting_payload["buyer_rfq_number"] = buyer_rfq_number
    handwriting_payload["input_pdf"] = str(input_pdf)
    handwriting_payload["writer_id"] = payload.get("writer_id") or "LMCP_REAL_INK_WRITER"
    handwriting_payload["reference_image"] = (
        payload.get("reference_image")
        or payload.get("clean_ink_path")
        or str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "clean_ink_cropped.png")
    )
    handwriting_payload["signature_image"] = (
        payload.get("signature_image")
        or payload.get("signature_path")
        or str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "signature.png")
    )
    handwriting_payload["ink_color"] = payload.get("ink_color") or "black"
    handwriting_payload["signature_ink_color"] = payload.get("signature_ink_color") or handwriting_payload["ink_color"]
    handwriting_payload["debug"] = bool(payload.get("debug", True))

    output_pdf = payload.get("output_pdf") or payload.get("output_path")
    if output_pdf:
        handwriting_payload["output_pdf"] = output_pdf
    else:
        handwriting_payload["output_pdf"] = str(
            HANDWRITING_DIR
            / "glyph_form_outputs"
            / f"{buyer_rfq_number}__v16_full_auto_completed_form.pdf"
        )

    handwriting_payload = _add_signature_field_if_requested(handwriting_payload, payload)

    if not handwriting_payload.get("fields"):
        result = FullAutoResult(
            status="error",
            engine_version="V16_FULL_AUTO_HANDWRITING",
            buyer_rfq_number=buyer_rfq_number,
            input_pdf=str(input_pdf),
            detected_count=int(detection.get("detected_count") or 0),
            mapped_count=0,
            output_pdf=None,
            output_png_preview=None,
            detection_preview=detection.get("debug_preview"),
            detection_manifest=detection.get("manifest_path"),
            handwriting_manifest=None,
            message="V15 detected fields, but none could be mapped to values.",
            error=json.dumps(detection, indent=2),
        )
        return asdict(result)

    handwriting_result = complete_handwriting_form(handwriting_payload)
    if handwriting_result.get("status") != "ok":
        result = FullAutoResult(
            status="error",
            engine_version="V16_FULL_AUTO_HANDWRITING",
            buyer_rfq_number=buyer_rfq_number,
            input_pdf=str(input_pdf),
            detected_count=int(detection.get("detected_count") or 0),
            mapped_count=len(handwriting_payload.get("fields") or []),
            output_pdf=None,
            output_png_preview=None,
            detection_preview=detection.get("debug_preview"),
            detection_manifest=detection.get("manifest_path"),
            handwriting_manifest=None,
            message="V13/V14 handwriting completion failed.",
            error=json.dumps(handwriting_result, indent=2),
        )
        return asdict(result)

    output_path = handwriting_result.get("output_pdf")
    manifest_path = None
    if output_path:
        p = Path(output_path)
        manifest_candidate = p.with_suffix(".manifest.json")
        manifest_path = str(manifest_candidate) if manifest_candidate.exists() else None

    result = FullAutoResult(
        status="ok",
        engine_version="V16_FULL_AUTO_HANDWRITING",
        buyer_rfq_number=buyer_rfq_number,
        input_pdf=str(input_pdf),
        detected_count=int(detection.get("detected_count") or 0),
        mapped_count=len(handwriting_payload.get("fields") or []),
        output_pdf=handwriting_result.get("output_pdf"),
        output_png_preview=handwriting_result.get("output_png_preview"),
        detection_preview=detection.get("debug_preview"),
        detection_manifest=detection.get("manifest_path"),
        handwriting_manifest=manifest_path,
        message="V16 full auto handwriting form completion finished successfully.",
    )

    full_auto_manifest = FULL_AUTO_DIR / f"{buyer_rfq_number}__v16_full_auto_manifest.json"
    full_auto_manifest.write_text(
        json.dumps(
            {
                "result": asdict(result),
                "detection": detection,
                "handwriting_payload": handwriting_payload,
                "handwriting_result": handwriting_result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    final = asdict(result)
    final["full_auto_manifest"] = str(full_auto_manifest)
    return final


def get_full_auto_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "handwriting_full_auto_service",
        "engine_version": "V16_FULL_AUTO_HANDWRITING",
        "full_auto_dir": str(FULL_AUTO_DIR),
        "pipeline": [
            "V15_AUTO_DETECT_FIELDS",
            "V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE",
            "PDF_OUTPUT",
        ],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def example_payload() -> Dict[str, Any]:
    return {
        "buyer_rfq_number": "TEST-V16-FULL-AUTO-001",
        "input_pdf": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "test_tender_pack" / "form.pdf"),
        "writer_id": "LMCP_REAL_INK_WRITER",
        "reference_image": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "clean_ink_cropped.png"),
        "signature_image": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "signature.png"),
        "ink_color": "black",
        "debug": True,
        "auto_add_signature": True,
        "values": {
            "company": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "name": "Lechesa Manaba",
            "capacity": "Director",
            "designation": "Director",
            "date": datetime.now().strftime("%Y-%m-%d"),
        },
    }


if __name__ == "__main__":
    print(json.dumps(get_full_auto_status(), indent=2))
