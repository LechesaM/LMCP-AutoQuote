"""
LMCP AutoQuote - Handwriting Real Form Overlay Service

Drop-in path:
    app/services/handwriting_form_overlay_service.py
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter


DEFAULT_RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "runtime"))

DEFAULT_FONT_CANDIDATES = [
    Path("app/assets/fonts/handwriting.ttf"),
    Path("app/assets/fonts/Handwriting.ttf"),
    Path("app/assets/fonts/director_handwriting.ttf"),
]


class HandwritingFormField(BaseModel):
    page: int = Field(..., ge=1)
    x: float
    y: float
    text: str
    font_size: Optional[float] = Field(None, ge=4, le=72)
    rotate: Optional[float] = 0
    max_width: Optional[float] = None
    line_height: Optional[float] = None


class HandwritingFormOverlayRequest(BaseModel):
    buyer_rfq_number: str = Field(..., min_length=1)
    input_pdf: str = Field(..., min_length=1)
    output_pdf: Optional[str] = None
    fields: List[HandwritingFormField] = Field(default_factory=list)
    default_font_size: float = Field(11, ge=4, le=72)
    default_font_name: str = "Helvetica-Oblique"
    font_path: Optional[str] = None

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: List[HandwritingFormField]) -> List[HandwritingFormField]:
        if not value:
            raise ValueError("At least one field is required.")
        return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ref(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in value.strip())
    return cleaned[:120] or f"RFQ-{uuid.uuid4().hex[:8]}"


def _runtime_dir(runtime_dir: Optional[str] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _output_dir(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_dir(runtime_dir) / "handwriting_simulation" / "real_form_outputs"


def _tmp_dir(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_dir(runtime_dir) / "handwriting_simulation" / "tmp"


def _ensure_dirs(runtime_dir: Optional[str] = None) -> None:
    _output_dir(runtime_dir).mkdir(parents=True, exist_ok=True)
    _tmp_dir(runtime_dir).mkdir(parents=True, exist_ok=True)


def _register_font(font_path: Optional[str], preferred_name: str) -> str:
    candidates: List[Path] = []
    if font_path:
        candidates.append(Path(font_path))
    candidates.extend(DEFAULT_FONT_CANDIDATES)

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                font_name = preferred_name or "LMCPHandwriting"
                pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
                return font_name
        except Exception:
            continue

    return preferred_name or "Helvetica-Oblique"


def _page_size(page: Any) -> tuple[float, float]:
    return float(page.mediabox.width), float(page.mediabox.height)


def _wrap_text(text: str, font_name: str, font_size: float, max_width: Optional[float]) -> List[str]:
    if not max_width or max_width <= 0:
        return text.splitlines() or [text]

    lines: List[str] = []
    for paragraph in (text.splitlines() or [text]):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        current = words[0]
        for word in words[1:]:
            test = f"{current} {word}"
            if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width:
                current = test
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _draw_field(c: canvas.Canvas, field: HandwritingFormField, font_name: str, default_font_size: float) -> None:
    text = str(field.text or "")
    if not text:
        return

    font_size = float(field.font_size or default_font_size)
    line_height = float(field.line_height or (font_size * 1.25))
    lines = _wrap_text(text, font_name, font_size, field.max_width)

    c.saveState()
    c.setFont(font_name, font_size)

    if field.rotate:
        c.translate(float(field.x), float(field.y))
        c.rotate(float(field.rotate))
        x = 0
        y = 0
    else:
        x = float(field.x)
        y = float(field.y)

    for idx, line in enumerate(lines):
        c.drawString(x, y - (idx * line_height), line)

    c.restoreState()


def overlay_handwriting_on_existing_pdf(
    payload: Dict[str, Any] | HandwritingFormOverlayRequest,
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure_dirs(runtime_dir)

    request = payload if isinstance(payload, HandwritingFormOverlayRequest) else HandwritingFormOverlayRequest(**payload)

    input_pdf = Path(request.input_pdf)
    if not input_pdf.exists() or not input_pdf.is_file():
        return {
            "status": "error",
            "message": f"Input PDF not found: {input_pdf}",
            "buyer_rfq_number": request.buyer_rfq_number,
            "created_at": _now_iso(),
        }

    safe_ref = _safe_ref(request.buyer_rfq_number)
    output_pdf = Path(request.output_pdf) if request.output_pdf else (
        _output_dir(runtime_dir) / f"{safe_ref}__handwritten_completed_form.pdf"
    )
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    overlay_pdf = _tmp_dir(runtime_dir) / f"{safe_ref}__overlay_{uuid.uuid4().hex[:8]}.pdf"

    try:
        reader = PdfReader(str(input_pdf))
        total_pages = len(reader.pages)

        fields_by_page: Dict[int, List[HandwritingFormField]] = {}
        skipped_fields: List[Dict[str, Any]] = []
        accepted_count = 0

        for field in request.fields:
            if field.page < 1 or field.page > total_pages:
                skipped_fields.append({
                    "field": field.dict(),
                    "reason": f"Page {field.page} is outside PDF range 1-{total_pages}",
                })
                continue
            fields_by_page.setdefault(field.page, []).append(field)
            accepted_count += 1

        if accepted_count == 0:
            return {
                "status": "error",
                "message": "No valid fields matched the input PDF page range.",
                "buyer_rfq_number": request.buyer_rfq_number,
                "input_pdf": str(input_pdf),
                "page_count": total_pages,
                "skipped_fields": skipped_fields,
                "created_at": _now_iso(),
            }

        font_name = _register_font(request.font_path, request.default_font_name)

        c = canvas.Canvas(str(overlay_pdf))
        for page_index in range(total_pages):
            page_number = page_index + 1
            width, height = _page_size(reader.pages[page_index])
            c.setPageSize((width, height))

            for field in fields_by_page.get(page_number, []):
                _draw_field(c, field, font_name, request.default_font_size)

            c.showPage()
        c.save()

        overlay_reader = PdfReader(str(overlay_pdf))
        writer = PdfWriter()

        for idx, original_page in enumerate(reader.pages):
            page = original_page
            page.merge_page(overlay_reader.pages[idx])
            writer.add_page(page)

        with output_pdf.open("wb") as f:
            writer.write(f)

        try:
            overlay_pdf.unlink(missing_ok=True)
        except Exception:
            pass

        return {
            "status": "ok",
            "message": "Handwriting overlay applied to existing PDF form.",
            "buyer_rfq_number": request.buyer_rfq_number,
            "input_pdf": str(input_pdf),
            "output_file": str(output_pdf),
            "page_count": total_pages,
            "field_count": accepted_count,
            "skipped_field_count": len(skipped_fields),
            "skipped_fields": skipped_fields,
            "font_used": font_name,
            "created_at": _now_iso(),
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to overlay handwriting on PDF: {exc}",
            "buyer_rfq_number": request.buyer_rfq_number,
            "input_pdf": str(input_pdf),
            "output_file": str(output_pdf),
            "created_at": _now_iso(),
        }


run_handwriting_form_overlay = overlay_handwriting_on_existing_pdf
