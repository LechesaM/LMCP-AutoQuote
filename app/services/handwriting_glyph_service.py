
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, validator
from PIL import Image, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter


RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "runtime"))
DEFAULT_SAMPLE_IMAGE = Path(os.getenv("LMCP_HANDWRITING_SAMPLE", "app/assets/handwriting_samples/lechesa_handwriting.jpg"))
DEFAULT_OUTPUT_DIR = RUNTIME_DIR / "handwriting_simulation" / "glyph_form_outputs"
DEFAULT_TMP_DIR = RUNTIME_DIR / "handwriting_simulation" / "glyph_tmp"
DEFAULT_GLYPH_DIR = RUNTIME_DIR / "handwriting_simulation" / "glyph_cache"


class GlyphField(BaseModel):
    page: int = Field(..., ge=1)
    x: float
    y: float
    text: str
    glyph_height: Optional[float] = Field(None, ge=4, le=80)
    letter_spacing: Optional[float] = Field(None, ge=-5, le=30)
    word_spacing: Optional[float] = Field(None, ge=0, le=80)
    line_spacing: Optional[float] = Field(None, ge=0, le=120)
    max_width: Optional[float] = Field(None, ge=20)
    uppercase: bool = True


class GlyphOverlayRequest(BaseModel):
    buyer_rfq_number: str = Field(..., min_length=1)
    input_pdf: str = Field(..., min_length=1)
    output_pdf: Optional[str] = None
    sample_image: Optional[str] = None
    fields: List[GlyphField] = Field(default_factory=list)
    default_glyph_height: float = Field(14, ge=4, le=80)
    default_letter_spacing: float = Field(1.0, ge=-5, le=30)
    default_word_spacing: float = Field(7.0, ge=0, le=80)
    default_line_spacing: float = Field(18.0, ge=0, le=120)

    @validator("fields")
    def validate_fields(cls, value: List[GlyphField]) -> List[GlyphField]:
        if not value:
            raise ValueError("At least one field is required.")
        return value


GLYPH_LAYOUT: List[List[str]] = [
    list("ABCDEFGHI"),
    list("JKLMNOPQ"),
    list("RSTUVWX"),
    list("YZ"),
    list("1234567890"),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ref(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in value.strip())
    return cleaned[:120] or f"RFQ-{uuid.uuid4().hex[:8]}"


def _ensure_dirs() -> None:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_GLYPH_DIR.mkdir(parents=True, exist_ok=True)


def _trim_and_transparent(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    pixels = rgba.load()

    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            brightness = (r + g + b) / 3
            if brightness > 145:
                pixels[x, y] = (255, 255, 255, 0)
            else:
                alpha = int(max(100, min(255, 255 - brightness)))
                pixels[x, y] = (20, 20, 20, alpha)

    gray = ImageOps.grayscale(rgba.convert("RGB"))
    inv = ImageOps.invert(gray)
    bbox = inv.point(lambda p: 255 if p > 35 else 0).getbbox()

    if bbox:
        cropped = rgba.crop(bbox)
        pad = 4
        out = Image.new("RGBA", (cropped.width + pad * 2, cropped.height + pad * 2), (255, 255, 255, 0))
        out.alpha_composite(cropped, (pad, pad))
        return out

    return rgba


def _crop_glyphs(sample: Image.Image) -> Dict[str, Image.Image]:
    w, h = sample.size

    left = int(w * 0.055)
    right = int(w * 0.92)
    top = int(h * 0.24)
    bottom = int(h * 0.68)

    work = sample.crop((left, top, right, bottom))
    ww, wh = work.size

    row_bands = [
        (0.00, 0.20),
        (0.21, 0.38),
        (0.39, 0.55),
        (0.56, 0.71),
        (0.78, 1.00),
    ]

    glyphs: Dict[str, Image.Image] = {}

    for row_idx, chars in enumerate(GLYPH_LAYOUT):
        y1 = int(wh * row_bands[row_idx][0])
        y2 = int(wh * row_bands[row_idx][1])
        row_img = work.crop((0, y1, ww, y2))

        if chars == ["Y", "Z"]:
            row_img = row_img.crop((0, 0, int(row_img.width * 0.28), row_img.height))

        count = len(chars)
        row_width = row_img.width

        for col_idx, ch in enumerate(chars):
            x1 = int(row_width * col_idx / count)
            x2 = int(row_width * (col_idx + 1) / count)
            glyphs[ch] = _trim_and_transparent(row_img.crop((x1, 0, x2, row_img.height)))

    return glyphs


def build_glyph_cache(sample_image: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    sample_path = Path(sample_image) if sample_image else DEFAULT_SAMPLE_IMAGE

    if not sample_path.exists():
        return {
            "status": "error",
            "message": f"Handwriting sample image not found: {sample_path}",
            "sample_image": str(sample_path),
            "created_at": _now_iso(),
        }

    existing = list(DEFAULT_GLYPH_DIR.glob("*.png"))
    if existing and not force:
        return {
            "status": "ok",
            "message": "Glyph cache already exists.",
            "sample_image": str(sample_path),
            "glyph_dir": str(DEFAULT_GLYPH_DIR),
            "glyph_count": len(existing),
            "created_at": _now_iso(),
        }

    for old in DEFAULT_GLYPH_DIR.glob("*.png"):
        old.unlink(missing_ok=True)

    sample = Image.open(sample_path).convert("RGBA")
    glyphs = _crop_glyphs(sample)

    saved = []
    for ch, img in glyphs.items():
        out = DEFAULT_GLYPH_DIR / f"{ch}.png"
        img.save(out)
        saved.append(str(out))

    return {
        "status": "ok",
        "message": "Glyph cache built from handwriting sample.",
        "sample_image": str(sample_path),
        "glyph_dir": str(DEFAULT_GLYPH_DIR),
        "glyph_count": len(saved),
        "glyphs": saved,
        "created_at": _now_iso(),
    }


def _glyph_path(ch: str) -> Optional[Path]:
    if ch.isalpha():
        ch = ch.upper()
    if ch.isdigit() or ("A" <= ch <= "Z"):
        path = DEFAULT_GLYPH_DIR / f"{ch}.png"
        return path if path.exists() else None
    return None


def _glyph_size(path: Path, target_height: float) -> Tuple[float, float]:
    with Image.open(path) as img:
        w, h = img.size
    scale = target_height / float(h or 1)
    return float(w) * scale, target_height


def _text_width(text: str, glyph_height: float, letter_spacing: float, word_spacing: float) -> float:
    width = 0.0
    for ch in text:
        if ch == " ":
            width += word_spacing
        else:
            path = _glyph_path(ch)
            if path:
                gw, _ = _glyph_size(path, glyph_height)
                width += gw + letter_spacing
            else:
                width += glyph_height * 0.35
    return width


def _wrap_text(text: str, max_width: Optional[float], glyph_height: float, letter_spacing: float, word_spacing: float) -> List[str]:
    if not max_width:
        return text.splitlines() or [text]

    lines: List[str] = []
    for paragraph in (text.splitlines() or [text]):
        current = ""
        for word in paragraph.split(" "):
            candidate = word if not current else current + " " + word
            if _text_width(candidate, glyph_height, letter_spacing, word_spacing) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines or [""]


def _draw_text(
    c: canvas.Canvas,
    field: GlyphField,
    default_glyph_height: float,
    default_letter_spacing: float,
    default_word_spacing: float,
    default_line_spacing: float,
) -> int:
    text = field.text.upper() if field.uppercase else field.text
    glyph_height = field.glyph_height or default_glyph_height
    letter_spacing = field.letter_spacing if field.letter_spacing is not None else default_letter_spacing
    word_spacing = field.word_spacing if field.word_spacing is not None else default_word_spacing
    line_spacing = field.line_spacing if field.line_spacing is not None else default_line_spacing

    lines = _wrap_text(text, field.max_width, glyph_height, letter_spacing, word_spacing)
    drawn = 0

    for line_idx, line in enumerate(lines):
        cursor_x = float(field.x)
        cursor_y = float(field.y) - (line_idx * line_spacing)

        for ch in line:
            if ch == " ":
                cursor_x += word_spacing
                continue

            path = _glyph_path(ch)
            if not path:
                cursor_x += glyph_height * 0.35
                continue

            gw, gh = _glyph_size(path, glyph_height)
            c.drawImage(ImageReader(str(path)), cursor_x, cursor_y, width=gw, height=gh, mask="auto")
            cursor_x += gw + letter_spacing
            drawn += 1

    return drawn


def overlay_glyph_handwriting_on_pdf(payload: Dict[str, Any] | GlyphOverlayRequest) -> Dict[str, Any]:
    _ensure_dirs()
    request = payload if isinstance(payload, GlyphOverlayRequest) else GlyphOverlayRequest(**payload)

    input_pdf = Path(request.input_pdf)
    if not input_pdf.exists() or not input_pdf.is_file():
        return {
            "status": "error",
            "message": f"Input PDF not found: {input_pdf}",
            "buyer_rfq_number": request.buyer_rfq_number,
            "created_at": _now_iso(),
        }

    cache = build_glyph_cache(sample_image=request.sample_image, force=False)
    if cache.get("status") != "ok":
        return cache

    safe_ref = _safe_ref(request.buyer_rfq_number)
    output_pdf = Path(request.output_pdf) if request.output_pdf else (
        DEFAULT_OUTPUT_DIR / f"{safe_ref}__glyph_handwritten_completed_form.pdf"
    )
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    overlay_pdf = DEFAULT_TMP_DIR / f"{safe_ref}__glyph_overlay_{uuid.uuid4().hex[:8]}.pdf"

    try:
        reader = PdfReader(str(input_pdf))
        total_pages = len(reader.pages)

        fields_by_page: Dict[int, List[GlyphField]] = {}
        skipped_fields: List[Dict[str, Any]] = []

        for field in request.fields:
            if field.page < 1 or field.page > total_pages:
                skipped_fields.append({"field": field.dict(), "reason": f"Page {field.page} outside PDF range 1-{total_pages}"})
                continue
            fields_by_page.setdefault(field.page, []).append(field)

        c = canvas.Canvas(str(overlay_pdf))
        drawn_glyphs = 0

        for page_index in range(total_pages):
            page_number = page_index + 1
            page = reader.pages[page_index]
            c.setPageSize((float(page.mediabox.width), float(page.mediabox.height)))

            for field in fields_by_page.get(page_number, []):
                drawn_glyphs += _draw_text(
                    c,
                    field,
                    request.default_glyph_height,
                    request.default_letter_spacing,
                    request.default_word_spacing,
                    request.default_line_spacing,
                )

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
            "message": "Glyph handwriting overlay applied to existing PDF form.",
            "buyer_rfq_number": request.buyer_rfq_number,
            "input_pdf": str(input_pdf),
            "output_file": str(output_pdf),
            "page_count": total_pages,
            "field_count": sum(len(v) for v in fields_by_page.values()),
            "drawn_glyph_count": drawn_glyphs,
            "skipped_field_count": len(skipped_fields),
            "skipped_fields": skipped_fields,
            "glyph_dir": str(DEFAULT_GLYPH_DIR),
            "created_at": _now_iso(),
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to apply glyph handwriting overlay: {exc}",
            "buyer_rfq_number": request.buyer_rfq_number,
            "input_pdf": str(input_pdf),
            "output_file": str(output_pdf),
            "created_at": _now_iso(),
        }


run_glyph_handwriting_overlay = overlay_glyph_handwriting_on_pdf
