
from __future__ import annotations
import io, re, uuid, random, math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List

try:
    import fitz
except Exception:
    fitz = None
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
except Exception:
    Image = ImageDraw = ImageFont = ImageOps = ImageFilter = None

ENGINE_VERSION = "V22.1_BASELINE_LOCK_ENGINE"
PROJECT_ROOT = Path("/app") if Path("/app").exists() else Path.cwd()
OUTPUT_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "completed_forms"
DEBUG_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence" / "debug"
GLYPH_DIR = PROJECT_ROOT / "runtime" / "handwriting_glyphs"
ROWS = [list("ABCDEFGHIJKLM"), list("NOPQRSTUVWXYZ"), list("1234567890"), list("abcdefghijklm"), list("nopqrstuvwxyz")]
ORDERED_GLYPHS = [c for r in ROWS for c in r]

@dataclass(frozen=True)
class Field:
    page:int; x:float; y:float; w:float; h:float
    text:str=""; name:str=""; size:int=12; mark:str="text"; align:str="left"; max_chars:int=0; baseline:float=.76

def _now(): return datetime.now(timezone.utc).isoformat()
def _clean(v): return re.sub(r"\s+", " ", str(v or "").replace("\n"," ").replace("\r"," ")).strip()
def _safe(v): return re.sub(r"[^A-Za-z0-9_.-]+","-",_clean(v))[:140] or f"RFQ-{uuid.uuid4().hex[:8]}"
def _deps():
    if fitz is None: return "PyMuPDF missing. Install: pip install pymupdf"
    if Image is None: return "Pillow missing. Install: pip install pillow"
    return None
def _resolve(p):
    raw=str(p or "").strip()
    if not raw: return None
    for c in [Path(raw), PROJECT_ROOT/raw, PROJECT_ROOT/raw.lstrip("/"), Path.cwd()/raw]:
        try:
            if c.exists(): return c.resolve()
        except Exception: pass
    return None
def _ink(c="black"): return (3,24,125,248) if "blue" in str(c).lower() else (0,0,0,248)
def _png(img):
    b=io.BytesIO(); img.save(b,format="PNG"); return b.getvalue()
def _font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            if Path(p).exists(): return ImageFont.truetype(p,size=size)
        except Exception: pass
    return ImageFont.load_default()

def _crop(img,pad=2):
    img=img.convert("RGBA"); bb=img.getchannel("A").getbbox()
    if not bb: return img
    x0,y0,x1,y1=bb
    return img.crop((max(0,x0-pad),max(0,y0-pad),min(img.width,x1+pad),min(img.height,y1+pad)))

def _to_alpha(src, ink=(0,0,0,255)):
    gray=ImageOps.autocontrast(ImageOps.grayscale(src.convert("RGB")))
    a=gray.point(lambda p:255 if p<170 else 0)
    out=Image.new("RGBA",gray.size,ink); out.putalpha(a); return out

def _row_boxes(alpha):
    a=alpha.getchannel("A"); w,h=a.size; pix=a.load()
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
        xs=[x for x in range(w) if any(pix[x,y]>0 for y in range(max(0,y0-3),min(h,y1+4)))]
        if xs: rows.append((min(xs),max(0,y0-5),max(xs)+1,min(h,y1+5)))
    return rows

def _segment(alpha,row_box,expected):
    x0,y0,x1,y1=row_box; row=alpha.crop((x0,y0,x1,y1))
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

def _norm(img,target_h=150,ink=(0,0,0,255)):
    img=_crop(img,5)
    if img.width<2 or img.height<2: return img
    sc=target_h/float(img.height)
    img=img.resize((max(3,int(img.width*sc)),target_h),Image.LANCZOS)
    out=Image.new("RGBA",img.size,ink); out.putalpha(img.getchannel("A"))
    return _crop(out,2)

def build_glyph_library(reference_image, force=False):
    err=_deps()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err}
    ref=_resolve(reference_image)
    if not ref: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Reference handwriting image not found."}
    GLYPH_DIR.mkdir(parents=True,exist_ok=True)
    if force:
        for p in GLYPH_DIR.glob("*.png"): p.unlink(missing_ok=True)
        (GLYPH_DIR/"glyph_meta.txt").unlink(missing_ok=True)
    src=Image.open(ref).convert("RGB")
    if src.width>1800:
        r=1800/float(src.width); src=src.resize((1800,int(src.height*r)),Image.LANCZOS)
    alpha=_to_alpha(src); rows=_row_boxes(alpha); saved=[]; diagnostics=[]
    for ri,chars in enumerate(ROWS):
        if ri>=len(rows):
            diagnostics.append({"row":ri+1,"error":"row_not_found","expected":"".join(chars)}); continue
        cells=_segment(alpha,rows[ri],len(chars))
        diagnostics.append({"row":ri+1,"expected_count":len(chars),"detected_cells":len(cells),"chars":"".join(chars)})
        for ch,cell in zip(chars,cells):
            x0,y0,x1,y1=cell; glyph=_norm(alpha.crop((x0,y0,x1,y1)))
            if glyph.width>1 and glyph.height>1:
                glyph.save(GLYPH_DIR/f"{ord(ch)}.png"); saved.append(ch)
    (GLYPH_DIR/"glyph_meta.txt").write_text("".join(saved),encoding="utf-8")
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V22.1 glyph library built.","reference_image":str(ref),"glyph_dir":str(GLYPH_DIR),"expected_glyphs":len(ORDERED_GLYPHS),"saved_glyphs":len(saved),"saved_chars":"".join(saved),"rows_found":len(rows),"diagnostics":diagnostics,"checked_at":_now()}

def _load(ch,ink):
    p=GLYPH_DIR/f"{ord(ch)}.png"
    if not p.exists(): return None
    img=Image.open(p).convert("RGBA"); out=Image.new("RGBA",img.size,ink); out.putalpha(img.getchannel("A"))
    return _crop(out,1)

def _fallback(ch,target_h,ink):
    img=Image.new("RGBA",(max(10,int(target_h*.75)),max(14,int(target_h*1.05))),(0,0,0,0))
    ImageDraw.Draw(img).text((1,0),ch,font=_font(max(8,int(target_h*.70))),fill=ink)
    return _crop(img,1)

def _pressure(glyph,ink,seed):
    random.seed(seed); glyph=glyph.convert("RGBA"); a=glyph.getchannel("A")
    factor=random.uniform(.93,1.0); a=a.point(lambda p:max(0,min(255,int(p*factor))))
    if random.random()<.12: a=a.filter(ImageFilter.GaussianBlur(radius=.025))
    out=Image.new("RGBA",glyph.size,ink); out.putalpha(a); return out

def _prepare(ch,target_h,ink,seed):
    g=_load(ch,ink) or _fallback(ch,target_h,ink)
    if g.height:
        sc=target_h/float(g.height); g=g.resize((max(3,int(g.width*sc)),max(5,int(g.height*sc))),Image.LANCZOS)
    random.seed(seed); g=g.rotate(random.uniform(-.12,.12),expand=True,resample=Image.BICUBIC,fillcolor=(0,0,0,0))
    return _pressure(g,ink,seed)

def _measure(text,target_h,ink,seed=0):
    cs=max(.5,target_h*.032); ws=max(2.0,target_h*.22); w=0.0
    for i,ch in enumerate(text):
        if ch==" ": w+=ws; continue
        w += _prepare(ch,target_h,ink,seed+i).width + cs
    return w

def _fit(text,target_h,max_w,ink,seed=0):
    text=_clean(text)
    if _measure(text,target_h,ink,seed)<=max_w: return text
    out=""
    for ch in text:
        if _measure(out+ch,target_h,ink,seed)>max_w: break
        out+=ch
    return out.rstrip()

def _text_img(text,w,h,size,ink,seed=0,align="left",max_chars=0,baseline=.76):
    text=_clean(text)
    if max_chars and len(text)>max_chars: text=text[:max_chars].rstrip()
    W,H=int(max(8,w)),int(max(8,h)); canvas=Image.new("RGBA",(W,H),(0,0,0,0))
    if not text: return canvas
    target=max(6,min(int(H*.44),int(size*.93)))
    for th in range(target,5,-1):
        if _measure(text,th,ink,seed)<=W-4: target=th; break
    text=_fit(text,target,W-4,ink,seed); line_w=_measure(text,target,ink,seed)
    x=max(1,int((W-line_w)/2)) if align=="center" else (max(1,int(W-line_w-2)) if align=="right" else 2)
    base=int(H*baseline); cs=max(.5,target*.032); ws=max(2.0,target*.22)
    for i,ch in enumerate(text):
        if ch==" ":
            x+=ws*random.uniform(.97,1.04); continue
        g=_prepare(ch,target,ink,seed+i)
        y=max(0,int(base-g.height+0.25*math.sin(i/4.0)))
        if x+g.width>W-1: break
        canvas.alpha_composite(g,(int(x),y))
        x += g.width + cs*random.uniform(.96,1.08)
    return canvas

def _xmark(w,h,ink,seed=0):
    random.seed(seed); scale=3; W,H=max(18,int(w)*scale),max(18,int(h)*scale)
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    pad=int(min(W,H)*.18); lw=max(2,int(min(W,H)*.055)); j=lambda:random.uniform(-.8,.8)
    d.line([(pad+j(),pad+j()),(W-pad+j(),H-pad+j())],fill=ink,width=lw)
    d.line([(W-pad+j(),pad+j()),(pad+j(),H-pad+j())],fill=ink,width=lw)
    img.thumbnail((int(w),int(h)),Image.LANCZOS)
    c=Image.new("RGBA",(int(w),int(h)),(0,0,0,0)); c.alpha_composite(img,(max(0,(c.width-img.width)//2),max(0,(c.height-img.height)//2))); return c

def _defaults(payload):
    return {
        "company_name":payload.get("company_name") or "LECHESA MANABA CONSULTING AND PROJECTS (PTY) LTD",
        "director_name":payload.get("director_name") or "LECHESA MANABA",
        "surname_name":payload.get("surname_and_name") or "MANABA, LECHESA",
        "designation":payload.get("designation") or "DIRECTOR",
        "date":payload.get("date") or payload.get("todays_date") or "27 APRIL 2026",
        "company_reg":payload.get("company_registration_number") or "2012/159509/07",
        "phone":payload.get("phone") or "0826338492",
        "email":payload.get("email") or "lechesam@me.com",
        "tcs_pin":payload.get("tcs_pin") or "2C151 C823M",
        "csd":payload.get("csd_number") or "MAAA0002664",
    }

def _f(page,x,y,w,h,text="",name="",size=12,mark="text",align="left",max_chars=0,baseline=.76):
    return Field(int(page),float(x),float(y),float(w),float(h),_clean(text),str(name or ""),int(size),str(mark or "text"),str(align or "left"),int(max_chars or 0),float(baseline))

def _training_map(payload):
    d=_defaults(payload)
    fields=[
        _f(5,230,346,330,24,d["company_name"],"rfq_company",8,max_chars=42),_f(5,230,371,330,24,"1787 DUBE STREET, BATHO LOCATION","rfq_postal",8,max_chars=35),_f(5,230,396,330,24,"1787 DUBE STREET, BATHO LOCATION","rfq_street",8,max_chars=35),_f(5,432,421,110,22,d["phone"],"rfq_phone",10,baseline=.74),_f(5,250,446,180,22,d["phone"],"rfq_cell",10,baseline=.74),_f(5,230,496,260,24,d["email"],"rfq_email",10,max_chars=22),_f(5,254,543,75,34,d["tcs_pin"],"rfq_tcs",7,max_chars=10,baseline=.72),_f(5,453,543,120,25,d["csd"],"rfq_csd",9,max_chars=12,baseline=.74),
        _f(8,514,418,18,18,name="sbd4_2_1_no",mark="x"),_f(8,514,499,18,18,name="sbd4_2_2_no",mark="x"),_f(8,466,600,18,18,name="sbd4_2_3_yes",mark="x"),_f(8,195,520,95,24,"N/A","sbd4_2_2_1_na",12,align="center"),
        _f(10,360,663,150,24,d["date"],"sbd4_date",9,max_chars=13),_f(10,88,720,170,24,d["designation"],"sbd4_position",9,max_chars=12),_f(10,245,720,335,24,d["company_name"],"sbd4_bidder",7,max_chars=42),
        _f(12,488,420,55,28,"20","sbd6_black_points",16,align="center",baseline=.70),_f(12,488,455,55,28,"4","sbd6_local_points",16,align="center",baseline=.70),_f(12,488,490,55,28,"0","sbd6_woman_points",16,align="center",baseline=.70),_f(12,488,525,55,28,"0","sbd6_youth_points",16,align="center",baseline=.70),_f(12,488,560,55,28,"0","sbd6_disability_points",16,align="center",baseline=.70),
        _f(15,245,235,300,24,d["company_name"],"sbd6_company",7,max_chars=42),_f(15,265,264,180,24,d["company_reg"],"sbd6_reg",9,max_chars=14),_f(15,78,345,18,18,name="sbd6_pty_ltd_tick",mark="x"),
        _f(16,335,558,170,24,d["date"],"sbd6_date",9,max_chars=13),_f(16,250,610,220,24,d["surname_name"],"sbd6_name",9,max_chars=18),_f(16,250,640,285,24,"1787 DUBE STREET","sbd6_address_1",8,max_chars=20),_f(16,250,666,285,24,"BATHO LOCATION","sbd6_address_2",8,max_chars=20),_f(16,250,692,285,24,"BLOEMFONTEIN, 9323","sbd6_address_3",8,max_chars=22),
        _f(18,514,235,20,20,name="sbd8_4_1_no",mark="x"),_f(18,514,468,20,20,name="sbd8_4_2_no",mark="x"),_f(19,514,145,20,20,name="sbd8_4_3_no",mark="x"),_f(19,514,346,20,20,name="sbd8_4_4_no",mark="x"),
        _f(18,210,365,120,45,"N/A","sbd8_4_1_details",18,align="center",baseline=.66),_f(19,210,164,120,45,"N/A","sbd8_4_3_details",18,align="center",baseline=.66),
        _f(19,490,465,170,24,d["director_name"],"sbd8_name",8,max_chars=16),_f(19,390,678,150,24,d["date"],"sbd8_date",9,max_chars=13),_f(19,80,722,160,24,d["designation"],"sbd8_position",9,max_chars=12),_f(19,245,722,330,24,d["company_name"],"sbd8_bidder",7,max_chars=42),
        _f(21,115,408,360,24,d["company_name"],"sbd9_bidder_page21",7,max_chars=42),_f(23,428,447,150,24,d["date"],"sbd9_date",9,max_chars=13),_f(23,92,510,160,24,d["designation"],"sbd9_position",9,max_chars=12),_f(23,245,510,330,24,d["company_name"],"sbd9_bidder",7,max_chars=42),
    ]
    return fields, {"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","mode":"v22_1_baseline_lock_training_map","field_count":len(fields),"baseline_lock":True}

def _manual(payload):
    out=[]
    for i,item in enumerate(payload.get("fields") or []):
        if not isinstance(item,dict): continue
        text=_clean(item.get("text") or item.get("value") or ""); mark=str(item.get("mark") or "").lower().strip()
        if not text and mark!="x": continue
        out.append(_f(item.get("page") or 1,item.get("x") or 0,item.get("y") or 0,item.get("w") or 260,item.get("h") or 28,text,item.get("name") or f"manual_{i+1}",item.get("font_size") or item.get("size") or 12,mark or "text",item.get("align") or "left",item.get("max_chars") or 0,item.get("baseline") or .76))
    return out

def complete_tender_form_intelligence(payload):
    err=_deps()
    if err: return {"status":"error","engine_version":ENGINE_VERSION,"message":err,"checked_at":_now()}
    payload=payload or {}; ref=payload.get("glyph_reference_image") or payload.get("reference_image") or payload.get("handwriting_reference")
    glyph_build_result=build_glyph_library(ref,force=bool(payload.get("force_rebuild_glyphs"))) if ref else None
    pdf=_resolve(payload.get("input_pdf") or payload.get("pdf_path")); buyer=_clean(payload.get("buyer_rfq_number") or f"RFQ-{uuid.uuid4().hex[:8]}")
    if not pdf: return {"status":"error","engine_version":ENGINE_VERSION,"message":"Input PDF not found","checked_at":_now()}
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True); DEBUG_DIR.mkdir(parents=True,exist_ok=True)
    output=OUTPUT_DIR/f"{_safe(buyer)}__v22_1_baseline_lock_completed.pdf"; ink=_ink(payload.get("ink_color") or "black")
    doc=fitz.open(str(pdf)); inserted=[]; skipped=[]; report={}; rendered=set()
    try:
        fields=[]
        if payload.get("training_map") or payload.get("auto_fill") or payload.get("use_glyph_handwriting"): fields,report=_training_map(payload)
        fields+=_manual(payload)
        for idx,field in enumerate(fields):
            key=(field.page,field.name)
            if key in rendered:
                skipped.append({"name":field.name,"page":field.page,"reason":"duplicate_render_suppressed"}); continue
            rendered.add(key)
            try:
                if field.page<1 or field.page>len(doc):
                    skipped.append({"name":field.name,"page":field.page,"reason":"page_out_of_range"}); continue
                page=doc[field.page-1]; rect=fitz.Rect(field.x,field.y,field.x+field.w,field.y+field.h)
                if field.mark=="x":
                    overlay=_xmark(field.w,field.h,ink,idx); typ="baseline_locked_x_mark"
                else:
                    overlay=_text_img(field.text,field.w,field.h,field.size,ink,seed=abs(hash((buyer,field.name,idx)))%999999,align=field.align,max_chars=field.max_chars,baseline=field.baseline); typ="baseline_locked_handwriting"
                page.insert_image(rect,stream=_png(overlay),overlay=True)
                inserted.append({"name":field.name,"type":typ,"page":field.page,"x":field.x,"y":field.y,"w":field.w,"h":field.h,"text_preview":field.text[:80]})
            except Exception as exc:
                skipped.append({"name":field.name,"page":field.page,"reason":"field_failed","error":str(exc)})
        doc.save(str(output),garbage=4,deflate=True,clean=True)
        return {"status":"ok","engine_version":ENGINE_VERSION,"buyer_rfq_number":buyer,"message":"Completed using V22.1 baseline lock engine. No typed PDF text insertion was used.","input_pdf":str(pdf),"output_pdf":str(output),"glyph_dir":str(GLYPH_DIR),"glyph_build_result":glyph_build_result,"training_map":bool(payload.get("training_map") or payload.get("auto_fill") or payload.get("use_glyph_handwriting")),"training_report":report,"inserted_count":len(inserted),"skipped_count":len(skipped),"inserted":inserted,"skipped":skipped,"checked_at":_now()}
    finally:
        doc.close()

def get_tender_form_intelligence_status():
    glyphs=list(GLYPH_DIR.glob("*.png")) if GLYPH_DIR.exists() else []
    return {"status":"ok","engine_version":ENGINE_VERSION,"mode":"baseline_lock_human_written","typed_pdf_text_disabled":True,"single_pass_rendering":True,"ghost_suppression":True,"baseline_lock":True,"human_written_target":True,"glyph_count":len(glyphs),"glyph_dir":str(GLYPH_DIR),"glyph_library_exists":GLYPH_DIR.exists(),"output_dir":str(OUTPUT_DIR),"debug_dir":str(DEBUG_DIR),"checked_at":_now()}

def detect_training_template(input_pdf):
    pdf=_resolve(input_pdf); return {"status":"ok" if pdf else "error","engine_version":ENGINE_VERSION,"template":"ISIMANGALISO_CORPORATE_GIFT_PACKS","matched":bool(pdf),"input_pdf":str(pdf) if pdf else None}
def detect_sbd_pages(input_pdf):
    pdf=_resolve(input_pdf); return {"status":"ok" if pdf else "error","engine_version":ENGINE_VERSION,"input_pdf":str(pdf) if pdf else None,"message":"V22.1 uses baseline-lock trained map."}
def locate_writable_fields(input_pdf,page_number=1,limit=30):
    return {"status":"ok","engine_version":ENGINE_VERSION,"message":"V22.1 uses baseline-lock trained map; locator disabled for known template.","candidates":[]}
def complete_form_with_tender_intelligence(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form(payload): return complete_tender_form_intelligence(payload)
def complete_form(payload): return complete_tender_form_intelligence(payload)
def complete_sbd_form(payload): return complete_tender_form_intelligence(payload)
def complete_tender_form_from_payload(payload): return complete_tender_form_intelligence(payload)
def run_tender_form_intelligence(payload): return complete_tender_form_intelligence(payload)
