from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image, ImageFilter


RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
NORMALIZED_V7_DIR = HANDWRITING_DIR / "normalized_ink_v7"
PEN_FLOW_V8_DIR = HANDWRITING_DIR / "pen_flow_v8"

PEN_FLOW_V8_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(value: Any, fallback: str = "UNKNOWN") -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def _density(alpha: np.ndarray) -> float:
    total = alpha.shape[0] * alpha.shape[1]
    if total <= 0:
        return 0.0
    return float(np.count_nonzero(alpha > 20)) / float(total)


def apply_pen_flow_v8(
    input_path: str | Path,
    output_path: str | Path,
    *,
    pressure_variation: float = 0.10,
    edge_softness: float = 0.25,
    ink_texture: float = 0.06,
    darken_factor: float = 0.92,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Adds subtle natural pen-flow variation to an existing transparent handwriting PNG.
    Transparent background is preserved.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    src = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        return {"status": "error", "message": f"Input file not found: {src}"}

    img = Image.open(src).convert("RGBA")
    arr = np.array(img).astype(np.float32)

    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    before_density = _density(alpha.astype(np.uint8))

    h, w = alpha.shape
    x = np.linspace(0, np.pi * random.uniform(1.2, 2.4), max(1, w))
    wave = 1.0 + (np.sin(x + random.uniform(-1.0, 1.0)) * pressure_variation)
    wave = np.tile(wave, (h, 1))

    noise = np.random.normal(loc=1.0, scale=max(0.0, ink_texture), size=(h, w))
    factor = np.clip(wave * noise, 0.72, 1.22)

    alpha2 = np.clip(alpha * factor, 0, 255)

    if edge_softness > 0:
        alpha_img = Image.fromarray(alpha2.astype(np.uint8), mode="L")
        alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=float(edge_softness)))
        alpha2 = np.array(alpha_img).astype(np.float32)

    rgb2 = np.clip(rgb * float(darken_factor), 0, 255)

    out_arr = np.dstack([rgb2, alpha2]).astype(np.uint8)
    Image.fromarray(out_arr, mode="RGBA").save(out)

    return {
        "status": "ok",
        "engine": "pen_flow_v8",
        "input_path": str(src),
        "output_path": str(out),
        "before_density": before_density,
        "after_density": _density(alpha2.astype(np.uint8)),
        "settings": {
            "pressure_variation": pressure_variation,
            "edge_softness": edge_softness,
            "ink_texture": ink_texture,
            "darken_factor": darken_factor,
            "seed": seed,
        },
    }


def apply_pen_flow_to_job_v8(
    *,
    job_id: str = "REAL-HANDWRITING",
    pressure_variation: float = 0.10,
    edge_softness: float = 0.25,
    ink_texture: float = 0.06,
    darken_factor: float = 0.92,
) -> Dict[str, Any]:
    safe_job = _safe_filename(job_id)
    src_dir = NORMALIZED_V7_DIR / safe_job
    out_dir = PEN_FLOW_V8_DIR / safe_job
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        return {
            "status": "error",
            "message": f"V7 normalized source folder not found: {src_dir}",
            "job_id": job_id,
        }

    assets = []
    for idx, src in enumerate(sorted(src_dir.glob("line_*.png")), start=1):
        out = out_dir / src.name
        result = apply_pen_flow_v8(
            src,
            out,
            pressure_variation=pressure_variation,
            edge_softness=edge_softness,
            ink_texture=ink_texture,
            darken_factor=darken_factor,
            seed=idx * 1007,
        )
        assets.append(result)

    manifest = {
        "status": "ok",
        "engine": "pen_flow_v8",
        "job_id": job_id,
        "source_dir": str(src_dir),
        "output_dir": str(out_dir),
        "asset_count": len(assets),
        "assets": assets,
        "settings": {
            "pressure_variation": pressure_variation,
            "edge_softness": edge_softness,
            "ink_texture": ink_texture,
            "darken_factor": darken_factor,
        },
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def resolve_pen_flow_asset_v8(
    *,
    job_id: str = "REAL-HANDWRITING",
    line_index: Optional[int] = None,
) -> Optional[Path]:
    if not line_index:
        return None

    safe_job = _safe_filename(job_id)
    asset = PEN_FLOW_V8_DIR / safe_job / f"line_{int(line_index):03d}.png"

    if asset.exists():
        return asset

    apply_pen_flow_to_job_v8(job_id=job_id)

    return asset if asset.exists() else None
