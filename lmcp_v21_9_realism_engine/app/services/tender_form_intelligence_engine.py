
from __future__ import annotations
import io, re, uuid, random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

try:
    import fitz
except Exception:
    fitz = None
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
except Exception:
    Image = ImageDraw = ImageFont = ImageOps = ImageFilter = None

ENGINE_VERSION = "V21.9_REALISM_ENGINE"
PROJECT_ROOT = Path("/app") if Path("/app").exists() else Path.cwd()
OUTPUT_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "completed_forms"
DEBUG_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "debug"
GLYPH_DIR = PROJECT_ROOT / "runtime" / "handwriting_glyphs"
ROWS = [list("ABCDEFGHIJKLM"), list("NOPQRSTUVWXYZ"), list("1234567890"), list("abcdefghijklm"), list("nopqrstuvwxyz")]
ORDERED_GLYPHS = [c for r in ROWS for c in r]

@dataclass(frozen=True)
class Field:
    page:int; x:float; y:float; w:float; h:float
    text:str=""; name:str=""; size:int=12; mark:str="text"; align:str="left"; max_chars:int=0

def _now(): return datetime.now(timezone.utc).isoformat()
def _clean(v): return re.sub(r"\s+", " ", str(v or "").replace("\n"," ").replace("\r"," ")).strip()
def _safe_filename(v): return re.sub(r"[^A-Za-z0-9_.-]+","-",_clean(v))[:140] or f"RFQ-{uuid.uuid4().hex[:8]}"
def _deps():
    if fitz is None: return "PyMuPDF is not installed. Install with: pip install pymupdf"
    if Image is None: return "Pillow is not installed. Install with: pip install pillow"
    return None
def _resolve(p):
    raw=str(p or "").strip()
    if not raw: return None
    for c in [Path(raw), PROJECT_ROOT/raw, PROJECT_ROOT/raw.lstrip("/"), Path.cwd()/raw]:
        try:
            if c.exists(): return c.resolve()
        except Exception: pass
    return None
def _ink(color="black"):
    return (3,24,125,245) if "blue" in str(color).lower() else (0,0,0,245)
def _png(img):
    b=io.BytesIO(); img.save(b, format="PNG"); return b.getvalue()
def _font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            if Path(p).exists(): return ImageFont.truetype(p,size=size)
        except Exception: pass
    return ImageFont.load_default()

def _crop_alpha(img,pad=2):
    img=img.convert("RGBA"); bb=img.getchannel("A").getbbox()
    if not bb: return img
    x0,y0,x1,y1=bb
    return img.crop((max(0,x0-pad),max(0,y0-pad),min(img.width,x1+pad),min(img.height,y1+pad)))

def _to_alpha(src, ink=(0,0,0,255)):
    gray=ImageOps.autocontrast(ImageOps.grayscale(src.convert("RGB")))
    alpha=gray.point(lambda p:255 if p<170 else 0)
    out=Image.new("RGBA", gray.size, ink); out.putalpha(alpha); return out

def _row_boxes(alpha_img):
    a=alpha_img.getchannel("A"); w,h=a.size; pix=a.load()
    counts=[sum(1 for x in range(w) if pix[x,y]>0) for y in range(h)]
    th=max(5,int(w*.002)); bands=[]; start=0; on=False
    for y,c in enumerate(counts):
        if c>th and not on: start=y; on=True
        if (c<=th or y==h-1) and on:
            if y-start>8: bands.append((start,y))
            on=False
    merged=[]
    for b in bands:
        if not merged or b[0]-merged[-1][1]>18: merged.append([b[0],b[1]])
        else: merged[-1][1]=b[1]
    rows=[]
    for y0,y1 in merged:
        xs=[x for x in range(w) if any(pix[x,y]>0 for y in range(max(0,y0-3), min(h,y1+4)))]
        if xs: rows.append((min(xs), max(0,y0-5), max(xs)+1, min(h,y1+5)))
    return rows

def _segment_row(alpha_img,row_box,expected):
    x0,y0,x1,y1=row_box; row=alpha_img.crop((x0,y0,x1,y1))
    a=row.getchannel("A"); w,h=a.size; pix=a.load()
    counts=[sum(1 for y in range(h) if pix[x,y]>0) for x in range(w)]
    th=max(1,int(h*.03)); bands=[]; start=0; on=False
    for x,c in enumerate(counts):
        if c>th and not on: start=x; on=True
        if (c<=th or x==w-1) and on:
            if x-start>3: bands.append((start,x))
            on=False
    merged=[]
    for b in bands:
        if not merged or b[0]-merged[-1][1]>10: merged.append([b[0],b[1]])
        else: merged[-1][1]=b[1]
    bands=[(a0,b0) for a0,b0 in merged if b0-a0>4]
    if len(bands)==expected: return [(x0+a0,y0,x0+b0,y1) for a0,b0 in bands]
    cells=[]; cell=w/expected
    for i in range(expected):
        cx0,cx1=int(i*cell),int((i+1)*cell); crop=row.crop((cx0,0,cx1,h)); bb=crop.getchannel("A").getbbox()
        if bb:
            gx0,gy0,gx1,gy1=bb; cells.append((x0+cx0+gx0,y0+gy0,x0+cx0+gx1,y0+gy1))
        else: cells.append((x0+cx0,y0,x0+cx1,y1))
    return cells

def _normalise_glyph(img,target_h=150,ink=(0,0,0,255)):
    img=_crop_alpha(img,5)
    if img.width<2 or img.height<2: return img
    scale=target_h/float(img.height)
    img=img.resize((max(3,int(img.width*scale)),target_h), Image.LANCZOS)
    alpha=img.getchannel("A"); out=Image.new("RGBA", img.size, ink); out.putalpha(alpha)
    return _crop_alpha(out,2)

def build_glyph_library(reference_image, force=False):
    err=_deps()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err}
    ref=_resolve(reference_image)
    if not ref: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Reference handwriting image not found."}
    GLYPH_DIR.mkdir(parents=True, exist_ok=True)
    if force:
        for p in GLYPH_DIR.glob("*.png"): p.unlink(missing_ok=True)
        (GLYPH_DIR/"glyph_meta.txt").unlink(missing_ok=True)
    src=Image.open(ref).convert("RGB")
    if src.width>1800:
        ratio=1800/float(src.width); src=src.resize((1800,int(src.height*ratio)), Image.LANCZOS)
    alpha=_to_alpha(src); rows=_row_boxes(alpha); saved=[]; diagnostics=[]
    for ri,chars in enumerate(ROWS):
        if ri>=len(rows):
            diagnostics.append({"row":ri+1,"error":"row_not_found","expected":"".join(chars)}); continue
        cells=_segment_row(alpha,rows[ri],len(chars))
        diagnostics.append({"row":ri+1,"expected_count":len(chars),"detected_cells":len(cells),"chars":"".join(chars)})
        for ch,cell in zip(chars,cells):
            x0,y0,x1,y1=cell; glyph=_normalise_glyph(alpha.crop((x0,y0,x1,y1)))
            if glyph.width>1 and glyph.height>1:
                glyph.save(GLYPH_DIR/f"{ord(ch)}.png"); saved.append(ch)
    (GLYPH_DIR/"glyph_meta.txt").write_text("".join(saved), encoding="utf-8")
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V21.9 glyph library built.","reference_image":str(ref),"glyph_dir":str(GLYPH_DIR),"expected_glyphs":len(ORDERED_GLYPHS),"saved_glyphs":len(saved),"saved_chars":"".join(saved),"rows_found":len(rows),"diagnostics":diagnostics,"checked_at":_now()}

def _load_glyph(ch,ink):
    p=GLYPH_DIR/f"{ord(ch)}.png"
    if not p.exists(): return None
    img=Image.open(p).convert("RGBA"); a=img.getchannel("A")
    out=Image.new("RGBA", img.size, ink); out.putalpha(a); return _crop_alpha(out,1)

def _fallback_char(ch,target_h,ink):
    img=Image.new("RGBA",(max(10,int(target_h*.75)),max(14,int(target_h*1.05))),(0,0,0,0))
    d=ImageDraw.Draw(img); d.text((1,0), ch, font=_font(max(8,int(target_h*.70))), fill=ink)
    return _crop_alpha(img,1)

def _apply_realism(glyph,ink,seed):
    random.seed(seed); glyph=glyph.convert("RGBA"); alpha=glyph.getchannel("A")
    factor=random.uniform(.88,1.0); alpha=alpha.point(lambda p:max(0,min(255,int(p*factor))))
    if random.random()<.30: alpha=alpha.filter(ImageFilter.GaussianBlur(radius=.06))
    out=Image.new("RGBA", glyph.size, ink); out.putalpha(alpha); return out

def _prepare(ch,target_h,ink,seed):
    glyph=_load_glyph(ch,ink) or _fallback_char(ch,target_h,ink)
    if glyph.height:
        scale=target_h/float(glyph.height); glyph=glyph.resize((max(3,int(glyph.width*scale)),max(5,int(glyph.height*scale))), Image.LANCZOS)
    random.seed(seed); angle=random.uniform(-.35,.35)
    glyph=glyph.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))
    return _apply_realism(glyph,ink,seed)

def _measure(text,target_h,ink,seed=0):
    char_sp=max(.5,target_h*.04); word_sp=max(2.0,target_h*.24); width=0.0
    for i,ch in enumerate(text):
        if ch==" ": width+=word_sp; continue
        g=_prepare(ch,target_h,ink,seed+i); width+=g.width+char_sp
    return width

def _truncate_to_fit(text,target_h,max_w,ink,seed=0):
    text=_clean(text)
    if _measure(text,target_h,ink,seed)<=max_w: return text
    out=""
    for ch in text:
        if _measure(out+ch,target_h,ink,seed)>max_w: break
        out+=ch
    return out.rstrip()

def _glyph_text(text,w,h,size,ink,seed=0,align="left",max_chars=0):
    text=_clean(text)
    if max_chars and len(text)>max_chars: text=text[:max_chars].rstrip()
    W,H=int(max(8,w)),int(max(8,h)); canvas=Image.new("RGBA",(W,H),(0,0,0,0))
    if not text: return canvas
    target_h=max(6,min(int(H*.50),int(size*1.02)))
    for th in range(target_h,5,-1):
        if _measure(text,th,ink,seed)<=W-4: target_h=th; break
    text=_truncate_to_fit(text,target_h,W-4,ink,seed)
    line_w=_measure(text,target_h,ink,seed)
    x=max(1,int((W-line_w)/2)) if align=="center" else (max(1,int(W-line_w-2)) if align=="right" else 2)
    baseline=int(H*.68); char_sp=max(.5,target_h*.04); word_sp=max(2.0,target_h*.24)
    for i,ch in enumerate(text):
        if ch==" ":
            x+=word_sp*random.uniform(.92,1.10); continue
        glyph=_prepare(ch,target_h,ink,seed+i)
        y=max(0,int(baseline-glyph.height+random.uniform(-.55,.55)))
        if x+glyph.width>W-1: break
        canvas.alpha_composite(glyph,(int(x),y))
        x+=glyph.width+char_sp*random.uniform(.90,1.20)
    return canvas

def _xmark(w,h,ink,seed=0):
    random.seed(seed); scale=3; W,H=max(18,int(w)*scale),max(18,int(h)*scale)
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    pad=int(min(W,H)*.18); lw=max(2,int(min(W,H)*.055)); j=lambda:random.uniform(-1.5,1.5)
    d.line([(pad+j(),pad+j()),(W-pad+j(),H-pad+j())],fill=ink,width=lw)
    d.line([(W-pad+j(),pad+j()),(pad+j(),H-pad+j())],fill=ink,width=lw)
    img.thumbnail((int(w),int(h)), Image.LANCZOS)
    c=Image.new("RGBA",(int(w),int(h)),(0,0,0,0)); c.alpha_composite(img,(max(0,(c.width-img.width)//2),max(0,(c.height-img.height)//2))); return c

def _defaults(payload):
    return {
        "company_name": payload.get("company_name") or "LECHESA MANABA CONSULTING AND PROJECTS (PTY) LTD",
        "director_name": payload.get("director_name") or "LECHESA MANABA",
        "surname_name": payload.get("surname_and_name") or "MANABA, LECHESA",
        "designation": payload.get("designation") or "DIRECTOR",
        "date": payload.get("date") or payload.get("todays_date") or "27 APRIL 2026",
        "company_reg": payload.get("company_registration_number") or "2012/159509/07",
        "phone": payload.get("phone") or "0826338492",
        "email": payload.get("email") or "lechesam@me.com",
        "tcs_pin": payload.get("tcs_pin") or "2C151 C823M",
        "csd": payload.get("csd_number") or "MAAA0002664",
    }

def _f(page,x,y,w,h,text="",name="",size=12,mark="text",align="left",max_chars=0):
    return Field(int(page),float(x),float(y),float(w),float(h),_clean(text),str(name or ""),int(size),str(mark or "text"),str(align or "left"),int(max_chars or 0))

def _training_map(payload):
    d=_defaults(payload)
    fields=[
        _f(5,230,346,330,24,d["company_name"],"rfq_company",8,max_chars=42),
        _f(5,230,371,330,24,"1787 DUBE STREET, BATHO LOCATION","rfq_postal",8,max_chars=35),
        _f(5,230,396,330,24,"1787 DUBE STREET, BATHO LOCATION","rfq_street",8,max_chars=35),
        _f(5,432,421,110,22,d["phone"],"rfq_phone",10),
        _f(5,250,446,180,22,d["phone"],"rfq_cell",10),
        _f(5,230,496,260,24,d["email"],"rfq_email",10,max_chars=22),
        _f(5,254,543,75,34,d["tcs_pin"],"rfq_tcs",7,max_chars=10),
        _f(5,453,543,120,25,d["csd"],"rfq_csd",9,max_chars=12),
        _f(8,514,418,18,18,name="sbd4_2_1_no",mark="x"), _f(8,514,499,18,18,name="sbd4_2_2_no",mark="x"), _f(8,466,600,18,18,name="sbd4_2_3_yes",mark="x"),
        _f(8,195,520,95,24,"N/A","sbd4_2_2_1_na",12),
        _f(10,360,663,150,24,d["date"],"sbd4_date",9,max_chars=13), _f(10,88,720,170,24,d["designation"],"sbd4_position",9,max_chars=12), _f(10,245,720,335,24,d["company_name"],"sbd4_bidder",7,max_chars=42),
        _f(12,488,420,55,28,"20","sbd6_black_points",16,align="center"), _f(12,488,455,55,28,"4","sbd6_local_points",16,align="center"), _f(12,488,490,55,28,"0","sbd6_woman_points",16,align="center"), _f(12,488,525,55,28,"0","sbd6_youth_points",16,align="center"), _f(12,488,560,55,28,"0","sbd6_disability_points",16,align="center"),
        _f(15,245,235,300,24,d["company_name"],"sbd6_company",7,max_chars=42), _f(15,265,264,180,24,d["company_reg"],"sbd6_reg",9,max_chars=14), _f(15,78,345,18,18,name="sbd6_pty_ltd_tick",mark="x"),
        _f(16,335,558,170,24,d["date"],"sbd6_date",9,max_chars=13), _f(16,250,610,220,24,d["surname_name"],"sbd6_name",9,max_chars=18), _f(16,250,640,285,24,"1787 DUBE STREET","sbd6_address_1",8,max_chars=20), _f(16,250,666,285,24,"BATHO LOCATION","sbd6_address_2",8,max_chars=20), _f(16,250,692,285,24,"BLOEMFONTEIN, 9323","sbd6_address_3",8,max_chars=22),
        _f(18,514,235,20,20,name="sbd8_4_1_no",mark="x"), _f(18,514,468,20,20,name="sbd8_4_2_no",mark="x"), _f(19,514,145,20,20,name="sbd8_4_3_no",mark="x"), _f(19,514,346,20,20,name="sbd8_4_4_no",mark="x"),
        _f(18,210,365,120,45,"N/A","sbd8_4_1_details",18,align="center"), _f(19,210,164,120,45,"N/A","sbd8_4_3_details",18,align="center"),
        _f(19,490,465,170,24,d["director_name"],"sbd8_name",8,max_chars=16), _f(19,390,678,150,24,d["date"],"sbd8_date",9,max_chars=13), _f(19,80,722,160,24,d["designation"],"sbd8_position",9,max_chars=12), _f(19,245,722,330,24,d["company_name"],"sbd8_bidder",7,max_chars=42),
        _f(21,115,408,360,24,d["company_name"],"sbd9_bidder_page21",7,max_chars=42), _f(23,428,447,150,24,d["date"],"sbd9_date",9,max_chars=13), _f(23,92,510,160,24,d["designation"],"sbd9_position",9,max_chars=12), _f(23,245,510,330,24,d["company_name"],"sbd9_bidder",7,max_chars=42),
    ]
    return fields, {"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","mode":"v21_9_realism_training_map","field_count":len(fields),"long_overlay_suppression":True,"realism_layer":True}

def _manual(payload):
    out=[]
    for i,item in enumerate(payload.get("fields") or []):
        if not isinstance(item,dict): continue
        text=_clean(item.get("text") or item.get("value") or ""); mark=str(item.get("mark") or "").lower().strip()
        if not text and mark!="x": continue
        out.append(_f(item.get("page") or 1,item.get("x") or 0,item.get("y") or 0,item.get("w") or 260,item.get("h") or 28,text,item.get("name") or f"manual_{i+1}",item.get("font_size") or item.get("size") or 12,mark or "text",item.get("align") or "left",item.get("max_chars") or 0))
    return out

def complete_tender_form_intelligence(payload):
    err=_deps()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err,"checked_at":_now()}
    payload=payload or {}; ref=payload.get("glyph_reference_image") or payload.get("reference_image") or payload.get("handwriting_reference")
    glyph_build_result=build_glyph_library(ref, force=bool(payload.get("force_rebuild_glyphs"))) if ref else None
    pdf=_resolve(payload.get("input_pdf") or payload.get("pdf_path")); buyer=_clean(payload.get("buyer_rfq_number") or f"RFQ-{uuid.uuid4().hex[:8]}")
    if not pdf: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found","checked_at":_now()}
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True); DEBUG_DIR.mkdir(parents=True,exist_ok=True)
    output=OUTPUT_DIR/f"{_safe_filename(buyer)}__v21_9_realism_completed.pdf"; ink=_ink(payload.get("ink_color") or "black")
    doc=fitz.open(str(pdf)); inserted=[]; skipped=[]; report={}; rendered=set()
    try:
        fields=[]
        if payload.get("training_map") or payload.get("auto_fill") or payload.get("use_glyph_handwriting"):
            fields,report=_training_map(payload)
        fields += _manual(payload)
        for index,field in enumerate(fields):
            key=(field.page,field.name)
            if key in rendered:
                skipped.append({"name":field.name,"page":field.page,"reason":"duplicate_render_suppressed"}); continue
            rendered.add(key)
            try:
                if field.page<1 or field.page>len(doc):
                    skipped.append({"name":field.name,"page":field.page,"reason":"page_out_of_range"}); continue
                page=doc[field.page-1]; rect=fitz.Rect(field.x,field.y,field.x+field.w,field.y+field.h)
                if field.mark=="x":
                    overlay=_xmark(field.w,field.h,ink,index); typ="realistic_x_mark"
                else:
                    overlay=_glyph_text(field.text,field.w,field.h,field.size,ink,seed=abs(hash((buyer,field.name,index)))%999999,align=field.align,max_chars=field.max_chars); typ="realistic_handwriting"
                page.insert_image(rect,stream=_png(overlay),overlay=True)
                inserted.append({"name":field.name,"type":typ,"page":field.page,"x":field.x,"y":field.y,"w":field.w,"h":field.h,"text_preview":field.text[:80]})
            except Exception as exc:
                skipped.append({"name":field.name,"page":field.page,"reason":"field_failed","error":str(exc)})
        doc.save(str(output),garbage=4,deflate=True,clean=True)
        return {"status":"ok","engine_version":ENGINE_VERSION,"buyer_rfq_number":buyer,"message":"Completed using V21.9 realism engine. No typed PDF text insertion was used.","input_pdf":str(pdf),"output_pdf":str(output),"glyph_dir":str(GLYPH_DIR),"glyph_build_result":glyph_build_result,"training_map":bool(payload.get("training_map") or payload.get("auto_fill") or payload.get("use_glyph_handwriting")),"training_report":report,"inserted_count":len(inserted),"skipped_count":len(skipped),"inserted":inserted,"skipped":skipped,"checked_at":_now()}
    finally: doc.close()

def get_tender_form_intelligence_status():
    glyphs=list(GLYPH_DIR.glob("*.png")) if GLYPH_DIR.exists() else []
    return {"status":"ok","engine_version":ENGINE_VERSION,"mode":"realism_layer_single_pass","typed_pdf_text_disabled":True,"single_pass_rendering":True,"ghost_suppression":True,"long_overlay_suppression":True,"realism_layer":True,"glyph_count":len(glyphs),"glyph_dir":str(GLYPH_DIR),"glyph_library_exists":GLYPH_DIR.exists(),"output_dir":str(OUTPUT_DIR),"debug_dir":str(DEBUG_DIR),"checked_at":_now()}

def detect_training_template(input_pdf): 
    pdf=_resolve(input_pdf); return {"status":"ok" if pdf else "error","engine_version":ENGINE_VERSION,"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","matched":bool(pdf),"input_pdf":str(pdf) if pdf else None}
def detect_sbd_pages(input_pdf):
    pdf=_resolve(input_pdf); return {"status":"ok" if pdf else "error","engine_version":ENGINE_VERSION,"input_pdf":str(pdf) if pdf else None,"message":"V21.9 uses realism trained map."}
def locate_writable_fields(input_pdf,page_number=1,limit=30):
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V21.9 uses realism trained map; locator disabled for known template.","candidates":[]}

def complete_form_with_tender_intelligence(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form(payload): return complete_tender_form_intelligence(payload)
def complete_form(payload): return complete_tender_form_intelligence(payload)
def complete_sbd_form(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form_from_payload(payload): return complete_tender_form_intelligence(payload)
def run_tender_form_intelligence(payload): return complete_tender_form_intelligence(payload)
