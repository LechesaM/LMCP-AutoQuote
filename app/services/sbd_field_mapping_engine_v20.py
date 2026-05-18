"""
LMCP AutoQuote — V20.1 Clean Writer Engine
File: app/services/sbd_field_mapping_engine_v20.py

V20.1.1 purpose:
- Keep V18 intelligence for page classification and action discovery.
- Keep V20 cleanup for duplicate/noise suppression.
- NEW: Regenerate a clean PDF from the ORIGINAL buyer PDF using cleaned actions.
- Do not return the messy V18-rendered PDF as the main output.

This is a controlled writer. It focuses on safer placement:
- write text with width guards
- tick boxes with centered X
- place signature image once per signature action when available
- clamp coordinates
- skip unsafe/empty/duplicate actions
"""

from __future__ import annotations

import copy
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover
    fitz = None
    _FITZ_IMPORT_ERROR = exc
else:
    _FITZ_IMPORT_ERROR = None

try:
    from app.services.tender_form_intelligence_engine import (
        run_tender_form_intelligence_completion,
        run_sbd_intelligence_completion,
        get_tender_form_intelligence_status,
        get_sbd_intelligence_status,
    )
except Exception:
    run_tender_form_intelligence_completion = None
    run_sbd_intelligence_completion = None
    get_tender_form_intelligence_status = None
    get_sbd_intelligence_status = None


ENGINE_VERSION = "V20_1_1_COORDINATE_FIXED_WRITER"
V20_RUNTIME_DIR = Path("/app/runtime/handwriting_simulation/v20_field_mapping")
V20_OUTPUT_DIR = Path("/app/runtime/handwriting_simulation/v20_clean_writer_outputs")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return re.sub(r"\s+", " ", text)


def _project_roots() -> List[Path]:
    roots: List[Path] = []
    for raw in [
        os.getenv("LMCP_PROJECT_ROOT"),
        "/app",
        "/Users/Shared/LMCP-AutoQuote-Server",
        str(Path.cwd()),
    ]:
        if not raw:
            continue
        try:
            p = Path(raw).expanduser().resolve()
        except Exception:
            p = Path(raw)
        if p not in roots:
            roots.append(p)
    return roots


def resolve_runtime_path(value: Any, must_exist: bool = False) -> Optional[Path]:
    """
    Path-safe resolver. Preserves double spaces in filenames.
    """
    value_str = _path_text(value)
    if not value_str:
        return None

    raw = Path(value_str).expanduser()
    candidates: List[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
        raw_str = str(raw)

        if raw_str.startswith("/app/"):
            suffix = raw_str[len("/app/") :]
            for root in _project_roots():
                candidates.append(root / suffix)

        marker = "LMCP-AutoQuote-Server/"
        if marker in raw_str:
            suffix = raw_str.split(marker, 1)[1]
            for root in _project_roots():
                candidates.append(root / suffix)
    else:
        candidates.append(raw)
        for root in _project_roots():
            candidates.append(root / raw)

    seen = set()
    unique: List[Path] = []
    for c in candidates:
        try:
            cc = c.resolve()
        except Exception:
            cc = c
        s = str(cc)
        if s not in seen:
            seen.add(s)
            unique.append(cc)

    if must_exist:
        for c in unique:
            if c.exists():
                return c
        return None

    return unique[0] if unique else raw


def _action_key(action: Dict[str, Any]) -> Tuple[Any, ...]:
    page = int(action.get("page") or 0)
    field = _safe_text(action.get("field_name") or action.get("label_hint") or "")
    text = _safe_text(action.get("text") or "")
    x = round(float(action.get("x") or 0) / 8) * 8
    y = round(float(action.get("y") or 0) / 8) * 8
    kind = _safe_text(action.get("action") or "write")
    return (page, field, text, x, y, kind)


def _looks_like_particulars(action: Dict[str, Any]) -> bool:
    field = _safe_text(action.get("field_name") or "").lower()
    source = _safe_text(action.get("source_rule") or "").lower()
    text = _safe_text(action.get("text") or "").lower()

    if "particular" in field or "particular" in source:
        return True
    if field.endswith("_na") or text == "n/a":
        return False
    return False


def _is_low_confidence_noise(action: Dict[str, Any]) -> bool:
    text = _safe_text(action.get("text") or "")
    font_size = float(action.get("font_size") or 10)
    x = float(action.get("x") or 0)
    y = float(action.get("y") or 0)

    if not text:
        return True
    if x < 15 or y < 5:
        return True
    if len(text) > 15 and font_size <= 7:
        return True
    return False


def _clamp_action(action: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(action)

    try:
        x = float(a.get("x") or 0)
        y = float(a.get("y") or 0)
    except Exception:
        return a

    a["x"] = max(25.0, min(x, 545.0))
    a["y"] = max(20.0, min(y, 805.0))

    text = _safe_text(a.get("text") or "")
    if len(text) > 50 and not a.get("max_width"):
        a["max_width"] = 260

    return a


def clean_v18_actions(actions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    seen = set()

    no_answer_sources = set()
    for a in actions:
        text = _safe_text(a.get("text") or "").upper()
        source = _safe_text(a.get("source_rule") or "")
        field = _safe_text(a.get("field_name") or "")
        if text in {"NO", "N/A"} or source.endswith("=no") or source.endswith("=n/a") or field.endswith("_NO"):
            root = source.split("=")[0] if "=" in source else field
            if root:
                no_answer_sources.add(root)

    for action in actions:
        a = copy.deepcopy(action)

        if _is_low_confidence_noise(a):
            removed.append({"reason": "low_confidence_or_edge_noise", "action": action})
            continue

        if _looks_like_particulars(a):
            source = _safe_text(a.get("source_rule") or "")
            root = source.split("=")[0] if "=" in source else ""
            if root in no_answer_sources or "related-enterprises" in source:
                removed.append({"reason": "suppressed_particulars_for_no_or_na_answer", "action": action})
                continue

        a = _clamp_action(a)
        key = _action_key(a)

        if key in seen:
            removed.append({"reason": "duplicate_action", "action": action})
            continue

        seen.add(key)
        cleaned.append(a)

    stats = {
        "input_action_count": len(actions),
        "cleaned_action_count": len(cleaned),
        "removed_action_count": len(removed),
        "removed": removed[:250],
        "cleanup_rules": [
            "duplicate_action_suppression",
            "low_confidence_edge_noise_suppression",
            "particulars_suppression_when_no_or_na",
            "coordinate_soft_clamp",
            "long_text_max_width_guard",
        ],
    }
    return cleaned, stats


def _call_v18(payload: Dict[str, Any]) -> Dict[str, Any]:
    if callable(run_tender_form_intelligence_completion):
        return run_tender_form_intelligence_completion(payload)
    if callable(run_sbd_intelligence_completion):
        return run_sbd_intelligence_completion(payload)
    raise RuntimeError(
        "Could not import V18 tender form intelligence function. "
        "Expected run_tender_form_intelligence_completion or run_sbd_intelligence_completion."
    )


def _fit_text_font_size(text: str, requested: float, max_width: Optional[float]) -> float:
    """
    Simple conservative font sizing.
    """
    font_size = float(requested or 10)
    if not max_width:
        return max(7.0, min(font_size, 13.0))

    # Approx text width estimate: 0.52 * font_size * chars.
    estimated = len(text) * font_size * 0.52
    if estimated <= max_width:
        return max(7.0, min(font_size, 13.0))

    reduced = max_width / max(1.0, len(text) * 0.52)
    return max(6.5, min(font_size, reduced))


def _to_pymupdf_y(page: Any, detected_y: float) -> float:
    """
    V18/V20 detected coordinates behave like bottom-left PDF coordinates.
    PyMuPDF writing uses top-left coordinates.
    Convert Y before writing.
    """
    return max(20.0, min(float(page.rect.height) - float(detected_y), float(page.rect.height) - 20.0))


def _insert_wrapped_text(page: Any, x: float, y: float, text: str, font_size: float, max_width: Optional[float]) -> None:
    text = _safe_text(text)
    if not text:
        return

    if max_width and max_width > 40:
        rect_height = max(16, font_size * 3.2)
        rect = fitz.Rect(x, y - font_size, min(x + max_width, page.rect.width - 25), y + rect_height)
        page.insert_textbox(
            rect,
            text,
            fontsize=font_size,
            fontname="helv",
            color=(0, 0, 0),
            align=0,
            overlay=True,
        )
    else:
        page.insert_text(
            fitz.Point(x, y),
            text,
            fontsize=font_size,
            fontname="helv",
            color=(0, 0, 0),
            overlay=True,
        )


def _insert_signature(page: Any, action: Dict[str, Any], signature_image: Optional[Path]) -> bool:
    x = float(action.get("x") or 72)
    detected_y = float(action.get("y") or 72)
    y = _to_pymupdf_y(page, detected_y)
    width = float(action.get("signature_width") or action.get("width") or 125)
    height = float(action.get("signature_height") or action.get("height") or 40)

    if signature_image and signature_image.exists():
        rect = fitz.Rect(x, y - height + 8, x + width, y + 8)
        page.insert_image(rect, filename=str(signature_image), overlay=True)
        return True

    # Fallback if signature image missing.
    page.insert_text(
        fitz.Point(x, y),
        "SIGNATURE",
        fontsize=10,
        fontname="helv",
        color=(0, 0, 0),
        overlay=True,
    )
    return False


def _write_clean_pdf(
    input_pdf: Path,
    output_pdf: Path,
    actions: List[Dict[str, Any]],
    signature_image: Optional[Path] = None,
) -> Dict[str, Any]:
    if fitz is None:
        raise RuntimeError(f"PyMuPDF unavailable: {_FITZ_IMPORT_ERROR}")

    doc = fitz.open(str(input_pdf))
    page_count = len(doc)

    written = 0
    skipped: List[Dict[str, Any]] = []
    signature_written = 0
    signature_image_used = 0

    # Avoid duplicate signatures on same page+field.
    signature_seen = set()

    for idx, action in enumerate(actions):
        try:
            page_number = int(action.get("page") or 1)
            page_index = max(0, page_number - 1)

            if page_index >= page_count:
                skipped.append({"index": idx, "reason": "page_out_of_range", "action": action})
                continue

            page = doc[page_index]
            kind = _safe_text(action.get("action") or "write").lower()
            text = _safe_text(action.get("text") or "")

            x = float(action.get("x") or 72)
            detected_y = float(action.get("y") or 72)

            # Clamp X to actual page bounds. Convert Y from detected bottom-left style
            # to PyMuPDF top-left style before writing.
            x = max(20.0, min(x, float(page.rect.width) - 40.0))
            y = _to_pymupdf_y(page, detected_y)

            if kind == "signature" or text.upper() == "SIGNATURE":
                sig_key = (page_number, _safe_text(action.get("field_name") or ""), round(x / 10) * 10, round(y / 10) * 10)
                if sig_key in signature_seen:
                    skipped.append({"index": idx, "reason": "duplicate_signature", "action": action})
                    continue
                signature_seen.add(sig_key)
                used_image = _insert_signature(page, {**action, "x": x, "y": y}, signature_image)
                signature_written += 1
                if used_image:
                    signature_image_used += 1
                written += 1
                continue

            if kind == "tick":
                # Use a small centered X, not a huge text block.
                page.insert_text(
                    fitz.Point(x, y),
                    "X",
                    fontsize=float(action.get("font_size") or 12),
                    fontname="helv",
                    color=(0, 0, 0),
                    overlay=True,
                )
                written += 1
                continue

            if not text:
                skipped.append({"index": idx, "reason": "empty_text", "action": action})
                continue

            max_width = action.get("max_width")
            try:
                max_width_float = float(max_width) if max_width is not None else None
            except Exception:
                max_width_float = None

            font_size = _fit_text_font_size(text, float(action.get("font_size") or 10), max_width_float)
            _insert_wrapped_text(page, x, y, text, font_size, max_width_float)
            written += 1

        except Exception as exc:
            skipped.append({"index": idx, "reason": f"writer_error: {exc}", "action": action})

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_pdf), deflate=True, garbage=4)
    doc.close()

    return {
        "page_count": page_count,
        "actions_received": len(actions),
        "actions_written": written,
        "actions_skipped": len(skipped),
        "skipped": skipped[:250],
        "signature_written": signature_written,
        "signature_image_used": signature_image_used,
    }


def complete_sbd_form_v20(payload: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = _safe_text(payload.get("buyer_rfq_number"), f"V20-{uuid.uuid4().hex[:8]}")
    input_pdf_raw = _path_text(payload.get("input_pdf"))

    resolved_pdf = resolve_runtime_path(input_pdf_raw, must_exist=True)
    if resolved_pdf is None:
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq_number,
            "input_pdf": input_pdf_raw,
            "resolved_input_pdf": None,
            "message": "Input PDF not found. V20.1 preserves whitespace and checked Docker/Mac project roots.",
            "warnings": [
                "Check exact file name with: docker compose exec -T api ls -lah '/app/runtime/playwright/downloads/'",
                f"Checked roots: {[str(p) for p in _project_roots()]}",
            ],
            "error": "Input PDF not found",
        }

    signature_image = resolve_runtime_path(
        payload.get("signature_image") or "runtime/handwriting_simulation/signature.png",
        must_exist=True,
    )

    # Call V18 on resolved PDF so it can classify/discover fields.
    # V18 may still create its own output, but V20.1 will return the clean writer output.
    v18_payload = dict(payload)
    v18_payload["input_pdf"] = str(resolved_pdf)
    v18_payload.setdefault("debug", True)
    v18_payload.setdefault("use_handwriting", True)
    v18_payload.setdefault("handwritten_mode", True)

    try:
        v18_result = _call_v18(v18_payload)
    except Exception as exc:
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq_number,
            "input_pdf": input_pdf_raw,
            "resolved_input_pdf": str(resolved_pdf),
            "message": "V20.1 failed while calling V18 intelligence engine.",
            "error": str(exc),
        }

    actions = v18_result.get("actions") or []
    cleaned_actions, cleanup_stats = clean_v18_actions(actions if isinstance(actions, list) else [])

    safe_rfq = re.sub(r"[^A-Za-z0-9_.-]+", "_", buyer_rfq_number).strip("_") or "UNKNOWN"
    output_dir = V20_OUTPUT_DIR / safe_rfq
    output_pdf = output_dir / f"{safe_rfq}__v20_1_1_coordinate_fixed_completed.pdf"
    manifest_path = V20_RUNTIME_DIR / f"{safe_rfq}__v20_1_1_coordinate_fixed_manifest.json"

    try:
        writer_stats = _write_clean_pdf(
            input_pdf=resolved_pdf,
            output_pdf=output_pdf,
            actions=cleaned_actions,
            signature_image=signature_image,
        )
    except Exception as exc:
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq_number,
            "input_pdf": input_pdf_raw,
            "resolved_input_pdf": str(resolved_pdf),
            "message": "V20.1.1 coordinate-fixed clean writer failed while regenerating PDF.",
            "v18_output_pdf": v18_result.get("output_pdf"),
            "cleanup_stats": cleanup_stats,
            "error": str(exc),
        }

    V20_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "created_at": _utc_now(),
        "buyer_rfq_number": buyer_rfq_number,
        "input_pdf_raw": input_pdf_raw,
        "resolved_input_pdf": str(resolved_pdf),
        "output_pdf": str(output_pdf),
        "v18_engine_version": v18_result.get("engine_version"),
        "v18_output_pdf": v18_result.get("output_pdf"),
        "v18_output_png_preview": v18_result.get("output_png_preview"),
        "cleanup_stats": cleanup_stats,
        "writer_stats": writer_stats,
        "cleaned_actions": cleaned_actions,
        "signature_image": str(signature_image) if signature_image else None,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "buyer_rfq_number": buyer_rfq_number,
        "input_pdf": input_pdf_raw,
        "resolved_input_pdf": str(resolved_pdf),
        "message": "V20.1.1 coordinate-fixed clean writer completed. Output PDF was regenerated from original buyer PDF using cleaned actions.",
        "output_pdf": str(output_pdf),
        "manifest_path": str(manifest_path),
        "v18_output_pdf": v18_result.get("output_pdf"),
        "v18_engine_version": v18_result.get("engine_version"),
        "v18_action_count": len(actions) if isinstance(actions, list) else 0,
        "v20_cleaned_action_count": len(cleaned_actions),
        "v20_removed_action_count": cleanup_stats.get("removed_action_count"),
        "cleanup_stats": cleanup_stats,
        "writer_stats": writer_stats,
        "classified_pages": v18_result.get("classified_pages", []),
        "warnings": [
            "V20.1.1 coordinate-fixed clean writer is active.",
            "If any page still looks off, inspect the debug overlay for that page and we can add per-form coordinate maps in V20.2.",
        ],
        "error": None,
    }


def get_v20_status() -> Dict[str, Any]:
    v18_status: Dict[str, Any] = {}
    if callable(get_tender_form_intelligence_status):
        try:
            v18_status = get_tender_form_intelligence_status()
        except Exception as exc:
            v18_status = {"status": "warning", "error": str(exc)}
    elif callable(get_sbd_intelligence_status):
        try:
            v18_status = get_sbd_intelligence_status()
        except Exception as exc:
            v18_status = {"status": "warning", "error": str(exc)}

    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "checked_at": _utc_now(),
        "runtime_dir": str(V20_RUNTIME_DIR),
        "output_dir": str(V20_OUTPUT_DIR),
        "path_whitespace_preserved": True,
        "pymupdf_available": fitz is not None,
        "features": [
            "v18_intelligence_wrapper",
            "path_safe_pdf_resolution",
            "duplicate_action_cleanup",
            "unsafe_coordinate_guard",
            "particulars_suppression_for_no_or_na",
            "v20_manifest_generation",
            "v20_1_1_coordinate_fixed_clean_pdf_writer",
            "bottom_left_to_top_left_y_conversion",
            "signature_image_writer",
            "checkbox_tick_writer",
        ],
        "v18_status": v18_status,
    }

