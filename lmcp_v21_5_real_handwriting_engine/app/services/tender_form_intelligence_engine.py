
"""
LMCP AutoQuote System
V21.5 Real Handwriting Engine

Drop-in target:
    app/services/tender_form_intelligence_engine.py

This version improves V21.4 by:
- building a cleaner glyph library from the handwriting alphabet image
- forcing row/column glyph ordering instead of noisy connected-component ordering
- normalising every glyph to a standard baseline height
- rendering readable words from glyphs
- falling back cleanly for missing glyphs
- keeping V21.3/V21.4 training-map placement
- never inserting typed PDF text
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
    import fitz
except Exception:
    fitz = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except Exception:
    Image = ImageDraw = ImageFont = ImageFilter = ImageOps = None


ENGINE_VERSION = "V21.5_REAL_HANDWRITING_ENGINE"
PROJECT_ROOT = Path("/app") if Path("/app").exists() else Path.cwd()
OUTPUT_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "completed_forms"
DEBUG_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "debug"
GLYPH_DIR = PROJECT_ROOT / "runtime" / "handwriting_glyphs"

ROWS = [
    list("ABCDEFGHIJKLM"),
    list("NOPQRSTUVWXYZ"),
    list("1234567890"),
    list("abcdefghijklm"),
    list("nopqrstuvwxyz"),
]
ORDERED_GLYPHS = [c for row in ROWS for c in row]


@dataclass
class Field:
    page: int
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    name: str = ""
    size: int = 14
    mark: str = "text"   # text, x, square, signature
    lines: int = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ").replace("\r", " ")).strip()


def _resolve(p: Any) -> Optional[Path]:
    raw = str(p or "").strip()
    if not raw:
        return None
    for c in [Path(raw), PROJECT_ROOT / raw, PROJECT_ROOT / raw.lstrip("/"), Path.cwd() / raw]:
        try:
            if c.exists():
                return c.resolve()
        except Exception:
            pass
    return None


def _deps() -> Optional[str]:
    if fitz is None:
        return "PyMuPDF is not installed. Install with: pip install pymupdf"
    if Image is None:
        return "Pillow is not installed. Install with: pip install pillow"
    return None


def _ink(color: str = "black") -> Tuple[int, int, int, int]:
    if "blue" in str(color).lower():
        return (4, 28, 140, 245)
    return (2, 2, 2, 245)


def _png(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def _font(size: int):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _fallback_text(text: str, w: int, h: int, size: int, ink, seed: int = 0) -> Image.Image:
    random.seed(seed)
    scale = 3
    W, H = max(20, int(w) * scale), max(16, int(h) * scale)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _font(max(8, int(size) * scale))
    x, y = 5, int(H * 0.08)
    for i, ch in enumerate(str(text)):
        d.text((x + random.uniform(-1, 1), y + math.sin(i * 0.8) * 2), ch, font=f, fill=ink)
        try:
            bbox = d.textbbox((0, 0), ch, font=f)
            cw = bbox[2] - bbox[0]
        except Exception:
            cw = size * scale * 0.6
        x += cw + random.uniform(0, 2)
        if x > W - 8:
            break
    img = img.filter(ImageFilter.GaussianBlur(radius=0.18))
    img.thumbnail((int(w), int(h)), Image.LANCZOS)
    c = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    c.alpha_composite(img, (max(0, (c.width - img.width) // 2), max(0, (c.height - img.height) // 2)))
    return c


def _to_alpha_image(src: Image.Image, ink=(2, 2, 2, 255)) -> Image.Image:
    """Convert a photo/scan to transparent handwritten ink."""
    gray = ImageOps.grayscale(src.convert("RGB"))
    gray = ImageOps.autocontrast(gray)

    # Strong threshold but not too harsh. Dark writing becomes alpha.
    # Any faint paper shadows vanish.
    alpha = gray.point(lambda p: 255 if p < 165 else 0)
    rgba = Image.new("RGBA", gray.size, ink)
    rgba.putalpha(alpha)
    return rgba


def _crop_alpha(img: Image.Image, pad: int = 4) -> Image.Image:
    img = img.convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    return img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad)))


def _row_bounding_boxes(alpha_img: Image.Image) -> List[Tuple[int, int, int, int]]:
    """Find handwriting rows by scanning horizontal alpha density."""
    a = alpha_img.getchannel("A")
    w, h = a.size
    pix = a.load()
    row_counts = []
    for y in range(h):
        count = 0
        for x in range(w):
            if pix[x, y] > 0:
                count += 1
        row_counts.append(count)

    threshold = max(5, int(w * 0.002))
    bands = []
    in_band = False
    start = 0
    for y, count in enumerate(row_counts):
        if count > threshold and not in_band:
            start = y
            in_band = True
        if (count <= threshold or y == h - 1) and in_band:
            end = y
            if end - start > 10:
                bands.append((start, end))
            in_band = False

    # Merge close row fragments.
    merged = []
    for band in bands:
        if not merged or band[0] - merged[-1][1] > 25:
            merged.append(list(band))
        else:
            merged[-1][1] = band[1]

    rows = []
    for y0, y1 in merged:
        cols = []
        for x in range(w):
            col_count = 0
            for y in range(max(0, y0 - 3), min(h, y1 + 4)):
                if pix[x, y] > 0:
                    col_count += 1
            if col_count > 0:
                cols.append(x)
        if cols:
            rows.append((min(cols), max(0, y0 - 6), max(cols) + 1, min(h, y1 + 6)))

    return rows


def _segment_row(alpha_img: Image.Image, row_box: Tuple[int, int, int, int], expected_count: int) -> List[Tuple[int, int, int, int]]:
    """
    Segment a row into expected_count glyph cells.
    Uses vertical ink columns + fallback equal-width slicing.
    """
    x0, y0, x1, y1 = row_box
    row = alpha_img.crop((x0, y0, x1, y1))
    a = row.getchannel("A")
    w, h = a.size
    pix = a.load()

    col_counts = []
    for x in range(w):
        count = sum(1 for y in range(h) if pix[x, y] > 0)
        col_counts.append(count)

    # detect ink bands
    bands = []
    in_band = False
    start = 0
    threshold = max(1, int(h * 0.03))
    for x, count in enumerate(col_counts):
        if count > threshold and not in_band:
            start = x
            in_band = True
        if (count <= threshold or x == w - 1) and in_band:
            end = x
            if end - start > 3:
                bands.append((start, end))
            in_band = False

    # Merge tiny stroke fragments close together.
    merged = []
    for b in bands:
        if not merged or b[0] - merged[-1][1] > 10:
            merged.append([b[0], b[1]])
        else:
            merged[-1][1] = b[1]

    bands = [(a, b) for a, b in merged if b - a > 4]

    # If detection is not exact, use equal cell centres but crop local ink inside each cell.
    if len(bands) != expected_count:
        cells = []
        cell_w = w / expected_count
        for i in range(expected_count):
            cx0 = int(i * cell_w)
            cx1 = int((i + 1) * cell_w)
            crop = row.crop((cx0, 0, cx1, h))
            bbox = crop.getchannel("A").getbbox()
            if bbox:
                gx0, gy0, gx1, gy1 = bbox
                cells.append((x0 + cx0 + gx0, y0 + gy0, x0 + cx0 + gx1, y0 + gy1))
            else:
                cells.append((x0 + cx0, y0, x0 + cx1, y1))
        return cells

    return [(x0 + a, y0, x0 + b, y1) for a, b in bands]


def _normalize_glyph(glyph: Image.Image, target_h: int = 96, ink=(2, 2, 2, 255)) -> Image.Image:
    glyph = _crop_alpha(glyph, pad=6)
    if glyph.width <= 1 or glyph.height <= 1:
        return glyph
    scale = target_h / glyph.height
    new_w = max(3, int(glyph.width * scale))
    glyph = glyph.resize((new_w, target_h), Image.LANCZOS)

    # Recolor, smooth, and clean.
    alpha = glyph.getchannel("A").filter(ImageFilter.GaussianBlur(radius=0.25))
    out = Image.new("RGBA", glyph.size, ink)
    out.putalpha(alpha)
    return _crop_alpha(out, pad=4)


def build_glyph_library(reference_image: str, force: bool = False) -> Dict[str, Any]:
    err = _deps()
    if err:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": err}

    ref = _resolve(reference_image)
    if not ref:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "Reference handwriting image not found."}

    GLYPH_DIR.mkdir(parents=True, exist_ok=True)

    # Clear old glyphs when force.
    if force:
        for p in GLYPH_DIR.glob("*.png"):
            p.unlink(missing_ok=True)
        (GLYPH_DIR / "glyph_meta.txt").unlink(missing_ok=True)

    src = Image.open(ref).convert("RGB")
    if src.width > 1800:
        ratio = 1800 / src.width
        src = src.resize((1800, int(src.height * ratio)), Image.LANCZOS)

    alpha_img = _to_alpha_image(src, ink=(2, 2, 2, 255))
    rows = _row_bounding_boxes(alpha_img)

    saved = []
    diagnostics = []

    for row_index, expected_chars in enumerate(ROWS):
        if row_index >= len(rows):
            diagnostics.append({"row": row_index + 1, "error": "row_not_found", "expected": "".join(expected_chars)})
            continue

        row_box = rows[row_index]
        cells = _segment_row(alpha_img, row_box, len(expected_chars))
        diagnostics.append({
            "row": row_index + 1,
            "expected_count": len(expected_chars),
            "detected_cells": len(cells),
            "chars": "".join(expected_chars),
        })

        for ch, cell in zip(expected_chars, cells):
            x0, y0, x1, y1 = cell
            raw = alpha_img.crop((x0, y0, x1, y1))
            glyph = _normalize_glyph(raw, target_h=96, ink=(2, 2, 2, 255))
            if glyph.width < 2 or glyph.height < 2:
                continue
            glyph.save(GLYPH_DIR / f"{ord(ch)}.png")
            saved.append(ch)

    (GLYPH_DIR / "glyph_meta.txt").write_text("".join(saved), encoding="utf-8")

    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "message": "V21.5 glyph library built with row/column segmentation and normalisation.",
        "reference_image": str(ref),
        "glyph_dir": str(GLYPH_DIR),
        "expected_glyphs": len(ORDERED_GLYPHS),
        "saved_glyphs": len(saved),
        "saved_chars": "".join(saved),
        "rows_found": len(rows),
        "diagnostics": diagnostics,
        "checked_at": _now(),
    }


def _load_glyph(ch: str, ink=(2, 2, 2, 245)) -> Optional[Image.Image]:
    p = GLYPH_DIR / f"{ord(ch)}.png"
    if not p.exists():
        return None
    img = Image.open(p).convert("RGBA")
    alpha = img.getchannel("A")
    out = Image.new("RGBA", img.size, ink)
    out.putalpha(alpha)
    return _crop_alpha(out, pad=2)


def _glyph_text(text: str, w: float, h: float, size: int, ink, seed: int = 0, lines: int = 1) -> Image.Image:
    random.seed(seed)
    text = _clean(text)
    W, H = int(max(8, w)), int(max(8, h))
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not text:
        return canvas

    target_h = max(9, int(size * 1.45))
    line_h = max(target_h + 5, int(H / max(1, lines)))
    x = 2
    y = max(0, int(H * 0.12))
    max_x = W - 2

    for idx, ch in enumerate(text):
        if ch == " ":
            x += random.uniform(size * 0.45, size * 0.85)
            continue

        glyph = _load_glyph(ch, ink)
        if glyph is None:
            glyph = _fallback_text(ch, max(10, int(size * 1.1)), max(14, int(size * 1.6)), size, ink, seed + idx)

        if glyph.height > 0:
            scale = target_h / glyph.height
            gw = max(3, int(glyph.width * scale * random.uniform(0.92, 1.07)))
            gh = max(5, int(glyph.height * scale * random.uniform(0.95, 1.08)))
            glyph = glyph.resize((gw, gh), Image.LANCZOS)

        glyph = glyph.rotate(random.uniform(-2.2, 2.2), expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
        yy = int(y + random.uniform(-1.5, 1.5) + math.sin(idx * 0.65) * 1.1)

        if x + glyph.width > max_x:
            if lines > 1 and y + line_h + glyph.height < H:
                x = 2
                y += line_h
            else:
                break

        canvas.alpha_composite(glyph, (int(x), max(0, yy)))
        x += glyph.width + random.uniform(0, 2.4)

    # soften just enough to avoid cutout look
    return canvas.filter(ImageFilter.GaussianBlur(radius=0.08))


def _xmark(w, h, ink, seed=0):
    random.seed(seed)
    scale = 3
    W, H = max(18, int(w) * scale), max(18, int(h) * scale)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(min(W, H) * 0.18)
    lw = max(2, int(min(W, H) * 0.06))
    d.line([(pad, pad), (W - pad, H - pad)], fill=ink, width=lw)
    d.line([(W - pad, pad), (pad, H - pad)], fill=ink, width=lw)
    img.thumbnail((int(w), int(h)), Image.LANCZOS)
    c = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    c.alpha_composite(img, (max(0, (c.width - img.width) // 2), max(0, (c.height - img.height) // 2)))
    return c


def _square(w, h, ink, seed=0):
    random.seed(seed)
    scale = 3
    W, H = max(18, int(w) * scale), max(18, int(h) * scale)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(min(W, H) * 0.23)
    lw = max(2, int(min(W, H) * 0.055))
    d.line([(pad, pad), (W - pad, pad), (W - pad, H - pad), (pad, H - pad), (pad, pad)], fill=ink, width=lw)
    img.thumbnail((int(w), int(h)), Image.LANCZOS)
    c = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    c.alpha_composite(img, (max(0, (c.width - img.width) // 2), max(0, (c.height - img.height) // 2)))
    return c


def _defaults(payload):
    return {
        "company_name": payload.get("company_name") or "LECHESA MANABA CONSULTING AND PROJECTS (PTY) LTD",
        "director_name": payload.get("director_name") or "LECHESA MANABA",
        "surname_name": payload.get("surname_and_name") or "MANABA, LECHESA",
        "designation": payload.get("designation") or "DIRECTOR",
        "date": payload.get("date") or payload.get("todays_date") or "27 APRIL 2026",
        "company_reg": payload.get("company_registration_number") or "2012/159509/07",
        "other_enterprises": payload.get("other_enterprises") or "2012/156056/07, 2015/188051/07, 2016/014596/07, 2018/634795/07, 2021/800163/07, 2022/479536/07, 2024/480881/07",
        "address": payload.get("address") or "1787 DUBE STREET, BATHO LOCATION, BLOEMFONTEIN, 9323",
        "phone": payload.get("phone") or "0826338492",
        "email": payload.get("email") or "lechesam@me.com",
        "tcs_pin": payload.get("tcs_pin") or "2C151 C823M",
        "csd": payload.get("csd_number") or "MAAA0002664",
        "buyer_name": payload.get("buyer_name") or "iSIMANGALISO WETLAND PARK AUTHORITY",
        "bid_description": payload.get("bid_description") or "SUPPLY AND DELIVERY OF CORPORATE GIFT PACKS",
    }


def _f(page, x, y, w, h, text="", name="", size=13, mark="text", lines=1):
    return Field(page=page, x=x, y=y, w=w, h=h, text=text, name=name, size=size, mark=mark, lines=lines)


def _training_map(payload):
    d = _defaults(payload)
    fields = []

    fields += [
        _f(5,230,372,305,21,d["company_name"],"rfq_company",9),
        _f(5,230,391,305,21,d["address"],"rfq_postal",8),
        _f(5,230,410,305,21,d["address"],"rfq_street",8),
        _f(5,432,428,96,21,d["phone"],"rfq_phone",12),
        _f(5,250,447,180,21,d["phone"],"rfq_cell",12),
        _f(5,230,486,260,21,d["email"],"rfq_email",13),
        _f(5,254,526,75,42,d["tcs_pin"],"rfq_tcs",9,lines=2),
        _f(5,453,532,105,25,d["csd"],"rfq_csd",11),
    ]

    fields += [
        _f(8,514,418,18,18,name="sbd4_2_1_no",mark="square"),
        _f(8,514,499,18,18,name="sbd4_2_2_no",mark="square"),
        _f(8,466,600,18,18,name="sbd4_2_3_yes",mark="square"),
        _f(8,195,520,95,24,"N/A","sbd4_2_2_1_na",14),
        _f(8,190,622,390,40,d["other_enterprises"],"sbd4_2_3_1_details",8,lines=2),
        _f(10,88,640,155,45,name="sbd4_signature",mark="signature"),
        _f(10,360,663,150,24,d["date"],"sbd4_date",11),
        _f(10,88,720,170,24,d["designation"],"sbd4_position",12),
        _f(10,245,720,335,24,d["company_name"],"sbd4_bidder",8),
    ]

    fields += [
        _f(12,488,420,55,28,"20","sbd6_black_points",20),
        _f(12,488,455,55,28,"4","sbd6_local_points",20),
        _f(12,488,490,55,28,"0","sbd6_woman_points",20),
        _f(12,488,525,55,28,"0","sbd6_youth_points",20),
        _f(12,488,560,55,28,"0","sbd6_disability_points",20),
        _f(15,245,235,300,24,d["company_name"],"sbd6_company",8),
        _f(15,265,264,180,24,d["company_reg"],"sbd6_reg",12),
        _f(15,78,345,18,18,name="sbd6_pty_ltd_tick",mark="x"),
        _f(16,90,540,160,45,name="sbd6_signature",mark="signature"),
        _f(16,335,558,170,24,d["date"],"sbd6_date",11),
        _f(16,250,610,220,24,d["surname_name"],"sbd6_name",11),
        _f(16,250,640,285,55,d["address"],"sbd6_address",8,lines=2),
    ]

    fields += [
        _f(18,514,235,20,20,name="sbd8_4_1_no",mark="x"),
        _f(18,514,468,20,20,name="sbd8_4_2_no",mark="x"),
        _f(19,514,145,20,20,name="sbd8_4_3_no",mark="x"),
        _f(19,514,346,20,20,name="sbd8_4_4_no",mark="x"),
        _f(18,210,365,120,45,"N/A","sbd8_4_1_details",26),
        _f(19,210,164,120,45,"N/A","sbd8_4_3_details",26),
        _f(19,88,620,160,50,name="sbd8_signature",mark="signature"),
        _f(19,490,465,170,24,d["director_name"],"sbd8_name",10),
        _f(19,390,678,150,24,d["date"],"sbd8_date",11),
        _f(19,80,722,160,24,d["designation"],"sbd8_position",11),
        _f(19,245,722,330,24,d["company_name"],"sbd8_bidder",8),
    ]

    fields += [
        _f(21,115,408,360,24,d["company_name"],"sbd9_bidder_page21",8),
        _f(21,214,502,160,50,name="sbd9_signature_page21",mark="signature"),
        _f(23,100,389,160,50,name="sbd9_signature",mark="signature"),
        _f(23,428,447,150,24,d["date"],"sbd9_date",11),
        _f(23,92,510,160,24,d["designation"],"sbd9_position",11),
        _f(23,245,510,330,24,d["company_name"],"sbd9_bidder",8),
    ]

    return fields, {"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","mode":"v21_5_real_handwriting_training_map","field_count":len(fields)}


def _manual(payload):
    out = []
    for i, it in enumerate(payload.get("fields") or []):
        if not isinstance(it, dict):
            continue
        text = _clean(it.get("text") or it.get("value") or "")
        mark = str(it.get("mark") or "").lower().strip()
        if not text and mark not in {"x", "square", "signature"} and not it.get("signature"):
            continue
        out.append(Field(
            page=int(it.get("page") or 1),
            x=float(it.get("x") or 0),
            y=float(it.get("y") or 0),
            w=float(it.get("w") or 260),
            h=float(it.get("h") or 28),
            text=text,
            name=str(it.get("name") or f"manual_{i+1}"),
            size=int(it.get("font_size") or it.get("size") or 13),
            mark=mark or ("signature" if it.get("signature") else "text"),
            lines=int(it.get("max_lines") or 1),
        ))
    return out


def _insert_signature(page, rect, sig_path, ink):
    if sig_path and sig_path.exists():
        try:
            sig = Image.open(sig_path).convert("RGBA")
            data = []
            for r, g, b, a in sig.getdata():
                data.append((255, 255, 255, 0) if r > 235 and g > 235 and b > 235 else (r, g, b, a))
            sig.putdata(data)
            sig.thumbnail((int(rect.width), int(rect.height)), Image.LANCZOS)
            can = Image.new("RGBA", (int(rect.width), int(rect.height)), (0, 0, 0, 0))
            can.alpha_composite(sig, (max(0, (can.width - sig.width) // 2), max(0, (can.height - sig.height) // 2)))
            page.insert_image(rect, stream=_png(can), overlay=True)
            return
        except Exception:
            pass
    page.insert_image(rect, stream=_png(_glyph_text("LM", int(rect.width), int(rect.height), 24, ink, seed=99)), overlay=True)


def complete_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    err = _deps()
    if err:
        return {"status":"error","engine_version":ENGINE_VERSION,"message":err,"checked_at":_now()}

    payload = payload or {}

    ref = payload.get("glyph_reference_image") or payload.get("reference_image") or payload.get("handwriting_reference")
    glyph_build_result = None
    if ref:
        glyph_build_result = build_glyph_library(ref, force=bool(payload.get("force_rebuild_glyphs")))

    pdf = _resolve(payload.get("input_pdf") or payload.get("pdf_path"))
    buyer = _clean(payload.get("buyer_rfq_number") or f"RFQ-{uuid.uuid4().hex[:8]}")
    if not pdf:
        return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found","checked_at":_now()}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{re.sub(r'[^A-Za-z0-9_.-]+','-',buyer)}__v21_5_real_handwriting_completed.pdf"
    ink = _ink(payload.get("ink_color") or "black")
    sig = _resolve(payload.get("signature_image") or payload.get("signature_path"))

    doc = fitz.open(str(pdf))
    inserted, skipped, report = [], [], {}
    try:
        fields = []
        if payload.get("training_map") or payload.get("auto_fill"):
            fields, report = _training_map(payload)
        fields += _manual(payload)

        for idx, field in enumerate(fields):
            try:
                if field.page < 1 or field.page > len(doc):
                    skipped.append({"name":field.name,"reason":"page_out_of_range","page":field.page})
                    continue
                page = doc[field.page - 1]
                rect = fitz.Rect(field.x, field.y, field.x + field.w, field.y + field.h)
                if field.mark == "signature":
                    _insert_signature(page, rect, sig, ink)
                    typ = "signature"
                elif field.mark == "x":
                    page.insert_image(rect, stream=_png(_xmark(field.w, field.h, ink, idx)), overlay=True)
                    typ = "x_mark"
                elif field.mark == "square":
                    page.insert_image(rect, stream=_png(_square(field.w, field.h, ink, idx)), overlay=True)
                    typ = "square_mark"
                else:
                    page.insert_image(
                        rect,
                        stream=_png(_glyph_text(field.text, field.w, field.h, field.size, ink, seed=hash((buyer, field.name, idx)) % 999999, lines=field.lines)),
                        overlay=True,
                    )
                    typ = "real_handwriting_text"
                inserted.append({"name":field.name,"type":typ,"page":field.page,"x":field.x,"y":field.y,"text_preview":field.text[:80]})
            except Exception as e:
                skipped.append({"name":field.name,"reason":"field_failed","error":str(e)})

        doc.save(str(output), garbage=4, deflate=True, clean=True)
        return {
            "status":"ok",
            "engine_version":ENGINE_VERSION,
            "buyer_rfq_number":buyer,
            "message":"Completed using V21.5 real handwriting engine. No typed PDF text insertion was used.",
            "input_pdf":str(pdf),
            "output_pdf":str(output),
            "glyph_dir":str(GLYPH_DIR),
            "glyph_reference_used":str(_resolve(ref)) if ref else None,
            "glyph_build_result":glyph_build_result,
            "training_map": bool(payload.get("training_map") or payload.get("auto_fill")),
            "training_report":report,
            "inserted_count":len(inserted),
            "skipped_count":len(skipped),
            "inserted":inserted,
            "skipped":skipped,
            "checked_at":_now(),
        }
    finally:
        doc.close()


def get_tender_form_intelligence_status():
    glyphs = list(GLYPH_DIR.glob("*.png")) if GLYPH_DIR.exists() else []
    return {
        "status":"ok",
        "engine_version":ENGINE_VERSION,
        "mode":"real_handwriting_training_map",
        "typed_pdf_text_disabled":True,
        "real_handwriting_supported":True,
        "glyph_dir":str(GLYPH_DIR),
        "glyph_library_exists":GLYPH_DIR.exists(),
        "glyph_count":len(glyphs),
        "supported_template":"ISIMANGALISO_CORPORATE_GIFT_PACKS",
        "output_dir":str(OUTPUT_DIR),
        "debug_dir":str(DEBUG_DIR),
        "checked_at":_now(),
    }


def detect_training_template(input_pdf: str):
    pdf = _resolve(input_pdf)
    if not pdf:
        return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found"}
    return {"status":"ok","engine_version":ENGINE_VERSION,"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","matched":True,"input_pdf":str(pdf)}


def detect_sbd_pages(input_pdf: str):
    pdf = _resolve(input_pdf)
    if not pdf:
        return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found"}
    doc = fitz.open(str(pdf))
    try:
        return {"status":"ok","engine_version":ENGINE_VERSION,"input_pdf":str(pdf),"page_count":len(doc),"message":"V21.5 uses trained map for known RFQ pack."}
    finally:
        doc.close()


def locate_writable_fields(input_pdf: str, page_number: int = 1, limit: int = 30):
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V21.5 uses real handwriting training maps; locator not used for trained template.","candidates":[]}


# compatibility aliases
def complete_form_with_tender_intelligence(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form(payload): return complete_tender_form_intelligence(payload)
def complete_form(payload): return complete_tender_form_intelligence(payload)
def complete_sbd_form(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form_from_payload(payload): return complete_tender_form_intelligence(payload)
def run_tender_form_intelligence(payload): return complete_tender_form_intelligence(payload)
