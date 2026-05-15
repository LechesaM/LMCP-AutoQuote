
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, validator
from PIL import Image, ImageOps, ImageFilter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "runtime"))
DEFAULT_SAMPLE_IMAGE = Path(os.getenv("LMCP_HANDWRITING_SAMPLE", "app/assets/handwriting_samples/lechesa_handwriting.jpg"))
DEFAULT_OUTPUT_DIR = RUNTIME_DIR / "handwriting_simulation" / "glyph_form_outputs"
DEFAULT_TMP_DIR = RUNTIME_DIR / "handwriting_simulation" / "glyph_tmp"
DEFAULT_GLYPH_DIR = RUNTIME_DIR / "handwriting_simulation" / "glyph_cache"

EXPECTED_CHARS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + list("1234567890")


class GlyphField(BaseModel):
    page: int = Field(..., ge=1)
    x: float
    y: float
    text: str
    glyph_height: Optional[float] = Field(None, ge=4, le=90)
    letter_spacing: Optional[float] = Field(None, ge=-5, le=40)
    word_spacing: Optional[float] = Field(None, ge=0, le=100)
    line_spacing: Optional[float] = Field(None, ge=0, le=140)
    max_width: Optional[float] = Field(None, ge=20)
    uppercase: bool = True


class GlyphOverlayRequest(BaseModel):
    buyer_rfq_number: str = Field(..., min_length=1)
    input_pdf: str = Field(..., min_length=1)
    output_pdf: Optional[str] = None
    sample_image: Optional[str] = None
    fields: List[GlyphField] = Field(default_factory=list)
    default_glyph_height: float = Field(14, ge=4, le=90)
    default_letter_spacing: float = Field(1.0, ge=-5, le=40)
    default_word_spacing: float = Field(7.0, ge=0, le=100)
    default_line_spacing: float = Field(18.0, ge=0, le=140)

    @validator("fields")
    def validate_fields(cls, value: List[GlyphField]) -> List[GlyphField]:
        if not value:
            raise ValueError("At least one field is required.")
        return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ref(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in value.strip())
    return cleaned[:120] or f"RFQ-{uuid.uuid4().hex[:8]}"


def _ensure_dirs() -> None:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_GLYPH_DIR.mkdir(parents=True, exist_ok=True)


def _load_sample(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGB")
    max_width = 1500
    if img.width > max_width:
        ratio = max_width / float(img.width)
        img = img.resize((max_width, int(img.height * ratio)))
    return img


def _threshold_ink(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img).filter(ImageFilter.MedianFilter(size=3))
    hist = gray.histogram()
    total = sum(hist) or 1
    mean = sum(i * c for i, c in enumerate(hist)) / total
    threshold = max(55, min(140, int(mean * 0.58)))
    return gray.point(lambda p: 0 if p < threshold else 255, mode="L")


def _component_boxes(binary: Image.Image) -> List[Tuple[int, int, int, int]]:
    w, h = binary.size
    pix = binary.load()
    visited = bytearray(w * h)

    def idx(x: int, y: int) -> int:
        return y * w + x

    boxes: List[Tuple[int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            i = idx(x, y)
            if visited[i]:
                continue
            visited[i] = 1
            if pix[x, y] > 30:
                continue

            stack = [(x, y)]
            min_x = max_x = x
            min_y = max_y = y
            count = 0

            while stack:
                cx, cy = stack.pop()
                count += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)

                for nx in (cx - 1, cx, cx + 1):
                    for ny in (cy - 1, cy, cy + 1):
                        if nx < 0 or ny < 0 or nx >= w or ny >= h:
                            continue
                        ni = idx(nx, ny)
                        if visited[ni]:
                            continue
                        visited[ni] = 1
                        if pix[nx, ny] <= 30:
                            stack.append((nx, ny))

            bw = max_x - min_x + 1
            bh = max_y - min_y + 1
            if count >= 10 and bw >= 3 and bh >= 7 and bw < w * 0.22 and bh < h * 0.22:
                boxes.append((min_x, min_y, max_x + 1, max_y + 1))
    return boxes


def _merge_boxes(boxes: List[Tuple[int, int, int, int]]) -> List[Tuple[int, int, int, int]]:
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    merged: List[Tuple[int, int, int, int]] = []
    for box in boxes:
        x1, y1, x2, y2 = box
        done = False
        for i, e in enumerate(merged):
            ex1, ey1, ex2, ey2 = e
            h_gap = max(0, max(x1, ex1) - min(x2, ex2))
            v_gap = max(0, max(y1, ey1) - min(y2, ey2))
            overlap_x = min(x2, ex2) - max(x1, ex1)
            if (overlap_x > -5 and v_gap <= 12) or (h_gap <= 5 and v_gap <= 6):
                merged[i] = (min(x1, ex1), min(y1, ey1), max(x2, ex2), max(y2, ey2))
                done = True
                break
        if not done:
            merged.append(box)
    return merged


def _group_rows(boxes: List[Tuple[int, int, int, int]]) -> List[List[Tuple[int, int, int, int]]]:
    if not boxes:
        return []
    heights = [b[3] - b[1] for b in boxes]
    avg_h = sum(heights) / len(heights)
    tolerance = max(18, avg_h * 0.8)
    rows: List[List[Tuple[int, int, int, int]]] = []
    for b in sorted(boxes, key=lambda b: ((b[1]+b[3])/2, b[0])):
        cy = (b[1] + b[3]) / 2
        placed = False
        for row in rows:
            rcy = sum((x[1]+x[3])/2 for x in row) / len(row)
            if abs(cy - rcy) <= tolerance:
                row.append(b); placed = True; break
        if not placed:
            rows.append([b])
    rows = [sorted(r, key=lambda b: b[0]) for r in rows if len(r) >= 2]
    return sorted(rows, key=lambda r: sum((b[1]+b[3])/2 for b in r)/len(r))


def _select_boxes(boxes: List[Tuple[int, int, int, int]]) -> List[Tuple[int, int, int, int]]:
    merged = _merge_boxes(boxes)
    if not merged:
        return []
    widths = sorted([b[2]-b[0] for b in merged])
    heights = sorted([b[3]-b[1] for b in merged])
    mw, mh = widths[len(widths)//2], heights[len(heights)//2]
    filtered = []
    for b in merged:
        bw, bh = b[2]-b[0], b[3]-b[1]
        if bw >= max(3, mw*0.18) and bh >= max(6, mh*0.30):
            filtered.append(b)
    rows = _group_rows(filtered)
    if len(rows) > 5:
        rows = sorted(rows, key=lambda r: (-len(r), -sum((b[2]-b[0])*(b[3]-b[1]) for b in r)))
        rows = sorted(rows[:5], key=lambda r: sum((b[1]+b[3])/2 for b in r)/len(r))
    flat = []
    for r in rows:
        flat.extend(sorted(r, key=lambda b: b[0]))
    return flat[:len(EXPECTED_CHARS)]


def _clean_glyph(original: Image.Image, box: Tuple[int, int, int, int]) -> Image.Image:
    pad = 12
    x1,y1,x2,y2 = box
    x1=max(0,x1-pad); y1=max(0,y1-pad); x2=min(original.width,x2+pad); y2=min(original.height,y2+pad)
    crop = original.crop((x1,y1,x2,y2)).convert("RGBA")
    gray = ImageOps.grayscale(crop.convert("RGB")).filter(ImageFilter.MedianFilter(size=3))
    hist = gray.histogram(); total=sum(hist) or 1
    mean=sum(i*c for i,c in enumerate(hist))/total
    th=max(65, min(160, int(mean*0.66)))
    pix=crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            r,g,b,a=pix[x,y]; br=(r+g+b)//3
            if br > th:
                pix[x,y]=(255,255,255,0)
            else:
                pix[x,y]=(18,18,18,max(140,min(255,255-br+55)))
    bbox=crop.getchannel("A").getbbox()
    if bbox:
        crop=crop.crop(bbox)
    out=Image.new("RGBA",(crop.width+8,crop.height+8),(255,255,255,0))
    out.alpha_composite(crop,(4,4))
    return out


def build_glyph_cache(sample_image: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    _ensure_dirs()
    sample_path = Path(sample_image) if sample_image else DEFAULT_SAMPLE_IMAGE
    if not sample_path.exists():
        return {"status":"error","message":f"Handwriting sample image not found: {sample_path}","sample_image":str(sample_path),"created_at":_now_iso()}

    existing = list(DEFAULT_GLYPH_DIR.glob("*.png"))
    if existing and not force:
        return {"status":"ok","message":"Glyph cache already exists. Use /build-cache to rebuild.","sample_image":str(sample_path),"glyph_dir":str(DEFAULT_GLYPH_DIR),"glyph_count":len(existing),"created_at":_now_iso()}

    for old in DEFAULT_GLYPH_DIR.glob("*.png"):
        old.unlink(missing_ok=True)

    original = _load_sample(sample_path)
    binary = _threshold_ink(original)
    boxes = _component_boxes(binary)
    selected = _select_boxes(boxes)

    mapped=[]; saved=[]
    for idx,ch in enumerate(EXPECTED_CHARS):
        if idx >= len(selected): break
        glyph = _clean_glyph(original, selected[idx])
        out = DEFAULT_GLYPH_DIR / f"{ch}.png"
        glyph.save(out)
        saved.append(str(out))
        mapped.append({"char":ch,"box":selected[idx],"file":str(out)})

    status = "ok" if len(saved) >= 30 else "warning"
    return {"status":status,"message":"Smart glyph cache built from handwriting sample.","sample_image":str(sample_path),"glyph_dir":str(DEFAULT_GLYPH_DIR),"detected_component_count":len(boxes),"selected_glyph_count":len(selected),"glyph_count":len(saved),"expected_glyph_count":len(EXPECTED_CHARS),"mapped":mapped,"created_at":_now_iso()}


def _glyph_path(ch: str) -> Optional[Path]:
    if ch.isalpha(): ch = ch.upper()
    if ch.isdigit() or ("A" <= ch <= "Z"):
        p = DEFAULT_GLYPH_DIR / f"{ch}.png"
        return p if p.exists() else None
    return None


def _glyph_size(path: Path, target_height: float) -> Tuple[float, float]:
    with Image.open(path) as img:
        w,h=img.size
    scale = target_height / float(h or 1)
    return float(w)*scale, target_height


def _text_width(text: str, glyph_height: float, letter_spacing: float, word_spacing: float) -> float:
    width=0.0
    for ch in text:
        if ch == " ":
            width += word_spacing; continue
        p=_glyph_path(ch)
        if p:
            gw,_=_glyph_size(p,glyph_height); width += gw + letter_spacing
        else:
            width += glyph_height*0.35
    return width


def _wrap_text(text: str, max_width: Optional[float], glyph_height: float, letter_spacing: float, word_spacing: float) -> List[str]:
    if not max_width: return text.splitlines() or [text]
    lines=[]
    for para in (text.splitlines() or [text]):
        current=""
        for word in para.split(" "):
            cand=word if not current else current+" "+word
            if _text_width(cand,glyph_height,letter_spacing,word_spacing) <= max_width:
                current=cand
            else:
                if current: lines.append(current)
                current=word
        if current: lines.append(current)
    return lines or [""]


def _draw_text(c: canvas.Canvas, field: GlyphField, default_glyph_height: float, default_letter_spacing: float, default_word_spacing: float, default_line_spacing: float) -> int:
    text = field.text.upper() if field.uppercase else field.text
    gh = field.glyph_height or default_glyph_height
    ls = field.letter_spacing if field.letter_spacing is not None else default_letter_spacing
    ws = field.word_spacing if field.word_spacing is not None else default_word_spacing
    line_s = field.line_spacing if field.line_spacing is not None else default_line_spacing
    drawn=0
    for line_idx,line in enumerate(_wrap_text(text, field.max_width, gh, ls, ws)):
        x=float(field.x); y=float(field.y) - line_idx*line_s
        for ch in line:
            if ch == " ":
                x += ws; continue
            p=_glyph_path(ch)
            if not p:
                x += gh*0.35; continue
            gw,hh = _glyph_size(p, gh)
            c.drawImage(ImageReader(str(p)), x, y, width=gw, height=hh, mask="auto")
            x += gw + ls; drawn += 1
    return drawn


def overlay_glyph_handwriting_on_pdf(payload: Dict[str, Any] | GlyphOverlayRequest) -> Dict[str, Any]:
    _ensure_dirs()
    req = payload if isinstance(payload, GlyphOverlayRequest) else GlyphOverlayRequest(**payload)
    input_pdf = Path(req.input_pdf)
    if not input_pdf.exists() or not input_pdf.is_file():
        return {"status":"error","message":f"Input PDF not found: {input_pdf}","buyer_rfq_number":req.buyer_rfq_number,"created_at":_now_iso()}

    cache = build_glyph_cache(sample_image=req.sample_image, force=False)
    if cache.get("status") not in ("ok","warning"):
        return cache

    safe_ref=_safe_ref(req.buyer_rfq_number)
    output_pdf = Path(req.output_pdf) if req.output_pdf else DEFAULT_OUTPUT_DIR / f"{safe_ref}__glyph_handwritten_completed_form.pdf"
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    overlay_pdf = DEFAULT_TMP_DIR / f"{safe_ref}__glyph_overlay_{uuid.uuid4().hex[:8]}.pdf"

    try:
        reader=PdfReader(str(input_pdf))
        total_pages=len(reader.pages)
        fields_by_page: Dict[int,List[GlyphField]]={}
        skipped=[]
        for f in req.fields:
            if f.page < 1 or f.page > total_pages:
                skipped.append({"field":f.dict(),"reason":f"Page {f.page} outside PDF range 1-{total_pages}"})
                continue
            fields_by_page.setdefault(f.page,[]).append(f)

        if not fields_by_page:
            return {"status":"error","message":"No valid fields matched the input PDF page range.","buyer_rfq_number":req.buyer_rfq_number,"input_pdf":str(input_pdf),"page_count":total_pages,"created_at":_now_iso()}

        c=canvas.Canvas(str(overlay_pdf))
        drawn=0
        for page_index in range(total_pages):
            page_num=page_index+1
            page=reader.pages[page_index]
            c.setPageSize((float(page.mediabox.width), float(page.mediabox.height)))
            for f in fields_by_page.get(page_num,[]):
                drawn += _draw_text(c, f, req.default_glyph_height, req.default_letter_spacing, req.default_word_spacing, req.default_line_spacing)
            c.showPage()
        c.save()

        overlay_reader=PdfReader(str(overlay_pdf))
        writer=PdfWriter()
        for idx, original_page in enumerate(reader.pages):
            page=original_page
            page.merge_page(overlay_reader.pages[idx])
            writer.add_page(page)
        with output_pdf.open("wb") as f:
            writer.write(f)
        try: overlay_pdf.unlink(missing_ok=True)
        except Exception: pass

        return {"status":"ok","message":"Smart glyph handwriting overlay applied to existing PDF form.","buyer_rfq_number":req.buyer_rfq_number,"input_pdf":str(input_pdf),"output_file":str(output_pdf),"page_count":total_pages,"field_count":sum(len(v) for v in fields_by_page.values()),"drawn_glyph_count":drawn,"skipped_field_count":len(skipped),"skipped_fields":skipped,"glyph_dir":str(DEFAULT_GLYPH_DIR),"created_at":_now_iso()}
    except Exception as exc:
        return {"status":"error","message":f"Failed to apply smart glyph handwriting overlay: {exc}","buyer_rfq_number":req.buyer_rfq_number,"input_pdf":str(input_pdf),"output_file":str(output_pdf),"created_at":_now_iso()}


run_glyph_handwriting_overlay = overlay_glyph_handwriting_on_pdf
