"""
LMCP AutoQuote - V14 Signature Intelligence Engine

Drop-in target:
    app/services/handwriting_signature_engine.py

Purpose:
    Adds signature intelligence on top of the V13.2 real-ink handwriting engine.

What it does:
    - Detects signature-like fields by text / label_hint / field_name.
    - Converts those fields into signature overlay instructions.
    - Loads a real signature image from:
        runtime/handwriting_simulation/signature.png
        runtime/handwriting_simulation/sample_signature_real.png
        runtime/handwriting_simulation/sample_signature.png
        runtime/handwriting_simulation/sample_signature.jpg
    - Cleans white background into transparent alpha.
    - Recolors to requested black/blue ink.
    - Applies natural scale, opacity, and slight rotation.
    - Can be used independently or from handwriting_simulation_service.py.

Important:
    This engine does not generate a fake signature from text.
    It only places a provided real signature/reference image.
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from PIL import Image, ImageFilter, ImageOps
except Exception as exc:  # pragma: no cover
    Image = None
    ImageFilter = None
    ImageOps = None
    PIL_IMPORT_ERROR = exc
else:
    PIL_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
HANDWRITING_DIR = RUNTIME_DIR / "handwriting_simulation"
SIGNATURE_DEBUG_DIR = HANDWRITING_DIR / "signature_debug"
SIGNATURE_DEBUG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SignatureInstruction:
    is_signature: bool
    page: int
    x: float
    y: float
    width: float = 180.0
    height: float = 58.0
    signature_image: Optional[str] = None
    ink_color: Any = "black"
    opacity: float = 0.96
    rotation_degrees: float = 0.0
    detected_reason: str = ""
    engine_version: str = "V14_1_CLEAN_SIGNATURE_INTELLIGENCE"


def _safe_slug(value: Any, fallback: str = "signature") -> str:
    raw = str(value or fallback).strip()
    raw = unicodedata.normalize("NFKD", raw)
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-._")
    return raw[:90] or fallback


def _stable_int_seed(*parts: Any) -> int:
    joined = "::".join(str(p) for p in parts if p is not None)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_ink_color(value: Any, fallback: Tuple[int, int, int, int] = (18, 18, 20, 245)) -> Tuple[int, int, int, int]:
    if value is None:
        return fallback

    if isinstance(value, (list, tuple)) and len(value) in (3, 4):
        vals = [int(_clamp(float(v), 0, 255)) for v in value]
        if len(vals) == 3:
            vals.append(245)
        return tuple(vals)  # type: ignore[return-value]

    if isinstance(value, str):
        s = value.strip().lower()
        if s.startswith("#"):
            s = s[1:]
            if len(s) == 6:
                return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (245,)
            if len(s) == 8:
                return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]

        named = {
            "black": (18, 18, 20, 245),
            "pen-black": (12, 12, 14, 235),
            "soft-black": (28, 28, 30, 230),
            "blue": (24, 47, 132, 245),
            "darkblue": (12, 35, 110, 245),
            "navy": (8, 28, 92, 245),
        }
        return named.get(s, fallback)

    return fallback


def resolve_signature_image(payload: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    payload = payload or {}

    raw = (
        payload.get("signature_image")
        or payload.get("signature_path")
        or payload.get("director_signature")
        or payload.get("signature_reference")
    )

    candidates = []
    if raw:
        p = Path(str(raw))
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        candidates.append(p)

    candidates.extend(
        [
            HANDWRITING_DIR / "signature.png",
            HANDWRITING_DIR / "director_signature.png",
            HANDWRITING_DIR / "sample_signature_real.png",
            HANDWRITING_DIR / "sample_signature.png",
            HANDWRITING_DIR / "sample_signature.jpg",
            PROJECT_ROOT / "app" / "assets" / "signatures" / "director.png",
        ]
    )

    for path in candidates:
        if path.exists() and path.is_file():
            return path

    return None


def is_signature_field(field: Any) -> Tuple[bool, str]:
    """
    Accepts either dataclass-like field or dict.
    """
    def get(name: str, default: Any = "") -> Any:
        if isinstance(field, dict):
            return field.get(name, default)
        return getattr(field, name, default)

    text = str(get("text", "") or "")
    field_name = str(get("field_name", "") or "")
    label_hint = str(get("label_hint", "") or "")

    haystack = " ".join([text, field_name, label_hint]).lower()
    haystack = re.sub(r"[^a-z0-9\s]", " ", haystack)
    haystack = re.sub(r"\s+", " ", haystack).strip()

    signature_terms = [
        "signature",
        "sign here",
        "signatory",
        "authorised signatory",
        "authorized signatory",
        "signature of bidder",
        "signature of tenderer",
        "signature of authorised",
        "signature of authorized",
        "signed by",
        "signed at",
    ]

    for term in signature_terms:
        if term in haystack:
            return True, f"matched:{term}"

    # Avoid treating normal Director / Name fields as signatures.
    return False, "no-signature-keyword"


def make_signature_instruction(field: Any, payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    payload = payload or {}
    ok, reason = is_signature_field(field)
    if not ok:
        return None

    def get(name: str, default: Any = None) -> Any:
        if isinstance(field, dict):
            return field.get(name, default)
        return getattr(field, name, default)

    sig_path = resolve_signature_image(payload)
    if not sig_path:
        return {
            "is_signature": True,
            "status": "missing_signature_image",
            "reason": reason,
            "message": "Signature field detected, but no signature image was found.",
        }

    width = float(get("max_width", None) or get("width", None) or payload.get("signature_width") or 180)
    height = float(get("height", None) or payload.get("signature_height") or 58)

    seed = _stable_int_seed(
        payload.get("buyer_rfq_number"),
        get("page", 1),
        get("x", 0),
        get("y", 0),
        str(sig_path),
    )
    rng = random.Random(seed)

    inst = SignatureInstruction(
        is_signature=True,
        page=int(get("page", 1) or 1),
        x=float(get("x", 0) or 0),
        y=float(get("y", 0) or 0),
        width=width,
        height=height,
        signature_image=str(sig_path),
        ink_color=payload.get("signature_ink_color") or payload.get("ink_color") or "black",
        opacity=float(payload.get("signature_opacity") or 0.96),
        rotation_degrees=float(payload.get("signature_rotation", rng.uniform(-1.2, 1.2))),
        detected_reason=reason,
    )
    return asdict(inst)


def apply_signature_if_needed(field: Any, payload: Optional[Dict[str, Any]] = None) -> Any:
    """
    Compatibility helper for services that loop through fields.

    If a field is signature-like, it returns a dict with:
        text=""
        is_signature=True
        signature_instruction={...}

    If not, it returns the field unchanged.
    """
    instruction = make_signature_instruction(field, payload)
    if not instruction or instruction.get("status") == "missing_signature_image":
        return field

    if isinstance(field, dict):
        out = dict(field)
    else:
        out = dict(getattr(field, "__dict__", {}) or {})

    out["text"] = ""
    out["is_signature"] = True
    out["signature_instruction"] = instruction
    out["field_type"] = "signature"
    return out


def clean_signature_to_alpha(signature_path: Path) -> "Image.Image":
    """
    V14.1 clean-ink extraction for signature placement.

    Fixes the pasted-photo look by removing grey paper background and keeping
    only dark ink strokes as alpha.
    """
    if Image is None or ImageOps is None:
        raise RuntimeError(f"Pillow is not available: {PIL_IMPORT_ERROR}")

    img = Image.open(signature_path).convert("RGBA")

    # Flatten against white for scanned/photographed signatures.
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(bg, img).convert("RGB")
    gray = ImageOps.grayscale(flat)

    # Estimate paper background from bright pixels and subtract it.
    # This handles grey paper and uneven lighting better than a fixed threshold.
    hist = gray.histogram()
    total = sum(hist) or 1
    cumulative = 0
    paper_level = 245
    for i in range(255, -1, -1):
        cumulative += hist[i]
        if cumulative / total >= 0.58:
            paper_level = i
            break

    # Build alpha only from pixels significantly darker than paper.
    # Soft ramp keeps pen edges natural but removes rectangular paper.
    cutoff = max(115, paper_level - 42)
    alpha = gray.point(
        lambda p: 0 if p >= cutoff else int(_clamp((cutoff - p) * 5.2, 0, 255))
    )

    # Remove weak background noise.
    alpha = alpha.point(lambda p: 0 if p < 28 else p)

    # Slightly connect ink, then soften edges.
    try:
        alpha = alpha.filter(ImageFilter.MaxFilter(3))
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=0.35))
        alpha = alpha.point(lambda p: 0 if p < 18 else int(_clamp(p * 1.08, 0, 255)))
    except Exception:
        pass

    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.putalpha(alpha)

    bbox = out.getchannel("A").getbbox()
    if bbox:
        l, t, r, b = bbox
        pad = 10
        l = max(0, l - pad)
        t = max(0, t - pad)
        r = min(out.size[0], r + pad)
        b = min(out.size[1], b + pad)
        out = out.crop((l, t, r, b))

    return out


def render_signature_asset(
    instruction: Dict[str, Any],
    debug_name: str = "signature",
) -> "Image.Image":
    """
    Returns transparent RGBA image ready to alpha_composite onto a page overlay.
    """
    if Image is None or ImageFilter is None:
        raise RuntimeError(f"Pillow is not available: {PIL_IMPORT_ERROR}")

    sig_path = Path(str(instruction.get("signature_image") or ""))
    if not sig_path.exists():
        raise FileNotFoundError(f"Signature image not found: {sig_path}")

    ink = parse_ink_color(instruction.get("ink_color") or "black")
    opacity = float(instruction.get("opacity") or 0.96)

    sig = clean_signature_to_alpha(sig_path)

    target_w = int(max(20, round(float(instruction.get("width") or 180))))
    target_h = int(max(12, round(float(instruction.get("height") or 58))))

    scale = min(target_w / max(1, sig.size[0]), target_h / max(1, sig.size[1]))
    new_w = int(max(1, round(sig.size[0] * scale)))
    new_h = int(max(1, round(sig.size[1] * scale)))
    sig = sig.resize((new_w, new_h), Image.Resampling.LANCZOS)

    alpha = sig.getchannel("A").point(lambda p: int(_clamp(p * opacity, 0, 255)))

    colored = Image.new("RGBA", sig.size, ink)
    colored.putalpha(alpha)

    # Slight realistic softness.
    colored = colored.filter(ImageFilter.GaussianBlur(radius=0.10))

    angle = float(instruction.get("rotation_degrees") or 0.0)
    if abs(angle) > 0.01:
        colored = colored.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    debug_path = SIGNATURE_DEBUG_DIR / f"{_safe_slug(debug_name)}__v14_signature_asset.png"
    try:
        colored.save(debug_path)
    except Exception:
        pass

    return colored


def get_signature_engine_status() -> Dict[str, Any]:
    sig_path = resolve_signature_image({})
    return {
        "status": "ok",
        "service": "handwriting_signature_engine",
        "engine_version": "V14_1_CLEAN_SIGNATURE_INTELLIGENCE",
        "signature_image_found": str(sig_path) if sig_path else None,
        "signature_debug_dir": str(SIGNATURE_DEBUG_DIR),
        "dependencies": {
            "pillow": Image is not None,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def example_instruction() -> Dict[str, Any]:
    return {
        "is_signature": True,
        "page": 1,
        "x": 120,
        "y": 650,
        "width": 180,
        "height": 58,
        "signature_image": str(resolve_signature_image({}) or HANDWRITING_DIR / "signature.png"),
        "ink_color": "black",
        "opacity": 0.96,
        "rotation_degrees": -0.45,
        "detected_reason": "example",
        "engine_version": "V14_1_CLEAN_SIGNATURE_INTELLIGENCE",
    }


if __name__ == "__main__":
    print(get_signature_engine_status())
