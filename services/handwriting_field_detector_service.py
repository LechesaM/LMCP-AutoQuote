"""
LMCP AutoQuote - Handwriting Field Detector Service
V15 Auto-Detect Fields Engine

Drop-in target:
    app/services/handwriting_field_detector_service.py

Purpose:
    Detect likely form fields / blank writing zones in PDF forms and prepare
    coordinates for the existing V13.2 real-ink handwriting engine.

Dependencies:
    pip install pymupdf pillow

Safe scope:
    - Detects blank lines, boxes, and likely text-entry zones.
    - Maps user-provided values into detected zones.
    - Does not create or forge signatures by itself.
"""

from __future__ import annotations

import json
import math
import os
import re
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover
    fitz = None
    FITZ_IMPORT_ERROR = exc
else:
    FITZ_IMPORT_ERROR = None

try:
    from PIL import Image, ImageDraw, ImageOps
except Exception as exc:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageOps = None
    PIL_IMPORT_ERROR = exc
else:
    PIL_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_field_detector"
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
DETECTION_DIR = HANDWRITING_DIR / "field_detection"
DETECTION_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DetectedField:
    page: int
    x: float
    y: float
    width: float
    height: float
    field_type: str = "blank_line"
    label_hint: Optional[str] = None
    confidence: float = 0.5
    source: str = "v15_auto_detect"


@dataclass
class FieldDetectionResult:
    status: str
    engine_version: str
    input_pdf: Optional[str]
    detected_count: int
    detected_fields: List[Dict[str, Any]]
    mapped_fields: List[Dict[str, Any]]
    debug_preview: Optional[str]
    manifest_path: Optional[str]
    message: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _safe_slug(value: Any, fallback: str = "field-detection") -> str:
    raw = str(value or fallback).strip()
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-._")
    return raw[:100] or fallback


def _resolve_path(path_value: Any) -> Optional[Path]:
    if not path_value:
        return None
    p = Path(str(path_value))
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def _render_page(page: Any, zoom: float = 2.0) -> Image.Image:
    if fitz is None:
        raise RuntimeError(f"PyMuPDF is not available: {FITZ_IMPORT_ERROR}")
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGB")


def _near(value: float, target: float, tolerance: float) -> bool:
    return abs(value - target) <= tolerance


def _line_is_blank_candidate(width: float, height: float, page_width: float) -> bool:
    if width < page_width * 0.10:
        return False
    if height > 3.5:
        return False
    if width < 55:
        return False
    return True


def _box_is_field_candidate(width: float, height: float, page_width: float, page_height: float) -> bool:
    if width < 45 or height < 12:
        return False
    if width > page_width * 0.95 or height > page_height * 0.20:
        return False
    if height < 8:
        return False
    return True


def _extract_label_hints(page: Any, field: DetectedField) -> Optional[str]:
    """
    Looks around a detected field for nearby printed words.
    """
    try:
        words = page.get_text("words") or []
    except Exception:
        return None

    # PyMuPDF word tuple: x0, y0, x1, y1, word, block, line, word_no
    # PDF coordinates here are top-left origin. Our field y is bottom-origin.
    rect = page.rect
    field_top = rect.height - field.y - field.height
    field_bottom = field_top + field.height

    candidates: List[Tuple[float, str]] = []
    for item in words:
        if len(item) < 5:
            continue
        x0, y0, x1, y1, word = float(item[0]), float(item[1]), float(item[2]), float(item[3]), str(item[4])

        same_row = abs(((y0 + y1) / 2) - ((field_top + field_bottom) / 2)) < 24
        above = 0 < field_top - y1 < 38
        left_side = x1 <= field.x + 12 and field.x - x1 < 180
        nearby = same_row or above

        if nearby and (left_side or x0 < field.x + field.width):
            dist = abs(x1 - field.x) + abs(y1 - field_top)
            candidates.append((dist, word))

    if not candidates:
        return None

    candidates.sort(key=lambda t: t[0])
    words = [w for _, w in candidates[:8]]
    hint = " ".join(words).strip()
    hint = re.sub(r"\s+", " ", hint)
    return hint[:160] if hint else None


def _dedupe_fields(fields: List[DetectedField]) -> List[DetectedField]:
    out: List[DetectedField] = []
    for f in sorted(fields, key=lambda z: (z.page, -z.y, z.x)):
        duplicate = False
        for e in out:
            if e.page != f.page:
                continue
            if abs(e.x - f.x) < 8 and abs(e.y - f.y) < 8 and abs(e.width - f.width) < 18:
                duplicate = True
                if f.confidence > e.confidence:
                    e.x, e.y, e.width, e.height = f.x, f.y, f.width, f.height
                    e.field_type, e.label_hint, e.confidence = f.field_type, f.label_hint, f.confidence
                break
        if not duplicate:
            out.append(f)
    return out


def _detect_drawn_fields(page: Any, page_no: int) -> List[DetectedField]:
    """
    Uses PDF vector drawings to find blank lines and boxes.
    This is the most accurate when the PDF has real vector form lines.
    """
    rect = page.rect
    page_width = float(rect.width)
    page_height = float(rect.height)
    fields: List[DetectedField] = []

    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []

    for drawing in drawings or []:
        drect = drawing.get("rect")
        if not drect:
            continue

        x0, y0, x1, y1 = float(drect.x0), float(drect.y0), float(drect.x1), float(drect.y1)
        width = abs(x1 - x0)
        height = abs(y1 - y0)

        # Convert top-origin to PDF bottom-origin expected by handwriting engine.
        bottom_y = page_height - y1

        if _line_is_blank_candidate(width, height, page_width):
            fields.append(
                DetectedField(
                    page=page_no,
                    x=x0 + 2,
                    y=bottom_y + 1,
                    width=width - 4,
                    height=max(12, height + 10),
                    field_type="blank_line",
                    confidence=0.72,
                )
            )

        elif _box_is_field_candidate(width, height, page_width, page_height):
            fields.append(
                DetectedField(
                    page=page_no,
                    x=x0 + 4,
                    y=bottom_y + 3,
                    width=max(10, width - 8),
                    height=max(12, height - 6),
                    field_type="box",
                    confidence=0.66,
                )
            )

    return fields


def _detect_text_gaps(page: Any, page_no: int) -> List[DetectedField]:
    """
    Fallback: detects likely spaces after labels such as Name:, Capacity:, Date:.
    """
    rect = page.rect
    page_width = float(rect.width)
    page_height = float(rect.height)

    try:
        words = page.get_text("words") or []
    except Exception:
        return []

    label_keywords = {
        "name": 0.78,
        "bidder": 0.72,
        "tenderer": 0.72,
        "signature": 0.62,
        "capacity": 0.78,
        "designation": 0.78,
        "director": 0.55,
        "date": 0.70,
        "company": 0.72,
        "address": 0.70,
        "telephone": 0.65,
        "email": 0.65,
        "initials": 0.65,
    }

    fields: List[DetectedField] = []
    for item in words:
        if len(item) < 5:
            continue
        x0, y0, x1, y1, word = float(item[0]), float(item[1]), float(item[2]), float(item[3]), str(item[4])
        clean = re.sub(r"[^a-zA-Z]", "", word).lower()
        if clean not in label_keywords:
            continue

        # Put field to the right of the label if space allows.
        gap_x = x1 + 10
        gap_w = page_width - gap_x - 50
        if gap_w >= 80:
            bottom_y = page_height - y1 - 2
            fields.append(
                DetectedField(
                    page=page_no,
                    x=gap_x,
                    y=bottom_y,
                    width=min(gap_w, 260),
                    height=max(14, y1 - y0 + 6),
                    field_type="label_gap",
                    label_hint=word,
                    confidence=label_keywords[clean],
                )
            )

    return fields


def detect_pdf_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main detection endpoint.

    Payload:
    {
      "input_pdf": "/tmp/lmcp_runtime/test_tender_pack/form.pdf",
      "buyer_rfq_number": "ABC-001",
      "limit": 50,
      "values": {
        "company": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "name": "Lechesa Manaba",
        "capacity": "Director",
        "date": "2026-04-26"
      }
    }
    """
    payload = payload or {}
    input_pdf = _resolve_path(payload.get("input_pdf") or payload.get("pdf_path") or payload.get("source_pdf"))
    if not input_pdf or not input_pdf.exists():
        result = FieldDetectionResult(
            status="error",
            engine_version="V15_AUTO_DETECT_FIELDS",
            input_pdf=str(input_pdf) if input_pdf else None,
            detected_count=0,
            detected_fields=[],
            mapped_fields=[],
            debug_preview=None,
            manifest_path=None,
            message=f"Input PDF not found: {input_pdf}",
        )
        return asdict(result)

    if fitz is None:
        result = FieldDetectionResult(
            status="error",
            engine_version="V15_AUTO_DETECT_FIELDS",
            input_pdf=str(input_pdf),
            detected_count=0,
            detected_fields=[],
            mapped_fields=[],
            debug_preview=None,
            manifest_path=None,
            message=f"PyMuPDF is not available: {FITZ_IMPORT_ERROR}",
        )
        return asdict(result)

    job_slug = _safe_slug(payload.get("buyer_rfq_number") or input_pdf.stem)
    limit = int(payload.get("limit") or 80)
    min_confidence = float(payload.get("min_confidence") or 0.50)

    doc = fitz.open(str(input_pdf))
    all_fields: List[DetectedField] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1

        fields = []
        fields.extend(_detect_drawn_fields(page, page_no))
        fields.extend(_detect_text_gaps(page, page_no))

        enriched: List[DetectedField] = []
        for f in fields:
            if not f.label_hint:
                f.label_hint = _extract_label_hints(page, f)
            if f.confidence >= min_confidence:
                enriched.append(f)

        all_fields.extend(enriched)

    all_fields = _dedupe_fields(all_fields)
    all_fields = sorted(all_fields, key=lambda f: (f.page, -f.y, f.x))[:limit]

    mapped = _map_values_to_fields(all_fields, payload.get("values") or payload.get("field_values") or {})

    debug_preview = _make_debug_preview(doc, all_fields, job_slug)
    doc.close()

    result = FieldDetectionResult(
        status="ok",
        engine_version="V15_AUTO_DETECT_FIELDS",
        input_pdf=str(input_pdf),
        detected_count=len(all_fields),
        detected_fields=[asdict(f) for f in all_fields],
        mapped_fields=mapped,
        debug_preview=str(debug_preview) if debug_preview else None,
        manifest_path=None,
        message="Fields detected successfully.",
    )

    manifest_path = DETECTION_DIR / f"{job_slug}__field_detection_manifest.json"
    manifest_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    result.manifest_path = str(manifest_path)
    manifest_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    return asdict(result)


def _normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _map_values_to_fields(fields: List[DetectedField], values: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Creates handwriting-engine-ready fields:
        [{"page": 1, "x": 120, "y": 720, "text": "..."}]
    """
    if not isinstance(values, dict) or not values:
        return []

    used = set()
    out: List[Dict[str, Any]] = []

    priority_aliases = [
        ("company", ["company", "bidder", "tenderer", "nameofbidder", "nameofcompany"]),
        ("name", ["name", "surname", "fullname", "representative"]),
        ("capacity", ["capacity", "designation", "position", "director"]),
        ("date", ["date"]),
        ("email", ["email"]),
        ("telephone", ["telephone", "phone", "cell"]),
        ("address", ["address"]),
    ]

    normalised_values = {_normalise_key(k): v for k, v in values.items() if str(v).strip()}

    for canonical, aliases in priority_aliases:
        value = None
        for alias in aliases:
            if _normalise_key(alias) in normalised_values:
                value = normalised_values[_normalise_key(alias)]
                break
        if value is None:
            continue

        best_idx = None
        best_score = -1.0

        for idx, f in enumerate(fields):
            if idx in used:
                continue
            hint = _normalise_key(f.label_hint or "")
            score = f.confidence

            for alias in aliases:
                if _normalise_key(alias) and _normalise_key(alias) in hint:
                    score += 0.55

            # Company names need wider zones.
            if canonical == "company":
                score += min(f.width / 300.0, 0.50)
            if canonical in {"name", "capacity", "date"}:
                score += 0.15 if f.width < 340 else 0.0

            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            continue

        used.add(best_idx)
        f = fields[best_idx]
        out.append(
            {
                "page": f.page,
                "x": round(float(f.x), 2),
                "y": round(float(f.y + max(2, f.height * 0.12)), 2),
                "text": str(value),
                "font_size": 12,
                "max_width": round(float(f.width), 2),
                "detected_field_type": f.field_type,
                "label_hint": f.label_hint,
                "confidence": round(float(best_score), 3),
            }
        )

    return out


def _make_debug_preview(doc: Any, fields: List[DetectedField], job_slug: str) -> Optional[Path]:
    if Image is None or ImageDraw is None:
        return None
    if len(doc) == 0:
        return None

    page = doc[0]
    zoom = 2.0
    img = _render_page(page, zoom=zoom).convert("RGBA")
    draw = ImageDraw.Draw(img)

    page_height = float(page.rect.height)

    for idx, f in enumerate([x for x in fields if x.page == 1]):
        x = int(round(f.x * zoom))
        y_top = int(round((page_height - f.y - f.height) * zoom))
        w = int(round(f.width * zoom))
        h = int(round(f.height * zoom))

        draw.rectangle((x, y_top, x + w, y_top + h), outline=(255, 0, 0, 230), width=3)
        draw.text((x, max(0, y_top - 16)), f"{idx+1}:{f.field_type}", fill=(255, 0, 0, 230))

    preview_path = DETECTION_DIR / f"{job_slug}__field_detection_preview.png"
    img.save(preview_path)
    return preview_path


def build_handwriting_payload_from_detection(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect fields and return a ready payload for /handwriting-simulation/complete-form.
    """
    detection = detect_pdf_fields(payload)
    if detection.get("status") != "ok":
        return detection

    return {
        "status": "ok",
        "engine_version": "V15_AUTO_DETECT_FIELDS",
        "handwriting_payload": {
            "buyer_rfq_number": payload.get("buyer_rfq_number") or _safe_slug(Path(str(payload.get("input_pdf", "form"))).stem),
            "input_pdf": payload.get("input_pdf") or payload.get("pdf_path") or payload.get("source_pdf"),
            "writer_id": payload.get("writer_id") or "LMCP_REAL_INK_WRITER",
            "reference_image": payload.get("reference_image") or str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "clean_ink_cropped.png"),
            "ink_color": payload.get("ink_color") or "black",
            "debug": bool(payload.get("debug", True)),
            "fields": detection.get("mapped_fields", []),
        },
        "detection": detection,
    }


def get_field_detector_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "handwriting_field_detector_service",
        "engine_version": "V15_AUTO_DETECT_FIELDS",
        "detection_dir": str(DETECTION_DIR),
        "dependencies": {
            "pymupdf": fitz is not None,
            "pillow": Image is not None,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def example_payload() -> Dict[str, Any]:
    return {
        "input_pdf": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "test_tender_pack" / "form.pdf"),
        "buyer_rfq_number": "TEST-AUTO-DETECT-001",
        "writer_id": "LMCP_REAL_INK_WRITER",
        "reference_image": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "clean_ink_cropped.png"),
        "ink_color": "black",
        "debug": True,
        "values": {
            "company": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "name": "Lechesa Manaba",
            "capacity": "Director",
            "date": datetime.now().strftime("%Y-%m-%d"),
        },
    }


if __name__ == "__main__":
    print(json.dumps(get_field_detector_status(), indent=2))
