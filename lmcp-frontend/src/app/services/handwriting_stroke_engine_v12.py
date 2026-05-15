from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


RUNTIME_DIR = Path("runtime")
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
STROKE_V12_DIR = HANDWRITING_DIR / "stroke_v12"
STROKE_V12_DIR.mkdir(parents=True, exist_ok=True)


DEFAULT_V12_STYLE = {
    "font_size": 28,
    "ink_gray": 42,
    "opacity": 235,
    "canvas_padding": 22,

    # Layout
    "max_chars_per_line": 44,
    "line_gap": 12,
    "letter_spacing": 1.0,
    "word_spacing": 8.0,
    "baseline_drift": 1.4,

    # Natural motion
    "character_jitter_x": 0.85,
    "character_jitter_y": 1.10,
    "rotation_degrees": 0.70,
    "stroke_pressure_variation": 0.13,
    "stroke_edge_softness": 0.18,
    "micro_wobble": 0.55,
    "letter_variant_strength": 0.09,
    "ink_texture": 0.055,

    # Output fitting
    "max_width": 520,
    "max_height": 95,
}


def _safe_filename(value: Any, fallback: str = "stroke-v12") -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def _find_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Uses installed/custom fonts if available.
    Put a preferred handwriting font in app/assets/fonts/ and pass:
      style.stroke_font_path = "app/assets/fonts/YourFont.ttf"
    """
    candidates = [
        "app/assets/fonts/PatrickHand-Regular.ttf",
        "app/assets/fonts/Caveat-Regular.ttf",
        "app/assets/fonts/GloriaHallelujah-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
        "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    ]

    for p in candidates:
        try:
            path = Path(p)
            if path.exists():
                return ImageFont.truetype(str(path), font_size)
        except Exception:
            pass

    return ImageFont.load_default()


def _get_font(font_size: int, font_path: Optional[str] = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        try:
            p = Path(font_path)
            if p.exists():
                return ImageFont.truetype(str(p), font_size)
        except Exception:
            pass
    return _find_font(font_size)


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if not text:
        return 1, 1
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])


def _wrap_text(text: str, max_chars: int) -> List[str]:
    words = str(text or "").strip().split()
    if not words:
        return [""]

    lines: List[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines or [""]


def _apply_alpha_pressure(alpha: np.ndarray, strength: float, texture: float) -> np.ndarray:
    h, w = alpha.shape
    if h <= 0 or w <= 0:
        return alpha

    x = np.linspace(0, math.pi * random.uniform(1.1, 2.6), w)
    wave = 1.0 + np.sin(x + random.uniform(-1.0, 1.0)) * strength
    wave = np.tile(wave, (h, 1))

    noise = np.random.normal(1.0, max(0.0, texture), (h, w))
    out = alpha.astype(np.float32) * wave * noise
    return np.clip(out, 0, 255).astype(np.uint8)


def _roughen_alpha_edges(alpha: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return alpha

    h, w = alpha.shape
    noise = np.random.normal(0, amount * 28.0, (h, w))
    out = alpha.astype(np.float32) + noise * (alpha > 5)
    return np.clip(out, 0, 255).astype(np.uint8)


def _render_character(
    ch: str,
    font: ImageFont.ImageFont,
    ink_gray: int,
    opacity: int,
    style: Dict[str, Any],
) -> Image.Image:
    tmp = Image.new("RGBA", (160, 160), (255, 255, 255, 0))
    draw = ImageDraw.Draw(tmp)
    w, h = _measure(draw, ch, font)

    canvas_w = max(8, w + 18)
    canvas_h = max(8, h + 18)
    img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)

    variant = float(style.get("letter_variant_strength", 0.09))
    jitter_x = random.uniform(-variant * 5, variant * 5)
    jitter_y = random.uniform(-variant * 3, variant * 3)

    d.text((8 + jitter_x, 6 + jitter_y), ch, font=font, fill=(ink_gray, ink_gray, ink_gray, opacity))

    # Alpha-level stroke pressure and texture.
    arr = np.array(img).astype(np.uint8)
    alpha = arr[:, :, 3]
    alpha = _apply_alpha_pressure(
        alpha,
        strength=float(style.get("stroke_pressure_variation", 0.13)),
        texture=float(style.get("ink_texture", 0.055)),
    )
    alpha = _roughen_alpha_edges(alpha, amount=float(style.get("micro_wobble", 0.55)) * 0.08)

    # Mild edge softness.
    softness = float(style.get("stroke_edge_softness", 0.18))
    if softness > 0:
        alpha_img = Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(radius=softness))
        alpha = np.array(alpha_img)

    arr[:, :, 3] = alpha
    img = Image.fromarray(arr, mode="RGBA")

    # Per-character tiny rotation.
    rot = float(style.get("rotation_degrees", 0.70))
    if rot:
        img = img.rotate(random.uniform(-rot, rot), expand=True, resample=Image.Resampling.BICUBIC)

    return img


def render_stroke_text_v12(
    text: str,
    *,
    output_path: str | Path,
    style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    style = {**DEFAULT_V12_STYLE, **(style or {})}

    font_size = int(style.get("font_size") or 28)
    font_path = str(style.get("stroke_font_path") or "").strip() or None
    font = _get_font(font_size, font_path)

    ink_gray = int(max(0, min(255, int(style.get("ink_gray") or 42))))
    opacity = int(max(10, min(255, int(style.get("opacity") or 235))))

    max_chars = int(style.get("max_chars_per_line") or 44)
    padding = int(style.get("canvas_padding") or 22)
    line_gap = int(style.get("line_gap") or 12)
    letter_spacing = float(style.get("letter_spacing") or 1.0)
    word_spacing = float(style.get("word_spacing") or 8.0)
    drift = float(style.get("baseline_drift") or 1.4)
    jitter_x = float(style.get("character_jitter_x") or 0.85)
    jitter_y = float(style.get("character_jitter_y") or 1.10)

    lines = _wrap_text(text, max_chars)

    # Measure rough canvas.
    probe = Image.new("RGBA", (10, 10), (255, 255, 255, 0))
    pd = ImageDraw.Draw(probe)

    line_metrics: List[Tuple[int, int]] = []
    for line in lines:
        line_w = 0
        line_h = 1
        for ch in line:
            cw, chh = _measure(pd, ch, font)
            line_w += cw + (word_spacing if ch == " " else letter_spacing)
            line_h = max(line_h, chh + 20)
        line_metrics.append((max(1, int(line_w)), max(1, int(line_h))))

    canvas_w = max([m[0] for m in line_metrics] + [1]) + padding * 2 + 80
    canvas_h = sum([m[1] for m in line_metrics]) + line_gap * max(0, len(lines) - 1) + padding * 2 + 40

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))

    y = padding
    for line_idx, line in enumerate(lines):
        x = padding + random.uniform(-2.0, 2.0)
        wave_seed = random.uniform(-2.0, 2.0)

        for idx, ch in enumerate(line):
            if ch == " ":
                x += word_spacing + random.uniform(-1.0, 1.8)
                continue

            char_img = _render_character(ch, font, ink_gray, opacity, style)
            cw, chh = _measure(pd, ch, font)

            baseline_wave = math.sin((idx / 3.0) + wave_seed) * drift
            px = int(x + random.uniform(-jitter_x, jitter_x))
            py = int(y + baseline_wave + random.uniform(-jitter_y, jitter_y))

            canvas.alpha_composite(char_img, (px, py))

            # Slight variable writing spacing.
            x += cw + letter_spacing + random.uniform(-0.9, 1.6)

        y += line_metrics[line_idx][1] + line_gap

    # Crop to actual ink bbox.
    arr = np.array(canvas)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 4)

    if len(xs) > 0 and len(ys) > 0:
        x1 = max(0, int(xs.min()) - 12)
        y1 = max(0, int(ys.min()) - 12)
        x2 = min(canvas.size[0], int(xs.max()) + 14)
        y2 = min(canvas.size[1], int(ys.max()) + 14)
        canvas = canvas.crop((x1, y1, x2, y2))

    # Optional output max fitting is handled later by PDF renderer; keep full PNG here.
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)

    return {
        "status": "ok",
        "engine": "stroke_v12",
        "text": text,
        "output_path": str(output_path),
        "width": canvas.size[0],
        "height": canvas.size[1],
        "settings": {
            "font_size": font_size,
            "font_path": font_path,
            "baseline_drift": drift,
            "stroke_pressure_variation": style.get("stroke_pressure_variation"),
            "micro_wobble": style.get("micro_wobble"),
        },
    }


def build_stroke_field_image_v12(
    *,
    buyer_rfq_number: str,
    field_index: int,
    text: str,
    style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    safe_rfq = _safe_filename(buyer_rfq_number)
    out_dir = STROKE_V12_DIR / safe_rfq
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"field_{int(field_index):03d}.png"

    return render_stroke_text_v12(text, output_path=out_path, style=style)
