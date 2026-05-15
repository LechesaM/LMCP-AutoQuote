from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RUNTIME_DIR = Path("runtime")
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
OUTPUT_DIR = HANDWRITING_DIR / "outputs"
GLYPH_OUTPUT_DIR = HANDWRITING_DIR / "glyph_form_outputs"
CLEAN_INK_V3_DIR = HANDWRITING_DIR / "clean_ink_v3"
DYNAMIC_V4_DIR = HANDWRITING_DIR / "dynamic_v4"
LINE_INK_V5_DIR = HANDWRITING_DIR / "line_ink_v5"
NORMALIZED_INK_V7_DIR = HANDWRITING_DIR / "normalized_ink_v7"
PEN_FLOW_V8_DIR = HANDWRITING_DIR / "pen_flow_v8"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GLYPH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_INK_V3_DIR.mkdir(parents=True, exist_ok=True)
DYNAMIC_V4_DIR.mkdir(parents=True, exist_ok=True)
LINE_INK_V5_DIR.mkdir(parents=True, exist_ok=True)
NORMALIZED_INK_V7_DIR.mkdir(parents=True, exist_ok=True)
PEN_FLOW_V8_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = HANDWRITING_DIR / "handwriting_history.json"

DEFAULT_STYLE = {
    "font_name": "Helvetica-Oblique",
    "font_size": 10,
    "jitter_x": 0.6,
    "jitter_y": 0.4,
    "rotation_degrees": 0.8,
    "line_gap": 12,
    "ink_gray": 0.08,

    # V3 clean ink image mode
    "use_clean_ink": False,
    "clean_ink_path": "",
    "clean_ink_job_id": "",
    "clean_ink_scale": 1.0,
    "clean_ink_max_width": 300,
    "clean_ink_max_height": 75,
    "clean_ink_opacity": 1.0,

    # V4 dynamic handwriting mode
    "use_dynamic_handwriting": False,
    "dynamic_font_size": 24,
    "dynamic_ink_gray": 55,
    "dynamic_opacity": 230,
    "dynamic_max_chars_per_line": 42,
    "dynamic_max_width": 420,
    "dynamic_max_height": 90,

    # V5 real line ink mode
    "use_line_ink": False,
    "line_ink_job_id": "REAL-HANDWRITING",
    "line_ink_max_width": 420,
    "line_ink_max_height": 55,

    # V6 field auto-map
    "auto_map_fields": False,

    # V7 normalized thickness
    "normalize_ink_thickness": True,
    "normalized_target_density": 0.075,
    "normalized_darken_factor": 0.78,

    # V8 pen-flow variation
    "use_pen_flow_v8": False,
    "pen_pressure_variation": 0.10,
    "pen_edge_softness": 0.25,
    "pen_ink_texture": 0.06,
    "pen_flow_darken_factor": 0.92,

    "fallback_to_font": True,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(value: Any, fallback: str = "UNKNOWN") -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def _read_history() -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_history(entry: Dict[str, Any]) -> None:
    history = _read_history()
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history[-500:], indent=2, default=str), encoding="utf-8")


def _latest_clean_ink_asset() -> Optional[Path]:
    candidates: List[Path] = []
    if CLEAN_INK_V3_DIR.exists():
        candidates.extend(CLEAN_INK_V3_DIR.rglob("clean_ink_cropped.png"))
        candidates.extend(CLEAN_INK_V3_DIR.rglob("clean_ink_transparent.png"))

    existing = [p for p in candidates if p.exists() and p.is_file()]
    return max(existing, key=lambda p: p.stat().st_mtime) if existing else None


def _clean_ink_asset_from_style(style: Dict[str, Any]) -> Optional[Path]:
    direct = str(style.get("clean_ink_path") or "").strip()
    if direct:
        p = Path(direct)
        if p.exists() and p.is_file():
            return p

    job_id = str(style.get("clean_ink_job_id") or "").strip()
    if job_id:
        job_dir = CLEAN_INK_V3_DIR / _safe_filename(job_id)
        for name in ("clean_ink_cropped.png", "clean_ink_transparent.png"):
            p = job_dir / name
            if p.exists() and p.is_file():
                return p

    return _latest_clean_ink_asset()


def _load_png_size(path: Path) -> Tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return (0, 0)


def _fit_image_size(
    image_width: float,
    image_height: float,
    *,
    max_width: float,
    max_height: float,
    scale: float,
) -> Tuple[float, float]:
    if image_width <= 0 or image_height <= 0:
        return 0.0, 0.0

    w = image_width * max(0.05, float(scale))
    h = image_height * max(0.05, float(scale))

    if max_width > 0 and w > max_width:
        factor = max_width / w
        w *= factor
        h *= factor

    if max_height > 0 and h > max_height:
        factor = max_height / h
        w *= factor
        h *= factor

    return max(1.0, w), max(1.0, h)


def get_handwriting_status(limit: int = 50) -> Dict[str, Any]:
    history = _read_history()
    limit = max(1, min(int(limit or 50), 500))

    return {
        "status": "ok",
        "engine": "handwriting_simulation_v8_pen_flow",
        "default_style": DEFAULT_STYLE,
        "output_dir": str(OUTPUT_DIR),
        "glyph_output_dir": str(GLYPH_OUTPUT_DIR),
        "clean_ink_v3_dir": str(CLEAN_INK_V3_DIR),
        "dynamic_v4_dir": str(DYNAMIC_V4_DIR),
        "line_ink_v5_dir": str(LINE_INK_V5_DIR),
        "normalized_ink_v7_dir": str(NORMALIZED_INK_V7_DIR),
        "pen_flow_v8_dir": str(PEN_FLOW_V8_DIR),
        "latest_clean_ink_asset": str(_latest_clean_ink_asset()) if _latest_clean_ink_asset() else None,
        "history_count": len(history),
        "recent_history": history[-limit:],
        "updated_at": _now_iso(),
    }


def preview_handwriting_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    style = {**DEFAULT_STYLE, **(payload.get("style") or {})}

    if style.get("auto_map_fields"):
        try:
            from app.services.handwriting_field_automap_v6 import automap_payload_fields

            payload = automap_payload_fields(payload)
        except Exception as exc:
            payload = {**payload, "auto_mapping_error": str(exc)}

    return {
        "status": "ok",
        "message": "Handwriting preview payload accepted.",
        "engine": "handwriting_simulation_v8_pen_flow",
        "payload": payload,
        "resolved_style": style,
        "checked_at": _now_iso(),
    }


def build_example_overlay_payload() -> Dict[str, Any]:
    return {
        "buyer_rfq_number": "TEST-HANDWRITING-V8-PEN-FLOW",
        "page_size": "A4",
        "style": {
            "use_line_ink": True,
            "line_ink_job_id": "REAL-HANDWRITING",
            "use_pen_flow_v8": True,
            "fallback_to_font": True,
            "line_ink_max_height": 55,
        },
        "fields": [
            {"page": 1, "x": 120, "y": 720, "line_index": 1, "scale": 0.95},
            {"page": 1, "x": 120, "y": 650, "line_index": 2, "scale": 1.10},
        ],
    }


def _draw_font_text(c: Any, field: Dict[str, Any], style: Dict[str, Any]) -> None:
    text = str(field.get("text") or "")
    x = float(field.get("x") or 0)
    y = float(field.get("y") or 0)

    c.setFont(str(style["font_name"]), float(field.get("font_size") or style["font_size"]))
    c.setFillGray(float(field.get("ink_gray") if field.get("ink_gray") is not None else style["ink_gray"]))

    c.saveState()
    c.translate(
        x + random.uniform(-float(style["jitter_x"]), float(style["jitter_x"])),
        y + random.uniform(-float(style["jitter_y"]), float(style["jitter_y"])),
    )
    c.rotate(random.uniform(-float(style["rotation_degrees"]), float(style["rotation_degrees"])))
    c.drawString(0, 0, text)
    c.restoreState()


def _draw_png_image(
    c: Any,
    field: Dict[str, Any],
    style: Dict[str, Any],
    image_path: Path,
    *,
    default_max_width: float,
    default_max_height: float,
) -> bool:
    try:
        from reportlab.lib.utils import ImageReader
    except Exception:
        return False

    if not image_path.exists():
        return False

    image_width, image_height = _load_png_size(image_path)
    if image_width <= 0 or image_height <= 0:
        return False

    max_width = float(field.get("max_width") or default_max_width)
    max_height = float(field.get("max_height") or default_max_height)
    scale = float(field.get("scale") or style.get("clean_ink_scale") or 1.0)

    draw_w, draw_h = _fit_image_size(
        image_width,
        image_height,
        max_width=max_width,
        max_height=max_height,
        scale=scale,
    )

    x = float(field.get("x") or 0)
    y = float(field.get("y") or 0)
    baseline_adjust = float(field.get("baseline_adjust") if field.get("baseline_adjust") is not None else -6)

    try:
        img_reader = ImageReader(str(image_path))
        c.saveState()
        c.translate(
            x + random.uniform(-float(style["jitter_x"]), float(style["jitter_x"])),
            y + baseline_adjust + random.uniform(-float(style["jitter_y"]), float(style["jitter_y"])),
        )
        c.rotate(random.uniform(-float(style["rotation_degrees"]), float(style["rotation_degrees"])))
        c.drawImage(
            img_reader,
            0,
            0,
            width=draw_w,
            height=draw_h,
            mask="auto",
            preserveAspectRatio=True,
            anchor="sw",
        )
        c.restoreState()
        return True
    except Exception:
        try:
            c.restoreState()
        except Exception:
            pass
        return False


def _draw_dynamic_handwriting(c: Any, field: Dict[str, Any], style: Dict[str, Any], rfq: str, field_index: int) -> bool:
    text = str(field.get("text") or "").strip()
    if not text:
        return False

    try:
        from app.services.handwriting_v4_dynamic_writer import build_dynamic_field_image
    except Exception:
        return False

    dynamic_style = {
        "font_size": int(field.get("dynamic_font_size") or style.get("dynamic_font_size") or 24),
        "ink_gray": int(field.get("dynamic_ink_gray") or style.get("dynamic_ink_gray") or 55),
        "opacity": int(field.get("dynamic_opacity") or style.get("dynamic_opacity") or 230),
        "jitter_x": float(style.get("jitter_x") or 0.6),
        "jitter_y": float(style.get("jitter_y") or 0.4),
        "rotation_degrees": float(style.get("rotation_degrees") or 0.8),
        "max_chars_per_line": int(field.get("max_chars_per_line") or style.get("dynamic_max_chars_per_line") or 42),
    }

    rendered = build_dynamic_field_image(
        buyer_rfq_number=rfq,
        field_index=field_index,
        text=text,
        style=dynamic_style,
    )

    if rendered.get("status") != "ok":
        return False

    return _draw_png_image(
        c,
        field,
        style,
        Path(str(rendered.get("output_path"))),
        default_max_width=float(field.get("max_width") or style.get("dynamic_max_width") or 420),
        default_max_height=float(field.get("max_height") or style.get("dynamic_max_height") or 90),
    )


def _draw_line_ink(c: Any, field: Dict[str, Any], style: Dict[str, Any]) -> bool:
    try:
        from app.services.handwriting_line_ink_v5 import build_line_ink_assets_v5, resolve_line_asset_v5
    except Exception:
        return False

    job_id = str(field.get("line_ink_job_id") or style.get("line_ink_job_id") or "REAL-HANDWRITING")
    line_index = field.get("line_index")

    # Always rebuild/refresh V5 and V7 first, so V8 has fresh normalized source assets.
    build_line_ink_assets_v5(
        job_id=job_id,
        normalize_v7=True,
        target_density=float(style.get("normalized_target_density") or 0.075),
        darken_factor=float(style.get("normalized_darken_factor") or 0.78),
    )

    asset: Optional[Path] = None
    used_v8 = False

    # V8 must be first priority when requested.
    if bool(style.get("use_pen_flow_v8", False)) or bool(field.get("use_pen_flow_v8", False)):
        try:
            from app.services.handwriting_pen_flow_v8 import (
                apply_pen_flow_to_job_v8,
                resolve_pen_flow_asset_v8,
            )

            apply_pen_flow_to_job_v8(
                job_id=job_id,
                pressure_variation=float(style.get("pen_pressure_variation") or 0.10),
                edge_softness=float(style.get("pen_edge_softness") or 0.25),
                ink_texture=float(style.get("pen_ink_texture") or 0.06),
                darken_factor=float(style.get("pen_flow_darken_factor") or 0.92),
            )

            asset = resolve_pen_flow_asset_v8(
                job_id=job_id,
                line_index=int(line_index) if line_index else None,
            )
            used_v8 = bool(asset and asset.exists())
        except Exception:
            asset = None
            used_v8 = False

    # Fallback to V7 normalized/raw V5.
    if not asset:
        asset = resolve_line_asset_v5(
            job_id=job_id,
            text=str(field.get("text") or ""),
            line_index=line_index,
            prefer_normalized=bool(style.get("normalize_ink_thickness", True)),
        )

    if not asset:
        return False

    # Store debug marker for result counting.
    field["_rendered_asset_path"] = str(asset)
    field["_rendered_with_pen_flow_v8"] = used_v8

    return _draw_png_image(
        c,
        field,
        style,
        asset,
        default_max_width=float(field.get("max_width") or style.get("line_ink_max_width") or 420),
        default_max_height=float(field.get("max_height") or style.get("line_ink_max_height") or 55),
    )


def create_handwriting_overlay_pdf(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, LETTER
    except Exception as exc:
        return {"status": "error", "message": f"reportlab is not installed or unavailable: {exc}"}

    style = {**DEFAULT_STYLE, **(payload.get("style") or {})}

    if style.get("auto_map_fields"):
        try:
            from app.services.handwriting_field_automap_v6 import automap_payload_fields

            payload = automap_payload_fields(payload)
            style = {**DEFAULT_STYLE, **(payload.get("style") or {})}
        except Exception as exc:
            payload = {**payload, "auto_mapping_error": str(exc)}

    rfq = str(payload.get("buyer_rfq_number") or "UNKNOWN")
    fields = [f for f in (payload.get("fields") or []) if isinstance(f, dict)]

    page_size_name = str(payload.get("page_size") or "A4").upper()
    page_size = LETTER if page_size_name == "LETTER" else A4

    safe_rfq = _safe_filename(rfq)
    out_path = OUTPUT_DIR / f"{safe_rfq}__handwriting_overlay.pdf"

    clean_ink_asset = _clean_ink_asset_from_style(style) if style.get("use_clean_ink") else None
    clean_ink_available = bool(clean_ink_asset and clean_ink_asset.exists())

    max_page = max([int(f.get("page") or 1) for f in fields] or [1])
    c = canvas.Canvas(str(out_path), pagesize=page_size)

    line_count = 0
    pen_flow_count = 0
    dynamic_count = 0
    clean_count = 0
    font_count = 0
    failed_count = 0
    auto_mapped_count = 0
    field_index = 0
    rendered_assets: List[str] = []

    for page in range(1, max_page + 1):
        page_fields = [f for f in fields if int(f.get("page") or 1) == page]

        for field in page_fields:
            field_index += 1
            mode = str(field.get("mode") or "").strip().lower()

            if field.get("auto_mapped"):
                auto_mapped_count += 1

            wants_line = bool(style.get("use_line_ink")) or mode in {"line_ink", "real_line", "real_handwriting"}
            wants_dynamic = bool(style.get("use_dynamic_handwriting")) or mode in {
                "dynamic",
                "dynamic_handwriting",
                "write",
                "text_ink",
            }
            wants_clean = bool(style.get("use_clean_ink")) or mode in {"clean_ink", "ink", "image"}

            if wants_line and _draw_line_ink(c, field, style):
                line_count += 1
                asset_path = str(field.get("_rendered_asset_path") or "")
                if asset_path:
                    rendered_assets.append(asset_path)
                if bool(field.get("_rendered_with_pen_flow_v8")):
                    pen_flow_count += 1
                continue

            if wants_dynamic and _draw_dynamic_handwriting(c, field, style, rfq, field_index):
                dynamic_count += 1
                continue

            if wants_clean and clean_ink_available and _draw_png_image(
                c,
                field,
                style,
                clean_ink_asset,  # type: ignore[arg-type]
                default_max_width=float(field.get("max_width") or style.get("clean_ink_max_width") or 300),
                default_max_height=float(field.get("max_height") or style.get("clean_ink_max_height") or 75),
            ):
                clean_count += 1
                continue

            if bool(style.get("fallback_to_font", True)):
                _draw_font_text(c, field, style)
                font_count += 1
            else:
                failed_count += 1

        c.showPage()

    c.save()

    result = {
        "status": "ok",
        "message": "Handwriting-style overlay PDF created.",
        "engine": "handwriting_simulation_v8_pen_flow",
        "buyer_rfq_number": rfq,
        "output_file": str(out_path),
        "field_count": len(fields),
        "auto_mapped_fields": auto_mapped_count,
        "drawn_with_line_ink": line_count,
        "drawn_with_pen_flow_v8": pen_flow_count,
        "drawn_with_dynamic_handwriting": dynamic_count,
        "drawn_with_clean_ink": clean_count,
        "drawn_with_font": font_count,
        "failed_fields": failed_count,
        "line_ink_requested": bool(style.get("use_line_ink")),
        "pen_flow_v8_requested": bool(style.get("use_pen_flow_v8")),
        "dynamic_handwriting_requested": bool(style.get("use_dynamic_handwriting")),
        "clean_ink_requested": bool(style.get("use_clean_ink")),
        "auto_map_requested": bool(style.get("auto_map_fields")),
        "rendered_assets": rendered_assets,
        "clean_ink_asset": str(clean_ink_asset) if clean_ink_available else None,
        "line_ink_v5_dir": str(LINE_INK_V5_DIR / _safe_filename(str(style.get("line_ink_job_id") or "REAL-HANDWRITING"))),
        "normalized_ink_v7_dir": str(NORMALIZED_INK_V7_DIR / _safe_filename(str(style.get("line_ink_job_id") or "REAL-HANDWRITING"))),
        "pen_flow_v8_dir": str(PEN_FLOW_V8_DIR / _safe_filename(str(style.get("line_ink_job_id") or "REAL-HANDWRITING"))),
        "page_size": page_size_name,
        "created_at": _now_iso(),
    }

    _write_history(result)
    return result


def create_handwriting_overlay(payload: Dict[str, Any]) -> Dict[str, Any]:
    return create_handwriting_overlay_pdf(payload)
