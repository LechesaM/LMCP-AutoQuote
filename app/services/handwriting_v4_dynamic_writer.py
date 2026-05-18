from __future__ import annotations

import math
import random
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont


RUNTIME_DIR = Path("runtime")
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
DYNAMIC_DIR = HANDWRITING_DIR / "dynamic_v4"
DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)


DEFAULT_V4_STYLE = {
    "font_size": 24,
    "ink_gray": 55,
    "opacity": 230,
    "jitter_x": 0.8,
    "jitter_y": 1.2,
    "letter_spacing": 1.2,
    "word_spacing": 8,
    "line_gap": 10,
    "rotation_degrees": 0.5,
    "blur_radius": 0.10,
    "max_chars_per_line": 42,
    "canvas_padding": 18,
}


def _safe_filename(value: Any, fallback: str = "dynamic-v4") -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def _find_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
        "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
        "/Library/Fonts/Arial Italic.ttf",
    ]
    for p in candidates:
        try:
            fp = Path(p)
            if fp.exists():
                return ImageFont.truetype(str(fp), font_size)
        except Exception:
            pass
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if not text:
        return 1, 1
    box = draw.textbbox((0, 0), text, font=font)
    return max(1, box[2] - box[0]), max(1, box[3] - box[1])


def _wrap_text(text: str, max_chars: int) -> List[str]:
    text = str(text or "").strip()
    if not text:
        return [""]
    lines: List[str] = []
    for raw in text.splitlines():
        lines.extend(textwrap.wrap(raw, width=max(8, int(max_chars)), break_long_words=False) or [""])
    return lines or [""]


def render_dynamic_handwriting_png(
    text: str,
    *,
    output_path: str | Path,
    style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    style = {**DEFAULT_V4_STYLE, **(style or {})}

    font_size = int(style.get("font_size") or 24)
    font = _find_font(font_size)
    padding = int(style.get("canvas_padding") or 18)
    max_chars = int(style.get("max_chars_per_line") or 42)
    line_gap = int(style.get("line_gap") or 10)
    letter_spacing = float(style.get("letter_spacing") or 1.2)
    word_spacing = float(style.get("word_spacing") or 8)
    ink_gray = int(max(0, min(255, int(style.get("ink_gray") or 55))))
    opacity = int(max(20, min(255, int(style.get("opacity") or 230))))

    lines = _wrap_text(text, max_chars)
    tmp = Image.new("RGBA", (10, 10), (255, 255, 255, 0))
    d = ImageDraw.Draw(tmp)

    line_widths: List[int] = []
    line_heights: List[int] = []

    for line in lines:
        w = 0
        h = 1
        for ch in line:
            cw, chh = _measure(d, ch, font)
            w += cw + (word_spacing if ch == " " else letter_spacing)
            h = max(h, chh)
        line_widths.append(max(1, int(w)))
        line_heights.append(max(1, int(h)))

    canvas_w = max(line_widths + [1]) + padding * 2
    canvas_h = sum(line_heights) + line_gap * max(0, len(lines) - 1) + padding * 2

    img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    y = padding
    for idx, line in enumerate(lines):
        x = padding + random.uniform(-1.5, 1.5)
        wave_seed = random.uniform(-0.8, 0.8)
        for char_index, ch in enumerate(line):
            cw, _ = _measure(draw, ch, font)
            jx = random.uniform(-float(style["jitter_x"]), float(style["jitter_x"]))
            jy = random.uniform(-float(style["jitter_y"]), float(style["jitter_y"]))
            wave = math.sin((char_index / 3.5) + wave_seed) * 0.7
            draw.text((x + jx, y + jy + wave), ch, font=font, fill=(ink_gray, ink_gray, ink_gray, opacity))
            x += cw + (word_spacing if ch == " " else letter_spacing)
        y += line_heights[idx] + line_gap

    blur = float(style.get("blur_radius") or 0)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))

    rot = float(style.get("rotation_degrees") or 0)
    if rot:
        img = img.rotate(random.uniform(-rot, rot), expand=True, resample=Image.Resampling.BICUBIC)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)

    return {"status": "ok", "output_path": str(output_path), "width": img.size[0], "height": img.size[1]}


def build_dynamic_field_image(
    *,
    buyer_rfq_number: str,
    field_index: int,
    text: str,
    style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    safe = _safe_filename(buyer_rfq_number)
    out = DYNAMIC_DIR / safe / f"field_{field_index:03d}.png"
    return render_dynamic_handwriting_png(text, output_path=out, style=style)
