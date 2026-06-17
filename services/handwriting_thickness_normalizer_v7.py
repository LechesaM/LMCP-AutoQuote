from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
from PIL import Image


RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
LINE_INK_V5_DIR = HANDWRITING_DIR / "line_ink_v5"
NORMALIZED_V7_DIR = HANDWRITING_DIR / "normalized_ink_v7"

NORMALIZED_V7_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(value: Any, fallback: str = "UNKNOWN") -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def _stroke_density(alpha: np.ndarray) -> float:
    total = alpha.shape[0] * alpha.shape[1]
    if total <= 0:
        return 0.0
    return float(np.count_nonzero(alpha > 20)) / float(total)


def normalize_ink_png_v7(
    input_path: str | Path,
    output_path: str | Path,
    *,
    target_density: float = 0.065,
    darken_factor: float = 0.82,
    max_dilate_iterations: int = 2,
) -> Dict[str, Any]:
    """
    Normalizes handwriting PNG thickness using alpha-mask density.

    - Thin strokes get slightly dilated.
    - Ink is gently darkened.
    - Transparent background is preserved.
    """
    src = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        return {"status": "error", "message": f"Input file not found: {src}"}

    img = Image.open(src).convert("RGBA")
    arr = np.array(img)

    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]

    before_density = _stroke_density(alpha)

    mask = alpha.copy()
    iterations = 0

    if before_density > 0 and before_density < target_density:
        ratio = target_density / max(before_density, 0.0001)
        iterations = min(max_dilate_iterations, max(1, int(round(ratio - 1))))

    if iterations > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        mask = cv2.dilate(mask, kernel, iterations=iterations)
        mask = cv2.GaussianBlur(mask, (3, 3), 0)

    # Darken ink but preserve texture.
    rgb = np.clip(rgb * float(darken_factor), 0, 255).astype(np.uint8)

    out_arr = np.dstack([rgb, mask]).astype(np.uint8)
    Image.fromarray(out_arr, mode="RGBA").save(out)

    return {
        "status": "ok",
        "input_path": str(src),
        "output_path": str(out),
        "before_density": before_density,
        "after_density": _stroke_density(mask),
        "dilate_iterations": iterations,
        "target_density": target_density,
        "darken_factor": darken_factor,
    }


def normalize_line_ink_job_v7(
    *,
    job_id: str = "REAL-HANDWRITING",
    target_density: float = 0.065,
    darken_factor: float = 0.82,
) -> Dict[str, Any]:
    """
    Normalizes all line_*.png assets from V5 into normalized_ink_v7/<job_id>/.
    """
    safe_job = _safe_filename(job_id)
    source_dir = LINE_INK_V5_DIR / safe_job
    out_dir = NORMALIZED_V7_DIR / safe_job
    out_dir.mkdir(parents=True, exist_ok=True)

    if not source_dir.exists():
        return {
            "status": "error",
            "message": f"Line ink source directory not found: {source_dir}",
            "job_id": job_id,
        }

    assets = []
    for src in sorted(source_dir.glob("line_*.png")):
        out = out_dir / src.name
        result = normalize_ink_png_v7(
            src,
            out,
            target_density=target_density,
            darken_factor=darken_factor,
        )
        assets.append(result)

    manifest = {
        "status": "ok",
        "engine": "normalized_ink_v7",
        "job_id": job_id,
        "source_dir": str(source_dir),
        "output_dir": str(out_dir),
        "asset_count": len(assets),
        "assets": assets,
        "settings": {
            "target_density": target_density,
            "darken_factor": darken_factor,
        },
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def resolve_normalized_line_asset_v7(
    *,
    job_id: str = "REAL-HANDWRITING",
    line_index: Optional[int] = None,
) -> Optional[Path]:
    if not line_index:
        return None

    safe_job = _safe_filename(job_id)
    out_dir = NORMALIZED_V7_DIR / safe_job
    asset = out_dir / f"line_{int(line_index):03d}.png"

    if asset.exists():
        return asset

    normalize_line_ink_job_v7(job_id=job_id)

    return asset if asset.exists() else None
