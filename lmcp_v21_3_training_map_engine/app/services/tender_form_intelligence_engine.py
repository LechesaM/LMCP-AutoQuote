
"""
LMCP AutoQuote System
V21.3 Training-Map Engine

Drop-in target:
    app/services/tender_form_intelligence_engine.py

Purpose:
- Stop weak guessing.
- Use trained page maps for the known RFQ_Corporate_Gift_Packs.pdf / iSimangaliso SBD pack.
- Fill exactly according to the training screenshots:
  - RFQ supplier information
  - SBD4
  - SBD6.1
  - SBD8
  - SBD9
- Keep handwriting as image overlays only.
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
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except Exception:
    Image = ImageDraw = ImageFont = ImageFilter = None


ENGINE_VERSION = "V21.3_TRAINING_MAP_ENGINE"
PROJECT_ROOT = Path("/app") if Path("/app").exists() else Path.cwd()
OUTPUT_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "completed_forms"
DEBUG_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "debug"

FONTS = [
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


@dataclass
class Field:
    page: int
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    name: str = ""
    size: int = 13
    mark: str = "text"   # text, x, square, signature
    lines: int = 1


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ").replace("\r", " ")).strip()


def _norm(v):
    return re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()


def _resolve(p):
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


def _deps():
    if fitz is None:
        return "PyMuPDF is not installed. Install with: pip install pymupdf"
    if Image is None:
        return "Pillow is not installed. Install with: pip install pillow"
    return None


def _font(size):
    for p in FONTS:
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("DejaVuSans-Oblique.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def _ink(color="black"):
    if "blue" in str(color).lower():
        return (4, 28, 140, 255)
    return (1, 1, 1, 255)


def _measure(draw, text, font):
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return max(1, b[2] - b[0]), max(1, b[3] - b[1])
    except Exception:
        return draw.textsize(text, font=font)


def _wrap(text, font, width, max_lines):
    words = _clean(text).split()
    if not words:
        return [""]
    probe = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(probe)
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        tw, _ = _measure(d, trial, font)
        if tw <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines] or [""]


def _hand(text, w, h, size, ink, seed=0, lines=1):
    random.seed(seed)
    scale = 3
    W, H = max(20, int(w) * scale), max(16, int(h) * scale)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _font(max(8, int(size) * scale))
    wrapped = _wrap(text, f, max(10, W - 14), lines)
    y = max(2, int(H * 0.05))
    lh = max((size + 7) * scale, int(H / max(1, len(wrapped))))
    for line in wrapped:
        x = 6 + random.uniform(-2, 2)
        wave = random.random() * 6.28
        for i, ch in enumerate(line):
            cw, _ = _measure(d, ch, f)
            jx = random.uniform(-0.6, 0.75) * scale
            jy = (math.sin(i * 0.7 + wave) * 0.6 + random.uniform(-0.4, 0.4)) * scale
            d.text((x + jx, y + jy), ch, font=f, fill=ink)
            if ch != " " and random.random() < 0.75:
                d.text((x + jx + random.uniform(-.35,.35), y + jy + random.uniform(-.35,.35)), ch, font=f, fill=(ink[0], ink[1], ink[2], 70))
            x += cw + random.uniform(-0.1, 0.85) * scale + (random.uniform(0.5, 2.1) * scale if ch == " " else 0)
            if x > W - 8:
                break
        y += lh
    img = img.filter(ImageFilter.GaussianBlur(radius=0.18))
    img = img.rotate(random.uniform(-0.18, 0.18), expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))
    img.thumbnail((int(w), int(h)), Image.LANCZOS)
    canvas = Image.new("RGBA", (int(w), int(h)), (0,0,0,0))
    canvas.alpha_composite(img, (max(0,(canvas.width-img.width)//2), max(0,(canvas.height-img.height)//2)))
    return canvas


def _x(w, h, ink, seed=0):
    random.seed(seed)
    scale = 3
    W, H = max(18, int(w)*scale), max(18, int(h)*scale)
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    pad = int(min(W,H)*0.18)
    lw = max(2, int(min(W,H)*0.06))
    d.line([(pad+random.uniform(-2,2),pad),(W-pad,H-pad+random.uniform(-2,2))], fill=ink, width=lw)
    d.line([(W-pad,pad+random.uniform(-2,2)),(pad,H-pad)], fill=ink, width=lw)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.22))
    img.thumbnail((int(w), int(h)), Image.LANCZOS)
    c = Image.new("RGBA", (int(w), int(h)), (0,0,0,0))
    c.alpha_composite(img, (max(0,(c.width-img.width)//2), max(0,(c.height-img.height)//2)))
    return c


def _square(w, h, ink, seed=0):
    random.seed(seed)
    scale = 3
    W, H = max(18, int(w)*scale), max(18, int(h)*scale)
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    pad = int(min(W,H)*0.23)
    lw = max(2, int(min(W,H)*0.055))
    pts = [(pad,pad),(W-pad,pad+random.uniform(-1,1)),(W-pad,H-pad),(pad,H-pad+random.uniform(-1,1)),(pad,pad)]
    d.line(pts, fill=ink, width=lw)
    img.thumbnail((int(w), int(h)), Image.LANCZOS)
    c = Image.new("RGBA", (int(w), int(h)), (0,0,0,0))
    c.alpha_composite(img, (max(0,(c.width-img.width)//2), max(0,(c.height-img.height)//2)))
    return c


def _png(img):
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def _page_text(page):
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""


def detect_training_template(input_pdf: str) -> Dict[str, Any]:
    err = _deps()
    if err:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": err}
    pdf = _resolve(input_pdf)
    if not pdf:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "Input PDF not found"}
    doc = fitz.open(str(pdf))
    try:
        all_text = " ".join(_page_text(p)[:1000] for p in doc[:min(len(doc), 12)])
        n = _norm(all_text)
        matched = "isimangaliso" in n and "corporate gift" in n
        return {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "input_pdf": str(pdf),
            "page_count": len(doc),
            "template": "ISIMANGALISO_CORPORATE_GIFT_PACKS" if matched else "UNKNOWN",
            "matched": matched,
            "checked_at": _now(),
        }
    finally:
        doc.close()


def detect_sbd_pages(input_pdf: str) -> Dict[str, Any]:
    err = _deps()
    if err:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": err}
    pdf = _resolve(input_pdf)
    if not pdf:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "Input PDF not found"}
    doc = fitz.open(str(pdf))
    pages = []
    try:
        for i, p in enumerate(doc, 1):
            n = _norm(_page_text(p))
            typ = "UNKNOWN"
            if "bidder s disclosure" in n or "sbd4" in n:
                typ = "SBD4"
            elif "sbd 6 1" in n or "preference points claim form" in n:
                typ = "SBD6_1"
            elif "sbd 8" in n or "past supply chain management practices" in n:
                typ = "SBD8"
            elif "sbd 9" in n or "certificate of independent bid determination" in n:
                typ = "SBD9"
            elif "supplier information" in n:
                typ = "RFQ_SUPPLIER_INFO"
            if typ != "UNKNOWN":
                pages.append({"page": i, "sbd_type": typ, "text_preview": _clean(_page_text(p))[:160]})
        return {"status":"ok","engine_version":ENGINE_VERSION,"input_pdf":str(pdf),"page_count":len(doc),"detected_count":len(pages),"detected_pages":pages}
    finally:
        doc.close()


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


def _f(page,x,y,w,h,text="",name="",size=13,mark="text",lines=1):
    return Field(page=page,x=x,y=y,w=w,h=h,text=text,name=name,size=size,mark=mark,lines=lines)


def _training_map(payload) -> Tuple[List[Field], Dict[str, Any]]:
    d = _defaults(payload)
    fields = []

    # PAGE 5: RFQ supplier information table
    fields += [
        _f(5,230,372,305,21,d["company_name"],"rfq_company",10),
        _f(5,230,391,305,21,d["address"],"rfq_postal",9),
        _f(5,230,410,305,21,d["address"],"rfq_street",9),
        _f(5,432,428,96,21,d["phone"],"rfq_phone",13),
        _f(5,250,447,180,21,d["phone"],"rfq_cell",13),
        _f(5,230,486,260,21,d["email"],"rfq_email",14),
        _f(5,254,526,75,42,d["tcs_pin"],"rfq_tcs",10,lines=2),
        _f(5,453,532,105,25,d["csd"],"rfq_csd",12),
    ]

    # PAGE 8: SBD4 disclosure page. Coordinates tuned for RFQ_Corporate_Gift_Packs.
    fields += [
        _f(8,514,418,18,18,name="sbd4_2_1_no",mark="square"),
        _f(8,514,499,18,18,name="sbd4_2_2_no",mark="square"),
        _f(8,466,600,18,18,name="sbd4_2_3_yes",mark="square"),
        _f(8,195,520,95,24,"N/A","sbd4_2_2_1_na",14),
        _f(8,190,622,390,40,d["other_enterprises"],"sbd4_2_3_1_details",9,lines=2),
    ]

    # PAGE 9 / 10 possible continuation signature area for SBD4. Conservative training-map entries.
    fields += [
        _f(10,88,640,155,45,name="sbd4_signature",mark="signature"),
        _f(10,360,663,150,24,d["date"],"sbd4_date",12),
        _f(10,88,720,170,24,d["designation"],"sbd4_position",12),
        _f(10,245,720,335,24,d["company_name"],"sbd4_bidder",9),
    ]

    # PAGE 12+: SBD6.1 points/declaration. First map known RFQ pack page 12 and later signature pages.
    fields += [
        _f(12,488,420,55,28,"20","sbd6_black_points",20),
        _f(12,488,455,55,28,"4","sbd6_local_points",20),
        _f(12,488,490,55,28,"0","sbd6_woman_points",20),
        _f(12,488,525,55,28,"0","sbd6_youth_points",20),
        _f(12,488,560,55,28,"0","sbd6_disability_points",20),
        _f(15,245,235,300,24,d["company_name"],"sbd6_company",10),
        _f(15,265,264,180,24,d["company_reg"],"sbd6_reg",13),
        _f(15,78,345,18,18,name="sbd6_pty_ltd_tick",mark="x"),
        _f(16,90,540,160,45,name="sbd6_signature",mark="signature"),
        _f(16,335,558,170,24,d["date"],"sbd6_date",12),
        _f(16,250,610,220,24,d["surname_name"],"sbd6_name",12),
        _f(16,250,640,285,55,d["address"],"sbd6_address",10,lines=2),
    ]

    # PAGE 18/19: SBD8 declaration.
    fields += [
        _f(18,514,235,20,20,name="sbd8_4_1_no",mark="x"),
        _f(18,514,468,20,20,name="sbd8_4_2_no",mark="x"),
        _f(19,514,145,20,20,name="sbd8_4_3_no",mark="x"),
        _f(19,514,346,20,20,name="sbd8_4_4_no",mark="x"),
        _f(18,210,365,120,45,"N/A","sbd8_4_1_details",28),
        _f(19,210,164,120,45,"N/A","sbd8_4_3_details",28),
        _f(19,88,620,160,50,name="sbd8_signature",mark="signature"),
        _f(19,490,465,170,24,d["director_name"],"sbd8_name",12),
        _f(19,390,678,150,24,d["date"],"sbd8_date",12),
        _f(19,80,722,160,24,d["designation"],"sbd8_position",12),
        _f(19,245,722,330,24,d["company_name"],"sbd8_bidder",9),
    ]

    # PAGE 21/23: SBD9 certification/signature.
    fields += [
        _f(21,115,408,360,24,d["company_name"],"sbd9_bidder_page21",9),
        _f(21,214,502,160,50,name="sbd9_signature_page21",mark="signature"),
        _f(23,100,389,160,50,name="sbd9_signature",mark="signature"),
        _f(23,428,447,150,24,d["date"],"sbd9_date",12),
        _f(23,92,510,160,24,d["designation"],"sbd9_position",12),
        _f(23,245,510,330,24,d["company_name"],"sbd9_bidder",9),
    ]

    report = {
        "template": "ISIMANGALISO_CORPORATE_GIFT_PACKS",
        "training_map_field_count": len(fields),
        "mode": "fixed_training_coordinates",
        "note": "Uses the screenshots/trained RFQ pack layout instead of weak phrase guessing."
    }
    return fields, report


def _manual(payload):
    out=[]
    for i,it in enumerate(payload.get("fields") or []):
        if not isinstance(it, dict): continue
        text=_clean(it.get("text") or it.get("value") or "")
        mark=str(it.get("mark") or "").lower().strip()
        if not text and mark not in {"x","square","signature"} and not it.get("signature"): continue
        out.append(Field(
            page=int(it.get("page") or 1), x=float(it.get("x") or 0), y=float(it.get("y") or 0),
            w=float(it.get("w") or 260), h=float(it.get("h") or 28), text=text,
            name=str(it.get("name") or f"manual_{i+1}"), size=int(it.get("font_size") or it.get("size") or 13),
            mark=mark or ("signature" if it.get("signature") else "text"), lines=int(it.get("max_lines") or 1)
        ))
    return out


def _insert_signature(page, rect, sig_path, ink):
    if sig_path and sig_path.exists():
        try:
            sig = Image.open(sig_path).convert("RGBA")
            data=[]
            for r,g,b,a in sig.getdata():
                data.append((255,255,255,0) if r>235 and g>235 and b>235 else (r,g,b,a))
            sig.putdata(data)
            sig.thumbnail((int(rect.width), int(rect.height)), Image.LANCZOS)
            can=Image.new("RGBA",(int(rect.width),int(rect.height)),(0,0,0,0))
            can.alpha_composite(sig,(max(0,(can.width-sig.width)//2),max(0,(can.height-sig.height)//2)))
            page.insert_image(rect, stream=_png(can), overlay=True)
            return
        except Exception:
            pass
    page.insert_image(rect, stream=_png(_hand("LM", int(rect.width), int(rect.height), 24, ink, seed=99)), overlay=True)


def complete_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    err=_deps()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err,"checked_at":_now()}

    payload=payload or {}
    pdf=_resolve(payload.get("input_pdf") or payload.get("pdf_path"))
    buyer=_clean(payload.get("buyer_rfq_number") or f"RFQ-{uuid.uuid4().hex[:8]}")
    if not pdf: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found","checked_at":_now()}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True); DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    output=OUTPUT_DIR / f"{re.sub(r'[^A-Za-z0-9_.-]+','-',buyer)}__v21_3_training_map_completed.pdf"
    ink=_ink(payload.get("ink_color") or "black")
    sig=_resolve(payload.get("signature_image") or payload.get("signature_path"))

    doc=fitz.open(str(pdf))
    inserted=[]; skipped=[]; report={}
    try:
        fields=[]
        if payload.get("training_map") or payload.get("auto_fill"):
            fields, report = _training_map(payload)
        fields += _manual(payload)

        for idx, field in enumerate(fields):
            try:
                if field.page < 1 or field.page > len(doc):
                    skipped.append({"name":field.name,"reason":"page_out_of_range","page":field.page}); continue
                page=doc[field.page-1]
                rect=fitz.Rect(field.x,field.y,field.x+field.w,field.y+field.h)
                if field.mark=="signature":
                    _insert_signature(page, rect, sig, ink)
                    typ="signature"
                elif field.mark=="x":
                    page.insert_image(rect, stream=_png(_x(field.w, field.h, ink, idx)), overlay=True)
                    typ="x_mark"
                elif field.mark=="square":
                    page.insert_image(rect, stream=_png(_square(field.w, field.h, ink, idx)), overlay=True)
                    typ="square_mark"
                else:
                    page.insert_image(rect, stream=_png(_hand(field.text, int(field.w), int(field.h), field.size, ink, seed=hash((buyer,field.name,idx))%999999, lines=field.lines)), overlay=True)
                    typ="handwritten_text"
                inserted.append({"name":field.name,"type":typ,"page":field.page,"x":field.x,"y":field.y,"text_preview":field.text[:80]})
            except Exception as e:
                skipped.append({"name":field.name,"reason":"field_failed","error":str(e)})

        doc.save(str(output), garbage=4, deflate=True, clean=True)
        return {
            "status":"ok","engine_version":ENGINE_VERSION,"buyer_rfq_number":buyer,
            "message":"Completed using V21.3 training-map engine. No typed PDF text insertion was used.",
            "input_pdf":str(pdf),"output_pdf":str(output),"training_map": bool(payload.get("training_map") or payload.get("auto_fill")),
            "training_report":report,"inserted_count":len(inserted),"skipped_count":len(skipped),
            "inserted":inserted,"skipped":skipped,"checked_at":_now()
        }
    finally:
        doc.close()


def locate_writable_fields(input_pdf: str, page_number: int = 1, limit: int = 30):
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V21.3 uses training maps; locator not used for trained template.","page_number":page_number,"candidates":[]}


def get_tender_form_intelligence_status():
    return {
        "status":"ok","engine_version":ENGINE_VERSION,"mode":"training_map_engine",
        "typed_pdf_text_disabled":True,"training_map_supported":True,
        "supported_template":"ISIMANGALISO_CORPORATE_GIFT_PACKS",
        "supported_forms":["RFQ supplier information","SBD4","SBD6.1","SBD8","SBD9"],
        "output_dir":str(OUTPUT_DIR),"debug_dir":str(DEBUG_DIR),"checked_at":_now()
    }


# compatibility aliases
def complete_form_with_tender_intelligence(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form(payload): return complete_tender_form_intelligence(payload)
def complete_form(payload): return complete_tender_form_intelligence(payload)
def complete_sbd_form(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form_from_payload(payload): return complete_tender_form_intelligence(payload)
def run_tender_form_intelligence(payload): return complete_tender_form_intelligence(payload)
