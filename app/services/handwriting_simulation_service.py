"""
LMCP AutoQuote - Handwriting Simulation Service
V13.2 Real Ink Reference Engine

Drop-in target:
    app/services/handwriting_simulation_service.py

What this version fixes:
    - Stops using computer-font handwriting as the main output.
    - Uses the real extracted handwriting image, e.g.
        runtime/handwriting_simulation/clean_ink_cropped.png
      as the default reference.
    - Automatically segments the real ink image into handwriting lines.
    - Maps:
        Director -> Director handwriting line
        Lechesa Manaba -> name handwriting line
        company name -> longest company handwriting line
    - Preserves PDF overlay, preview output, and API compatibility.

Dependencies:
    pip install pymupdf pillow
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import traceback
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

fitz = None
FITZ_IMPORT_ERROR = None


def _get_fitz():
    global fitz, FITZ_IMPORT_ERROR
    if fitz is not None or FITZ_IMPORT_ERROR is not None:
        return fitz
    try:
        import fitz as fitz_module  # PyMuPDF
    except Exception as exc:  # pragma: no cover
        FITZ_IMPORT_ERROR = exc
        return None
    fitz = fitz_module
    return fitz

try:
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
except Exception as exc:  # pragma: no cover
    Image = None
    ImageChops = None
    ImageDraw = None
    ImageEnhance = None
    ImageFilter = None
    ImageFont = None
    ImageOps = None
    PIL_IMPORT_ERROR = exc
else:
    PIL_IMPORT_ERROR = None


try:
    from app.services.handwriting_signature_engine import (
        make_signature_instruction,
        render_signature_asset,
    )
except Exception:  # pragma: no cover
    make_signature_instruction = None
    render_signature_asset = None

try:
    from app.services.handwriting_line_ink_v5 import resolve_line_asset_v5, resolve_line_asset_v7
except Exception:  # pragma: no cover
    resolve_line_asset_v5 = None
    resolve_line_asset_v7 = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
OUTPUT_DIR = HANDWRITING_DIR / "glyph_form_outputs"
LEGACY_OUTPUT_DIR = HANDWRITING_DIR / "outputs"
IDENTITY_DIR = HANDWRITING_DIR / "identity_profiles"
DEBUG_DIR = HANDWRITING_DIR / "debug"

for p in (HANDWRITING_DIR, OUTPUT_DIR, LEGACY_OUTPUT_DIR, IDENTITY_DIR, DEBUG_DIR):
    p.mkdir(parents=True, exist_ok=True)


@dataclass
class HandwritingField:
    page: int = 1
    x: float = 120.0
    y: float = 720.0
    text: str = ""
    font_size: int = 13
    max_width: Optional[float] = None
    line_height: Optional[float] = None
    field_name: Optional[str] = None
    ink_color: Optional[Tuple[int, int, int, int]] = None


@dataclass
class WriterIdentity:
    writer_id: str = "LMCP_REAL_INK_WRITER"
    pressure_mean: float = 0.84
    pressure_variation: float = 0.035
    baseline_drift: float = 0.25
    rotation_variation: float = 0.18
    scale_variation: float = 0.025
    opacity: float = 0.96
    ink_blue_strength: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engine_version: str = "V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE"


@dataclass
class HandwritingJobResult:
    status: str
    engine_version: str
    buyer_rfq_number: str
    input_pdf: Optional[str]
    output_pdf: Optional[str]
    output_png_preview: Optional[str]
    field_count: int
    page_count: int
    writer_id: str
    identity_profile_path: str
    debug_path: Optional[str]
    message: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _safe_slug(value: Any, fallback: str = "HANDWRITING-JOB") -> str:
    raw = str(value or fallback).strip()
    raw = unicodedata.normalize("NFKD", raw)
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-._")
    return raw[:100] or fallback


def _now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _stable_int_seed(*parts: Any) -> int:
    joined = "::".join(str(p) for p in parts if p is not None)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _parse_color(value: Any, fallback: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    if value is None:
        return fallback
    if isinstance(value, (list, tuple)) and len(value) in (3, 4):
        vals = [int(_clamp(float(v), 0, 255)) for v in value]
        if len(vals) == 3:
            vals.append(255)
        return tuple(vals)  # type: ignore[return-value]
    if isinstance(value, str):
        s = value.strip().lower()
        if s.startswith("#"):
            s = s[1:]
            if len(s) == 6:
                return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
            if len(s) == 8:
                return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]
        named = {
            "blue": (24, 47, 132, 245),
            "darkblue": (12, 35, 110, 245),
            "navy": (8, 28, 92, 245),
            "black": (22, 22, 24, 245),
        }
        return named.get(s, fallback)
    return fallback


def _normalise_fields(fields: Sequence[Dict[str, Any]]) -> List[HandwritingField]:
    out: List[HandwritingField] = []
    for item in fields or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        out.append(
            HandwritingField(
                page=int(item.get("page") or 1),
                x=float(item.get("x") or 120.0),
                y=float(item.get("y") or 720.0),
                text=text,
                font_size=int(item.get("font_size") or item.get("size") or 13),
                max_width=float(item["max_width"]) if item.get("max_width") else None,
                line_height=float(item["line_height"]) if item.get("line_height") else None,
                field_name=item.get("field_name"),
                ink_color=_parse_color(item.get("ink_color"), (24, 47, 132, 245)) if item.get("ink_color") else None,
            )
        )
    return out


def _load_font(font_size: int) -> Any:
    if ImageFont is None:
        raise RuntimeError(f"Pillow is not available: {PIL_IMPORT_ERROR}")
    candidates = [
        PROJECT_ROOT / "app" / "assets" / "fonts" / "handwriting.ttf",
        PROJECT_ROOT / "app" / "assets" / "fonts" / "Caveat-Regular.ttf",
        PROJECT_ROOT / "app" / "assets" / "fonts" / "PatrickHand-Regular.ttf",
        Path("/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        try:
            if path.exists():
                return ImageFont.truetype(str(path), font_size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        return ImageFont.load_default()


def _text_bbox(draw: Any, text: str, font: Any) -> Tuple[int, int, int, int]:
    try:
        return draw.textbbox((0, 0), text, font=font)
    except Exception:
        w, h = draw.textsize(text, font=font)
        return (0, 0, int(w), int(h))


class V13RealInkIdentity:
    def __init__(
        self,
        writer_id: str = "LMCP_REAL_INK_WRITER",
        job_id: str = "REAL-HANDWRITING",
        identity_overrides: Optional[Dict[str, Any]] = None,
        persist_identity: bool = True,
    ) -> None:
        self.writer_id = _safe_slug(writer_id or "LMCP_REAL_INK_WRITER", "LMCP_REAL_INK_WRITER")
        self.job_id = _safe_slug(job_id or "REAL-HANDWRITING", "REAL-HANDWRITING")
        self.profile_path = IDENTITY_DIR / f"{self.writer_id}.json"
        self.persist_identity = persist_identity
        self.identity = self._load_or_create(identity_overrides or {})
        self.seed = _stable_int_seed(self.writer_id, self.job_id, self.identity.created_at)
        self.rng = random.Random(self.seed)

    def _load_or_create(self, overrides: Dict[str, Any]) -> WriterIdentity:
        if self.profile_path.exists():
            try:
                data = json.loads(self.profile_path.read_text(encoding="utf-8"))
                allowed = set(WriterIdentity.__dataclass_fields__.keys())
                base = asdict(WriterIdentity(writer_id=self.writer_id))
                base.update({k: v for k, v in data.items() if k in allowed})
                ident = WriterIdentity(**base)
            except Exception:
                ident = WriterIdentity(writer_id=self.writer_id)
        else:
            ident = WriterIdentity(writer_id=self.writer_id)

        allowed = set(WriterIdentity.__dataclass_fields__.keys())
        for key, value in overrides.items():
            if key in allowed and key not in {"writer_id", "created_at", "engine_version"}:
                setattr(ident, key, value)

        ident.writer_id = self.writer_id
        ident.engine_version = "V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE"

        if self.persist_identity:
            self.save(ident)
        return ident

    def save(self, ident: Optional[WriterIdentity] = None) -> None:
        ident = ident or self.identity
        self.profile_path.write_text(json.dumps(asdict(ident), indent=2), encoding="utf-8")

    def field_rng(self, field: HandwritingField, index: int) -> random.Random:
        return random.Random(_stable_int_seed(self.seed, field.page, field.x, field.y, field.text, index))


class RealInkReferenceRenderer:
    """
    Uses real extracted handwriting as the source.

    Expected reference image:
        runtime/handwriting_simulation/clean_ink_cropped.png

    The file can contain multiple handwritten lines. The renderer automatically
    detects dark ink rows and crops them into reusable line assets.
    """

    def __init__(
        self,
        identity_engine: V13RealInkIdentity,
        reference_image_path: Optional[Path] = None,
        default_ink_color: Tuple[int, int, int, int] = (24, 47, 132, 245),
        line_ink_job_id: Optional[str] = None,
    ) -> None:
        if Image is None:
            raise RuntimeError(f"Pillow is not available: {PIL_IMPORT_ERROR}")

        self.identity_engine = identity_engine
        self.identity = identity_engine.identity
        self.default_ink_color = default_ink_color
        self.line_ink_job_id = str(line_ink_job_id or "").strip() or None
        self.reference_image_path = reference_image_path or self._find_reference_image()
        self.line_assets = self._load_reference_lines()

    def _find_reference_image(self) -> Optional[Path]:
        candidates = [
            HANDWRITING_DIR / "clean_ink_cropped.png",
            HANDWRITING_DIR / "clean_ink.png",
            HANDWRITING_DIR / "sample_handwriting.png",
            HANDWRITING_DIR / "sample_signature_real.png",
            HANDWRITING_DIR / "sample_signature.png",
            HANDWRITING_DIR / "sample_signature.jpg",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_reference_lines(self) -> List[Image.Image]:
        if not self.reference_image_path or not self.reference_image_path.exists():
            return []

        img = Image.open(self.reference_image_path).convert("RGBA")
        img = self._trim_transparent_or_white(img, pad=8)

        gray = ImageOps.grayscale(img)
        # Dark ink mask. Works for black/grey handwriting on white background.
        mask = gray.point(lambda p: 255 if p < 205 else 0)

        width, height = mask.size
        pix = mask.load()

        row_counts: List[int] = []
        for y in range(height):
            count = 0
            for x in range(width):
                if pix[x, y] > 0:
                    count += 1
            row_counts.append(count)

        threshold = max(8, int(width * 0.006))
        ranges: List[Tuple[int, int]] = []
        in_run = False
        start = 0

        for y, count in enumerate(row_counts):
            if count >= threshold and not in_run:
                in_run = True
                start = y
            elif count < threshold and in_run:
                end = y
                if end - start >= 8:
                    ranges.append((start, end))
                in_run = False

        if in_run:
            ranges.append((start, height - 1))

        # Merge close ranges, because tall handwriting letters may split rows.
        merged: List[Tuple[int, int]] = []
        for start, end in ranges:
            if not merged:
                merged.append((start, end))
            else:
                ps, pe = merged[-1]
                if start - pe <= 16:
                    merged[-1] = (ps, end)
                else:
                    merged.append((start, end))

        assets: List[Image.Image] = []
        for start, end in merged:
            top = max(0, start - 10)
            bottom = min(height, end + 12)
            crop_mask = mask.crop((0, top, width, bottom))
            bbox = crop_mask.getbbox()
            if not bbox:
                continue
            left, upper, right, lower = bbox
            left = max(0, left - 12)
            right = min(width, right + 12)
            line = img.crop((left, top, right, bottom))
            line = self._ink_to_alpha(line)
            line = self._trim_alpha(line, pad=6)
            if line.size[0] > 20 and line.size[1] > 8:
                assets.append(line)

        # Sort top-to-bottom already. If there are too many tiny pieces, keep useful ones.
        assets = [a for a in assets if a.size[0] >= 40]
        return assets

    def _trim_transparent_or_white(self, img: Image.Image, pad: int = 4) -> Image.Image:
        rgba = img.convert("RGBA")
        gray = ImageOps.grayscale(rgba)
        mask = gray.point(lambda p: 255 if p < 245 else 0)
        bbox = mask.getbbox()
        if not bbox:
            return rgba
        l, t, r, b = bbox
        l = max(0, l - pad)
        t = max(0, t - pad)
        r = min(rgba.size[0], r + pad)
        b = min(rgba.size[1], b + pad)
        return rgba.crop((l, t, r, b))

    def _trim_alpha(self, img: Image.Image, pad: int = 4) -> Image.Image:
        bbox = img.getchannel("A").getbbox()
        if not bbox:
            return img
        l, t, r, b = bbox
        l = max(0, l - pad)
        t = max(0, t - pad)
        r = min(img.size[0], r + pad)
        b = min(img.size[1], b + pad)
        return img.crop((l, t, r, b))

    def _load_line_ink_asset(self, text: str) -> Optional[Image.Image]:
        if not self.line_ink_job_id:
            return None

        asset_path = None
        if resolve_line_asset_v5 is not None:
            try:
                asset_path = resolve_line_asset_v5(job_id=self.line_ink_job_id, text=text)
            except Exception:
                asset_path = None

        if not asset_path and resolve_line_asset_v7 is not None:
            try:
                asset_path = resolve_line_asset_v7(job_id=self.line_ink_job_id)
            except Exception:
                asset_path = None

        if not asset_path:
            return None

        try:
            with Image.open(asset_path) as img:
                return self._trim_alpha(img.convert("RGBA"), pad=4)
        except Exception:
            return None

    def _ink_to_alpha(self, img: Image.Image) -> Image.Image:
        """
        Convert photographed/scanned ink to transparent alpha.
        """
        rgba = img.convert("RGBA")
        gray = ImageOps.grayscale(rgba)

        # Strong alpha for darker pixels, no alpha for white paper.
        alpha = gray.point(lambda p: int(_clamp((235 - p) * 2.4, 0, 255)))

        # Keep original darkness shape but recolor later.
        out = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        out.putalpha(alpha)
        return out

    def _select_line_asset(self, text: str) -> Optional[Image.Image]:
        line_ink_asset = self._load_line_ink_asset(text)
        if line_ink_asset is not None:
            return line_ink_asset

        if not self.line_assets:
            return None

        clean = str(text or "").strip().lower()

        # In the reference image from the user, common order appears:
        #   name
        #   director
        #   company line
        # But automatic detection can vary, so use size and text hints.
        sorted_by_width = sorted(self.line_assets, key=lambda im: im.size[0], reverse=True)

        if "director" in clean:
            # Director is usually shorter than name/company. Prefer line with medium width.
            candidates = sorted(self.line_assets, key=lambda im: abs(im.size[0] - sorted_by_width[-1].size[0]))
            return candidates[0].copy()

        if "consulting" in clean or "projects" in clean or "(pty" in clean or "ltd" in clean:
            return sorted_by_width[0].copy()

        if "lechesa" in clean or "manaba" in clean:
            # Name is usually not the longest and not the shortest.
            if len(self.line_assets) >= 3:
                by_width = sorted(self.line_assets, key=lambda im: im.size[0])
                return by_width[min(1, len(by_width) - 1)].copy()
            return sorted_by_width[-1].copy()

        # Fallback to longest if unknown.
        return sorted_by_width[0].copy()

    def render_field_layer(
        self,
        page_width: int,
        page_height: int,
        field: HandwritingField,
        field_index: int,
    ) -> Image.Image:
        page_width = int(round(float(page_width)))
        page_height = int(round(float(page_height)))
        layer = Image.new("RGBA", (page_width, page_height), (0, 0, 0, 0))

        rng = self.identity_engine.field_rng(field, field_index)
        ink = field.ink_color or self.default_ink_color

        asset = self._select_line_asset(field.text)
        if asset is None:
            self._fallback_font_line(layer, field, rng, ink)
            return layer

        asset = self._recolor_asset(asset, ink, rng)

        # Scale real handwriting to requested form font size.
        target_h = max(14, int(round(field.font_size * 2.0)))
        scale = target_h / max(1, asset.size[1])
        scale *= rng.uniform(0.98 - self.identity.scale_variation, 1.02 + self.identity.scale_variation)

        if field.max_width:
            max_w = int(round(field.max_width))
            if asset.size[0] * scale > max_w:
                scale = max_w / max(1, asset.size[0])

        new_w = max(1, int(round(asset.size[0] * scale)))
        new_h = max(1, int(round(asset.size[1] * scale)))
        asset = asset.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Small natural variation, not enough to ruin the real handwriting.
        angle = rng.uniform(-self.identity.rotation_variation, self.identity.rotation_variation)
        asset = asset.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

        # Add slight paper/pen softness.
        asset = asset.filter(ImageFilter.GaussianBlur(radius=0.08))

        x = int(round(float(field.x)))
        y_top = int(round(float(page_height) - float(field.y) - asset.size[1]))
        y_top += int(round(rng.uniform(-self.identity.baseline_drift, self.identity.baseline_drift)))

        layer.alpha_composite(asset, (x, y_top))
        return layer

    def _recolor_asset(
        self,
        asset: Image.Image,
        ink: Tuple[int, int, int, int],
        rng: random.Random,
    ) -> Image.Image:
        alpha = asset.getchannel("A")
        alpha = alpha.point(lambda p: int(_clamp(p * self.identity.opacity * rng.uniform(0.96, 1.02), 0, 255)))

        # Preserve natural pressure using alpha; color is blue/black ink.
        r, g, b, a = ink
        color = Image.new("RGBA", asset.size, (r, g, b, a))
        color.putalpha(alpha)

        # Slight texture.
        if rng.random() < 0.85:
            alpha2 = color.getchannel("A")
            lut = []
            for p in range(256):
                jitter = rng.uniform(0.94, 1.04)
                lut.append(int(_clamp(p * jitter, 0, 255)))
            alpha2 = alpha2.point(lut)
            color.putalpha(alpha2)

        return color

    def _fallback_font_line(
        self,
        layer: Image.Image,
        field: HandwritingField,
        rng: random.Random,
        ink: Tuple[int, int, int, int],
    ) -> None:
        # Only fallback when no real ink image exists.
        font = _load_font(max(9, int(field.font_size * 1.25)))
        draw = ImageDraw.Draw(layer)
        x = int(round(float(field.x)))
        y = int(round(float(layer.size[1]) - float(field.y) - float(field.font_size * 1.4)))
        draw.text((x, y), field.text, font=font, fill=ink)


def _create_blank_pdf(output_pdf: Path, page_size: str = "A4") -> Path:
    fitz_module = _get_fitz()
    if fitz_module is None:
        raise RuntimeError(f"PyMuPDF is not available: {FITZ_IMPORT_ERROR}")

    sizes = {
        "A4": fitz_module.paper_rect("a4"),
        "LETTER": fitz_module.paper_rect("letter"),
    }
    rect = sizes.get(str(page_size or "A4").upper(), fitz_module.paper_rect("a4"))
    doc = fitz_module.open()
    doc.new_page(width=rect.width, height=rect.height)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_pdf))
    doc.close()
    return output_pdf


def _render_pdf_page_to_image(page: Any, zoom: float = 2.0) -> Image.Image:
    fitz_module = _get_fitz()
    if fitz_module is None:
        raise RuntimeError(f"PyMuPDF is not available: {FITZ_IMPORT_ERROR}")
    matrix = fitz_module.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")


def _overlay_pdf_with_handwriting(
    input_pdf: Path,
    output_pdf: Path,
    fields: List[HandwritingField],
    identity_engine: V13RealInkIdentity,
    ink_color: Tuple[int, int, int, int],
    reference_image_path: Optional[Path] = None,
    line_ink_job_id: Optional[str] = None,
    debug: bool = False,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Optional[Path]]:
    fitz_module = _get_fitz()
    if fitz_module is None:
        raise RuntimeError(f"PyMuPDF is not available: {FITZ_IMPORT_ERROR}")

    doc = fitz_module.open(str(input_pdf))
    renderer = RealInkReferenceRenderer(
        identity_engine=identity_engine,
        reference_image_path=reference_image_path,
        default_ink_color=ink_color,
        line_ink_job_id=line_ink_job_id,
    )

    grouped: Dict[int, List[Tuple[int, HandwritingField]]] = {}
    for idx, field_obj in enumerate(fields):
        page_no = max(1, int(field_obj.page))
        grouped.setdefault(page_no, []).append((idx, field_obj))

    debug_preview_path: Optional[Path] = None

    for page_no, page_fields in grouped.items():
        if page_no > len(doc):
            continue

        page = doc[page_no - 1]
        rect = page.rect
        zoom = 2.0
        page_w = int(round(float(rect.width) * zoom))
        page_h = int(round(float(rect.height) * zoom))

        overlay = Image.new("RGBA", (page_w, page_h), (0, 0, 0, 0))

        for idx, field_obj in page_fields:
            scaled = HandwritingField(
                page=field_obj.page,
                x=float(field_obj.x) * zoom,
                y=float(field_obj.y) * zoom,
                text=field_obj.text,
                font_size=max(8, int(round(field_obj.font_size * zoom))),
                max_width=(field_obj.max_width * zoom) if field_obj.max_width else None,
                line_height=(field_obj.line_height * zoom) if field_obj.line_height else None,
                field_name=field_obj.field_name,
                ink_color=field_obj.ink_color,
            )

            # V14 Signature Intelligence:
            # If the field is a signature zone, place the real signature image
            # instead of rendering the word "SIGNATURE" as handwriting.
            signature_instruction = None
            if make_signature_instruction is not None and render_signature_asset is not None:
                try:
                    signature_payload = dict(payload or {})
                    signature_payload.setdefault("ink_color", signature_payload.get("signature_ink_color") or "black")
                    signature_instruction = make_signature_instruction(
                        {
                            "page": scaled.page,
                            "x": scaled.x,
                            "y": scaled.y,
                            "text": scaled.text,
                            "field_name": scaled.field_name,
                            "width": scaled.max_width or float(signature_payload.get("signature_width") or 190) * zoom,
                            "height": float(signature_payload.get("signature_height") or 58) * zoom,
                            "max_width": scaled.max_width or float(signature_payload.get("signature_width") or 190) * zoom,
                        },
                        signature_payload,
                    )
                except Exception:
                    signature_instruction = None

            if signature_instruction and signature_instruction.get("is_signature") and not signature_instruction.get("status"):
                try:
                    sig_asset = render_signature_asset(
                        signature_instruction,
                        debug_name=f"{output_pdf.stem}__page_{page_no}__field_{idx}",
                    )
                    sig_x = int(round(float(scaled.x)))
                    sig_y = int(round(float(page_h) - float(scaled.y) - float(sig_asset.size[1])))
                    sig_layer = Image.new("RGBA", (page_w, page_h), (0, 0, 0, 0))
                    sig_layer.alpha_composite(sig_asset, (sig_x, sig_y))
                    overlay = Image.alpha_composite(overlay, sig_layer)
                    continue
                except Exception:
                    # Fall back to handwriting renderer if signature image fails.
                    pass

            field_layer = renderer.render_field_layer(page_w, page_h, scaled, idx)
            overlay = Image.alpha_composite(overlay, field_layer)

        overlay_path = DEBUG_DIR / f"{output_pdf.stem}__page_{page_no}_overlay.png"
        overlay.save(overlay_path)

        if debug_preview_path is None:
            base_img = _render_pdf_page_to_image(page, zoom=zoom)
            preview = Image.alpha_composite(base_img, overlay)
            debug_preview_path = DEBUG_DIR / f"{output_pdf.stem}__preview.png"
            preview.save(debug_preview_path)

        page.insert_image(rect, filename=str(overlay_path), overlay=True)

    page_count = int(len(doc))
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_pdf), deflate=True, garbage=4)
    doc.close()

    return page_count, debug_preview_path


def complete_handwriting_form(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = payload or {}

    buyer_rfq_number = _safe_slug(
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("quote_number")
        or f"HANDWRITING-{_now_slug()}"
    )

    fields = _normalise_fields(payload.get("fields") or [])
    if not fields:
        result = HandwritingJobResult(
            status="error",
            engine_version="V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE",
            buyer_rfq_number=buyer_rfq_number,
            input_pdf=None,
            output_pdf=None,
            output_png_preview=None,
            field_count=0,
            page_count=0,
            writer_id=str(payload.get("writer_id") or "LMCP_REAL_INK_WRITER"),
            identity_profile_path="",
            debug_path=None,
            message="No valid handwriting fields were supplied.",
        )
        return asdict(result)

    writer_id = str(payload.get("writer_id") or payload.get("identity_id") or "LMCP_REAL_INK_WRITER")
    job_id = str(payload.get("line_ink_job_id") or payload.get("job_id") or buyer_rfq_number)
    persist_identity = bool(payload.get("persist_identity", True))
    debug = bool(payload.get("debug", True))

    identity_engine = V13RealInkIdentity(
        writer_id=writer_id,
        job_id=job_id,
        identity_overrides=dict(payload.get("identity_overrides") or {}),
        persist_identity=persist_identity,
    )

    ink = _parse_color(payload.get("ink_color") or payload.get("pen_color") or "blue", (24, 47, 132, 245))

    reference_raw = payload.get("reference_image") or payload.get("reference_image_path") or payload.get("clean_ink_path")
    reference_path: Optional[Path] = None
    if reference_raw:
        reference_path = Path(str(reference_raw))
        if not reference_path.is_absolute():
            reference_path = PROJECT_ROOT / reference_path

    input_pdf_raw = payload.get("input_pdf") or payload.get("source_pdf") or payload.get("pdf_path")
    if input_pdf_raw:
        input_pdf = Path(str(input_pdf_raw))
        if not input_pdf.is_absolute():
            input_pdf = PROJECT_ROOT / input_pdf
    else:
        input_pdf = HANDWRITING_DIR / f"{buyer_rfq_number}__blank_input.pdf"
        _create_blank_pdf(input_pdf, page_size=str(payload.get("page_size") or "A4"))

    if not input_pdf.exists():
        result = HandwritingJobResult(
            status="error",
            engine_version="V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE",
            buyer_rfq_number=buyer_rfq_number,
            input_pdf=str(input_pdf),
            output_pdf=None,
            output_png_preview=None,
            field_count=len(fields),
            page_count=0,
            writer_id=identity_engine.writer_id,
            identity_profile_path=str(identity_engine.profile_path),
            debug_path=None,
            message=f"Input PDF does not exist: {input_pdf}",
        )
        return asdict(result)

    output_pdf_raw = payload.get("output_pdf") or payload.get("output_path")
    if output_pdf_raw:
        output_pdf = Path(str(output_pdf_raw))
        if not output_pdf.is_absolute():
            output_pdf = PROJECT_ROOT / output_pdf
    else:
        output_pdf = OUTPUT_DIR / f"{buyer_rfq_number}__v13_real_ink_completed_form.pdf"

    try:
        page_count, debug_preview = _overlay_pdf_with_handwriting(
            input_pdf=input_pdf,
            output_pdf=output_pdf,
            fields=fields,
            identity_engine=identity_engine,
            ink_color=ink,
            reference_image_path=reference_path,
            line_ink_job_id=job_id,
            debug=debug,
            payload=payload,
        )
    except Exception as exc:
        result = HandwritingJobResult(
            status="error",
            engine_version="V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE",
            buyer_rfq_number=buyer_rfq_number,
            input_pdf=str(input_pdf),
            output_pdf=None,
            output_png_preview=None,
            field_count=len(fields),
            page_count=0,
            writer_id=identity_engine.writer_id,
            identity_profile_path=str(identity_engine.profile_path),
            debug_path=None,
            message=f"Handwriting render failed: {exc}\n{traceback.format_exc()}",
        )
        return asdict(result)

    result = HandwritingJobResult(
        status="ok",
        engine_version="V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE",
        buyer_rfq_number=buyer_rfq_number,
        input_pdf=str(input_pdf),
        output_pdf=str(output_pdf),
        output_png_preview=str(debug_preview) if debug_preview else None,
        field_count=len(fields),
        page_count=page_count,
        writer_id=identity_engine.writer_id,
        identity_profile_path=str(identity_engine.profile_path),
        debug_path=str(DEBUG_DIR),
        message="V14 signature + V13.2 real ink handwriting form completed successfully.",
    )

    manifest_path = output_pdf.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    return asdict(result)


def simulate_handwriting(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_handwriting_form(payload)


def run_handwriting_simulation(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_handwriting_form(payload)


def get_handwriting_status() -> Dict[str, Any]:
    profiles = sorted(IDENTITY_DIR.glob("*.json"))
    outputs = sorted(OUTPUT_DIR.glob("*.pdf"))
    reference_candidates = [
        HANDWRITING_DIR / "clean_ink_cropped.png",
        HANDWRITING_DIR / "clean_ink.png",
        HANDWRITING_DIR / "sample_handwriting.png",
        HANDWRITING_DIR / "sample_signature_real.png",
        HANDWRITING_DIR / "sample_signature.png",
        HANDWRITING_DIR / "sample_signature.jpg",
    ]
    reference_found = [str(p) for p in reference_candidates if p.exists()]

    return {
        "status": "ok",
        "service": "handwriting_simulation_service",
        "engine_version": "V14_SIGNATURE_PLUS_V13_2_REAL_INK_ENGINE",
        "runtime_dir": str(HANDWRITING_DIR),
        "output_dir": str(OUTPUT_DIR),
        "identity_dir": str(IDENTITY_DIR),
        "identity_profiles": len(profiles),
        "completed_outputs": len(outputs),
        "reference_images_found": reference_found,
        "dependencies": {
            "pymupdf": fitz is not None,
            "pillow": Image is not None,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def example_payload() -> Dict[str, Any]:
    return {
        "buyer_rfq_number": "TEST-V13-REAL-INK-001",
        "page_size": "A4",
        "writer_id": "LMCP_REAL_INK_WRITER",
        "line_ink_job_id": "REAL-HANDWRITING",
        "ink_color": "blue",
        "debug": True,
        "reference_image": "runtime/handwriting_simulation/clean_ink_cropped.png",
        "fields": [
            {
                "page": 1,
                "x": 120,
                "y": 720,
                "text": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                "font_size": 13,
            },
            {
                "page": 1,
                "x": 120,
                "y": 695,
                "text": "Lechesa Manaba",
                "font_size": 13,
            },
            {
                "page": 1,
                "x": 120,
                "y": 670,
                "text": "Director",
                "font_size": 13,
            },
        ],
    }


if __name__ == "__main__":
    print(json.dumps(complete_handwriting_form(example_payload()), indent=2))
