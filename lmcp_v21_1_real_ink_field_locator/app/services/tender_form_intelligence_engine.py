
"""
LMCP AutoQuote System
V21.1 Real Ink + Field Locator Engine

Drop-in target:
    app/services/tender_form_intelligence_engine.py

What changed from V21:
- Keeps image-overlay only handwriting. No typed PDF text insertion.
- Darker, sharper ink with better natural variation.
- Better long-text fitting.
- Adds field locator:
    - can locate blank horizontal lines/boxes from PDF drawings
    - can anchor below labels like "NAME", "SIGNATURE", "COMPANY", "DESIGNATION"
    - can return detected writable areas for debugging
- Manual coordinates still supported and remain the safest override.
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
except Exception:
    fitz = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageFilter = None
    ImageOps = None


ENGINE_VERSION = "V21.1_REAL_INK_FIELD_LOCATOR"
PROJECT_ROOT = Path("/app") if Path("/app").exists() else Path.cwd()
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "completed_forms"
DEBUG_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "debug"

DEFAULT_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
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
    anchor: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


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
    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except Exception:
            pass
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
        return (4, 32, 130, 255)
    if n in {"black", "dark", "pen_black"}:
        return (3, 3, 3, 255)
    if n == "purple":
        return (45, 22, 100, 255)
    return (3, 3, 3, 255)


def _sample_reference_ink(reference_image: Optional[Path], fallback: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    if not reference_image or not reference_image.exists():
        return fallback
    try:
        img = Image.open(reference_image).convert("RGB")
        gray = ImageOps.grayscale(img)
        small = gray.resize((max(1, gray.width // 4), max(1, gray.height // 4)))
        dark = [p for p in small.getdata() if p < 160]
        if not dark:
            return fallback
        avg = sum(dark) / len(dark)
        factor = max(0.72, min(1.0, avg / 110.0))
        r, g, b, a = fallback
        return (max(0, int(r * factor)), max(0, int(g * factor)), max(0, int(b * factor)), a)
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
        trial = word if not current else current + " " + word
        w, _ = _text_size(draw, trial, font)
        if w <= max_width or not current:
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


def _fit_font_size(text: str, box_w: int, box_h: int, requested: Optional[int], max_lines: int, preferred_font: Optional[str]) -> int:
    start = int(requested) if requested else max(9, min(18, int(box_h * 0.55)))
    probe = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(probe)

    for size in range(start, 7, -1):
        font = _find_font(preferred_font, size=size)
        lines = _wrap_text(text, font, max(8, box_w - 8), max_lines=max_lines)
        widest = max(_text_size(draw, line, font)[0] for line in lines)
        total_h = len(lines) * (size + 6)
        if widest <= box_w - 4 and total_h <= box_h + 8:
            return size

    return 8


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
    if seed is not None:
        random.seed(seed)

    scale = 3
    W = max(18, box_width * scale)
    H = max(12, box_height * scale)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = _find_font(preferred_font, size=max(8, font_size * scale))
    margin_x = max(3 * scale, int(W * 0.018))
    margin_y = max(1 * scale, int(H * 0.06))
    lines = _wrap_text(text, font, max(10, W - margin_x * 2), max_lines=max_lines)

    line_height = max((font_size + 7) * scale, int(H / max(1, len(lines))))
    y = margin_y

    for line in lines:
        x = margin_x + random.uniform(-1.2, 1.2) * scale
        wave_seed = random.uniform(0, 6.28)

        for i, ch in enumerate(line):
            ch_w, ch_h = _text_size(draw, ch, font)

            jitter_x = random.uniform(-0.45, 0.75) * scale
            jitter_y = (math.sin(i * 0.75 + wave_seed) * 0.55 + random.uniform(-0.35, 0.35)) * scale

            alpha = max(215, min(255, ink_color[3] + random.randint(-8, 0)))
            color = (ink_color[0], ink_color[1], ink_color[2], alpha)

            draw.text((x + jitter_x, y + jitter_y), ch, font=font, fill=color)

            if random.random() < 0.70 and ch != " ":
                draw.text(
                    (
                        x + jitter_x + random.uniform(-0.18, 0.18) * scale,
                        y + jitter_y + random.uniform(-0.18, 0.18) * scale,
                    ),
                    ch,
                    font=font,
                    fill=(ink_color[0], ink_color[1], ink_color[2], 72),
                )

            if i > 0 and ch not in {" ", ".", ",", "/", "-", ":"} and random.random() < 0.28:
                yy = y + font_size * scale * 0.78 + random.uniform(-0.25, 0.25) * scale
                draw.line(
                    [(x - 0.9 * scale, yy), (x + 1.6 * scale, yy + random.uniform(-0.18, 0.18) * scale)],
                    fill=(ink_color[0], ink_color[1], ink_color[2], 90),
                    width=max(1, int(0.55 * scale)),
                )

            space_boost = random.uniform(0.6, 2.2) * scale if ch == " " else 0
            x += ch_w + random.uniform(-0.12, 0.85) * scale + space_boost

            if x > W - margin_x:
                break

        y += line_height
        if y > H:
            break

    img = img.filter(ImageFilter.GaussianBlur(radius=0.10 * scale))
    angle = random.uniform(-0.28, 0.28)
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
    img.thumbnail((box_width, box_height), Image.LANCZOS)

    canvas = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
    canvas.alpha_composite(img, (max(0, (box_width - img.width) // 2), max(0, (box_height - img.height) // 2)))
    return canvas


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _find_text_anchor(page, anchor: str) -> Optional[fitz.Rect]:
    if not anchor:
        return None
    needle = anchor.lower().strip()
    try:
        words = page.get_text("words")
        for w in words:
            x0, y0, x1, y1, word = w[:5]
            if needle in str(word).lower():
                return fitz.Rect(x0, y0, x1, y1)
    except Exception:
        return None
    return None


def _extract_line_candidates(page, min_width: float = 75.0) -> List[FieldBox]:
    candidates: List[FieldBox] = []
    try:
        drawings = page.get_drawings()
        for drawing in drawings:
            for item in drawing.get("items", []):
                if not item:
                    continue
                op = item[0]

                if op == "l" and len(item) >= 3:
                    p1, p2 = item[1], item[2]
                    x0, y0, x1, y1 = float(p1.x), float(p1.y), float(p2.x), float(p2.y)
                    if abs(y0 - y1) <= 1.2 and abs(x1 - x0) >= min_width:
                        x = min(x0, x1) + 3
                        y = min(y0, y1) - 22
                        w = abs(x1 - x0) - 6
                        h = 20
                        if w >= min_width and y >= 0:
                            candidates.append(FieldBox(page=page.number + 1, x=x, y=y, w=w, h=h, text="", name="detected_line"))

                if op == "re" and len(item) >= 2:
                    r = item[1]
                    w = float(r.width)
                    h = float(r.height)
                    if w >= min_width and 12 <= h <= 80:
                        candidates.append(
                            FieldBox(
                                page=page.number + 1,
                                x=float(r.x0) + 4,
                                y=float(r.y0) + 4,
                                w=max(20, w - 8),
                                h=max(12, h - 8),
                                text="",
                                name="detected_box",
                            )
                        )
    except Exception:
        pass

    unique: List[FieldBox] = []
    seen = set()
    for c in candidates:
        key = (round(c.x / 5) * 5, round(c.y / 5) * 5, round(c.w / 5) * 5)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return sorted(unique, key=lambda b: (b.page, b.y, b.x))


def locate_writable_fields(input_pdf: str, page_number: int = 1, limit: int = 30) -> Dict[str, Any]:
    dep_error = _ensure_dependencies()
    if dep_error:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": dep_error, "checked_at": _now_iso()}

    pdf = _resolve_path(input_pdf)
    if not pdf:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "Input PDF not found.", "input_pdf": input_pdf}

    doc = fitz.open(str(pdf))
    try:
        if page_number < 1 or page_number > len(doc):
            return {"status": "error", "message": "page out of range", "page_number": page_number, "page_count": len(doc)}

        page = doc[page_number - 1]
        candidates = _extract_line_candidates(page)
        return {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "input_pdf": str(pdf),
            "page_number": page_number,
            "page_count": len(doc),
            "candidate_count": len(candidates),
            "candidates": [
                {"page": c.page, "x": round(c.x, 2), "y": round(c.y, 2), "w": round(c.w, 2), "h": round(c.h, 2), "name": c.name}
                for c in candidates[:limit]
            ],
            "checked_at": _now_iso(),
        }
    finally:
        doc.close()


def _auto_place_fields(doc, fields: List[FieldBox]) -> Tuple[List[FieldBox], List[Dict[str, Any]]]:
    warnings: List[Dict[str, Any]] = []
    placed: List[FieldBox] = []

    page_candidates: Dict[int, List[FieldBox]] = {}
    used: set = set()

    for pno in range(1, len(doc) + 1):
        page_candidates[pno] = _extract_line_candidates(doc[pno - 1])

    for idx, f in enumerate(fields):
        has_manual = f.x > 0 and f.y > 0 and f.w > 0 and f.h > 0 and not str(f.anchor or "").strip()
        if has_manual:
            placed.append(f)
            continue

        page_no = max(1, min(len(doc), f.page or 1))
        page = doc[page_no - 1]

        anchor_rect = _find_text_anchor(page, f.anchor or f.name)
        if anchor_rect:
            x = min(anchor_rect.x1 + 12, page.rect.width - 240)
            y = max(0, anchor_rect.y0 - 2)
            w = min(max(160, f.w or 220), page.rect.width - x - 24)
            h = max(18, f.h or 24)
            placed.append(FieldBox(page=page_no, x=x, y=y, w=w, h=h, text=f.text, name=f.name, font_size=f.font_size, ink_color=f.ink_color, max_lines=f.max_lines, signature=f.signature, anchor=f.anchor))
            continue

        selected = None
        for cidx, c in enumerate(page_candidates.get(page_no, [])):
            key = (page_no, cidx)
            if key in used:
                continue
            if c.w < max(90, min(180, len(f.text) * 4)):
                continue
            selected = (cidx, c)
            break

        if selected:
            cidx, c = selected
            used.add((page_no, cidx))
            placed.append(FieldBox(page=page_no, x=c.x, y=c.y, w=max(c.w, f.w or c.w), h=max(c.h, f.h or c.h), text=f.text, name=f.name, font_size=f.font_size, ink_color=f.ink_color, max_lines=f.max_lines, signature=f.signature, anchor=f.anchor))
        else:
            fallback_y = min(page.rect.height - 80, 700 + (idx * 32))
            warnings.append({"name": f.name, "warning": "auto_locator_fallback_used", "page": page_no})
            placed.append(FieldBox(page=page_no, x=72, y=fallback_y, w=f.w or 360, h=f.h or 28, text=f.text, name=f.name, font_size=f.font_size, ink_color=f.ink_color, max_lines=f.max_lines, signature=f.signature, anchor=f.anchor))

    return placed, warnings


def _default_fields_from_payload(payload: Dict[str, Any]) -> List[FieldBox]:
    company = payload.get("company_name") or "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    director = payload.get("director_name") or payload.get("signed_by") or "Lechesa Manaba"
    designation = payload.get("designation") or "Director"
    rfq = payload.get("buyer_rfq_number") or payload.get("rfq_number") or ""
    return [
        FieldBox(page=1, x=0, y=0, w=360, h=28, text=company, name="company_name", anchor="COMPANY", font_size=14),
        FieldBox(page=1, x=0, y=0, w=220, h=28, text=director, name="director_name", anchor="NAME", font_size=14),
        FieldBox(page=1, x=0, y=0, w=180, h=28, text=designation, name="designation", anchor="DESIGNATION", font_size=14),
        FieldBox(page=1, x=0, y=0, w=220, h=28, text=rfq, name="buyer_rfq_number", anchor="RFQ", font_size=13),
    ]


def _parse_fields(payload: Dict[str, Any]) -> Tuple[List[FieldBox], bool]:
    raw_fields = payload.get("fields")
    auto_locate = bool(payload.get("auto_locate_fields") or payload.get("field_locator") or payload.get("auto_place"))

    parsed: List[FieldBox] = []
    if isinstance(raw_fields, list) and raw_fields:
        for idx, item in enumerate(raw_fields):
            if not isinstance(item, dict):
                continue
            text = _clean_text(item.get("text") or item.get("value") or item.get("answer") or item.get("field_value") or "")
            if not text:
                continue

            item_auto = bool(item.get("auto") or item.get("auto_locate") or item.get("field_locator"))
            if item_auto:
                auto_locate = True

            parsed.append(
                FieldBox(
                    page=int(item.get("page") or item.get("page_number") or 1),
                    x=float(item.get("x") or item.get("left") or 0),
                    y=float(item.get("y") or item.get("top") or 0),
                    w=float(item.get("w") or item.get("width") or 260),
                    h=float(item.get("h") or item.get("height") or 28),
                    text=text,
                    name=str(item.get("name") or item.get("field_name") or f"field_{idx+1}"),
                    align=str(item.get("align") or "left"),
                    font_size=int(item.get("font_size") or item.get("size") or 0) or None,
                    ink_color=str(item.get("ink_color") or payload.get("ink_color") or "black"),
                    max_lines=int(item.get("max_lines") or 1),
                    signature=bool(item.get("signature") or item.get("is_signature")),
                    anchor=str(item.get("anchor") or ""),
                )
            )

    if not parsed:
        parsed = _default_fields_from_payload(payload)
        auto_locate = True

    return parsed, auto_locate


def _insert_signature(page, signature_path: Path, box: FieldBox) -> bool:
    try:
        sig = Image.open(signature_path).convert("RGBA")
        cleaned = []
        for r, g, b, a in sig.getdata():
            if r > 235 and g > 235 and b > 235:
                cleaned.append((255, 255, 255, 0))
            else:
                cleaned.append((r, g, b, a))
        sig.putdata(cleaned)
        sig.thumbnail((int(box.w), int(box.h)), Image.LANCZOS)
        canvas = Image.new("RGBA", (int(box.w), int(box.h)), (0, 0, 0, 0))
        canvas.alpha_composite(sig, (max(0, int((box.w - sig.width) / 2)), max(0, int((box.h - sig.height) / 2))))
        page.insert_image(fitz.Rect(box.x, box.y, box.x + box.w, box.y + box.h), stream=_png_bytes(canvas), overlay=True)
        return True
    except Exception:
        return False


def complete_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    dep_error = _ensure_dependencies()
    if dep_error:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": dep_error, "checked_at": _now_iso()}

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

    output_name = f"{re.sub(r'[^A-Za-z0-9_.-]+', '-', buyer_rfq)}__v21_1_real_ink_completed_form.pdf"
    output_pdf = DEFAULT_OUTPUT_DIR / output_name

    fields, auto_locate = _parse_fields(payload)
    inserted = []
    skipped = []
    locator_warnings = []
    debug = bool(payload.get("debug"))
    preferred_font = payload.get("font_path")
    base_ink = _sample_reference_ink(reference_image, _ink_rgba(str(payload.get("ink_color") or "black")))

    doc = None
    try:
        doc = fitz.open(str(input_pdf))

        if auto_locate:
            fields, locator_warnings = _auto_place_fields(doc, fields)

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

                w = max(22, int(box.w))
                h = max(14, int(box.h))
                fs = _fit_font_size(box.text, w, h, box.font_size, max(1, box.max_lines), preferred_font)
                field_ink = _sample_reference_ink(reference_image, _ink_rgba(box.ink_color or payload.get("ink_color") or "black")) if box.ink_color else base_ink

                image = _make_handwriting_image(
                    text=box.text,
                    box_width=w,
                    box_height=h,
                    ink_color=field_ink,
                    font_size=fs,
                    max_lines=max(1, box.max_lines),
                    preferred_font=preferred_font,
                    seed=hash((buyer_rfq, box.name, idx, ENGINE_VERSION)) % 999999,
                )

                rect = fitz.Rect(box.x, box.y, box.x + box.w, box.y + box.h)
                page.insert_image(rect, stream=_png_bytes(image), overlay=True)

                if debug:
                    image.save(DEBUG_DIR / f"{output_name}__{idx+1}_{box.name or 'field'}.png")

                inserted.append({
                    "name": box.name,
                    "type": "real_ink_overlay",
                    "page": box.page,
                    "x": round(box.x, 2),
                    "y": round(box.y, 2),
                    "w": round(box.w, 2),
                    "h": round(box.h, 2),
                    "font_size": fs,
                    "anchor": box.anchor or None,
                    "text_preview": box.text[:100],
                })

            except Exception as field_error:
                skipped.append({"name": box.name, "reason": "field_failed", "error": str(field_error)})

        doc.save(str(output_pdf), garbage=4, deflate=True, clean=True)
        doc.close()

        return {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq,
            "message": "Completed PDF using V21.1 real ink overlays and field locator support. No typed PDF text insertion was used.",
            "input_pdf": str(input_pdf),
            "output_pdf": str(output_pdf),
            "auto_locate_fields": auto_locate,
            "inserted_count": len(inserted),
            "skipped_count": len(skipped),
            "inserted": inserted,
            "skipped": skipped,
            "locator_warnings": locator_warnings,
            "reference_image_used": str(reference_image) if reference_image else None,
            "signature_image_used": str(signature_image) if signature_image else None,
            "checked_at": _now_iso(),
        }

    except Exception as exc:
        try:
            if doc:
                doc.close()
        except Exception:
            pass
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "buyer_rfq_number": buyer_rfq,
            "message": "V21.1 real ink field locator engine failed.",
            "error": str(exc),
            "input_pdf": str(input_pdf) if input_pdf else None,
            "checked_at": _now_iso(),
        }


def complete_form_with_tender_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)

def complete_tender_form(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)

def complete_form(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)

def complete_sbd_form(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)

def complete_tender_form_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)

def run_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)

def get_tender_form_intelligence_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "mode": "real_ink_field_locator",
        "typed_pdf_text_disabled": True,
        "manual_coordinates_supported": True,
        "auto_field_locator_supported": True,
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "debug_dir": str(DEBUG_DIR),
        "checked_at": _now_iso(),
    }
