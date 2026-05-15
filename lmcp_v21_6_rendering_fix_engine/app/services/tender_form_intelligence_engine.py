
from __future__ import annotations

import io, re, uuid, random, math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

try:
    import fitz
except Exception:
    fitz = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except Exception:
    Image = ImageDraw = ImageFont = ImageFilter = ImageOps = None

ENGINE_VERSION = "V21.6_RENDERING_FIX_ENGINE"
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
ORDERED_GLYPHS = [c for r in ROWS for c in r]


@dataclass
class Field:
    page: int
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    name: str = ""
    size: int = 12
    mark: str = "text"
    lines: int = 1


def _now(): return datetime.now(timezone.utc).isoformat()
def _clean(v): return re.sub(r"\s+", " ", str(v or "").replace("\n", " ")).strip()
def _deps():
    if fitz is None: return "PyMuPDF is not installed. Install with: pip install pymupdf"
    if Image is None: return "Pillow is not installed. Install with: pip install pillow"
    return None
def _resolve(p):
    raw = str(p or "").strip()
    if not raw: return None
    for c in [Path(raw), PROJECT_ROOT / raw, PROJECT_ROOT / raw.lstrip("/"), Path.cwd() / raw]:
        try:
            if c.exists(): return c.resolve()
        except Exception:
            pass
    return None
def _ink(color="black"):
    return (4, 28, 140, 230) if "blue" in str(color).lower() else (2, 2, 2, 230)
def _png(img):
    b = io.BytesIO(); img.save(b, format="PNG"); return b.getvalue()
def _font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            if Path(p).exists(): return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _crop_alpha(img, pad=2):
    img = img.convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    if not bbox: return img
    x0, y0, x1, y1 = bbox
    return img.crop((max(0, x0-pad), max(0, y0-pad), min(img.width, x1+pad), min(img.height, y1+pad)))


def _to_alpha(src, ink=(2,2,2,255)):
    gray = ImageOps.autocontrast(ImageOps.grayscale(src.convert("RGB")))
    alpha = gray.point(lambda p: 255 if p < 165 else 0)
    out = Image.new("RGBA", gray.size, ink)
    out.putalpha(alpha)
    return out


def _row_boxes(alpha_img):
    a = alpha_img.getchannel("A"); w, h = a.size; pix = a.load()
    counts = [sum(1 for x in range(w) if pix[x, y] > 0) for y in range(h)]
    threshold = max(5, int(w * 0.002))
    bands, start, on = [], 0, False
    for y, c in enumerate(counts):
        if c > threshold and not on:
            start, on = y, True
        if (c <= threshold or y == h-1) and on:
            if y - start > 8: bands.append((start, y))
            on = False
    merged = []
    for b in bands:
        if not merged or b[0] - merged[-1][1] > 18:
            merged.append([b[0], b[1]])
        else:
            merged[-1][1] = b[1]
    rows = []
    for y0, y1 in merged:
        xs = [x for x in range(w) if any(pix[x, y] > 0 for y in range(max(0,y0-3), min(h,y1+4)))]
        if xs: rows.append((min(xs), max(0,y0-5), max(xs)+1, min(h,y1+5)))
    return rows


def _segment_row(alpha_img, row_box, expected):
    x0,y0,x1,y1 = row_box
    row = alpha_img.crop((x0,y0,x1,y1))
    a = row.getchannel("A"); w,h = a.size; pix = a.load()
    counts = [sum(1 for y in range(h) if pix[x,y] > 0) for x in range(w)]
    threshold = max(1, int(h*0.03))
    bands, start, on = [], 0, False
    for x,c in enumerate(counts):
        if c > threshold and not on:
            start,on = x,True
        if (c <= threshold or x == w-1) and on:
            if x-start > 3: bands.append((start,x))
            on=False
    merged=[]
    for b in bands:
        if not merged or b[0] - merged[-1][1] > 10:
            merged.append([b[0],b[1]])
        else:
            merged[-1][1] = b[1]
    bands = [(a0,b0) for a0,b0 in merged if b0-a0 > 4]
    if len(bands) == expected:
        return [(x0+a0,y0,x0+b0,y1) for a0,b0 in bands]
    # predictable slicing if detection is imperfect
    out=[]; cell = w / expected
    for i in range(expected):
        cx0, cx1 = int(i*cell), int((i+1)*cell)
        crop = row.crop((cx0,0,cx1,h))
        bb = crop.getchannel("A").getbbox()
        if bb:
            gx0,gy0,gx1,gy1 = bb
            out.append((x0+cx0+gx0, y0+gy0, x0+cx0+gx1, y0+gy1))
        else:
            out.append((x0+cx0,y0,x0+cx1,y1))
    return out


def _normalise_glyph(img, target_h=140, ink=(2,2,2,255)):
    img = _crop_alpha(img, 5)
    if img.width < 2 or img.height < 2: return img
    scale = target_h / img.height
    img = img.resize((max(3, int(img.width*scale)), target_h), Image.LANCZOS)
    alpha = img.getchannel("A").filter(ImageFilter.GaussianBlur(0.12))
    out = Image.new("RGBA", img.size, ink); out.putalpha(alpha)
    return _crop_alpha(out, 2)


def build_glyph_library(reference_image: str, force: bool = False) -> Dict[str, Any]:
    err = _deps()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err}
    ref = _resolve(reference_image)
    if not ref: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Reference handwriting image not found."}
    GLYPH_DIR.mkdir(parents=True, exist_ok=True)
    if force:
        for p in GLYPH_DIR.glob("*.png"): p.unlink(missing_ok=True)
        (GLYPH_DIR / "glyph_meta.txt").unlink(missing_ok=True)
    src = Image.open(ref).convert("RGB")
    if src.width > 1800:
        ratio = 1800 / src.width
        src = src.resize((1800, int(src.height*ratio)), Image.LANCZOS)
    alpha = _to_alpha(src)
    rows = _row_boxes(alpha)
    saved, diagnostics = [], []
    for i, chars in enumerate(ROWS):
        if i >= len(rows):
            diagnostics.append({"row":i+1,"error":"row_not_found","expected":"".join(chars)})
            continue
        cells = _segment_row(alpha, rows[i], len(chars))
        diagnostics.append({"row":i+1,"expected_count":len(chars),"detected_cells":len(cells),"chars":"".join(chars)})
        for ch, cell in zip(chars, cells):
            x0,y0,x1,y1 = cell
            glyph = _normalise_glyph(alpha.crop((x0,y0,x1,y1)))
            if glyph.width > 1 and glyph.height > 1:
                glyph.save(GLYPH_DIR / f"{ord(ch)}.png")
                saved.append(ch)
    (GLYPH_DIR / "glyph_meta.txt").write_text("".join(saved), encoding="utf-8")
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V21.6 glyph library built.","reference_image":str(ref),"glyph_dir":str(GLYPH_DIR),"expected_glyphs":len(ORDERED_GLYPHS),"saved_glyphs":len(saved),"saved_chars":"".join(saved),"rows_found":len(rows),"diagnostics":diagnostics,"checked_at":_now()}


def _load_glyph(ch, ink):
    p = GLYPH_DIR / f"{ord(ch)}.png"
    if not p.exists(): return None
    img = Image.open(p).convert("RGBA")
    a = img.getchannel("A")
    out = Image.new("RGBA", img.size, ink); out.putalpha(a)
    return _crop_alpha(out, 1)


def _fallback_char(ch, target_h, ink):
    W,H = max(10,int(target_h*.8)), max(14,int(target_h*1.1))
    img = Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img); f=_font(max(8,int(target_h*.72)))
    d.text((1,0), ch, font=f, fill=ink)
    return _crop_alpha(img,1)


def _prepare(ch, target_h, ink, seed):
    g = _load_glyph(ch, ink) or _fallback_char(ch, target_h, ink)
    if g.height:
        scale = target_h / g.height
        g = g.resize((max(3,int(g.width*scale)), max(5,int(g.height*scale))), Image.LANCZOS)
    random.seed(seed)
    # tiny rotation only
    return g.rotate(random.uniform(-0.45,0.45), expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))


def _measure_line(text, target_h, ink, seed=0):
    char_sp = max(1.0, target_h*.055); word_sp=max(3.0,target_h*.32)
    width, maxh = 0.0, 0
    for i,ch in enumerate(text):
        if ch == " ":
            width += word_sp; continue
        g = _prepare(ch, target_h, ink, seed+i)
        width += g.width + char_sp
        maxh = max(maxh, g.height)
    return width, maxh


def _split_lines(text, target_h, max_w, max_lines, ink, seed):
    text = _clean(text)
    if max_lines <= 1: return [text]
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if _measure_line(trial, target_h, ink, seed)[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = word
            if len(lines) >= max_lines-1: break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines or [""]


def _glyph_text(text, w, h, size, ink, seed=0, lines=1):
    text = _clean(text)
    W,H = int(max(8,w)), int(max(8,h))
    canvas = Image.new("RGBA",(W,H),(0,0,0,0))
    if not text: return canvas
    base_h = max(7, min(int(H*.58), int(size*1.22)))
    draw_lines = [text]; target_h = base_h
    for th in range(base_h, 6, -1):
        ls = _split_lines(text, th, W-6, lines, ink, seed)
        widest = max(_measure_line(l, th, ink, seed)[0] for l in ls)
        if widest <= W-4 and (len(ls)*th + (len(ls)-1)*2) <= H+2:
            target_h, draw_lines = th, ls
            break
    char_sp = max(1.0,target_h*.055); word_sp=max(3.0,target_h*.32)
    line_gap = max(2, int(target_h*.20))
    total_h = len(draw_lines)*target_h + (len(draw_lines)-1)*line_gap
    y_start = max(0, int((H-total_h)/2))
    for li,line in enumerate(draw_lines):
        x = 2
        baseline = y_start + li*(target_h+line_gap) + target_h
        for i,ch in enumerate(line):
            if ch == " ":
                x += word_sp; continue
            g = _prepare(ch, target_h, ink, seed + li*1000 + i)
            y = int(baseline - g.height)
            if x + g.width > W-1: break
            canvas.alpha_composite(g, (int(x), max(0,y)))
            x += g.width + char_sp
    return canvas.filter(ImageFilter.GaussianBlur(0.02))


def _xmark(w,h,ink,seed=0):
    scale=3; W,H=max(18,int(w)*scale),max(18,int(h)*scale)
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    pad=int(min(W,H)*.18); lw=max(2,int(min(W,H)*.06))
    d.line([(pad,pad),(W-pad,H-pad)], fill=ink, width=lw)
    d.line([(W-pad,pad),(pad,H-pad)], fill=ink, width=lw)
    img.thumbnail((int(w),int(h)), Image.LANCZOS)
    c=Image.new("RGBA",(int(w),int(h)),(0,0,0,0)); c.alpha_composite(img,((c.width-img.width)//2,(c.height-img.height)//2)); return c


def _square(w,h,ink,seed=0):
    scale=3; W,H=max(18,int(w)*scale),max(18,int(h)*scale)
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    pad=int(min(W,H)*.23); lw=max(2,int(min(W,H)*.055))
    d.line([(pad,pad),(W-pad,pad),(W-pad,H-pad),(pad,H-pad),(pad,pad)], fill=ink, width=lw)
    img.thumbnail((int(w),int(h)), Image.LANCZOS)
    c=Image.new("RGBA",(int(w),int(h)),(0,0,0,0)); c.alpha_composite(img,((c.width-img.width)//2,(c.height-img.height)//2)); return c


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
    }


def _f(page,x,y,w,h,text="",name="",size=12,mark="text",lines=1):
    return Field(page,x,y,w,h,text,name,size,mark,lines)


def _training_map(payload):
    d = _defaults(payload)
    fields = [
        _f(5,230,346,330,24,d["company_name"],"rfq_company",10),
        _f(5,230,371,330,24,d["address"],"rfq_postal",8),
        _f(5,230,396,330,24,d["address"],"rfq_street",8),
        _f(5,432,421,110,22,d["phone"],"rfq_phone",11),
        _f(5,250,446,180,22,d["phone"],"rfq_cell",11),
        _f(5,230,496,260,24,d["email"],"rfq_email",12),
        _f(5,254,543,75,42,d["tcs_pin"],"rfq_tcs",8,lines=2),
        _f(5,453,543,120,25,d["csd"],"rfq_csd",10),
        _f(8,514,418,18,18,name="sbd4_2_1_no",mark="square"),
        _f(8,514,499,18,18,name="sbd4_2_2_no",mark="square"),
        _f(8,466,600,18,18,name="sbd4_2_3_yes",mark="square"),
        _f(8,195,520,95,24,"N/A","sbd4_2_2_1_na",13),
        _f(8,190,622,390,40,d["other_enterprises"],"sbd4_2_3_1_details",8,lines=2),
        _f(10,88,640,155,45,name="sbd4_signature",mark="signature"),
        _f(10,360,663,150,24,d["date"],"sbd4_date",10),
        _f(10,88,720,170,24,d["designation"],"sbd4_position",11),
        _f(10,245,720,335,24,d["company_name"],"sbd4_bidder",8),
        _f(12,488,420,55,28,"20","sbd6_black_points",18),
        _f(12,488,455,55,28,"4","sbd6_local_points",18),
        _f(12,488,490,55,28,"0","sbd6_woman_points",18),
        _f(12,488,525,55,28,"0","sbd6_youth_points",18),
        _f(12,488,560,55,28,"0","sbd6_disability_points",18),
        _f(15,245,235,300,24,d["company_name"],"sbd6_company",8),
        _f(15,265,264,180,24,d["company_reg"],"sbd6_reg",10),
        _f(15,78,345,18,18,name="sbd6_pty_ltd_tick",mark="x"),
        _f(16,90,540,160,45,name="sbd6_signature",mark="signature"),
        _f(16,335,558,170,24,d["date"],"sbd6_date",10),
        _f(16,250,610,220,24,d["surname_name"],"sbd6_name",10),
        _f(16,250,640,285,55,d["address"],"sbd6_address",8,lines=2),
        _f(18,514,235,20,20,name="sbd8_4_1_no",mark="x"),
        _f(18,514,468,20,20,name="sbd8_4_2_no",mark="x"),
        _f(19,514,145,20,20,name="sbd8_4_3_no",mark="x"),
        _f(19,514,346,20,20,name="sbd8_4_4_no",mark="x"),
        _f(18,210,365,120,45,"N/A","sbd8_4_1_details",22),
        _f(19,210,164,120,45,"N/A","sbd8_4_3_details",22),
        _f(19,88,620,160,50,name="sbd8_signature",mark="signature"),
        _f(19,490,465,170,24,d["director_name"],"sbd8_name",9),
        _f(19,390,678,150,24,d["date"],"sbd8_date",10),
        _f(19,80,722,160,24,d["designation"],"sbd8_position",10),
        _f(19,245,722,330,24,d["company_name"],"sbd8_bidder",8),
        _f(21,115,408,360,24,d["company_name"],"sbd9_bidder_page21",8),
        _f(21,214,502,160,50,name="sbd9_signature_page21",mark="signature"),
        _f(23,100,389,160,50,name="sbd9_signature",mark="signature"),
        _f(23,428,447,150,24,d["date"],"sbd9_date",10),
        _f(23,92,510,160,24,d["designation"],"sbd9_position",10),
        _f(23,245,510,330,24,d["company_name"],"sbd9_bidder",8),
    ]
    return fields, {"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","mode":"v21_6_rendering_fix_training_map","field_count":len(fields)}


def _manual(payload):
    out=[]
    for i,it in enumerate(payload.get("fields") or []):
        if not isinstance(it, dict): continue
        text=_clean(it.get("text") or it.get("value") or "")
        mark=str(it.get("mark") or "").lower().strip()
        if not text and mark not in {"x","square","signature"} and not it.get("signature"): continue
        out.append(Field(int(it.get("page") or 1), float(it.get("x") or 0), float(it.get("y") or 0), float(it.get("w") or 260), float(it.get("h") or 28), text, str(it.get("name") or f"manual_{i+1}"), int(it.get("font_size") or it.get("size") or 12), mark or ("signature" if it.get("signature") else "text"), int(it.get("max_lines") or 1)))
    return out


def _insert_signature(page, rect, sig_path, ink):
    if sig_path and sig_path.exists():
        try:
            sig=Image.open(sig_path).convert("RGBA")
            data=[(255,255,255,0) if r>235 and g>235 and b>235 else (r,g,b,a) for r,g,b,a in sig.getdata()]
            sig.putdata(data); sig.thumbnail((int(rect.width),int(rect.height)), Image.LANCZOS)
            can=Image.new("RGBA",(int(rect.width),int(rect.height)),(0,0,0,0))
            can.alpha_composite(sig,((can.width-sig.width)//2,(can.height-sig.height)//2))
            page.insert_image(rect, stream=_png(can), overlay=True); return
        except Exception: pass
    page.insert_image(rect, stream=_png(_glyph_text("LM", rect.width, rect.height, 20, ink)), overlay=True)


def complete_tender_form_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    err=_deps()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err,"checked_at":_now()}
    payload = payload or {}
    ref = payload.get("glyph_reference_image") or payload.get("reference_image") or payload.get("handwriting_reference")
    glyph_build_result = build_glyph_library(ref, force=bool(payload.get("force_rebuild_glyphs"))) if ref else None
    pdf = _resolve(payload.get("input_pdf") or payload.get("pdf_path"))
    buyer = _clean(payload.get("buyer_rfq_number") or f"RFQ-{uuid.uuid4().hex[:8]}")
    if not pdf: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found","checked_at":_now()}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True); DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{re.sub(r'[^A-Za-z0-9_.-]+','-',buyer)}__v21_6_rendering_fix_completed.pdf"
    ink = _ink(payload.get("ink_color") or "black")
    sig = _resolve(payload.get("signature_image") or payload.get("signature_path"))
    doc = fitz.open(str(pdf)); inserted=[]; skipped=[]; report={}
    try:
        fields=[]
        if payload.get("training_map") or payload.get("auto_fill") or payload.get("use_glyph_handwriting"):
            fields, report = _training_map(payload)
        fields += _manual(payload)
        for idx, field in enumerate(fields):
            try:
                if field.page < 1 or field.page > len(doc):
                    skipped.append({"name":field.name,"reason":"page_out_of_range","page":field.page}); continue
                page = doc[field.page-1]
                rect = fitz.Rect(field.x, field.y, field.x+field.w, field.y+field.h)
                if field.mark == "signature":
                    _insert_signature(page, rect, sig, ink); typ="signature"
                elif field.mark == "x":
                    page.insert_image(rect, stream=_png(_xmark(field.w, field.h, ink, idx)), overlay=True); typ="x_mark"
                elif field.mark == "square":
                    page.insert_image(rect, stream=_png(_square(field.w, field.h, ink, idx)), overlay=True); typ="square_mark"
                else:
                    page.insert_image(rect, stream=_png(_glyph_text(field.text, field.w, field.h, field.size, ink, seed=hash((buyer,field.name,idx))%999999, lines=field.lines)), overlay=True); typ="rendering_fixed_handwriting"
                inserted.append({"name":field.name,"type":typ,"page":field.page,"x":field.x,"y":field.y,"text_preview":field.text[:80]})
            except Exception as e:
                skipped.append({"name":field.name,"reason":"field_failed","error":str(e)})
        doc.save(str(output), garbage=4, deflate=True, clean=True)
        return {"status":"ok","engine_version":ENGINE_VERSION,"buyer_rfq_number":buyer,"message":"Completed using V21.6 rendering fix engine. No typed PDF text insertion was used.","input_pdf":str(pdf),"output_pdf":str(output),"glyph_dir":str(GLYPH_DIR),"glyph_build_result":glyph_build_result,"training_map":bool(payload.get("training_map") or payload.get("auto_fill") or payload.get("use_glyph_handwriting")),"training_report":report,"inserted_count":len(inserted),"skipped_count":len(skipped),"inserted":inserted,"skipped":skipped,"checked_at":_now()}
    finally:
        doc.close()


def get_tender_form_intelligence_status():
    glyphs=list(GLYPH_DIR.glob("*.png")) if GLYPH_DIR.exists() else []
    return {"status":"ok","engine_version":ENGINE_VERSION,"mode":"rendering_fix_training_map","typed_pdf_text_disabled":True,"glyph_count":len(glyphs),"glyph_dir":str(GLYPH_DIR),"glyph_library_exists":GLYPH_DIR.exists(),"output_dir":str(OUTPUT_DIR),"debug_dir":str(DEBUG_DIR),"checked_at":_now()}


def detect_training_template(input_pdf: str):
    pdf=_resolve(input_pdf)
    return {"status":"ok" if pdf else "error","engine_version":ENGINE_VERSION,"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","matched":bool(pdf),"input_pdf":str(pdf) if pdf else None}
def detect_sbd_pages(input_pdf: str):
    pdf=_resolve(input_pdf)
    return {"status":"ok" if pdf else "error","engine_version":ENGINE_VERSION,"input_pdf":str(pdf) if pdf else None,"message":"V21.6 uses trained map."}
def locate_writable_fields(input_pdf: str, page_number: int=1, limit: int=30):
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V21.6 uses rendering-fixed training maps.","candidates":[]}

def complete_form_with_tender_intelligence(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form(payload): return complete_tender_form_intelligence(payload)
def complete_form(payload): return complete_tender_form_intelligence(payload)
def complete_sbd_form(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form_from_payload(payload): return complete_tender_form_intelligence(payload)
def run_tender_form_intelligence(payload): return complete_tender_form_intelligence(payload)
