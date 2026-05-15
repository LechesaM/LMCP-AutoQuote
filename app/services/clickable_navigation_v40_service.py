"""
LMCP AutoQuote System
V40 Clickable Navigation Extractor Service

Purpose:
- Extract real clickable PDF navigation from tender/RFQ documents.
- Detect PDF link annotations, bookmarks / table of contents, internal page jumps,
  external links, email links, and page-text navigation candidates.
- Produce stable JSON output that can be consumed by downstream form-intelligence,
  SBD-navigation, pricing-schedule, and true-navigation workflows.

Safe dependency behavior:
- Uses PyMuPDF / fitz when available.
- Returns a clear dependency error if PyMuPDF is missing instead of crashing.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import os
import re
import traceback


SERVICE_VERSION = "V40_CLICKABLE_NAVIGATION_EXTRACTOR"
DEFAULT_OUTPUT_DIR = Path("runtime/clickable_navigation_v40")
NAV_KEYWORDS = [
    "contents",
    "table of contents",
    "index",
    "pricing schedule",
    "price schedule",
    "bill of quantities",
    "boq",
    "scope of work",
    "terms of reference",
    "specification",
    "declaration",
    "sbd",
    "mbd",
    "returnable",
    "submission",
    "bid document",
    "evaluation",
    "functionality",
    "compulsory briefing",
    "closing date",
]


@dataclass
class ClickableNavigationItem:
    item_id: str
    source: str
    page: int
    page_index: int
    text: str
    navigation_type: str
    target_page: Optional[int] = None
    target_page_index: Optional[int] = None
    target_uri: Optional[str] = None
    target_email: Optional[str] = None
    target_kind: str = "unknown"
    rect: Optional[Dict[str, float]] = None
    confidence: float = 0.0
    reason: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _rect_to_dict(rect: Any) -> Optional[Dict[str, float]]:
    if rect is None:
        return None
    try:
        return {
            "x0": round(_safe_float(rect.x0), 2),
            "y0": round(_safe_float(rect.y0), 2),
            "x1": round(_safe_float(rect.x1), 2),
            "y1": round(_safe_float(rect.y1), 2),
            "width": round(_safe_float(rect.x1) - _safe_float(rect.x0), 2),
            "height": round(_safe_float(rect.y1) - _safe_float(rect.y0), 2),
        }
    except Exception:
        try:
            x0, y0, x1, y1 = rect
            return {
                "x0": round(_safe_float(x0), 2),
                "y0": round(_safe_float(y0), 2),
                "x1": round(_safe_float(x1), 2),
                "y1": round(_safe_float(y1), 2),
                "width": round(_safe_float(x1) - _safe_float(x0), 2),
                "height": round(_safe_float(y1) - _safe_float(y0), 2),
            }
        except Exception:
            return None


def _hash_item(*parts: Any) -> str:
    raw = "|".join(_normalise_text(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _infer_target_kind(uri: Optional[str], target_page: Optional[int], target_email: Optional[str]) -> str:
    if target_email:
        return "email"
    if uri:
        uri_l = uri.lower()
        if uri_l.startswith("mailto:"):
            return "email"
        if uri_l.startswith("http://") or uri_l.startswith("https://"):
            return "external_web"
        if uri_l.startswith("#") or uri_l.startswith("file:"):
            return "document_reference"
        return "external_or_named"
    if target_page is not None:
        return "internal_page"
    return "unknown"


def _extract_email(uri: Optional[str], text: str = "") -> Optional[str]:
    source = f"{uri or ''} {text or ''}"
    source = source.replace("mailto:", " ")
    match = re.search(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", source, flags=re.I)
    return match.group(0) if match else None


def _keyword_score(text: str) -> Tuple[float, str]:
    t = (text or "").lower()
    hits = [kw for kw in NAV_KEYWORDS if kw in t]
    if not hits:
        return 0.35, "clickable item"
    score = min(0.95, 0.55 + (0.06 * len(hits)))
    return score, "keyword match: " + ", ".join(hits[:5])


def _line_looks_like_navigation(text: str) -> bool:
    t = _normalise_text(text)
    if len(t) < 4:
        return False

    lower = t.lower()
    if any(kw in lower for kw in NAV_KEYWORDS):
        return True

    # TOC-like: "1.2 Pricing Schedule ........ 14"
    if re.search(r"(\.{3,}|\s{3,})\s*\d{1,4}\s*$", t):
        return True

    # Section heading + page number: "SBD 4 Declaration of Interest 23"
    if re.search(r"^(sbd|mbd)\s*\d+[a-z]?\b.*\b\d{1,4}$", t, flags=re.I):
        return True

    # Numbered section with likely destination page.
    if re.search(r"^\d+(\.\d+)*\s+.{6,}\s+\d{1,4}$", t):
        return True

    return False


def _extract_destination_page_from_line(text: str, page_count: int) -> Optional[int]:
    t = _normalise_text(text)
    m = re.search(r"(\d{1,4})\s*$", t)
    if not m:
        return None
    value = int(m.group(1))
    if 1 <= value <= page_count:
        return value
    return None


def _text_from_rect(page: Any, rect: Any) -> str:
    try:
        text = page.get_textbox(rect)
        text = _normalise_text(text)
        if text:
            return text
    except Exception:
        pass
    return ""


def _extract_clickable_links(doc: Any) -> List[ClickableNavigationItem]:
    items: List[ClickableNavigationItem] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_number = page_index + 1

        try:
            links = page.get_links() or []
        except Exception:
            links = []

        for link_index, link in enumerate(links):
            rect = link.get("from")
            uri = _normalise_text(link.get("uri")) or None
            target_page_index = link.get("page")
            target_page = None

            if isinstance(target_page_index, int) and target_page_index >= 0:
                target_page = target_page_index + 1

            text = _text_from_rect(page, rect)
            if not text:
                if uri:
                    text = uri
                elif target_page:
                    text = f"Go to page {target_page}"
                else:
                    text = "Clickable PDF link"

            email = _extract_email(uri, text)
            target_kind = _infer_target_kind(uri, target_page, email)
            confidence, reason = _keyword_score(text)
            if target_kind in {"internal_page", "external_web", "email"}:
                confidence = max(confidence, 0.78)

            item_id = _hash_item("link", page_number, link_index, text, uri, target_page)

            items.append(
                ClickableNavigationItem(
                    item_id=item_id,
                    source="pdf_link_annotation",
                    page=page_number,
                    page_index=page_index,
                    text=text,
                    navigation_type="clickable_link",
                    target_page=target_page,
                    target_page_index=target_page_index if isinstance(target_page_index, int) and target_page_index >= 0 else None,
                    target_uri=uri,
                    target_email=email,
                    target_kind=target_kind,
                    rect=_rect_to_dict(rect),
                    confidence=round(confidence, 3),
                    reason=reason,
                )
            )

    return items


def _extract_bookmarks(doc: Any) -> List[ClickableNavigationItem]:
    items: List[ClickableNavigationItem] = []
    try:
        toc = doc.get_toc(simple=True) or []
    except Exception:
        toc = []

    for idx, row in enumerate(toc):
        try:
            level, title, page_number = row[:3]
        except Exception:
            continue

        title = _normalise_text(title)
        if not title:
            continue

        target_page = int(page_number) if isinstance(page_number, int) and page_number > 0 else None
        confidence, reason = _keyword_score(title)
        confidence = max(confidence, 0.82)

        items.append(
            ClickableNavigationItem(
                item_id=_hash_item("bookmark", idx, level, title, target_page),
                source="pdf_bookmark_toc",
                page=target_page or 1,
                page_index=(target_page - 1) if target_page else 0,
                text=title,
                navigation_type="bookmark",
                target_page=target_page,
                target_page_index=(target_page - 1) if target_page else None,
                target_kind="internal_page" if target_page else "unknown",
                confidence=round(confidence, 3),
                reason=f"pdf bookmark level {level}; {reason}",
            )
        )

    return items


def _extract_page_text_navigation_candidates(doc: Any, max_pages_scan: int = 8) -> List[ClickableNavigationItem]:
    items: List[ClickableNavigationItem] = []
    page_count = len(doc)
    pages_to_scan = min(page_count, max_pages_scan)

    for page_index in range(pages_to_scan):
        page = doc[page_index]
        page_number = page_index + 1

        try:
            raw_text = page.get_text("text") or ""
        except Exception:
            raw_text = ""

        lines = [_normalise_text(line) for line in raw_text.splitlines()]
        lines = [line for line in lines if line]

        for line_index, line in enumerate(lines):
            if not _line_looks_like_navigation(line):
                continue

            target_page = _extract_destination_page_from_line(line, page_count)
            confidence, reason = _keyword_score(line)
            if target_page:
                confidence = max(confidence, 0.72)
                reason = f"{reason}; trailing page number detected"
            else:
                confidence = max(confidence, 0.48)

            items.append(
                ClickableNavigationItem(
                    item_id=_hash_item("textnav", page_number, line_index, line, target_page),
                    source="page_text_navigation_candidate",
                    page=page_number,
                    page_index=page_index,
                    text=line,
                    navigation_type="text_navigation_candidate",
                    target_page=target_page,
                    target_page_index=(target_page - 1) if target_page else None,
                    target_kind="internal_page" if target_page else "unknown",
                    confidence=round(confidence, 3),
                    reason=reason,
                )
            )

    return items


def _dedupe_items(items: List[ClickableNavigationItem]) -> List[ClickableNavigationItem]:
    best: Dict[str, ClickableNavigationItem] = {}

    for item in items:
        key = "|".join(
            [
                item.source,
                str(item.page),
                _normalise_text(item.text).lower(),
                str(item.target_page or ""),
                str(item.target_uri or ""),
            ]
        )

        existing = best.get(key)
        if existing is None or item.confidence > existing.confidence:
            best[key] = item

    return sorted(
        best.values(),
        key=lambda x: (
            x.page,
            -float(x.confidence or 0),
            x.source,
            x.text.lower(),
        ),
    )


def _summarise(items: List[ClickableNavigationItem]) -> Dict[str, Any]:
    by_source: Dict[str, int] = {}
    by_kind: Dict[str, int] = {}
    for item in items:
        by_source[item.source] = by_source.get(item.source, 0) + 1
        by_kind[item.target_kind] = by_kind.get(item.target_kind, 0) + 1

    high_confidence = [item for item in items if item.confidence >= 0.75]
    pricing_like = [
        item for item in items
        if any(kw in item.text.lower() for kw in ["pricing", "price schedule", "bill of quantities", "boq"])
    ]
    sbd_like = [
        item for item in items
        if re.search(r"\b(sbd|mbd)\s*\d+", item.text, flags=re.I)
    ]

    return {
        "total_items": len(items),
        "high_confidence_items": len(high_confidence),
        "by_source": by_source,
        "by_target_kind": by_kind,
        "pricing_navigation_candidates": len(pricing_like),
        "sbd_mbd_navigation_candidates": len(sbd_like),
        "has_real_clickable_links": by_source.get("pdf_link_annotation", 0) > 0,
        "has_pdf_bookmarks": by_source.get("pdf_bookmark_toc", 0) > 0,
        "has_text_navigation_candidates": by_source.get("page_text_navigation_candidate", 0) > 0,
    }


def extract_clickable_navigation(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    output_dir: Optional[str] = None,
    max_pages_scan: int = 8,
    include_low_confidence: bool = True,
) -> Dict[str, Any]:
    """
    Main V40 extraction function.

    Args:
        input_pdf: Path to source PDF. Works with project-relative and absolute paths.
        buyer_rfq_number: Optional RFQ number used in output naming.
        output_dir: Optional output directory.
        max_pages_scan: Number of first pages to scan for text-based navigation candidates.
        include_low_confidence: If False, returns only confidence >= 0.50.

    Returns:
        JSON-serialisable dict with extraction result and artifact paths.
    """

    started_at = _now_iso()
    input_path = Path(input_pdf)

    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path

    if not input_path.exists():
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Input PDF not found.",
            "input_pdf": str(input_path),
            "buyer_rfq_number": buyer_rfq_number,
            "started_at": started_at,
            "completed_at": _now_iso(),
        }

    try:
        import fitz  # type: ignore
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "PyMuPDF dependency is missing. Install with: pip install pymupdf",
            "input_pdf": str(input_path),
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }

    out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not out_root.is_absolute():
        out_root = Path.cwd() / out_root
    out_root.mkdir(parents=True, exist_ok=True)

    safe_rfq = re.sub(r"[^A-Za-z0-9_.-]+", "-", buyer_rfq_number or input_path.stem).strip("-") or "RFQ"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    json_path = out_root / f"{safe_rfq}__{SERVICE_VERSION}__{timestamp}.json"

    try:
        doc = fitz.open(str(input_path))
        page_count = len(doc)

        items: List[ClickableNavigationItem] = []
        items.extend(_extract_clickable_links(doc))
        items.extend(_extract_bookmarks(doc))
        items.extend(_extract_page_text_navigation_candidates(doc, max_pages_scan=max_pages_scan))

        items = _dedupe_items(items)

        if not include_low_confidence:
            items = [item for item in items if item.confidence >= 0.50]

        payload = {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "message": "Clickable navigation extraction completed.",
            "input_pdf": str(input_path),
            "buyer_rfq_number": buyer_rfq_number,
            "page_count": page_count,
            "started_at": started_at,
            "completed_at": _now_iso(),
            "summary": _summarise(items),
            "items": [asdict(item) for item in items],
            "output_json": str(json_path),
        }

        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            doc.close()
        except Exception:
            pass

        return payload

    except Exception as exc:
        error_payload = {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Clickable navigation extraction failed.",
            "input_pdf": str(input_path),
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }
        try:
            json_path.write_text(json.dumps(error_payload, indent=2, ensure_ascii=False), encoding="utf-8")
            error_payload["output_json"] = str(json_path)
        except Exception:
            pass
        return error_payload


def get_clickable_navigation_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V40 Clickable Navigation Extractor",
        "description": "Extracts PDF clickable links, bookmarks, internal page jumps, external URLs, emails, and text navigation candidates.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "endpoints": {
            "status": "/v40-clickable-navigation/status",
            "extract": "/v40-clickable-navigation/extract",
        },
        "ready": True,
    }
