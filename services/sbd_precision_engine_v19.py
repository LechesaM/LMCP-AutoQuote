"""
LMCP AutoQuote — V19 Precision Engine
Service file: app/services/sbd_precision_engine_v19.py

V19.1 fix:
- NEVER normalise whitespace in input_pdf / file paths.
- This fixes files like: "RFQ  Corporate Gift Packs.pdf" with double spaces.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover
    fitz = None
    _FITZ_IMPORT_ERROR = exc
else:
    _FITZ_IMPORT_ERROR = None


ENGINE_VERSION = "V19_PRECISION_ENGINE"

PROJECT_ROOT_CANDIDATES = [
    Path(os.getenv("LMCP_PROJECT_ROOT", "")).expanduser() if os.getenv("LMCP_PROJECT_ROOT") else None,
    Path("/app"),
    Path("/Users/Shared/LMCP-AutoQuote-Server"),
    Path.cwd(),
]


@dataclass
class PrecisionField:
    page: int
    x: float
    y: float
    text: str
    font_size: float = 9.5
    color: Tuple[float, float, float] = (0, 0, 0)
    field_name: str = "field"


@dataclass
class V19Result:
    status: str
    engine_version: str
    buyer_rfq_number: str
    input_pdf: str
    output_pdf: Optional[str]
    debug_json: Optional[str]
    message: str
    fields_written: int
    resolved_input_pdf: Optional[str] = None
    warnings: Optional[List[str]] = None
    error: Optional[str] = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_roots() -> List[Path]:
    roots: List[Path] = []
    for p in PROJECT_ROOT_CANDIDATES:
        if not p:
            continue
        try:
            pp = p.expanduser().resolve()
        except Exception:
            pp = p
        if pp not in roots:
            roots.append(pp)
    return roots


def _path_text(value: Any) -> str:
    """
    Convert a path value to string without collapsing whitespace.
    IMPORTANT: filenames may contain double spaces.
    """
    if value is None:
        return ""
    return str(value).strip()


def resolve_runtime_path(value: Optional[str], must_exist: bool = False) -> Optional[Path]:
    """
    Resolve paths from:
    - Docker container: /app/runtime/...
    - Mac host project root: /Users/Shared/LMCP-AutoQuote-Server/runtime/...
    - Relative project path: runtime/...
    """
    if value is None:
        return None

    value_str = _path_text(value)
    if not value_str:
        return None

    raw = Path(value_str).expanduser()
    candidates: List[Path] = []

    if raw.is_absolute():
        candidates.append(raw)

        raw_str = str(raw)
        if raw_str.startswith("/app/"):
            suffix = raw_str[len("/app/") :]
            for root in _project_roots():
                candidates.append(root / suffix)

        marker = "LMCP-AutoQuote-Server/"
        if marker in raw_str:
            suffix = raw_str.split(marker, 1)[1]
            for root in _project_roots():
                candidates.append(root / suffix)
    else:
        candidates.append(raw)
        for root in _project_roots():
            candidates.append(root / raw)

    seen = set()
    unique: List[Path] = []
    for c in candidates:
        try:
            cc = c.resolve()
        except Exception:
            cc = c
        s = str(cc)
        if s not in seen:
            seen.add(s)
            unique.append(cc)

    if must_exist:
        for c in unique:
            if c.exists():
                return c
        return None

    return unique[0] if unique else raw


def ensure_output_dir(buyer_rfq_number: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", buyer_rfq_number or "UNKNOWN").strip("_") or "UNKNOWN"
    out = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "sbd_intelligence" / "v19_outputs" / safe
    out.mkdir(parents=True, exist_ok=True)
    return out


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return re.sub(r"\s+", " ", text)


def build_default_precision_fields(payload: Dict[str, Any]) -> List[PrecisionField]:
    company_name = _safe_text(payload.get("company_name"), "Lechesa Manaba Consulting and Projects (Pty) Ltd")
    director_name = _safe_text(payload.get("director_name"), "Lechesa Manaba")
    designation = _safe_text(payload.get("designation"), "Director")
    buyer_name = _safe_text(payload.get("buyer_name"), "")
    bid_description = _safe_text(payload.get("bid_description"), payload.get("title", ""))
    rfq = _safe_text(payload.get("buyer_rfq_number"), "UNKNOWN")

    requested_fields = payload.get("fields")
    fields: List[PrecisionField] = []

    if isinstance(requested_fields, list) and requested_fields:
        for i, f in enumerate(requested_fields):
            if not isinstance(f, dict):
                continue
            fields.append(
                PrecisionField(
                    page=int(f.get("page", 1)),
                    x=float(f.get("x", 72)),
                    y=float(f.get("y", 72)),
                    text=_safe_text(f.get("text"), ""),
                    font_size=float(f.get("font_size", 9.5)),
                    field_name=_safe_text(f.get("field_name"), f"field_{i+1}"),
                )
            )
        return fields

    fields.extend(
        [
            PrecisionField(page=1, x=72, y=105, text=company_name, font_size=9.5, field_name="company_name"),
            PrecisionField(page=1, x=72, y=122, text=director_name, font_size=9.5, field_name="director_name"),
            PrecisionField(page=1, x=72, y=139, text=designation, font_size=9.5, field_name="designation"),
            PrecisionField(page=1, x=72, y=156, text=rfq, font_size=9.0, field_name="buyer_rfq_number"),
        ]
    )

    if buyer_name:
        fields.append(PrecisionField(page=1, x=72, y=173, text=buyer_name, font_size=8.5, field_name="buyer_name"))
    if bid_description:
        fields.append(PrecisionField(page=1, x=72, y=190, text=bid_description[:120], font_size=8.0, field_name="bid_description"))

    return fields


def _insert_text(page: Any, field: PrecisionField, handwritten_mode: bool = False) -> None:
    fontsize = max(8.0, field.font_size) if handwritten_mode else field.font_size
    page.insert_text(
        fitz.Point(field.x, field.y),
        field.text,
        fontsize=fontsize,
        fontname="helv",
        color=field.color,
        overlay=True,
    )


def complete_sbd_form_v19(payload: Dict[str, Any]) -> Dict[str, Any]:
    if fitz is None:
        return asdict(
            V19Result(
                status="error",
                engine_version=ENGINE_VERSION,
                buyer_rfq_number=_safe_text(payload.get("buyer_rfq_number"), "UNKNOWN"),
                input_pdf=_path_text(payload.get("input_pdf")),
                output_pdf=None,
                debug_json=None,
                message="PyMuPDF is not installed. Install with: pip install pymupdf",
                fields_written=0,
                warnings=[],
                error=str(_FITZ_IMPORT_ERROR),
            )
        )

    buyer_rfq_number = _safe_text(payload.get("buyer_rfq_number"), f"V19-{uuid.uuid4().hex[:8]}")
    input_pdf_raw = _path_text(payload.get("input_pdf"))
    debug = bool(payload.get("debug", False))
    handwritten_mode = bool(payload.get("handwritten_mode", True))
    warnings: List[str] = []

    input_pdf = resolve_runtime_path(input_pdf_raw, must_exist=True)
    if input_pdf is None:
        search_roots = [str(p) for p in _project_roots()]
        return asdict(
            V19Result(
                status="error",
                engine_version=ENGINE_VERSION,
                buyer_rfq_number=buyer_rfq_number,
                input_pdf=input_pdf_raw,
                resolved_input_pdf=None,
                output_pdf=None,
                debug_json=None,
                message="Input PDF not found. V19 checked Docker, Mac project-root, and relative runtime paths.",
                fields_written=0,
                warnings=[
                    "Use the exact filename visible inside Docker.",
                    "Confirm with: docker compose exec -T api ls -lah '/app/runtime/playwright/downloads/'",
                    f"Checked roots: {search_roots}",
                ],
                error="Input PDF not found",
            )
        )

    reference_image = resolve_runtime_path(payload.get("reference_image"), must_exist=True)
    signature_image = resolve_runtime_path(payload.get("signature_image"), must_exist=True)

    if payload.get("reference_image") and reference_image is None:
        warnings.append("Reference handwriting image was not found; V19 continued with clean precision text.")
    if payload.get("signature_image") and signature_image is None:
        warnings.append("Signature image was not found; V19 continued without image signature placement.")

    output_dir = ensure_output_dir(buyer_rfq_number)
    output_pdf = output_dir / f"{buyer_rfq_number}__v19_precision_completed.pdf"
    debug_json = output_dir / f"{buyer_rfq_number}__v19_precision_debug.json"

    fields = build_default_precision_fields(payload)

    try:
        doc = fitz.open(str(input_pdf))
        page_count = len(doc)

        written = 0
        skipped: List[Dict[str, Any]] = []

        for field in fields:
            page_index = max(0, int(field.page) - 1)
            if page_index >= page_count:
                skipped.append({**asdict(field), "reason": "page_out_of_range", "page_count": page_count})
                continue
            if not field.text:
                skipped.append({**asdict(field), "reason": "empty_text"})
                continue
            _insert_text(doc[page_index], field, handwritten_mode=handwritten_mode)
            written += 1

        sig_cfg = payload.get("signature_position") or {}
        if signature_image and isinstance(sig_cfg, dict):
            try:
                sig_page = int(sig_cfg.get("page", 1)) - 1
                sig_x = float(sig_cfg.get("x", 72))
                sig_y = float(sig_cfg.get("y", 220))
                sig_w = float(sig_cfg.get("width", 120))
                sig_h = float(sig_cfg.get("height", 42))
                if 0 <= sig_page < page_count:
                    rect = fitz.Rect(sig_x, sig_y, sig_x + sig_w, sig_y + sig_h)
                    doc[sig_page].insert_image(rect, filename=str(signature_image), overlay=True)
                else:
                    warnings.append("Signature placement skipped because page is out of range.")
            except Exception as exc:
                warnings.append(f"Signature placement skipped: {exc}")

        doc.save(str(output_pdf), deflate=True, garbage=4)
        doc.close()

        debug_payload = {
            "status": "ok",
            "engine_version": ENGINE_VERSION,
            "created_at": _utc_now(),
            "buyer_rfq_number": buyer_rfq_number,
            "input_pdf_raw": input_pdf_raw,
            "resolved_input_pdf": str(input_pdf),
            "output_pdf": str(output_pdf),
            "page_count": page_count,
            "fields_requested": len(fields),
            "fields_written": written,
            "fields_skipped": skipped,
            "warnings": warnings,
            "project_roots_checked": [str(p) for p in _project_roots()],
        }

        if debug:
            debug_json.write_text(json.dumps(debug_payload, indent=2), encoding="utf-8")

        return asdict(
            V19Result(
                status="ok",
                engine_version=ENGINE_VERSION,
                buyer_rfq_number=buyer_rfq_number,
                input_pdf=input_pdf_raw,
                resolved_input_pdf=str(input_pdf),
                output_pdf=str(output_pdf),
                debug_json=str(debug_json) if debug else None,
                message="V19 precision completion finished successfully.",
                fields_written=written,
                warnings=warnings,
                error=None,
            )
        )

    except Exception as exc:
        return asdict(
            V19Result(
                status="error",
                engine_version=ENGINE_VERSION,
                buyer_rfq_number=buyer_rfq_number,
                input_pdf=input_pdf_raw,
                resolved_input_pdf=str(input_pdf),
                output_pdf=None,
                debug_json=None,
                message="V19 precision completion failed while processing the PDF.",
                fields_written=0,
                warnings=warnings,
                error=str(exc),
            )
        )


def get_v19_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "checked_at": _utc_now(),
        "pymupdf_available": fitz is not None,
        "project_roots_checked": [str(p) for p in _project_roots()],
        "path_whitespace_preserved": True,
    }
