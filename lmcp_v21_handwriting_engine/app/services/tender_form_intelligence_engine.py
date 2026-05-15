
"""
LMCP AutoQuote System
V21 Real Handwriting Overlay Engine

Purpose:
- Complete tender/SBD PDF fields using image-based handwriting overlays.
- Avoid typed PDF text completely.
- Render each value onto transparent PNG ink and place it onto the PDF.
- Support reference handwriting image tint/texture influence.
- Support signatures as image overlays.

Drop-in target:
    app/services/tender_form_intelligence_engine.py

Main public function:
    complete_tender_form_intelligence(payload: dict) -> dict
"""

from __future__ import annotations

import io
import math
import random
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover
    fitz = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except Exception as exc:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageFilter = None
    ImageOps = None


ENGINE_VERSION = "V21_REAL_HANDWRITING_OVERLAY"
PROJECT_ROOT = Path("/app") if Path("/app").exists() else Path.cwd()
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "completed_forms"
DEBUG_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "debug"
DEFAULT_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Chalkboard SE.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


@dataclass
class FieldBox:
    page: int
    x: float
    y: float
    w: float
    h: float
    text: str
    name: str = ""
    align: str = "left"
    font_size: Optional[int] = None
    ink_color: str = "black"
    max_lines: int = 1
    signature: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _resolve_path(path_value: Any) -> Optional[Path]:
    if not path_value:
        return None

    raw = str(path_value).strip()
    if not raw:
        return None

    p = Path(raw)
    candidates = [
        p,
        PROJECT_ROOT / raw,
        PROJECT_ROOT / raw.lstrip("/"),
        Path.cwd() / raw,
        Path.cwd() / raw.lstrip("/"),
    ]

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except Exception:
            continue

    return None


def _ensure_dependencies() -> Optional[str]:
    if fitz is None:
        return "PyMuPDF is not installed. Install with: pip install pymupdf"
    if Image is None or ImageDraw is None or ImageFont is None:
        return "Pillow is not installed. Install with: pip install pillow"
    return None


def _find_font(preferred: Optional[str] = None, size: int = 24):
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(DEFAULT_FONT_CANDIDATES)

    for font_path in candidates:
        try:
            if Path(font_path).exists():
                return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass

    try:
        return ImageFont.truetype("DejaVuSans-Oblique.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def _ink_rgba(name: str) -> Tuple[int, int, int, int]:
    n = (name or "black").lower().strip()
    if n in {"blue", "dark_blue", "pen_blue"}:
        return (10, 45, 145, 235)
    if n in {"black", "dark", "pen_black"}:
        return (15, 15, 15, 235)
    if n in {"purple"}:
        return (65, 35, 110, 235)
    return (15, 15, 15, 235)


def _sample_reference_ink(reference_image: Optional[Path], fallback: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    if not reference_image or not reference_image.exists():
        return fallback

    try:
        img = Image.open(reference_image).convert("RGBA")
        img = ImageOps.grayscale(img.convert("RGB"))
        small = img.resize((max(1, img.width // 4), max(1, img.height // 4)))
        pixels = list(small.getdata())
        dark = [p for p in pixels if p < 130]
        if not dark:
            return fallback
        avg = sum(dark) / len(dark)
        # Keep chosen hue but slightly adapt darkness from sample.
        factor = max(0.55, min(1.15, avg / 85.0))
        r, g, b, a = fallback
        return (int(r * factor), int(g * factor), int(b * factor), a)
    except Exception:
        return fallback


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    if not text:
        return (1, 1)
    try:
        box = draw.textbbox((0, 0), text, font=font)
        return (max(1, box[2] - box[0]), max(1, box[3] - box[1]))
    except Exception:
        return draw.textsize(text, font=font)


def _wrap_text(text: str, font, max_width: int, max_lines: int) -> List[str]:
    text = _clean_text(text)
    if not text:
        return [""]

    probe = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(probe)

    words = text.split(" ")
    lines: List[str] = []
    current = ""

    for word in words:
        trial = word if not current else f"{current} {word}"
        tw, _ = _text_size(draw, trial, font)
        if tw <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    return lines or [""]


def _make_handwriting_image(
    text: str,
    box_width: int,
    box_height: int,
    ink_color: Tuple[int, int, int, int],
    font_size: int,
    max_lines: int = 1,
    preferred_font: Optional[str] = None,
    seed: Optional[int] = None,
) -> Image.Image:
    """
    Creates a transparent PNG-like handwriting overlay.
    This uses per-character jitter and slight stroke layering.
    """
    if seed is not None:
        random.seed(seed)

    margin_x = max(4, int(box_width * 0.025))
    margin_y = max(2, int(box_height * 0.08))

    img = Image.new("RGBA", (max(8, box_width), max(8, box_height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = _find_font(preferred_font, size=max(8, font_size))
    lines = _wrap_text(text, font, max(8, box_width - margin_x * 2), max_lines=max_lines)

    line_height = max(font_size + 6, int(box_height / max(1, len(lines))))
    y = margin_y

    for line in lines:
        x = margin_x + random.uniform(-1.2, 1.2)
        baseline_wave = random.uniform(-0.8, 0.8)

        for i, ch in enumerate(line):
            if ch == "":
                continue

            ch_w, ch_h = _text_size(draw, ch, font)
            jitter_x = random.uniform(-0.55, 0.85)
            jitter_y = math.sin((i + random.random()) * 0.65) * 0.9 + random.uniform(-0.6, 0.6) + baseline_wave

            alpha = max(165, min(245, ink_color[3] + random.randint(-28, 8)))
            color = (ink_color[0], ink_color[1], ink_color[2], alpha)

            # Main stroke
            draw.text((x + jitter_x, y + jitter_y), ch, font=font, fill=color)

            # Micro pressure pass - creates pen density without becoming bold typed text.
            if random.random() < 0.42:
                draw.text(
                    (x + jitter_x + random.uniform(-0.28, 0.28), y + jitter_y + random.uniform(-0.22, 0.22)),
                    ch,
                    font=font,
                    fill=(ink_color[0], ink_color[1], ink_color[2], max(45, alpha // 4)),
                )

            # Occasional tiny connecting mark
            if i > 0 and ch not in {" ", ".", ",", "/"} and random.random() < 0.18:
                yline = y + font_size * 0.72 + random.uniform(-0.6, 0.6)
                draw.line(
                    [(x - 1.2, yline), (x + 1.5, yline + random.uniform(-0.45, 0.45))],
                    fill=(ink_color[0], ink_color[1], ink_color[2], 55),
                    width=1,
                )

            space_boost = 0
            if ch == " ":
                space_boost = random.uniform(1.0, 3.0)

            x += ch_w + random.uniform(-0.15, 1.35) + space_boost

            if x > box_width - margin_x:
                break

        y += line_height
        if y > box_height:
            break

    # Slight natural blur and paper absorption.
    if box_width > 50 and box_height > 10:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.18))

    # Slight rotation around transparent canvas.
    angle = random.uniform(-0.45, 0.45)
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))

    return img


def _image_to_pdf_pixmap_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _default_fields_from_payload(payload: Dict[str, Any]) -> List[FieldBox]:
    """
    Fallback fields for common SBD/RFQ cover areas.
    Coordinates are PDF points, page is 1-based.
    User can override by passing payload["fields"].
    """
    company = payload.get("company_name") or "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    director = payload.get("director_name") or payload.get("signed_by") or "Lechesa Manaba"
    designation = payload.get("designation") or "Director"
    buyer = payload.get("buyer_name") or ""
    rfq = payload.get("buyer_rfq_number") or payload.get("rfq_number") or ""
    bid_desc = payload.get("bid_description") or payload.get("description") or payload.get("title") or ""

    return [
        FieldBox(page=1, x=105, y=190, w=370, h=24, text=company, name="company_name", font_size=15),
        FieldBox(page=1, x=105, y=222, w=230, h=23, text=director, name="director_name", font_size=15),
        FieldBox(page=1, x=105, y=254, w=180, h=23, text=designation, name="designation", font_size=15),
        FieldBox(page=1, x=105, y=286, w=220, h=23, text=rfq, name="buyer_rfq_number", font_size=14),
        FieldBox(page=1, x=105, y=318, w=410, h=48, text=bid_desc, name="bid_description", font_size=13, max_lines=2),
        FieldBox(page=1, x=105, y=377, w=320, h=23, text=buyer, name="buyer_name", font_size=13),
    ]


def _parse_fields(payload: Dict[str, Any]) -> List[FieldBox]:
    raw_fields = payload.get("fields")
    parsed: List[FieldBox] = []

    if isinstance(raw_fields, list) and raw_fields:
        for idx, item in enumerate(raw_fields):
            if not isinstance(item, dict):
                continue

            text = _clean_text(
                item.get("text")
                or item.get("value")
                or item.get("answer")
                or item.get("field_value")
                or ""
            )
            if not text:
                continue

            parsed.append(
                FieldBox(
                    page=int(item.get("page") or item.get("page_number") or 1),
                    x=float(item.get("x") or item.get("left") or 0),
                    y=float(item.get("y") or item.get("top") or 0),
                    w=float(item.get("w") or item.get("width") or 220),
                    h=float(item.get("h") or item.get("height") or 28),
                    text=text,
                    name=str(item.get("name") or item.get("field_name") or f"field_{idx+1}"),
                    align=str(item.get("align") or "left"),
                    font_size=int(item.get("font_size") or item.get("size") or 15),
                    ink_color=str(item.get("ink_color") or payload.get("ink_color") or "black"),
                    max_lines=int(item.get("max_lines") or 1),
                    signature=bool(item.get("signature") or item.get("is_signature")),
                )
            )

    if parsed:
        return parsed

    return _default_fields_from_payload(payload)


def _fit_font_size(text: str, box_w: int, box_h: int, requested: Optional[int], max_lines: int) -> int:
    if requested:
        return int(requested)

    text = _clean_text(text)
    length = max(1, len(text))
    if max_lines > 1:
        return max(10, min(16, int(box_h / max_lines * 0.62)))

    estimated = int((box_w / max(1, length)) * 1.95)
    return max(9, min(18, estimated))


def _insert_signature(page, signature_path: Path, box: FieldBox) -> bool:
    try:
        sig = Image.open(signature_path).convert("RGBA")
        # Remove white-ish background.
        datas = []
        for r, g, b, a in sig.getdata():
            if r > 235 and g > 235 and b > 235:
                datas.append((255, 255, 255, 0))
            else:
                datas.append((r, g, b, a))
        sig.putdata(datas)

        sig.thumbnail((int(box.w), int(box.h)), Image.LANCZOS)
        canvas = Image.new("RGBA", (int(box.w), int(box.h)), (0, 0, 0, 0))
        px = max(0, int((box.w - sig.width) / 2))
        py = max(0, int((box.h - sig.height) / 2))
        canvas.alpha_composite(sig, (px, py))

        rect = fitz.Rect(box.x, box.y, box.x + box.w, box.y + box.h)
        page.insert_image(rect, stream=_image_to_pdf_pixmap_bytes(canvas), overlay=True)
        return True
    except Exception:
        return False


def complete_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point used by API.
    Expected payload:
        {
          "buyer_rfq_number": "TEST-V21",
          "input_pdf": "runtime/playwright/downloads/file.pdf",
          "reference_image": "runtime/handwriting_simulation/clean_ink_cropped.png",
          "signature_image": "runtime/handwriting_simulation/signature.png",
          "ink_color": "black",
          "fields": [
            {"page":1,"x":120,"y":720,"w":300,"h":32,"text":"..."}
          ],
          "debug": true
        }
    """
    dep_error = _ensure_dependencies()
    if dep_error:
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "message": dep_error,
            "checked_at": _now_iso(),
        }

    payload = payload or {}
    buyer_rfq = _clean_text(payload.get("buyer_rfq_number") or payload.get("rfq_number") or f"RFQ-{uuid.uuid4().hex[:8]}")
    input_pdf = _resolve_path(payload.get("input_pdf") or payload.get("pdf_path"))
    reference_image = _resolve_path(payload.get("reference_image") or payload.get("handwriting_reference"))
    signature_image = _resolve_path(payload.get("signature_image") or payload.get("signature_path"))

    if not input_pdf:
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq,
            "message": "Input PDF not found.",
            "input_pdf": str(payload.get("input_pdf") or payload.get("pdf_path") or ""),
            "checked_at": _now_iso(),
        }

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    output_name = f"{re.sub(r'[^A-Za-z0-9_.-]+', '-', buyer_rfq)}__v21_real_handwritten_completed_form.pdf"
    output_pdf = DEFAULT_OUTPUT_DIR / output_name

    fields = _parse_fields(payload)
    inserted = []
    skipped = []
    debug = bool(payload.get("debug"))

    base_ink = _ink_rgba(str(payload.get("ink_color") or "black"))
    sampled_ink = _sample_reference_ink(reference_image, base_ink)
    preferred_font = payload.get("font_path")

    try:
        doc = fitz.open(str(input_pdf))

        for idx, box in enumerate(fields):
            try:
                if box.page < 1 or box.page > len(doc):
                    skipped.append({"name": box.name, "reason": "page_out_of_range", "page": box.page})
                    continue

                page = doc[box.page - 1]

                if box.signature and signature_image:
                    ok = _insert_signature(page, signature_image, box)
                    if ok:
                        inserted.append({"name": box.name, "type": "signature", "page": box.page, "x": box.x, "y": box.y, "w": box.w, "h": box.h})
                    else:
                        skipped.append({"name": box.name, "reason": "signature_insert_failed"})
                    continue

                w = max(20, int(box.w))
                h = max(12, int(box.h))
                font_size = _fit_font_size(box.text, w, h, box.font_size, box.max_lines)
                field_ink = _sample_reference_ink(reference_image, _ink_rgba(box.ink_color or payload.get("ink_color") or "black"))
                if reference_image:
                    field_ink = sampled_ink if box.ink_color == payload.get("ink_color", "black") else field_ink

                image = _make_handwriting_image(
                    text=box.text,
                    box_width=w,
                    box_height=h,
                    ink_color=field_ink,
                    font_size=font_size,
                    max_lines=max(1, box.max_lines),
                    preferred_font=preferred_font,
                    seed=hash((buyer_rfq, box.name, idx)) % 999999,
                )

                rect = fitz.Rect(box.x, box.y, box.x + box.w, box.y + box.h)
                page.insert_image(rect, stream=_image_to_pdf_pixmap_bytes(image), overlay=True)

                if debug:
                    image.save(DEBUG_DIR / f"{output_name}__{idx+1}_{box.name or 'field'}.png")

                inserted.append({
                    "name": box.name,
                    "type": "handwriting_overlay",
                    "page": box.page,
                    "x": box.x,
                    "y": box.y,
                    "w": box.w,
                    "h": box.h,
                    "font_size": font_size,
                    "text_preview": box.text[:80],
                })

            except Exception as field_error:
                skipped.append({
                    "name": box.name,
                    "reason": "field_failed",
                    "error": str(field_error),
                })

        doc.save(str(output_pdf), garbage=4, deflate=True, clean=True)
        doc.close()

        return {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq,
            "message": "Completed PDF using real image-based handwriting overlays. No typed PDF text insertion was used.",
            "input_pdf": str(input_pdf),
            "output_pdf": str(output_pdf),
            "inserted_count": len(inserted),
            "skipped_count": len(skipped),
            "inserted": inserted,
            "skipped": skipped,
            "reference_image_used": str(reference_image) if reference_image else None,
            "signature_image_used": str(signature_image) if signature_image else None,
            "checked_at": _now_iso(),
        }

    except Exception as exc:
        try:
            doc.close()
        except Exception:
            pass

        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq,
            "message": "V21 handwriting engine failed.",
            "error": str(exc),
            "input_pdf": str(input_pdf),
            "checked_at": _now_iso(),
        }


# Compatibility aliases for older routers/services.
def complete_form_with_tender_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)


def complete_tender_form(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)


def run_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)


def get_tender_form_intelligence_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "mode": "image_overlay_handwriting_only",
        "typed_pdf_text_disabled": True,
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "debug_dir": str(DEBUG_DIR),
        "checked_at": _now_iso(),
    }
