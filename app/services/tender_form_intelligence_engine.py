from __future__ import annotations

import io
import json
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.runtime_paths import PROJECT_ROOT, ensure_directories

ENGINE_VERSION = "V22.7.4_COMPANY_NAME_RECOVERY_LOCK_ENGINE"

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None


LOCAL_PROJECT_ROOT = Path.cwd().resolve()

RUNTIME_DIR = PROJECT_ROOT / "runtime" / "tender_form_intelligence"
COMPLETED_DIR = RUNTIME_DIR / "completed_forms"
DEBUG_DIR = RUNTIME_DIR / "debug"
PROFILE_DIR = RUNTIME_DIR / "stroke_profiles"

def ensure_tender_form_runtime_dirs() -> None:
    ensure_directories([RUNTIME_DIR, COMPLETED_DIR, DEBUG_DIR, PROFILE_DIR])


def _safe_filename(value: str, fallback: str = "FORM") -> str:
    value = str(value or "").strip() or fallback
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:90] or fallback


def _resolve_path(path_value: Union[str, Path, None]) -> Optional[Path]:
    if not path_value:
        return None

    raw = str(path_value).strip()
    if not raw:
        return None

    candidates: List[Path] = []
    p = Path(raw)
    candidates.append(p)

    if raw.startswith("/app/"):
        candidates.append(PROJECT_ROOT / raw.replace("/app/", "", 1))

    if not p.is_absolute():
        candidates.append(PROJECT_ROOT / raw)
        candidates.append(LOCAL_PROJECT_ROOT / raw)

    if "/runtime/" in raw:
        tail = raw.split("/runtime/", 1)[1]
        candidates.append(PROJECT_ROOT / "runtime" / tail)
        candidates.append(LOCAL_PROJECT_ROOT / "runtime" / tail)

    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except Exception:
            pass

    try:
        return candidates[0].resolve()
    except Exception:
        return candidates[0]


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _coerce_payload(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if isinstance(payload, dict):
        data.update(payload)
    data.update({k: v for k, v in kwargs.items() if v is not None})
    return data


def _default_values(payload: Dict[str, Any]) -> Dict[str, str]:
    return {
        "company_name": str(payload.get("company_name") or "Lechesa Manaba Consulting and Projects (Pty) Ltd"),
        "bidder_name": str(payload.get("bidder_name") or payload.get("company_name") or "Lechesa Manaba Consulting and Projects (Pty) Ltd"),
        "director_name": str(payload.get("director_name") or payload.get("representative_name") or "Lechesa Manaba"),
        "capacity": str(payload.get("capacity") or payload.get("designation") or "Director"),
        "date": str(payload.get("date") or datetime.now().strftime("%d/%m/%Y")),
        "buyer_rfq_number": str(payload.get("buyer_rfq_number") or payload.get("rfq_number") or ""),
        "buyer_name": str(payload.get("buyer_name") or ""),
        "bid_description": str(payload.get("bid_description") or payload.get("description") or payload.get("title") or ""),
    }


def _color_tuple(color: str) -> Tuple[int, int, int, int]:
    c = str(color or "black").strip().lower()
    if c in ("blue", "darkblue", "navy"):
        return (8, 30, 110, 255)
    if c == "red":
        return (140, 10, 10, 255)
    return (5, 5, 5, 255)


def _load_font(size: int) -> Any:
    if ImageFont is None:
        return None

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for fp in candidates:
        try:
            if Path(fp).exists():
                return ImageFont.truetype(fp, size=size)
        except Exception:
            pass

    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _make_handwriting_text_layer(
    text: str,
    font_size: int = 15,
    ink_color: str = "black",
    max_width_px: int = 520,
    max_height_px: int = 90,
) -> "Image.Image":
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required.")

    text = str(text or "").strip()
    font = _load_font(font_size)
    ink = _color_tuple(ink_color)

    canvas = Image.new("RGBA", (max_width_px, max_height_px), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)

    # Simple readable handwriting-like layer: slight offsets and variable alpha.
    x = 4
    y = max(2, int(max_height_px * 0.22))
    cursor = x

    for ch in text:
        if ch == " ":
            cursor += max(5, int(font_size * 0.35))
            continue

        try:
            bbox = draw.textbbox((0, 0), ch, font=font)
            cw = max(4, bbox[2] - bbox[0])
        except Exception:
            cw = int(font_size * 0.55)

        if cursor + cw > max_width_px - 5:
            break

        jitter_y = 0
        jitter_x = 0
        draw.text((cursor + jitter_x, y + jitter_y), ch, font=font, fill=ink)
        # soft second pass for ink strength
        draw.text((cursor + jitter_x + 0.25, y + jitter_y), ch, font=font, fill=(ink[0], ink[1], ink[2], 110))
        cursor += cw + 1

    return canvas


def _signature_candidates(path_value: Any) -> List[Path]:
    candidates: List[Path] = []
    p = _resolve_path(path_value)
    if p:
        candidates.append(p)

    names = [
        "signature.png",
        "sample_signature.png",
        "sample_signature_real.png",
        "sample_signature.jpg",
        "director.png",
    ]
    dirs = [
        PROJECT_ROOT / "runtime" / "handwriting_simulation",
        LOCAL_PROJECT_ROOT / "runtime" / "handwriting_simulation",
        PROJECT_ROOT / "app" / "assets" / "signatures",
        LOCAL_PROJECT_ROOT / "app" / "assets" / "signatures",
    ]
    for d in dirs:
        for n in names:
            candidates.append(d / n)

    return candidates


def _load_clean_signature(path_value: Any, ink_color: str = "black") -> Optional["Image.Image"]:
    if Image is None:
        return None

    ink = _color_tuple(ink_color)

    for path in _signature_candidates(path_value):
        try:
            if not path.exists() or not path.is_file():
                continue

            img = Image.open(str(path)).convert("RGBA")
            px = img.load()

            for y in range(img.height):
                for x in range(img.width):
                    r, g, b, a = px[x, y]
                    brightness = int((r + g + b) / 3)
                    spread = max(r, g, b) - min(r, g, b)
                    darkness = 255 - brightness

                    # Remove white and grey scanned-paper background.
                    if a < 20 or brightness > 170 or (brightness > 145 and spread < 28):
                        px[x, y] = (255, 255, 255, 0)
                    elif darkness > 30:
                        px[x, y] = (ink[0], ink[1], ink[2], min(255, max(140, darkness * 4)))
                    else:
                        px[x, y] = (255, 255, 255, 0)

            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)

            if img.width > 5 and img.height > 5:
                return img

        except Exception:
            continue

    return None


def _image_to_png_bytes(img: "Image.Image") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _page_text(page: Any) -> str:
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""


def _find_text_boxes(page: Any, patterns: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    text_dict = {}
    try:
        text_dict = page.get_text("dict")
    except Exception:
        text_dict = {}

    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            line_text = " ".join(str(s.get("text", "")).strip() for s in spans).strip()
            if not line_text:
                continue

            norm = re.sub(r"\s+", " ", line_text).lower()
            if any(re.search(p, norm, re.I) for p in patterns):
                bbox = line.get("bbox") or block.get("bbox")
                if bbox:
                    x0, y0, x1, y1 = bbox
                    results.append({
                        "text": line_text,
                        "x0": float(x0),
                        "y0": float(y0),
                        "x1": float(x1),
                        "y1": float(y1),
                        "cx": float((x0 + x1) / 2),
                        "cy": float((y0 + y1) / 2),
                    })
    return results


def _detect_horizontal_lines(page: Any) -> List[Dict[str, Any]]:
    """
    Detect real horizontal vector lines. Handles PyMuPDF drawing items safely.
    """
    lines: List[Dict[str, Any]] = []

    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []

    for drawing in drawings:
        for item in drawing.get("items", []):
            try:
                if not item or item[0] != "l":
                    continue

                p1 = item[1]
                p2 = item[2]
                x0, y0 = float(p1.x), float(p1.y)
                x1, y1 = float(p2.x), float(p2.y)

                if abs(y0 - y1) > 2.0:
                    continue

                length = abs(x1 - x0)
                if length < 80:
                    continue

                x_left = min(x0, x1)
                x_right = max(x0, x1)
                y = (y0 + y1) / 2

                lines.append({
                    "x0": x_left,
                    "x1": x_right,
                    "y": y,
                    "length": length,
                    "kind": "vector",
                })
            except Exception:
                continue

    # De-duplicate lines.
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for l in lines:
        key = (round(l["x0"] / 4), round(l["x1"] / 4), round(l["y"] / 3))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(l)

    return deduped




def _detect_text_dotted_lines(page: Any) -> List[Dict[str, Any]]:
    """
    Detect blank/dotted/underscore lines that are represented as PDF text,
    e.g. '....................' or '____________________'.
    """
    found: List[Dict[str, Any]] = []

    try:
        text_dict = page.get_text("dict")
    except Exception:
        return found

    dotted_re = re.compile(r"^[\s._\-–—·•]{8,}$")

    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            combined = "".join(str(s.get("text", "")) for s in spans).strip()

            # Some PDFs split dotted lines into spans, so also inspect each span.
            candidates = [combined] + [str(s.get("text", "")).strip() for s in spans]

            for candidate in candidates:
                compact = candidate.replace(" ", "")
                dot_count = compact.count(".")
                underscore_count = compact.count("_")
                dash_count = compact.count("-") + compact.count("–") + compact.count("—")

                if not dotted_re.match(compact):
                    if max(dot_count, underscore_count, dash_count) < 8:
                        continue

                bbox = line.get("bbox") or block.get("bbox")
                if not bbox:
                    continue

                x0, y0, x1, y1 = bbox
                length = float(x1 - x0)
                if length < 80:
                    continue

                found.append({
                    "x0": float(x0),
                    "x1": float(x1),
                    "y": float((y0 + y1) / 2),
                    "length": length,
                    "kind": "text_dotted",
                    "raw": candidate[:80],
                })
                break

    # De-duplicate
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for l in found:
        key = (round(l["x0"] / 5), round(l["x1"] / 5), round(l["y"] / 4))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(l)

    return deduped



def _split_text_dotted_row_lines(line: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Split text dotted rows that contain multiple dotted areas on one line.
    Example raw:
      '...........................................   ..................................'

    This allows the engine to write signature on the first dotted section and
    date/capacity/name on the second dotted section when labels are nearby.
    """
    raw = str(line.get("raw") or "")
    x0 = float(line.get("x0") or 0)
    x1 = float(line.get("x1") or 0)
    y = float(line.get("y") or 0)

    if not raw.strip() or line.get("kind") != "text_dotted":
        return [line]

    # Find runs of dots/underscores/dashes separated by spaces.
    parts = []
    for match in re.finditer(r"[._\-–—·•]{8,}", raw):
        parts.append((match.start(), match.end(), match.group(0)))

    if len(parts) <= 1:
        return [line]

    total_chars = max(1, len(raw))
    width = max(1.0, x1 - x0)
    split_lines: List[Dict[str, Any]] = []

    for idx, (s, e, txt) in enumerate(parts, start=1):
        sx0 = x0 + (s / total_chars) * width
        sx1 = x0 + (e / total_chars) * width
        if sx1 - sx0 < 45:
            continue
        split_lines.append({
            "x0": float(sx0),
            "x1": float(sx1),
            "y": y,
            "length": float(sx1 - sx0),
            "kind": "text_dotted_split",
            "raw": txt[:80],
            "parent_raw": raw[:120],
            "split_index": idx,
        })

    return split_lines or [line]



def _detect_all_blank_lines(page: Any) -> List[Dict[str, Any]]:
    """
    Combine vector and text dotted lines.
    """
    base_lines = []
    base_lines.extend(_detect_horizontal_lines(page))
    base_lines.extend(_detect_text_dotted_lines(page))

    lines: List[Dict[str, Any]] = []
    for l in base_lines:
        lines.extend(_split_text_dotted_row_lines(l))
    lines.extend(_detect_signature_date_combined_lines(page))

    # Keep only useful line widths.
    cleaned = []
    seen = set()
    for l in lines:
        if l.get("length", 0) < 45:
            continue
        key = (round(l["x0"] / 5), round(l["x1"] / 5), round(l["y"] / 4), l.get("split_index"))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(l)

    return sorted(cleaned, key=lambda x: (x["y"], x["x0"]))


def _detect_signature_date_combined_lines(page: Any) -> List[Dict[str, Any]]:
    """
    Strict detector for TRUE form rows only.

    Accept:
      SIGNATURE OF SIGNATORY: ................. DATE: .................
      SIGNATURE OF BIDDER: ................... DATE: .................
      SIGNATURE: ............................. DATE: .................

    Reject:
      normal sentences such as "agreement shall commence on the signature date..."
      witness rows
      contract clauses
    """
    targets: List[Dict[str, Any]] = []

    try:
        text_dict = page.get_text("dict")
    except Exception:
        return targets

    true_label_re = re.compile(
        r"^\s*(signature(\s+of\s+(signatory|bidder|tenderer|authori[sz]ed\s+person))?|signatory)\s*:?.{0,90}\bdate\s*:?",
        re.I,
    )

    reject_re = re.compile(
        r"(agreement|commence|period|months|contract|clause|signature\s+date|witness|witnesses|commissioner|official)",
        re.I,
    )

    dotted_re = re.compile(r"(\.{5,}|_{5,}|…{3,})")

    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            raw = "".join(str(s.get("text", "")) for s in spans).strip()
            compact = re.sub(r"\s+", " ", raw).strip()
            norm = compact.lower()

            if not compact:
                continue

            if reject_re.search(norm):
                continue

            if not true_label_re.search(compact):
                continue

            if not dotted_re.search(raw):
                continue

            bbox = line.get("bbox") or block.get("bbox")
            if not bbox:
                continue

            x0, y0, x1, y1 = bbox
            width = float(x1 - x0)
            y = float((y0 + y1) / 2)

            raw_lower = raw.lower()
            date_idx = raw_lower.find("date")
            sig_idx = raw_lower.find("signature")
            if sig_idx < 0:
                sig_idx = 0

            total_chars = max(1, len(raw))
            date_ratio = date_idx / total_chars if date_idx >= 0 else 0.68
            date_ratio = max(0.48, min(0.86, date_ratio))

            # Signature field starts after the signature label.
            colon_idx = raw.find(":")
            if colon_idx >= 0 and colon_idx < date_idx:
                sig_start_ratio = min(0.72, max(0.20, (colon_idx + 1) / total_chars))
            else:
                sig_start_ratio = 0.34

            split_x = float(x0 + width * date_ratio)

            sig_start = float(x0 + width * sig_start_ratio)
            sig_end = max(sig_start + 70, split_x - 10)

            # Date field starts after DATE:
            date_colon = raw_lower.find(":", date_idx)
            if date_colon >= 0:
                date_start_ratio = min(0.92, max(date_ratio, (date_colon + 1) / total_chars))
            else:
                date_start_ratio = min(0.90, date_ratio + 0.08)

            date_start = float(x0 + width * date_start_ratio)
            date_end = float(x1)

            if sig_end - sig_start >= 55:
                targets.append({
                    "x0": sig_start,
                    "x1": sig_end,
                    "y": y,
                    "length": sig_end - sig_start,
                    "kind": "signature_date_split",
                    "raw": raw[:160],
                    "split_role": "signature",
                    "true_label": True,
                })

            if date_end - date_start >= 45:
                targets.append({
                    "x0": date_start,
                    "x1": date_end,
                    "y": y,
                    "length": date_end - date_start,
                    "kind": "signature_date_split",
                    "raw": raw[:160],
                    "split_role": "date",
                    "true_label": True,
                })

    return targets



def _is_instruction_page(page_text: str) -> bool:
    n = re.sub(r"\s+", " ", page_text).lower()
    instruction_terms = [
        "purpose of the form",
        "terms and conditions for bidding",
        "bidders must ensure compliance",
        "the successful bidder will be required",
    ]
    return any(t in n for t in instruction_terms)


def _match_line_for_anchor(lines: List[Dict[str, Any]], anchor: Dict[str, Any], prefer: str = "right_or_below") -> Optional[Dict[str, Any]]:
    if not anchor:
        return None

    best = None
    best_score = 10**9

    ax0, ay0, ax1, ay1 = anchor["x0"], anchor["y0"], anchor["x1"], anchor["y1"]
    acy = anchor["cy"]

    for line in lines:
        lx0, lx1, ly = line["x0"], line["x1"], line["y"]

        # Candidate line to the right on same row, or just below the label.
        same_row = abs(ly - acy) <= 24 and lx0 >= ax1 - 30
        below = ly >= ay1 - 2 and ly <= ay1 + 110

        if prefer == "right":
            valid = same_row
        elif prefer == "below":
            valid = below
        else:
            valid = same_row or below

        if not valid:
            continue

        # Avoid full table borders at far left if the label is not near them.
        if line["length"] > 520 and same_row:
            continue

        distance = abs(ly - acy) + max(0, lx0 - ax1) * 0.25
        if below and not same_row:
            distance += (ly - ay1) * 2

        if distance < best_score:
            best = line
            best_score = distance

    return best


def _insert_image_on_line(page: Any, img: "Image.Image", line: Dict[str, Any], width: float, height: float, x_offset: float = 4) -> None:
    if fitz is None:
        raise RuntimeError("PyMuPDF is required.")

    # Fit image into the line area.
    target_w = min(width, max(70, line["x1"] - line["x0"] - 10))
    target_h = height

    work = img.copy()
    try:
        work.thumbnail((int(target_w * 2), int(target_h * 2)), Image.Resampling.LANCZOS)
    except Exception:
        work.thumbnail((int(target_w * 2), int(target_h * 2)))

    png = _image_to_png_bytes(work)

    x0 = line["x0"] + x_offset
    y0 = line["y"] - target_h + 4
    rect = fitz.Rect(x0, y0, x0 + target_w, y0 + target_h)
    page.insert_image(rect, stream=png, overlay=True)


def _insert_text_on_line(page: Any, text: str, line: Dict[str, Any], ink_color: str = "black", font_size: int = 15) -> None:
    if Image is None:
        # Emergency fallback. This is typed, but only if Pillow is unavailable.
        page.insert_text((line["x0"] + 4, line["y"] - 3), str(text), fontsize=font_size)
        return

    max_w = int(max(120, min(560, (line["x1"] - line["x0"]) * 2)))
    layer = _make_handwriting_text_layer(
        text=text,
        font_size=font_size * 2,
        ink_color=ink_color,
        max_width_px=max_w,
        max_height_px=70,
    )
    png = _image_to_png_bytes(layer)

    width = min((line["x1"] - line["x0"]), layer.width / 2)
    height = min(32, layer.height / 2)
    rect = fitz.Rect(line["x0"] + 4, line["y"] - 24, line["x0"] + 4 + width, line["y"] + 8)
    page.insert_image(rect, stream=png, overlay=True)


def _plan_blank_line_fields(doc: Any, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    values = _default_values(payload)
    planned: List[Dict[str, Any]] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        text = _page_text(page)
        lines = _detect_all_blank_lines(page)

        if not lines:
            continue

        page_num = page_index + 1

        # Signature anchors.
        signature_anchors = _find_text_boxes(page, [
            r"\bsignature\s+of\s+bidder\b",
            r"\bsignature\s+of\s+tenderer\b",
            r"\bsignature\b",
        ])

        for anchor in signature_anchors[:2]:
            # On instruction pages, only accept lower-page declaration/signature lines.
            if _is_instruction_page(text) and anchor["y0"] < 480:
                continue

            line = _match_line_for_anchor(lines, anchor, "right_or_below")
            if line:
                planned.append({
                    "page": page_num,
                    "kind": "signature",
                    "value": values["director_name"],
                    "line": line,
                    "anchor": anchor["text"],
                    "confidence": 0.94,
                })

        # Capacity / position.
        cap_anchors = _find_text_boxes(page, [
            r"\bcapacity\b",
            r"\bposition\b",
            r"\bdesignation\b",
        ])
        for anchor in cap_anchors[:2]:
            if _is_instruction_page(text) and anchor["y0"] < 480:
                continue
            line = _match_line_for_anchor(lines, anchor, "right_or_below")
            if line:
                planned.append({
                    "page": page_num,
                    "kind": "capacity",
                    "value": values["capacity"],
                    "line": line,
                    "anchor": anchor["text"],
                    "confidence": 0.90,
                })

        # Date.
        date_anchors = _find_text_boxes(page, [
            r"^\s*date\s*:?\s*$",
            r"\bdate\b",
        ])
        for anchor in date_anchors[:2]:
            if anchor["y0"] < 250:
                continue
            line = _match_line_for_anchor(lines, anchor, "right_or_below")
            if line:
                planned.append({
                    "page": page_num,
                    "kind": "date",
                    "value": values["date"],
                    "line": line,
                    "anchor": anchor["text"],
                    "confidence": 0.88,
                })

        # Name of bidder / tenderer. Avoid supplier-info table on first page unless line is clearly wide.
        name_anchors = _find_text_boxes(page, [
            r"\bname\s+of\s+bidder\b",
            r"\bbidder'?s\s+name\b",
            r"\bname\s+of\s+tenderer\b",
        ])
        for anchor in name_anchors[:2]:
            line = _match_line_for_anchor(lines, anchor, "right_or_below")
            if not line:
                continue
            if page_num == 1 and line["length"] < 250:
                continue
            planned.append({
                "page": page_num,
                "kind": "bidder_name",
                "value": values["bidder_name"],
                "line": line,
                "anchor": anchor["text"],
                "confidence": 0.86,
            })

        # Explicit combined signature/date line handling.
        combined_targets = _detect_signature_date_combined_lines(page)
        for target in combined_targets:
            role = target.get("split_role")
            if role == "signature":
                planned.append({
                    "page": page_num,
                    "kind": "signature",
                    "value": values["director_name"],
                    "line": target,
                    "anchor": "SIGNATURE OF SIGNATORY",
                    "confidence": 0.98,
                })
            elif role == "date":
                planned.append({
                    "page": page_num,
                    "kind": "date",
                    "value": values["date"],
                    "line": target,
                    "anchor": "DATE",
                    "confidence": 0.97,
                })


    # De-duplicate and limit.
    deduped: List[Dict[str, Any]] = []
    seen = set()

    priority = {
        "signature": 1,
        "capacity": 2,
        "date": 3,
        "bidder_name": 4,
    }

    planned = sorted(planned, key=lambda f: (f["page"], priority.get(f["kind"], 99), f["line"]["y"]))

    for f in planned:
        line = f["line"]
        key = (f["page"], f["kind"], round(line["x0"] / 12), round(line["y"] / 10))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    # Conservative cap for safety.
    return deduped[:18]




def _entity_type_from_payload(payload: Optional[Dict[str, Any]] = None) -> str:
    """
    Decide legal entity type for section selection.

    Defaults to pty_ltd because LMCP is Lechesa Manaba Consulting and Projects
    (Pty) Ltd.
    """
    payload = payload or {}
    raw = str(
        payload.get("entity_type")
        or payload.get("company_entity_type")
        or payload.get("legal_entity_type")
        or payload.get("business_type")
        or "pty_ltd"
    ).strip().lower()

    if any(x in raw for x in ["pty", "private company", "company", "(pty)", "limited"]):
        return "pty_ltd"
    if any(x in raw for x in ["sole", "proprietor", "one-person", "one person"]):
        return "sole_proprietor"
    if "partnership" in raw or "partner" in raw:
        return "partnership"
    if "close corporation" in raw or raw in ("cc", "c.c."):
        return "close_corporation"
    return "pty_ltd"


def _classify_page_section(page_text: str) -> Dict[str, Any]:
    """
    Classify which legal section a page appears to contain.
    """
    n = re.sub(r"\s+", " ", str(page_text or "")).lower()

    section = "unknown"
    score = 0.0
    reasons: List[str] = []

    if re.search(r"\bsole\s+proprietor\b|\bone\s*-\s*person\s+business\b", n, re.I):
        section = "sole_proprietor"
        score += 4
        reasons.append("sole proprietor section")

    if re.search(r"\bpartnership\b|full name of partner|undersigned partners", n, re.I):
        # Partnership should override sole if both are on same page because it
        # creates many repeated signature rows.
        section = "partnership"
        score += 5
        reasons.append("partnership section")

    if re.search(r"\bcompany\b|\bclose corporation\b|\bpty\b|\(pty\)\s*ltd|director|shareholder|board resolution", n, re.I):
        if section == "unknown":
            section = "company"
        score += 3
        reasons.append("company/cc terms")

    if re.search(r"\bsbd\s*4\b|declaration of interest|bidder'?s disclosure", n, re.I):
        section = "sbd_declaration"
        score += 5
        reasons.append("SBD declaration")

    if re.search(r"\bsbd\s*8\b|independent bid determination", n, re.I):
        section = "sbd_independent_bid"
        score += 5
        reasons.append("SBD independent bid determination")

    if re.search(r"\bsbd\s*9\b|certificate of independent bid determination", n, re.I):
        section = "sbd_certificate"
        score += 5
        reasons.append("SBD certificate")

    if re.search(r"signature\s+of\s+bidder|name\s+of\s+bidder|duly\s+authori[sz]ed", n, re.I):
        score += 2
        reasons.append("bidder signature context")

    return {
        "section": section,
        "score": score,
        "reasons": reasons,
    }


def _page_allowed_for_entity(page_text: str, entity_type: str) -> Tuple[bool, str]:
    """
    Decide if a page should be filled for the entity type.

    For pty_ltd:
      - skip sole proprietor section
      - skip partnership section
      - allow company/cc/SBD declaration sections
    """
    c = _classify_page_section(page_text)
    section = c["section"]

    if entity_type == "pty_ltd":
        if section in ("sole_proprietor", "partnership"):
            return False, f"Skipped {section} section for Pty Ltd entity."
        return True, f"Allowed {section} for Pty Ltd entity."

    if entity_type == "sole_proprietor":
        if section == "partnership":
            return False, "Skipped partnership section for sole proprietor."
        return True, f"Allowed {section} for sole proprietor."

    if entity_type == "partnership":
        if section == "sole_proprietor":
            return False, "Skipped sole proprietor section for partnership."
        return True, f"Allowed {section} for partnership."

    return True, f"Allowed {section} for entity type {entity_type}."


def _find_candidate_company_pages(doc: Any, entity_type: str) -> List[int]:
    """
    Rank pages that are likely appropriate for this entity type.
    """
    ranked: List[Tuple[float, int]] = []
    for i in range(len(doc)):
        page_text = _page_text(doc[i])
        allowed, _reason = _page_allowed_for_entity(page_text, entity_type)
        if not allowed:
            continue

        info = _classify_page_section(page_text)
        txt = re.sub(r"\s+", " ", page_text).lower()
        score = float(info.get("score") or 0)

        if "signature of bidder" in txt:
            score += 4
        if "name of bidder" in txt:
            score += 3
        if "capacity" in txt or "designation" in txt:
            score += 2
        if "date" in txt:
            score += 1
        if "director" in txt:
            score += 2
        if "duly authorised" in txt or "duly authorized" in txt:
            score += 2

        if score > 2:
            ranked.append((score, i + 1))

    ranked.sort(reverse=True)
    return [p for _score, p in ranked]





def _recover_company_name_field_for_page(page: Any, page_num: int) -> Optional[Dict[str, Any]]:
    """
    Recover a true company/bidder name field from the same company/signatory page.

    Avoids witness/partner/sole proprietor sections and only accepts clear labels.
    """
    try:
        text_dict = page.get_text("dict")
    except Exception:
        return None

    reject_re = re.compile(
        r"(witness|witnesses|partner|partnership|sole proprietor|commissioner|official|office use)",
        re.I,
    )

    label_re = re.compile(
        r"(name\s+of\s+(bidder|tenderer|company)|bidder'?s\s+name|company\s+name|signatory\s+name)",
        re.I,
    )

    dotted_re = re.compile(r"([.…._\-–— ]{5,})", re.I)

    candidates: List[Dict[str, Any]] = []

    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            raw = "".join(str(s.get("text", "")) for s in spans).strip()
            norm = re.sub(r"\s+", " ", raw).strip()

            if not norm:
                continue
            if reject_re.search(norm):
                continue
            if not label_re.search(norm):
                continue
            if not dotted_re.search(raw):
                continue

            bbox = line.get("bbox") or block.get("bbox")
            if not bbox:
                continue

            x0, y0, x1, y1 = bbox
            width = float(x1 - x0)
            y = float((y0 + y1) / 2)

            colon_idx = raw.find(":")
            total_chars = max(1, len(raw))
            if colon_idx >= 0:
                start_ratio = min(0.90, max(0.18, (colon_idx + 1) / total_chars))
            else:
                start_ratio = 0.42

            lx0 = float(x0 + width * start_ratio)
            lx1 = float(x1)

            if lx1 - lx0 < 75:
                continue

            score = 0.0
            lower = norm.lower()
            if "name of bidder" in lower or "bidder" in lower:
                score += 5
            if "company" in lower:
                score += 3
            if 250 <= y <= 620:
                score += 2

            candidates.append({
                "page": page_num,
                "kind": "bidder_name",
                "value": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                "line": {
                    "x0": lx0,
                    "x1": lx1,
                    "y": y,
                    "length": lx1 - lx0,
                    "kind": "company_name_recovery",
                    "raw": raw[:160],
                    "true_label": True,
                },
                "anchor": "NAME OF BIDDER / COMPANY",
                "confidence": 0.91,
                "_company_name_recovery_score": score,
            })

    if not candidates:
        return None

    candidates.sort(key=lambda f: f.get("_company_name_recovery_score", 0), reverse=True)
    return candidates[0]



def _recover_true_date_field_for_page(page: Any, page_num: int) -> Optional[Dict[str, Any]]:
    """
    Recover a TRUE date field from a company/signatory page.

    Avoids:
      - witness date rows
      - contract clause text containing 'signature date'
      - partnership/sole proprietor sections
    """
    try:
        text_dict = page.get_text("dict")
    except Exception:
        return None

    reject_re = re.compile(
        r"(witness|witnesses|agreement|commence|signature\s+date|contract|period|months|partner|partnership|sole proprietor)",
        re.I,
    )
    true_date_re = re.compile(r"\bdate\s*:?\s*([.…._\-–— ]{5,})", re.I)

    candidates: List[Dict[str, Any]] = []

    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            raw = "".join(str(s.get("text", "")) for s in spans).strip()
            norm = re.sub(r"\s+", " ", raw).strip()

            if not norm:
                continue
            if reject_re.search(norm):
                continue
            if "date" not in norm.lower():
                continue

            m = true_date_re.search(norm)
            if not m:
                continue

            bbox = line.get("bbox") or block.get("bbox")
            if not bbox:
                continue

            x0, y0, x1, y1 = bbox
            width = float(x1 - x0)
            y = float((y0 + y1) / 2)

            raw_lower = raw.lower()
            date_idx = raw_lower.find("date")
            colon_idx = raw_lower.find(":", date_idx)
            total_chars = max(1, len(raw))

            if colon_idx >= 0:
                start_ratio = min(0.92, max(0.10, (colon_idx + 1) / total_chars))
            else:
                start_ratio = min(0.90, max(0.10, (date_idx + 4) / total_chars))

            lx0 = float(x0 + width * start_ratio)
            lx1 = float(x1)

            if lx1 - lx0 < 45:
                continue

            score = 0.0
            if "date:" in norm.lower():
                score += 5
            if "signature" in norm.lower():
                score += 2
            if 300 <= y <= 735:
                score += 2
            if y > 760:
                score -= 4

            candidates.append({
                "page": page_num,
                "kind": "date",
                "value": datetime.now().strftime("%d/%m/%Y"),
                "line": {
                    "x0": lx0,
                    "x1": lx1,
                    "y": y,
                    "length": lx1 - lx0,
                    "kind": "date_recovery",
                    "raw": raw[:160],
                    "true_label": True,
                },
                "anchor": "DATE",
                "confidence": 0.93,
                "_date_recovery_score": score,
            })

    if not candidates:
        return None

    candidates.sort(key=lambda f: f.get("_date_recovery_score", 0), reverse=True)
    return candidates[0]



def _v22_7_3_limit_fields(fields: List[Dict[str, Any]], doc: Any) -> List[Dict[str, Any]]:
    """
    V22.7.1 Date Split Fix.

    Fixes:
      - block witness lines completely,
      - prefer combined SIGNATURE OF SIGNATORY / DATE split targets,
      - keep Pty Ltd company section logic from V22.7.
    """
    if not fields:
        return []

    entity_type = "pty_ltd"

    allowed_fields: List[Dict[str, Any]] = []
    for f in fields:
        page_num = int(f.get("page") or 0)
        if page_num < 1 or page_num > len(doc):
            continue

        text = _page_text(doc[page_num - 1])
        allowed, reason = _page_allowed_for_entity(text, entity_type)
        if not allowed:
            continue

        line = f.get("line") or {}
        raw = str(line.get("raw") or "").lower()
        anchor = str(f.get("anchor") or "").lower()

        # Hard block witnesses.
        if (
            "witness" in raw or "witness" in anchor or "witnesses" in raw or "witnesses" in anchor
            or "agreement shall commence" in raw
            or "signature date" in raw
            or "period of" in raw
            or "contract" in raw
        ):
            continue

        f["_decision_reason"] = reason
        f["_page_section"] = _classify_page_section(text).get("section")
        allowed_fields.append(f)

    if not allowed_fields:
        return []

    def context_near(f: Dict[str, Any], radius: float = 150) -> str:
        page_num = int(f.get("page") or 0)
        line = f.get("line") or {}
        y = float(line.get("y") or 0)
        anchor = str(f.get("anchor") or "")
        raw = str(line.get("raw") or "")

        try:
            page = doc[page_num - 1]
            text_dict = page.get_text("dict")
        except Exception:
            return f"{anchor} {raw}".lower()

        parts = [anchor, raw]
        for block in text_dict.get("blocks", []):
            for line_obj in block.get("lines", []):
                bbox = line_obj.get("bbox") or block.get("bbox")
                if not bbox:
                    continue
                x0, y0, x1, y1 = bbox
                cy = float((y0 + y1) / 2)
                if abs(cy - y) <= radius:
                    spans = line_obj.get("spans", [])
                    text = " ".join(str(s.get("text", "")).strip() for s in spans).strip()
                    if text:
                        parts.append(text)

        return re.sub(r"\s+", " ", " ".join(parts)).lower()

    def score(f: Dict[str, Any]) -> float:
        kind = str(f.get("kind") or "")
        line = f.get("line") or {}
        line_kind = str(line.get("kind") or "")
        split_role = str(line.get("split_role") or "")
        ctx = context_near(f)
        y = float(line.get("y") or 0)
        s = float(f.get("confidence") or 0.0)

        if "witness" in ctx or "witnesses" in ctx:
            return -999

        if line_kind == "signature_date_split" and bool(line.get("true_label")):
            s += 25
            if kind == split_role:
                s += 12
        elif line_kind == "signature_date_split":
            s -= 50

        if "signature of signatory" in ctx:
            s += 10
        if "signature of bidder" in ctx:
            s += 8
        if "date" in ctx and kind == "date":
            s += 8
        if "capacity" in ctx and kind == "capacity":
            s += 5
        if "in his/her capacity as" in ctx and kind == "capacity":
            s += 8
        if "company" in ctx or "director" in ctx:
            s += 2

        if kind == "signature":
            s += 4
        elif kind == "date":
            s += 4
        elif kind == "capacity":
            s += 3
        elif kind == "bidder_name":
            s += 2

        if 280 <= y <= 735:
            s += 1
        if y > 765:
            s -= 5

        if "sole proprietor" in ctx or "partnership" in ctx or "partner" in ctx:
            s -= 30
        if "commissioner" in ctx or "official use" in ctx:
            s -= 20

        return s

    ranked = sorted(allowed_fields, key=score, reverse=True)
    ranked = [f for f in ranked if score(f) > -100]

    if not ranked:
        return []

    # Prefer page containing the best combined split row.
    split_fields = [f for f in ranked if (f.get("line") or {}).get("kind") == "signature_date_split"]
    if split_fields:
        best_page = int(split_fields[0].get("page") or ranked[0].get("page") or 0)
    else:
        best_page = int(ranked[0].get("page") or 0)

    best_page_fields = [f for f in ranked if int(f.get("page") or 0) == best_page]

    kept: List[Dict[str, Any]] = []
    per_kind: Dict[str, int] = {}

    max_kind = {
        "signature": 1,
        "date": 1,
        "capacity": 1,
        "bidder_name": 1,
    }

    for f in best_page_fields:
        kind = str(f.get("kind") or "")
        if per_kind.get(kind, 0) >= max_kind.get(kind, 0):
            continue
        kept.append(f)
        per_kind[kind] = per_kind.get(kind, 0) + 1

    # Date recovery: only if a date was not already kept.
    if kept and not any(f.get("kind") == "date" for f in kept):
        best_page = int(kept[0].get("page") or 0)
        if 1 <= best_page <= len(doc):
            recovered_date = _recover_true_date_field_for_page(doc[best_page - 1], best_page)
            if recovered_date is not None:
                kept.append(recovered_date)

    # Company/name recovery: only if a true labelled company/name line exists.
    if kept and not any(f.get("kind") == "bidder_name" for f in kept):
        best_page = int(kept[0].get("page") or 0)
        if 1 <= best_page <= len(doc):
            recovered_name = _recover_company_name_field_for_page(doc[best_page - 1], best_page)
            if recovered_name is not None:
                kept.append(recovered_name)

    return sorted(
        kept,
        key=lambda f: (
            int(f.get("page") or 0),
            float((f.get("line") or {}).get("y") or 0),
            float((f.get("line") or {}).get("x0") or 0),
            str(f.get("kind") or ""),
        ),
    )



def build_field_plan(input_pdf: Union[str, Path], payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    ensure_tender_form_runtime_dirs()
    payload = _coerce_payload(payload, **kwargs)
    pdf_path = _resolve_path(input_pdf or payload.get("input_pdf") or payload.get("pdf_path"))

    if fitz is None:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "PyMuPDF/fitz is required."}

    if not pdf_path or not pdf_path.exists():
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "message": "Input PDF not found.",
            "input_pdf": str(pdf_path) if pdf_path else None,
        }

    doc = fitz.open(str(pdf_path))
    try:
        planned = _v22_7_3_limit_fields(_plan_blank_line_fields(doc, payload), doc)
        return {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "input_pdf": str(pdf_path),
            "page_count": len(doc),
            "planned_field_count": len(planned),
            "detected_anchor_count": len(planned),
            "fields": planned,
        }
    finally:
        doc.close()


def complete_pdf_with_stroke_flow(
    input_pdf: Union[str, Path, None] = None,
    output_pdf: Union[str, Path, None] = None,
    payload: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    ensure_tender_form_runtime_dirs()
    payload = _coerce_payload(payload, **kwargs)

    if fitz is None:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "PyMuPDF/fitz is required."}
    if Image is None:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "Pillow is required."}

    pdf_path = _resolve_path(input_pdf or payload.get("input_pdf") or payload.get("pdf_path"))
    buyer_rfq = str(payload.get("buyer_rfq_number") or payload.get("rfq_number") or "RFQ")
    ink_color = str(payload.get("ink_color") or "black")
    debug = bool(payload.get("debug", False))

    if not pdf_path or not pdf_path.exists():
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "input_pdf": str(pdf_path) if pdf_path else None,
            "buyer_rfq_number": buyer_rfq,
            "message": "Input PDF not found.",
        }

    if output_pdf:
        out_path = Path(output_pdf)
        if not out_path.is_absolute():
            out_path = PROJECT_ROOT / out_path
    else:
        out_path = COMPLETED_DIR / f"{_safe_filename(buyer_rfq)}__V22_7_4_company_name_recovery_lock_completed_form.pdf"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    signature_img = _load_clean_signature(payload.get("signature_image"), ink_color=ink_color)

    doc = fitz.open(str(pdf_path))
    debug_layers: List[str] = []
    written = 0

    try:
        fields = _v22_7_3_limit_fields(_plan_blank_line_fields(doc, payload), doc)

        for idx, field in enumerate(fields, start=1):
            page = doc[int(field["page"]) - 1]
            line = field["line"]
            kind = field["kind"]
            value = field["value"]

            if kind == "signature" and signature_img is not None:
                _insert_image_on_line(page, signature_img, line, width=160, height=34, x_offset=5)
                if debug:
                    dbg = DEBUG_DIR / f"{_safe_filename(buyer_rfq)}__p{field['page']}_{idx}_signature.png"
                    signature_img.save(str(dbg))
                    debug_layers.append(str(dbg))
            elif kind == "signature":
                _insert_text_on_line(page, value, line, ink_color=ink_color, font_size=14)
            elif kind == "date":
                _insert_text_on_line(page, value, line, ink_color=ink_color, font_size=13)
            elif kind == "capacity":
                _insert_text_on_line(page, value, line, ink_color=ink_color, font_size=13)
            else:
                _insert_text_on_line(page, value, line, ink_color=ink_color, font_size=12)

            written += 1

        doc.save(str(out_path), garbage=4, deflate=True, clean=True)

        result = {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "message": "Tender form completed with V22.7.4 company name recovery production lock.",
            "buyer_rfq_number": buyer_rfq,
            "input_pdf": str(pdf_path),
            "output_pdf": str(out_path),
            "completed_pdf": str(out_path),
            "page_count": len(doc),
            "planned_field_count": len(fields),
            "written_field_count": written,
            "detected_anchor_count": len(fields),
            "explicit_field_count": 0,
            "debug_layers": debug_layers,
            "used_signature_image": signature_img is not None,
            "used_reference_image": bool(_resolve_path(payload.get("reference_image"))) if payload.get("reference_image") else False,
        }

        if debug:
            plan_json = DEBUG_DIR / f"{_safe_filename(buyer_rfq)}__V22_7_4_plan.json"
            plan_json.write_text(json.dumps({"result": result, "fields": fields}, indent=2, default=_jsonable), encoding="utf-8")
            result["debug_plan_json"] = str(plan_json)

        return result

    except Exception as exc:
        return {
            "status": "error",
            "engine_version": ENGINE_VERSION,
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "input_pdf": str(pdf_path),
            "buyer_rfq_number": buyer_rfq,
        }
    finally:
        try:
            doc.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# API-facing wrappers and compatibility functions
# ---------------------------------------------------------------------------

def get_tender_form_intelligence_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "engine": "Form-Type Decision Engine with Company Name Recovery Lock",
        "runtime_dir": str(RUNTIME_DIR),
        "completed_dir": str(COMPLETED_DIR),
        "debug_dir": str(DEBUG_DIR),
        "dependencies": {
            "pymupdf_fitz": fitz is not None,
            "pillow": Image is not None,
        },
        "capabilities": [
            "blank_line_detection",
            "text_dotted_line_detection",
            "page_field_limiter",
            "bidder_only_signature_filter",
            "balanced_bidder_pack",
            "page34_bidder_pack",
            "split_dotted_row_detection",
            "form_type_decision",
            "pty_ltd_section_filter",
            "date_split_fix",
            "witness_line_blocking",
            "true_signature_label_filter",
            "contract_clause_rejection",
            "date_recovery",
            "company_name_recovery",
            "production_lock",
            "signature_line_matching",
            "capacity_line_matching",
            "date_line_matching",
            "bidder_name_line_matching",
            "signature_background_cleanup",
            "safe_sbd_placement_filter",
        ],
    }


def status() -> Dict[str, Any]:
    return get_tender_form_intelligence_status()


def get_status() -> Dict[str, Any]:
    return get_tender_form_intelligence_status()


def get_engine_status() -> Dict[str, Any]:
    return get_tender_form_intelligence_status()


def complete_tender_form(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    payload = _coerce_payload(payload, **kwargs)
    return complete_pdf_with_stroke_flow(payload=payload)


def complete_tender_form_intelligence(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def complete_form(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def complete_sbd_form(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def complete_sbd_intelligence(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def run_tender_form_intelligence(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def run(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def example_payload() -> Dict[str, Any]:
    return {
        "buyer_rfq_number": "TEST-V22.6",
        "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
        "signature_image": "runtime/handwriting_simulation/sample_signature.png",
        "ink_color": "black",
        "debug": True,
    }


def get_example_payload() -> Dict[str, Any]:
    return example_payload()


def build_glyph_library(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    payload = _coerce_payload(payload, **kwargs)
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "message": "V22.6 uses blank-line detection and dynamic handwriting layers; static glyph cache is not required.",
        "dynamic_blank_line_detection": True,
    }


def build_glyph_cache(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return build_glyph_library(payload, **kwargs)


def build_handwriting_glyph_library(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return build_glyph_library(payload, **kwargs)


def detect_sbd_pages(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    payload = _coerce_payload(payload, **kwargs)
    input_pdf = payload.get("input_pdf") or payload.get("pdf_path")
    pdf_path = _resolve_path(input_pdf)

    if fitz is None:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "PyMuPDF/fitz is required.", "sbd_pages": []}

    if not pdf_path or not pdf_path.exists():
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "Input PDF not found.", "sbd_pages": []}

    doc = fitz.open(str(pdf_path))
    pages: List[Dict[str, Any]] = []
    try:
        patterns = [
            r"\bsbd\s*1\b", r"\bsbd\s*4\b", r"\bsbd\s*6\.?1\b", r"\bsbd\s*8\b", r"\bsbd\s*9\b",
            r"invitation\s+to\s+bid", r"signature\s+of\s+bidder", r"name\s+of\s+bidder",
            r"certificate\s+of\s+independent\s+bid\s+determination", r"bidder.?s\s+disclosure",
        ]

        for i in range(len(doc)):
            text = re.sub(r"\s+", " ", _page_text(doc[i])).lower()
            matches = [p for p in patterns if re.search(p, text, re.I)]
            if matches:
                pages.append({
                    "page": i + 1,
                    "page_number": i + 1,
                    "confidence": min(0.98, 0.4 + len(matches) * 0.12),
                    "matched_patterns": matches,
                })

        return {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "input_pdf": str(pdf_path),
            "page_count": len(doc),
            "sbd_pages": [p["page"] for p in pages],
            "detected_pages": pages,
            "detected_count": len(pages),
        }
    finally:
        doc.close()


def detect_sbd_page_numbers(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return detect_sbd_pages(payload, **kwargs)


def find_sbd_pages(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return detect_sbd_pages(payload, **kwargs)


def detect_training_template(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    payload = _coerce_payload(payload, **kwargs)
    input_pdf = payload.get("input_pdf") or payload.get("pdf_path")
    result: Dict[str, Any] = {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "template_version": "V22.6_BLANK_LINE_DYNAMIC_TEMPLATE",
        "template_name": "blank_line_sbd_template",
        "message": "V22.6 dynamically detects blank lines; no static training template is required.",
        "input_pdf": str(input_pdf) if input_pdf else None,
    }
    if input_pdf:
        plan = build_field_plan(input_pdf, payload)
        result["field_plan"] = plan
        result["planned_field_count"] = plan.get("planned_field_count", 0)
    return result


def detect_template(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return detect_training_template(payload, **kwargs)


def find_training_template(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return detect_training_template(payload, **kwargs)


def get_training_template(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return detect_training_template(payload, **kwargs)


def load_training_template(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return detect_training_template(payload, **kwargs)


def locate_writable_fields(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    payload = _coerce_payload(payload, **kwargs)
    input_pdf = payload.get("input_pdf") or payload.get("pdf_path")
    if not input_pdf:
        return {"status": "error", "engine_version": ENGINE_VERSION, "message": "input_pdf is required.", "writable_fields": []}

    plan = build_field_plan(input_pdf, payload)
    fields = plan.get("fields", [])

    writable = []
    for idx, f in enumerate(fields, start=1):
        line = f.get("line", {})
        writable.append({
            "id": f"field_{idx}",
            "page": f.get("page"),
            "page_number": f.get("page"),
            "x": line.get("x0"),
            "y": line.get("y"),
            "width": (line.get("x1", 0) - line.get("x0", 0)) if line else None,
            "height": 24,
            "field_type": f.get("kind"),
            "value": f.get("value"),
            "anchor": f.get("anchor"),
            "confidence": f.get("confidence", 0.8),
            "writable": True,
        })

    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "input_pdf": plan.get("input_pdf"),
        "writable_field_count": len(writable),
        "writable_fields": writable,
        "fields": fields,
    }


def find_writable_fields(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return locate_writable_fields(payload, **kwargs)


def get_writable_fields(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return locate_writable_fields(payload, **kwargs)


def locate_form_fields(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return locate_writable_fields(payload, **kwargs)


def detect_tender_form_fields(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return locate_writable_fields(payload, **kwargs)


def detect_fields(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return locate_writable_fields(payload, **kwargs)


def build_handwriting_payload(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    payload = _coerce_payload(payload, **kwargs)
    plan = locate_writable_fields(payload)
    return {
        "status": plan.get("status"),
        "engine_version": ENGINE_VERSION,
        "handwriting_payload": {
            "buyer_rfq_number": payload.get("buyer_rfq_number") or "RFQ",
            "input_pdf": payload.get("input_pdf"),
            "fields": plan.get("writable_fields", []),
            "signature_image": payload.get("signature_image"),
            "debug": payload.get("debug", False),
        },
    }


def classify_tender_form(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    payload = _coerce_payload(payload, **kwargs)
    input_pdf = payload.get("input_pdf") or payload.get("pdf_path")
    result = {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "classification": "sbd_or_tender_form",
        "form_type": "tender_form",
        "confidence": 0.75,
        "input_pdf": input_pdf,
    }
    if input_pdf:
        pages = detect_sbd_pages(payload)
        result["sbd_pages"] = pages.get("sbd_pages", [])
        result["confidence"] = 0.92 if pages.get("detected_count", 0) else 0.65
    return result


def overlay_existing_pdf(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def overlay_pdf_with_handwriting(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def complete_with_handwriting(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)


def complete_with_stroke_flow(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return complete_tender_form(payload, **kwargs)
