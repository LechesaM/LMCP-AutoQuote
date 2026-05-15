
"""
LMCP AutoQuote System
V21.2 SBD Auto-Fill Decision Engine

Drop-in target:
    app/services/tender_form_intelligence_engine.py

This version adds the missing semantic layer:
- detects SBD4, SBD6.1, SBD8, SBD9 pages
- applies LMCP default answers
- writes with image-based handwriting only
- draws handwritten X/square marks
- supports signatures
- keeps manual field coordinates supported
"""

from __future__ import annotations

import io, re, math, random, uuid
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


ENGINE_VERSION = "V21.2_SBD_AUTOFILL_DECISION_ENGINE"
PROJECT_ROOT = Path("/app") if Path("/app").exists() else Path.cwd()
OUTPUT_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "completed_forms"
DEBUG_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "debug"

FONT_CANDIDATES = [
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
    text: str = ""
    name: str = ""
    font_size: Optional[int] = None
    max_lines: int = 1
    mark: str = "text"       # text, x, square, signature
    signature: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ").replace("\r", " ")).strip()


def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()


def _deps_error():
    if fitz is None:
        return "PyMuPDF is not installed. Install with: pip install pymupdf"
    if Image is None:
        return "Pillow is not installed. Install with: pip install pillow"
    return None


def _resolve(p: Any) -> Optional[Path]:
    raw = str(p or "").strip()
    if not raw:
        return None
    candidates = [Path(raw), PROJECT_ROOT / raw, PROJECT_ROOT / raw.lstrip("/"), Path.cwd() / raw]
    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except Exception:
            pass
    return None


def _font(size: int, preferred: Optional[str] = None):
    candidates = ([preferred] if preferred else []) + FONT_CANDIDATES
    for f in candidates:
        try:
            if f and Path(f).exists():
                return ImageFont.truetype(f, size=size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("DejaVuSans-Oblique.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def _ink(name: str = "black") -> Tuple[int, int, int, int]:
    n = (name or "black").lower()
    if "blue" in n:
        return (4, 28, 140, 255)
    return (2, 2, 2, 255)


def _measure(draw, text: str, font) -> Tuple[int, int]:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return max(1, b[2]-b[0]), max(1, b[3]-b[1])
    except Exception:
        return draw.textsize(text, font=font)


def _wrap(text: str, font, width: int, max_lines: int) -> List[str]:
    words = _clean(text).split()
    if not words:
        return [""]
    im = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(im)
    lines, cur = [], ""
    for w in words:
        trial = w if not cur else cur + " " + w
        tw, _ = _measure(d, trial, font)
        if tw <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines] or [""]


def _fit_size(text: str, w: int, h: int, requested: Optional[int], max_lines: int) -> int:
    start = requested or max(9, min(22, int(h * 0.68)))
    probe = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(probe)
    for size in range(int(start), 7, -1):
        f = _font(size)
        lines = _wrap(text, f, max(8, w-8), max_lines)
        widest = max(_measure(d, line, f)[0] for line in lines)
        if widest <= w - 4 and len(lines) * (size + 5) <= h + 8:
            return size
    return 8


def _hand_text(text: str, w: int, h: int, font_size: int, ink=(2,2,2,255), seed: int = 0, max_lines: int = 1) -> Image.Image:
    random.seed(seed)
    scale = 3
    W, H = max(20, w*scale), max(16, h*scale)
    im = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(im)
    f = _font(max(8, font_size*scale))
    lines = _wrap(text, f, max(10, W-16), max_lines)
    y = max(2, int(H * 0.06))
    lh = max((font_size+7)*scale, int(H / max(1, len(lines))))
    for line in lines:
        x = 6 + random.uniform(-2,2)
        wave = random.random() * 6.28
        for i, ch in enumerate(line):
            cw, _ = _measure(d, ch, f)
            jx = random.uniform(-0.5, 0.7) * scale
            jy = (math.sin(i * 0.7 + wave) * 0.55 + random.uniform(-0.35, 0.35)) * scale
            d.text((x+jx, y+jy), ch, font=f, fill=ink)
            if ch != " " and random.random() < 0.72:
                d.text((x+jx+random.uniform(-.4,.4), y+jy+random.uniform(-.4,.4)), ch, font=f, fill=(ink[0],ink[1],ink[2],70))
            x += cw + random.uniform(-0.1, 0.85)*scale + (random.uniform(0.6,2.2)*scale if ch == " " else 0)
            if x > W - 8:
                break
        y += lh
    im = im.filter(ImageFilter.GaussianBlur(radius=0.22))
    im = im.rotate(random.uniform(-0.25,0.25), expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))
    im.thumbnail((w,h), Image.LANCZOS)
    canvas = Image.new("RGBA", (w,h), (0,0,0,0))
    canvas.alpha_composite(im, (max(0,(w-im.width)//2), max(0,(h-im.height)//2)))
    return canvas


def _x_mark(w: int, h: int, ink=(2,2,2,255), seed: int = 0) -> Image.Image:
    random.seed(seed)
    scale = 3
    W, H = max(18,w*scale), max(18,h*scale)
    im = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(im)
    pad = int(min(W,H)*0.18)
    lw = max(2, int(min(W,H)*0.06))
    d.line([(pad,pad),(W-pad,H-pad)], fill=ink, width=lw)
    d.line([(W-pad,pad),(pad,H-pad)], fill=ink, width=lw)
    im = im.filter(ImageFilter.GaussianBlur(radius=0.25))
    im.thumbnail((w,h), Image.LANCZOS)
    c = Image.new("RGBA",(w,h),(0,0,0,0))
    c.alpha_composite(im,(max(0,(w-im.width)//2),max(0,(h-im.height)//2)))
    return c


def _square_mark(w: int, h: int, ink=(2,2,2,255), seed: int = 0) -> Image.Image:
    random.seed(seed)
    scale = 3
    W, H = max(18,w*scale), max(18,h*scale)
    im = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(im)
    pad = int(min(W,H)*0.22)
    lw = max(2, int(min(W,H)*0.06))
    d.line([(pad,pad),(W-pad,pad),(W-pad,H-pad),(pad,H-pad),(pad,pad)], fill=ink, width=lw)
    im.thumbnail((w,h), Image.LANCZOS)
    c = Image.new("RGBA",(w,h),(0,0,0,0))
    c.alpha_composite(im,(max(0,(w-im.width)//2),max(0,(h-im.height)//2)))
    return c


def _png(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, format="PNG")
    return b.getvalue()


def _page_text(page) -> str:
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""


def _words(page):
    try:
        return page.get_text("words")
    except Exception:
        return []


def _detect_type(text: str) -> str:
    t = _norm(text)
    if "sbd 4" in t or "bidder s declaration" in t:
        return "SBD4"
    if "sbd 6 1" in t or "preference points claim form" in t or "preferential procurement regulations 2022" in t:
        return "SBD6_1"
    if "sbd 8" in t or "past supply chain management practices" in t or "restricted suppliers" in t:
        return "SBD8"
    if "sbd 9" in t or "certificate of independent bid determination" in t:
        return "SBD9"
    if "supplier information" in t and "name of bidder" in t:
        return "RFQ_SUPPLIER_INFO"
    return "UNKNOWN"


def _phrase_rect(page, phrase: str):
    target = _norm(phrase).split()
    if not target:
        return None
    ws = _words(page)
    toks = [_norm(w[4]) for w in ws]
    for i in range(len(toks)):
        if toks[i:i+len(target)] == target:
            r = fitz.Rect(ws[i][0], ws[i][1], ws[i][2], ws[i][3])
            for j in range(i+1, i+len(target)):
                r |= fitz.Rect(ws[j][0], ws[j][1], ws[j][2], ws[j][3])
            return r
    return None


def _checkbox_near(page, anchor, answer="NO"):
    boxes = []
    try:
        for dr in page.get_drawings():
            for item in dr.get("items", []):
                if item and item[0] == "re" and len(item) > 1:
                    r = fitz.Rect(item[1])
                    if 4 <= r.width <= 20 and 4 <= r.height <= 20 and abs(r.y0-anchor.y0) < 55:
                        boxes.append(r)
    except Exception:
        pass
    if boxes:
        boxes = sorted(boxes, key=lambda r: r.x0)
        return boxes[-1] if answer.upper() == "NO" else boxes[0]
    return fitz.Rect(page.rect.width-80, anchor.y0, page.rect.width-62, anchor.y0+18) if answer.upper()=="NO" else fitz.Rect(page.rect.width-125, anchor.y0, page.rect.width-107, anchor.y0+18)


def _defaults(payload: Dict[str, Any]) -> Dict[str, str]:
    return {
        "company_name": str(payload.get("company_name") or "LECHESA MANABA CONSULTING AND PROJECTS (PTY) LTD"),
        "director_name": str(payload.get("director_name") or "LECHESA MANABA"),
        "surname_and_name": str(payload.get("surname_and_name") or "MANABA, LECHESA"),
        "designation": str(payload.get("designation") or "DIRECTOR"),
        "date": str(payload.get("date") or payload.get("todays_date") or "TODAY’S DATE"),
        "company_reg": str(payload.get("company_registration_number") or "2012/159509/07"),
        "other_enterprises": str(payload.get("other_enterprises") or "2012/156056/07 * 2015/188051/07 * 2016/014596/07 * 2018/634795/07 * 2021/800163/07 * 2022/479536/07 * 2024/480881/07"),
        "bid_description": str(payload.get("bid_description") or payload.get("description") or payload.get("title") or "RFQ"),
        "buyer_name": str(payload.get("buyer_name") or "BUYER"),
        "address_1": str(payload.get("address_1") or "1787 DUBE STREET"),
        "address_2": str(payload.get("address_2") or "BATHO LOCATION"),
        "address_3": str(payload.get("address_3") or "BLOEMFONTEIN, 9323"),
        "email": str(payload.get("email") or "lechesam@me.com"),
        "phone": str(payload.get("phone") or "0826338492"),
        "tcs_pin": str(payload.get("tcs_pin") or "2C151 C823M"),
        "csd_number": str(payload.get("csd_number") or "MAAA0002664"),
    }


def _add(fields, page, x, y, w, h, text="", name="", size=14, mark="text", max_lines=1, signature=False):
    fields.append(FieldBox(page=page, x=float(x), y=float(y), w=float(w), h=float(h), text=text, name=name, font_size=size, mark=mark, max_lines=max_lines, signature=signature))


def _sbd4(page, pno, payload):
    d = _defaults(payload); f = []; txt = _norm(_page_text(page))
    for phrase, ans, name in [
        ("employed by the state", "NO", "sbd4_2_1_no"),
        ("relationship with any person", "NO", "sbd4_2_2_no"),
        ("interest in any other related enterprise", "YES", "sbd4_2_3_yes"),
    ]:
        r = _phrase_rect(page, phrase)
        if r:
            b = _checkbox_near(page, r, ans)
            _add(f, pno, b.x0-1, b.y0-1, 18, 18, name=name, mark="square")
    r = _phrase_rect(page, "furnish particulars")
    if r:
        _add(f, pno, min(r.x1+18, 410), r.y0-2, 100, 22, "N/A", "sbd4_na", 14)
    r = _phrase_rect(page, "2 3 1") or _phrase_rect(page, "if so furnish particulars")
    if r:
        _add(f, pno, r.x1+12, r.y0-4, 430, 44, d["other_enterprises"], "sbd4_other_enterprises", 10, max_lines=2)
    if "signature" in txt:
        r = _phrase_rect(page, "signature")
        if r: _add(f, pno, r.x0+8, max(0,r.y0-62), 160, 50, name="sbd4_signature", mark="signature", signature=True)
        r = _phrase_rect(page, "date")
        if r: _add(f, pno, r.x0+8, max(0,r.y0-32), 170, 24, d["date"], "sbd4_date", 13)
        r = _phrase_rect(page, "position")
        if r: _add(f, pno, r.x0, max(0,r.y0-34), 170, 24, d["designation"], "sbd4_position", 13)
        r = _phrase_rect(page, "name of bidder")
        if r: _add(f, pno, max(40,r.x0-150), max(0,r.y0-34), 370, 24, d["company_name"], "sbd4_bidder", 10)
    return f


def _sbd6(page, pno, payload):
    d = _defaults(payload); f = []; txt = _norm(_page_text(page))
    if "specific goals" in txt and "points claimed" in txt:
        for phrase, val in [("black", "20"), ("local service", "4"), ("woman", "0"), ("youth", "0"), ("disabilities", "0")]:
            r = _phrase_rect(page, phrase)
            if r: _add(f, pno, min(page.rect.width-100, r.x1+245), r.y0-2, 58, 30, val, f"sbd6_points_{phrase}", 22)
    if "company registration number" in txt or "name of company" in txt:
        r = _phrase_rect(page, "name of company") or _phrase_rect(page, "name of company firm")
        if r: _add(f, pno, r.x1+10, r.y0-4, 360, 24, d["company_name"], "sbd6_company", 10)
        r = _phrase_rect(page, "company registration number")
        if r: _add(f, pno, r.x1+10, r.y0-4, 220, 24, d["company_reg"], "sbd6_reg", 14)
        r = _phrase_rect(page, "pty limited")
        if r: _add(f, pno, max(15,r.x0-20), r.y0-2, 20, 20, name="sbd6_pty_tick", mark="x")
    if "signature" in txt:
        r = _phrase_rect(page, "signature")
        if r: _add(f, pno, r.x0+8, max(0,r.y0-62), 160, 50, name="sbd6_signature", mark="signature", signature=True)
        r = _phrase_rect(page, "surname and name")
        if r: _add(f, pno, r.x1+10, r.y0-4, 220, 24, d["surname_and_name"], "sbd6_name", 13)
        r = _phrase_rect(page, "date")
        if r: _add(f, pno, r.x1+10, r.y0-4, 160, 24, d["date"], "sbd6_date", 13)
        r = _phrase_rect(page, "address")
        if r:
            _add(f, pno, r.x1+10, r.y0-4, 250, 22, d["address_1"], "sbd6_addr1", 12)
            _add(f, pno, r.x1+10, r.y0+22, 250, 22, d["address_2"], "sbd6_addr2", 12)
            _add(f, pno, r.x1+10, r.y0+48, 250, 22, d["address_3"], "sbd6_addr3", 12)
    return f


def _sbd8(page, pno, payload):
    d = _defaults(payload); f = []; txt = _norm(_page_text(page))
    for q in ["4 1", "4 2", "4 3", "4 4"]:
        r = _phrase_rect(page, q)
        if r:
            b = _checkbox_near(page, r, "NO")
            _add(f, pno, b.x0-1, b.y0-1, 20, 20, name=f"sbd8_{q}_no", mark="x")
    if "if so furnish particulars" in txt:
        # put N/A in the large particulars area, using common relative placement
        for r in [_phrase_rect(page, "if so furnish particulars")]:
            if r: _add(f, pno, r.x0+100, r.y0+18, 120, 45, "N/A", "sbd8_na", 30)
    if "signature" in txt or "certification" in txt:
        r = _phrase_rect(page, "signature")
        if r: _add(f, pno, r.x0+8, max(0,r.y0-62), 160, 50, name="sbd8_signature", mark="signature", signature=True)
        r = _phrase_rect(page, "full name") or _phrase_rect(page, "i the undersigned")
        if r: _add(f, pno, r.x1+10, r.y0-4, 220, 24, d["director_name"], "sbd8_name", 13)
        r = _phrase_rect(page, "date")
        if r: _add(f, pno, r.x1+10, r.y0-4, 160, 24, d["date"], "sbd8_date", 13)
        r = _phrase_rect(page, "position")
        if r: _add(f, pno, r.x0, max(0,r.y0-34), 160, 24, d["designation"], "sbd8_position", 13)
        r = _phrase_rect(page, "name of bidder")
        if r: _add(f, pno, max(40,r.x0-150), max(0,r.y0-34), 370, 24, d["company_name"], "sbd8_bidder", 10)
    return f


def _sbd9(page, pno, payload):
    d = _defaults(payload); f = []; txt = _norm(_page_text(page))
    r = _phrase_rect(page, "name of bid and description")
    if r: _add(f, pno, r.x0, r.y1+12, 440, 28, d["bid_description"], "sbd9_bid_desc", 12)
    r = _phrase_rect(page, "name of buyer")
    if r: _add(f, pno, r.x0, r.y1+12, 420, 28, d["buyer_name"], "sbd9_buyer", 12)
    r = _phrase_rect(page, "name of bidder")
    if r: _add(f, pno, max(40,r.x0-150), max(0,r.y0-34), 380, 24, d["company_name"], "sbd9_bidder", 10)
    if "signature" in txt:
        r = _phrase_rect(page, "signature")
        if r: _add(f, pno, r.x0+8, max(0,r.y0-62), 160, 50, name="sbd9_signature", mark="signature", signature=True)
        r = _phrase_rect(page, "date")
        if r: _add(f, pno, r.x1+10, r.y0-4, 160, 24, d["date"], "sbd9_date", 13)
        r = _phrase_rect(page, "position")
        if r: _add(f, pno, r.x0, max(0,r.y0-34), 160, 24, d["designation"], "sbd9_position", 13)
    return f


def _rfq_supplier(page, pno, payload):
    d = _defaults(payload); txt = _norm(_page_text(page)); f = []
    if "supplier information" in txt:
        _add(f,pno,230,372,305,21,d["company_name"],"rfq_company",10)
        _add(f,pno,230,391,305,21,f"{d['address_1']}, {d['address_2']}, BFN, 9323","rfq_postal",10)
        _add(f,pno,230,410,305,21,f"{d['address_1']}, {d['address_2']}, BFN, 9323","rfq_street",10)
        _add(f,pno,432,428,96,21,d["phone"],"rfq_phone",14)
        _add(f,pno,250,447,180,21,d["phone"],"rfq_cell",14)
        _add(f,pno,230,486,260,21,d["email"],"rfq_email",15)
        _add(f,pno,255,526,62,44,d["tcs_pin"],"rfq_tcs",11,max_lines=2)
        _add(f,pno,455,532,95,25,d["csd_number"],"rfq_csd",13)
    return f


def _auto_fields(doc, payload):
    fields, detected = [], []
    for pno, page in enumerate(doc, start=1):
        typ = _detect_type(_page_text(page))
        if typ != "UNKNOWN":
            detected.append({"page": pno, "sbd_type": typ})
        if typ == "SBD4": fields += _sbd4(page, pno, payload)
        elif typ == "SBD6_1": fields += _sbd6(page, pno, payload)
        elif typ == "SBD8": fields += _sbd8(page, pno, payload)
        elif typ == "SBD9": fields += _sbd9(page, pno, payload)
        elif typ == "RFQ_SUPPLIER_INFO": fields += _rfq_supplier(page, pno, payload)
    return fields, {"detected_pages": detected, "forms_detected": sorted(set(x["sbd_type"] for x in detected)), "auto_field_count": len(fields)}


def _manual_fields(payload):
    out = []
    for i, it in enumerate(payload.get("fields") or []):
        if not isinstance(it, dict): continue
        mark = str(it.get("mark") or "").lower()
        text = _clean(it.get("text") or it.get("value") or "")
        signature = bool(it.get("signature")) or mark == "signature"
        if not text and not signature and mark not in {"x","square"}: continue
        out.append(FieldBox(
            page=int(it.get("page") or 1), x=float(it.get("x") or 0), y=float(it.get("y") or 0),
            w=float(it.get("w") or 260), h=float(it.get("h") or 28), text=text,
            name=str(it.get("name") or f"manual_{i+1}"), font_size=int(it.get("font_size") or 0) or None,
            max_lines=int(it.get("max_lines") or 1), mark=mark or ("signature" if signature else "text"),
            signature=signature
        ))
    return out


def _insert_signature(page, rect, sig_path, ink):
    if sig_path and sig_path.exists():
        try:
            sig = Image.open(sig_path).convert("RGBA")
            data = []
            for r,g,b,a in sig.getdata():
                data.append((255,255,255,0) if r>235 and g>235 and b>235 else (r,g,b,a))
            sig.putdata(data)
            sig.thumbnail((int(rect.width), int(rect.height)), Image.LANCZOS)
            canvas = Image.new("RGBA", (int(rect.width), int(rect.height)), (0,0,0,0))
            canvas.alpha_composite(sig, (max(0,(canvas.width-sig.width)//2), max(0,(canvas.height-sig.height)//2)))
            page.insert_image(rect, stream=_png(canvas), overlay=True)
            return True
        except Exception:
            pass
    im = _hand_text("LM", int(rect.width), int(rect.height), 24, ink, seed=77)
    page.insert_image(rect, stream=_png(im), overlay=True)
    return True


def complete_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    err = _deps_error()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err,"checked_at":_now()}
    payload = payload or {}
    pdf = _resolve(payload.get("input_pdf") or payload.get("pdf_path"))
    buyer_rfq = _clean(payload.get("buyer_rfq_number") or f"RFQ-{uuid.uuid4().hex[:8]}")
    if not pdf: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found.","checked_at":_now()}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True); DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = OUTPUT_DIR / f"{re.sub(r'[^A-Za-z0-9_.-]+','-',buyer_rfq)}__v21_2_sbd_autofilled.pdf"
    sig_path = _resolve(payload.get("signature_image") or payload.get("signature_path"))
    ink = _ink(payload.get("ink_color") or "black")
    inserted, skipped = [], []
    auto_report = {}

    doc = fitz.open(str(pdf))
    try:
        fields = []
        if payload.get("auto_fill"):
            auto, auto_report = _auto_fields(doc, payload)
            fields.extend(auto)
        fields.extend(_manual_fields(payload))

        for idx, box in enumerate(fields):
            try:
                if box.page < 1 or box.page > len(doc):
                    skipped.append({"name":box.name,"reason":"page_out_of_range"}); continue
                page = doc[box.page-1]
                rect = fitz.Rect(box.x, box.y, box.x+box.w, box.y+box.h)
                mark = (box.mark or "text").lower()

                if mark == "signature" or box.signature:
                    _insert_signature(page, rect, sig_path, ink)
                    inserted.append({"name":box.name,"type":"signature","page":box.page,"x":round(box.x,2),"y":round(box.y,2)})
                elif mark == "x":
                    page.insert_image(rect, stream=_png(_x_mark(int(box.w), int(box.h), ink, idx)), overlay=True)
                    inserted.append({"name":box.name,"type":"x_mark","page":box.page,"x":round(box.x,2),"y":round(box.y,2)})
                elif mark == "square":
                    page.insert_image(rect, stream=_png(_square_mark(int(box.w), int(box.h), ink, idx)), overlay=True)
                    inserted.append({"name":box.name,"type":"square_mark","page":box.page,"x":round(box.x,2),"y":round(box.y,2)})
                else:
                    fs = _fit_size(box.text, int(box.w), int(box.h), box.font_size, box.max_lines)
                    img = _hand_text(box.text, int(box.w), int(box.h), fs, ink, seed=hash((buyer_rfq,box.name,idx))%999999, max_lines=box.max_lines)
                    page.insert_image(rect, stream=_png(img), overlay=True)
                    inserted.append({"name":box.name,"type":"handwritten_text","page":box.page,"x":round(box.x,2),"y":round(box.y,2),"text_preview":box.text[:80]})
            except Exception as e:
                skipped.append({"name":box.name,"reason":"field_failed","error":str(e)})

        doc.save(str(out_pdf), garbage=4, deflate=True, clean=True)
        return {
            "status":"ok","engine_version":ENGINE_VERSION,"buyer_rfq_number":buyer_rfq,
            "message":"Completed PDF using V21.2 SBD auto-fill decision engine. No typed PDF text insertion was used.",
            "input_pdf":str(pdf),"output_pdf":str(out_pdf),"auto_fill":bool(payload.get("auto_fill")),
            "auto_report":auto_report,"inserted_count":len(inserted),"skipped_count":len(skipped),
            "inserted":inserted,"skipped":skipped,"checked_at":_now()
        }
    finally:
        doc.close()


def detect_sbd_pages(input_pdf: str) -> Dict[str, Any]:
    err = _deps_error()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err}
    pdf = _resolve(input_pdf)
    if not pdf: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found."}
    doc = fitz.open(str(pdf))
    try:
        pages = []
        for i, page in enumerate(doc, start=1):
            typ = _detect_type(_page_text(page))
            if typ != "UNKNOWN":
                pages.append({"page":i,"sbd_type":typ,"text_preview":_clean(_page_text(page))[:160]})
        return {"status":"ok","engine_version":ENGINE_VERSION,"input_pdf":str(pdf),"page_count":len(doc),"detected_count":len(pages),"detected_pages":pages}
    finally:
        doc.close()


def locate_writable_fields(input_pdf: str, page_number: int = 1, limit: int = 30) -> Dict[str, Any]:
    err = _deps_error()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err}
    pdf = _resolve(input_pdf)
    if not pdf: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found."}
    doc = fitz.open(str(pdf))
    try:
        page = doc[page_number-1]
        return {"status":"ok","engine_version":ENGINE_VERSION,"input_pdf":str(pdf),"page_number":page_number,"sbd_type":_detect_type(_page_text(page)),"candidate_count":0,"candidates":[],"checked_at":_now()}
    finally:
        doc.close()


def get_tender_form_intelligence_status() -> Dict[str, Any]:
    return {
        "status":"ok","engine_version":ENGINE_VERSION,"mode":"sbd_autofill_decision_engine",
        "typed_pdf_text_disabled":True,"manual_coordinates_supported":True,"auto_fill_supported":True,
        "supported_forms":["SBD4","SBD6.1","SBD8","SBD9","RFQ supplier information"],
        "output_dir":str(OUTPUT_DIR),"debug_dir":str(DEBUG_DIR),"checked_at":_now()
    }


# compatibility aliases
def complete_form_with_tender_intelligence(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form(payload): return complete_tender_form_intelligence(payload)
def complete_form(payload): return complete_tender_form_intelligence(payload)
def complete_sbd_form(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form_from_payload(payload): return complete_tender_form_intelligence(payload)
def run_tender_form_intelligence(payload): return complete_tender_form_intelligence(payload)
