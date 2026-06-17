from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image


RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
CLEAN_INK_V3_DIR = HANDWRITING_DIR / "clean_ink_v3"
LINE_INK_V5_DIR = HANDWRITING_DIR / "line_ink_v5"
NORMALIZED_INK_V7_DIR = HANDWRITING_DIR / "normalized_ink_v7"

LINE_INK_V5_DIR.mkdir(parents=True, exist_ok=True)
NORMALIZED_INK_V7_DIR.mkdir(parents=True, exist_ok=True)


DEFAULT_LINE_LABELS = [
    "Lechesa Manaba",
    "Director",
    "Lechesa Manaba Consulting and Projects (Pty) Ltd",
]


def _safe_filename(value: Any, fallback: str = "UNKNOWN") -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def _latest_clean_ink_for_job(job_id: str) -> Optional[Path]:
    job_dir = CLEAN_INK_V3_DIR / _safe_filename(job_id)
    for name in ("clean_ink_cropped.png", "clean_ink_transparent.png"):
        p = job_dir / name
        if p.exists() and p.is_file():
            return p
    return None


def _alpha_mask_from_rgba(path: Path) -> Tuple[Image.Image, np.ndarray]:
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    return img, alpha


def _merge_close_bands(bands: List[Tuple[int, int]], max_gap: int = 8) -> List[Tuple[int, int]]:
    if not bands:
        return []

    bands = sorted(bands, key=lambda b: b[0])
    merged: List[Tuple[int, int]] = [bands[0]]

    for y1, y2 in bands[1:]:
        py1, py2 = merged[-1]
        if y1 - py2 <= max_gap:
            merged[-1] = (py1, max(py2, y2))
        else:
            merged.append((y1, y2))

    return merged


def _split_large_band_by_valleys(alpha: np.ndarray, band: Tuple[int, int]) -> List[Tuple[int, int]]:
    """
    Attempts to split a tall merged handwriting block using horizontal ink-density valleys.

    This helps when a title/company block is close together. If there is no real visual
    valley, the function safely keeps the block together instead of damaging the ink.
    """
    y1, y2 = band
    height = int(y2 - y1)

    if height < 80:
        return [band]

    row_counts = np.count_nonzero(alpha[y1:y2, :] > 20, axis=1).astype(float)
    if len(row_counts) < 20 or float(row_counts.max()) <= 0:
        return [band]

    kernel_size = max(7, min(31, int(height / 12)))
    smooth = np.convolve(row_counts, np.ones(kernel_size) / kernel_size, mode="same")

    max_count = float(smooth.max())
    valley_threshold = max(3.0, max_count * 0.10)

    low_rows = np.where(smooth <= valley_threshold)[0]
    if len(low_rows) == 0:
        return [band]

    valleys: List[Tuple[int, int]] = []
    start = int(low_rows[0])
    prev = int(low_rows[0])

    for r in low_rows[1:]:
        r = int(r)
        if r - prev > 1:
            valleys.append((start, prev))
            start = r
        prev = r

    valleys.append((start, prev))

    split_points: List[int] = []
    for a, b in valleys:
        width = b - a + 1
        midpoint = (a + b) // 2

        if width < 6:
            continue
        if midpoint < 18 or midpoint > height - 18:
            continue

        split_points.append(y1 + midpoint)

    if not split_points:
        return [band]

    points = [y1] + split_points + [y2]
    out: List[Tuple[int, int]] = []

    for a, b in zip(points[:-1], points[1:]):
        if b - a >= 18:
            out.append((a, b))

    return out or [band]


def _find_line_bands(alpha: np.ndarray) -> List[Tuple[int, int]]:
    """
    Smart row-density line detector.

    It is conservative: it avoids destroying real handwriting when lines are too close.
    If two physical lines are touching or have no meaningful white valley, they remain
    one ink block.
    """
    row_counts = np.count_nonzero(alpha > 20, axis=1).astype(float)

    if len(row_counts) == 0 or float(row_counts.max()) <= 0:
        return []

    smooth = np.convolve(row_counts, np.ones(11) / 11, mode="same")
    threshold = max(4.0, float(smooth.max()) * 0.08)

    active_rows = np.where(smooth > threshold)[0]
    if len(active_rows) == 0:
        return []

    raw_bands: List[Tuple[int, int]] = []
    start = int(active_rows[0])
    prev = int(active_rows[0])

    max_gap_between_parts = 18

    for r in active_rows[1:]:
        r = int(r)
        if r - prev > max_gap_between_parts:
            raw_bands.append((start, prev))
            start = r
        prev = r

    raw_bands.append((start, prev))
    raw_bands = _merge_close_bands(raw_bands, max_gap=4)

    h = alpha.shape[0]
    expanded: List[Tuple[int, int]] = []

    for y1, y2 in raw_bands:
        if (y2 - y1) < 10:
            continue

        band = (max(0, y1 - 8), min(h, y2 + 10))
        split_bands = _split_large_band_by_valleys(alpha, band)

        for sy1, sy2 in split_bands:
            if (sy2 - sy1) >= 16:
                expanded.append((max(0, sy1 - 4), min(h, sy2 + 4)))

    return _merge_close_bands(expanded, max_gap=2)


def _clear_previous_line_assets(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("line_*.png"):
        try:
            p.unlink()
        except Exception:
            pass


def _normalize_asset_if_possible(
    *,
    job_id: str,
    line_index: int,
    raw_asset: Path,
    target_density: float = 0.075,
    darken_factor: float = 0.78,
) -> Optional[Path]:
    """
    Creates a V7-normalized version of a line asset if the V7 normalizer exists.

    This function lets existing V5 callers benefit from V7 without needing the
    overlay service to be patched first.
    """
    try:
        from app.services.handwriting_thickness_normalizer_v7 import normalize_ink_png_v7
    except Exception:
        return None

    if not raw_asset.exists():
        return None

    safe_job = _safe_filename(job_id)
    out_dir = NORMALIZED_INK_V7_DIR / safe_job
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"line_{int(line_index):03d}.png"

    result = normalize_ink_png_v7(
        raw_asset,
        out_path,
        target_density=target_density,
        darken_factor=darken_factor,
    )

    if result.get("status") != "ok" or not out_path.exists():
        return None

    # Update/append lightweight manifest for verification.
    manifest_path = out_dir / "manifest.json"
    try:
        manifest = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assets = manifest.get("assets") or []
        assets = [a for a in assets if int(a.get("index") or 0) != int(line_index)]
        assets.append(
            {
                "index": int(line_index),
                "source": str(raw_asset),
                "path": str(out_path),
                "normalization": result,
            }
        )
        assets = sorted(assets, key=lambda a: int(a.get("index") or 0))

        manifest = {
            "status": "ok",
            "engine": "normalized_ink_v7",
            "job_id": job_id,
            "output_dir": str(out_dir),
            "asset_count": len(assets),
            "assets": assets,
        }

        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception:
        pass

    return out_path


def build_line_ink_assets_v5(
    *,
    job_id: str = "REAL-HANDWRITING",
    labels: Optional[List[str]] = None,
    normalize_v7: bool = True,
    target_density: float = 0.075,
    darken_factor: float = 0.78,
) -> Dict[str, Any]:
    """
    Splits the real clean handwriting ink into line-level PNG assets.

    Output:
        runtime/handwriting_simulation/line_ink_v5/<job_id>/
            line_001.png
            line_002.png
            ...
            manifest.json

    If V7 is installed, normalized assets are also created:
        runtime/handwriting_simulation/normalized_ink_v7/<job_id>/
            line_001.png
            line_002.png
            manifest.json
    """
    labels = labels or DEFAULT_LINE_LABELS
    source = _latest_clean_ink_for_job(job_id)

    if not source:
        return {
            "status": "error",
            "message": f"No clean ink asset found for job_id={job_id}",
            "job_id": job_id,
        }

    img, alpha = _alpha_mask_from_rgba(source)
    bands = _find_line_bands(alpha)

    out_dir = LINE_INK_V5_DIR / _safe_filename(job_id)
    _clear_previous_line_assets(out_dir)

    assets: List[Dict[str, Any]] = []
    width, height = img.size

    for i, (y1, y2) in enumerate(bands, start=1):
        crop_alpha = alpha[y1:y2, :]
        cols = np.where(np.count_nonzero(crop_alpha > 20, axis=0) > 0)[0]

        if len(cols) == 0:
            continue

        x1 = max(0, int(cols.min()) - 8)
        x2 = min(width, int(cols.max()) + 10)

        y1p = max(0, int(y1) - 4)
        y2p = min(height, int(y2) + 6)

        cropped = img.crop((x1, y1p, x2, y2p))
        out_path = out_dir / f"line_{i:03d}.png"
        cropped.save(out_path)

        normalized_path: Optional[Path] = None
        if normalize_v7:
            normalized_path = _normalize_asset_if_possible(
                job_id=job_id,
                line_index=i,
                raw_asset=out_path,
                target_density=target_density,
                darken_factor=darken_factor,
            )

        label = labels[i - 1] if i - 1 < len(labels) else f"line_{i:03d}"

        assets.append(
            {
                "index": i,
                "label": label,
                "path": str(out_path),
                "normalized_path": str(normalized_path) if normalized_path else None,
                "bbox": {"x1": x1, "y1": y1p, "x2": x2, "y2": y2p},
                "width": cropped.size[0],
                "height": cropped.size[1],
            }
        )

    manifest = {
        "status": "ok",
        "engine": "line_ink_v5",
        "job_id": job_id,
        "source": str(source),
        "output_dir": str(out_dir),
        "normalized_output_dir": str(NORMALIZED_INK_V7_DIR / _safe_filename(job_id)),
        "line_count": len(assets),
        "assets": assets,
        "detector": {
            "method": "row_density_with_safe_valley_split",
            "notes": (
                "Conservative line detector. If title/company have no real white gap, "
                "they remain one physical ink block. V7 normalization is applied when available."
            ),
        },
        "normalization": {
            "v7_requested": bool(normalize_v7),
            "target_density": target_density,
            "darken_factor": darken_factor,
        },
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _load_manifest(job_id: str) -> Optional[Dict[str, Any]]:
    manifest_path = LINE_INK_V5_DIR / _safe_filename(job_id) / "manifest.json"

    if not manifest_path.exists():
        build_line_ink_assets_v5(job_id=job_id)

    if not manifest_path.exists():
        return None

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _resolve_from_asset(asset: Dict[str, Any], prefer_normalized: bool = True) -> Optional[Path]:
    if prefer_normalized:
        normalized = asset.get("normalized_path")
        if normalized:
            p = Path(str(normalized))
            if p.exists():
                return p

    raw = asset.get("path")
    if raw:
        p = Path(str(raw))
        if p.exists():
            return p

    return None


def resolve_line_asset_v5(
    *,
    job_id: str = "REAL-HANDWRITING",
    text: str = "",
    line_index: Optional[int] = None,
    prefer_normalized: bool = True,
) -> Optional[Path]:
    """
    Resolves the best line asset.

    By default, it prefers the V7 normalized line image if available, then falls
    back to the raw V5 line image.
    """
    manifest = _load_manifest(job_id)
    if not manifest:
        return None

    assets = manifest.get("assets") or []
    if not assets:
        return None

    if line_index:
        for asset in assets:
            if int(asset.get("index") or 0) == int(line_index):
                return _resolve_from_asset(asset, prefer_normalized=prefer_normalized)

    normalized_text = " ".join(str(text or "").lower().split())

    if normalized_text:
        for asset in assets:
            label = " ".join(str(asset.get("label") or "").lower().split())
            if label and (normalized_text == label or normalized_text in label or label in normalized_text):
                return _resolve_from_asset(asset, prefer_normalized=prefer_normalized)

    return None
