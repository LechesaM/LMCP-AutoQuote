from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
from PIL import Image


DEFAULT_OUTPUT_ROOT = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "clean_ink_v3"


@dataclass
class CleanInkExtractionResult:
    status: str
    job_id: str
    source_path: str
    output_dir: str
    original_png: str
    normalized_png: str
    ink_mask_png: str
    clean_ink_transparent_png: str
    clean_ink_cropped_png: str
    metadata_json: str
    bbox: Dict[str, int]
    ink_pixel_count: int
    message: str


def _safe_job_id(value: Optional[str] = None) -> str:
    raw = value or f"CLEAN-INK-V3-{uuid.uuid4().hex[:10].upper()}"
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-")
    return raw or f"CLEAN-INK-V3-{uuid.uuid4().hex[:10].upper()}"


def _ensure_image(input_path: Path) -> Image.Image:
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    img = Image.open(input_path)

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    if img.mode == "RGBA":
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img).convert("RGB")

    return img.convert("RGB")


def _resize_if_huge(img: Image.Image, max_side: int = 2600) -> Image.Image:
    w, h = img.size
    longest = max(w, h)

    if longest <= max_side:
        return img

    scale = max_side / float(longest)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def _normalize_background(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (0, 0), sigmaX=25, sigmaY=25)
    normalized = cv2.divide(gray, blur, scale=255)

    normalized = cv2.normalize(normalized, None, 0, 255, cv2.NORM_MINMAX)
    normalized = cv2.fastNlMeansDenoising(
        normalized,
        None,
        h=7,
        templateWindowSize=7,
        searchWindowSize=21,
    )

    return normalized


def _extract_ink_mask(gray_normalized: np.ndarray, *, sensitivity: int = 38) -> np.ndarray:
    sensitivity = int(max(20, min(70, sensitivity)))

    adaptive = cv2.adaptiveThreshold(
        gray_normalized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        41,
        12,
    )

    global_threshold_value = max(0, 255 - sensitivity)
    _, global_mask = cv2.threshold(
        gray_normalized,
        global_threshold_value,
        255,
        cv2.THRESH_BINARY_INV,
    )

    mask = cv2.bitwise_or(adaptive, global_mask)

    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    kernel_join = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_small, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_join, iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cleaned = np.zeros_like(mask)

    for label in range(1, num_labels):
        x, y, w, h, area = stats[label]

        if area < 8:
            continue
        if w <= 1 or h <= 1:
            continue
        if area > (mask.shape[0] * mask.shape[1] * 0.45):
            continue

        cleaned[labels == label] = 255

    cleaned = cv2.dilate(cleaned, kernel_small, iterations=1)
    return cleaned


def _bbox_from_mask(mask: np.ndarray, padding: int = 14) -> Tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)

    if len(xs) == 0 or len(ys) == 0:
        return 0, 0, mask.shape[1], mask.shape[0]

    x1 = max(0, int(xs.min()) - padding)
    y1 = max(0, int(ys.min()) - padding)
    x2 = min(mask.shape[1], int(xs.max()) + padding)
    y2 = min(mask.shape[0], int(ys.max()) + padding)

    if x2 <= x1:
        x2 = min(mask.shape[1], x1 + 1)

    if y2 <= y1:
        y2 = min(mask.shape[0], y1 + 1)

    return x1, y1, x2, y2


def _make_transparent_ink_rgba(
    bgr: np.ndarray,
    mask: np.ndarray,
    ink_darkening: float = 0.74,
) -> Image.Image:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    rgb = np.clip(rgb * float(ink_darkening), 0, 255).astype(np.uint8)

    alpha = cv2.GaussianBlur(mask.copy(), (3, 3), 0)
    rgba = np.dstack([rgb, alpha]).astype(np.uint8)

    return Image.fromarray(rgba, mode="RGBA")


def extract_clean_ink_v3(
    input_path: str | Path,
    *,
    job_id: Optional[str] = None,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    sensitivity: int = 38,
    crop_padding: int = 14,
    max_side: int = 2600,
) -> Dict[str, Any]:
    src = Path(input_path)
    output_root = Path(output_root)

    job = _safe_job_id(job_id)
    out_dir = output_root / job
    out_dir.mkdir(parents=True, exist_ok=True)

    img = _ensure_image(src)
    img = _resize_if_huge(img, max_side=max_side)

    original_png = out_dir / "original.png"
    normalized_png = out_dir / "normalized.png"
    ink_mask_png = out_dir / "ink_mask.png"
    clean_png = out_dir / "clean_ink_transparent.png"
    cropped_png = out_dir / "clean_ink_cropped.png"
    metadata_json = out_dir / "metadata.json"

    img.save(original_png)

    rgb = np.array(img)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    normalized = _normalize_background(bgr)
    mask = _extract_ink_mask(normalized, sensitivity=sensitivity)

    x1, y1, x2, y2 = _bbox_from_mask(mask, padding=crop_padding)

    Image.fromarray(normalized).save(normalized_png)
    Image.fromarray(mask).save(ink_mask_png)

    transparent = _make_transparent_ink_rgba(bgr, mask)
    transparent.save(clean_png)

    cropped = transparent.crop((x1, y1, x2, y2))
    cropped.save(cropped_png)

    ink_pixel_count = int(np.count_nonzero(mask))

    result = CleanInkExtractionResult(
        status="ok" if ink_pixel_count > 0 else "warning",
        job_id=job,
        source_path=str(src),
        output_dir=str(out_dir),
        original_png=str(original_png),
        normalized_png=str(normalized_png),
        ink_mask_png=str(ink_mask_png),
        clean_ink_transparent_png=str(clean_png),
        clean_ink_cropped_png=str(cropped_png),
        metadata_json=str(metadata_json),
        bbox={
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "width": x2 - x1,
            "height": y2 - y1,
        },
        ink_pixel_count=ink_pixel_count,
        message=(
            "Clean ink extracted successfully."
            if ink_pixel_count > 0
            else "No strong ink detected. Try higher sensitivity or a clearer sample."
        ),
    )

    metadata = asdict(result)
    metadata["settings"] = {
        "sensitivity": sensitivity,
        "crop_padding": crop_padding,
        "max_side": max_side,
        "version": "v3-clean-ink-extraction",
    }

    metadata_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return metadata


def extract_clean_ink_from_latest_sample(
    *,
    sample_dir: str | Path = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation",
    job_id: Optional[str] = None,
    sensitivity: int = 38,
) -> Dict[str, Any]:
    root = Path(sample_dir)

    candidates = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        candidates.extend(root.rglob(ext))

    candidates = [
        p
        for p in candidates
        if "clean_ink_v3" not in str(p)
        and "outputs" not in str(p)
        and "glyph_form_outputs" not in str(p)
    ]

    if not candidates:
        raise FileNotFoundError(f"No handwriting sample image found under: {root}")

    newest = max(candidates, key=lambda p: p.stat().st_mtime)

    return extract_clean_ink_v3(
        newest,
        job_id=job_id,
        sensitivity=sensitivity,
    )
