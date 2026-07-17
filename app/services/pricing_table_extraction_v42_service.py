from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import math
import re
import traceback

from app.services.rfq_requirement_pack_service import (
    attach_requirement_pack_fields,
    build_requirement_pack,
    normalize_requirement_rows,
)

SERVICE_VERSION = "V42_PRICING_TABLE_EXTRACTION_ENGINE"
DEFAULT_OUTPUT_DIR = Path("runtime/pricing_table_extraction_v42")

PRICE_CONTEXT_TERMS = [
    "price", "pricing", "quotation", "quote", "amount", "total", "vat",
    "unit price", "qty", "quantity", "rate", "rand", "zar", "cost",
]
NON_ITEM_TERMS = [
    "closing date", "evaluation", "functionality", "declaration", "sbd",
    "terms and conditions", "tax compliance", "preference points",
    "submission", "bidder", "signature", "witness", "director",
]


@dataclass
class ExtractedLineItem:
    item_no: Optional[str]
    description: str
    quantity: Optional[float]
    unit: Optional[str]
    unit_price: Optional[float]
    total_excl_vat: Optional[float]
    total_incl_vat: Optional[float]
    vat_amount: Optional[float]
    currency: str
    page: int
    source: str
    confidence: float
    reason: str
    raw_text: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("R", "").replace("ZAR", "").replace("zar", "").replace(",", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _round_money(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 2)


def _money_values(text: str) -> List[float]:
    values: List[float] = []
    patterns = [
        r"(?:R|ZAR)?\s*\d{1,3}(?:[ ,]\d{3})+(?:\.\d{2})?",
        r"(?:R|ZAR)\s*\d+(?:\.\d{2})?",
        r"\b\d+\.\d{2}\b",
    ]
    for pat in patterns:
        for m in re.findall(pat, text, flags=re.I):
            val = _safe_float(m)
            if val is not None:
                values.append(round(val, 2))
    out: List[float] = []
    seen = set()
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _extract_quantity_and_unit(text: str) -> Tuple[Optional[float], Optional[str]]:
    lower = text.lower()
    patterns = [
        r"\bqty[:\s]+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
        r"\bquantity[:\s]+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?",
        r"\b(\d+(?:\.\d+)?)\s*(each|ea|units?|packs?|boxes|sets?|lots?|kg|g|m|mm|cm|l|ml|items?|services?)\b",
    ]
    for pat in patterns:
        m = re.search(pat, lower, flags=re.I)
        if m:
            qty = _safe_float(m.group(1))
            unit = m.group(2) if len(m.groups()) >= 2 and m.group(2) else None
            return qty, unit

    nums = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    money = _money_values(text)
    money_set = {round(x, 2) for x in money}
    for n in nums:
        val = _safe_float(n)
        if val is not None and 0 < val <= 100000 and round(val, 2) not in money_set:
            return val, None
    return None, None


def _looks_like_pricing_text(text: str) -> bool:
    t = _normalise_text(text).lower()
    if len(t) < 5:
        return False
    if any(term in t for term in NON_ITEM_TERMS) and not any(term in t for term in ["price", "amount", "total", "qty", "quantity"]):
        return False
    has_money = bool(_money_values(t))
    has_price_term = any(term in t for term in PRICE_CONTEXT_TERMS)
    has_qty = bool(re.search(r"\b(qty|quantity)\b|\b\d+\s*(each|ea|units?|packs?|boxes|sets?|lots?|kg|g|m|mm|cm|l|ml|items?)\b", t, flags=re.I))
    return has_money or (has_price_term and has_qty)


def _infer_description(text: str) -> str:
    line = _normalise_text(text)
    line = re.sub(r"^\s*(item\s*)?\d+[\).\-\s]+", "", line, flags=re.I)
    line = re.sub(r"(?:R|ZAR)?\s*\d{1,3}(?:[ ,]\d{3})+(?:\.\d{2})?", " ", line, flags=re.I)
    line = re.sub(r"(?:R|ZAR)\s*\d+(?:\.\d{2})?", " ", line, flags=re.I)
    line = re.sub(r"\b\d+\.\d{2}\b", " ", line)
    line = re.sub(r"\b(qty|quantity)\s*[:\-]?\s*\d+(?:\.\d+)?\s*[a-zA-Z]*", " ", line, flags=re.I)
    line = re.sub(r"\b(unit price|total price|total amount|amount|vat|total|price|rate|qty|quantity)\b", " ", line, flags=re.I)
    return re.sub(r"\s+", " ", line).strip(" -:;,.")


def _extract_item_no(text: str) -> Optional[str]:
    m = re.match(r"^\s*(?:item\s*)?(\d+(?:\.\d+)*)[\).\-\s]+", text, flags=re.I)
    return m.group(1) if m else None


def _build_line_item_from_text(text: str, page: int, source: str = "page_text_line") -> Optional[ExtractedLineItem]:
    raw = _normalise_text(text)
    if not _looks_like_pricing_text(raw):
        return None

    money = _money_values(raw)
    qty, unit = _extract_quantity_and_unit(raw)
    desc = _infer_description(raw)
    item_no = _extract_item_no(raw)

    if len(desc) < 3 and not money:
        return None

    unit_price = None
    total_incl = None
    total_excl = None
    vat_amount = None

    if len(money) >= 2:
        unit_price = money[0]
        total_incl = money[-1]
    elif len(money) == 1:
        if qty and qty > 1:
            total_incl = money[0]
            unit_price = round(money[0] / qty, 2)
        else:
            unit_price = money[0]
            total_incl = money[0] if qty in (None, 1) else None

    if total_incl is not None:
        total_excl = round(total_incl / 1.15, 2)
        vat_amount = round(total_incl - total_excl, 2)

    confidence = 0.45
    reasons = []
    if money:
        confidence += 0.22
        reasons.append("money value detected")
    if qty:
        confidence += 0.12
        reasons.append("quantity detected")
    if any(term in raw.lower() for term in PRICE_CONTEXT_TERMS):
        confidence += 0.08
        reasons.append("pricing context")
    if desc and len(desc) >= 10:
        confidence += 0.08
        reasons.append("usable description")
    if len(money) >= 2:
        confidence += 0.05
        reasons.append("multiple money columns")
    if any(term in raw.lower() for term in NON_ITEM_TERMS):
        confidence -= 0.12
        reasons.append("contains non-item wording")

    confidence = max(0.05, min(0.95, confidence))
    if confidence < 0.45:
        return None

    return ExtractedLineItem(
        item_no=item_no,
        description=desc or raw[:120],
        quantity=qty,
        unit=unit,
        unit_price=_round_money(unit_price),
        total_excl_vat=_round_money(total_excl),
        total_incl_vat=_round_money(total_incl),
        vat_amount=_round_money(vat_amount),
        currency="ZAR",
        page=page,
        source=source,
        confidence=round(confidence, 3),
        reason="; ".join(reasons) or "pricing-like text",
        raw_text=raw,
    )


def _dedupe_line_items(items: List[ExtractedLineItem]) -> List[ExtractedLineItem]:
    best: Dict[Tuple[int, str, Optional[float]], ExtractedLineItem] = {}
    for item in items:
        key = (item.page, item.description.lower()[:80], item.total_incl_vat or item.unit_price)
        old = best.get(key)
        if old is None or item.confidence > old.confidence:
            best[key] = item
    return sorted(best.values(), key=lambda x: (x.page, -(x.confidence or 0), x.item_no or "", x.description.lower()))


def _extract_text_lines_from_page(page: Any) -> List[str]:
    try:
        text = page.get_text("text") or ""
    except Exception:
        return []
    lines = [_normalise_text(line) for line in text.splitlines() if _normalise_text(line)]
    joined = []
    buffer = ""
    for line in lines:
        if not buffer:
            buffer = line
        elif len(buffer) < 90 and not _looks_like_pricing_text(buffer):
            buffer = buffer + " " + line
        else:
            joined.append(buffer)
            buffer = line
    if buffer:
        joined.append(buffer)
    return lines + joined


def _extract_table_rows_with_pymupdf(page: Any, page_number: int) -> List[ExtractedLineItem]:
    items: List[ExtractedLineItem] = []
    try:
        finder = page.find_tables()
        tables = getattr(finder, "tables", []) or []
    except Exception:
        return items

    for table_index, table in enumerate(tables):
        try:
            rows = table.extract() or []
        except Exception:
            continue
        for row_index, row in enumerate(rows):
            cells = [_normalise_text(c) for c in (row or []) if _normalise_text(c)]
            if not cells:
                continue
            raw = " | ".join(cells)
            item = _build_line_item_from_text(raw, page_number, source=f"pymupdf_table_{table_index}_row_{row_index}")
            if item:
                items.append(item)
    return items


def _normalise_pages(pages: Optional[List[int]], page_count: int) -> List[int]:
    if not pages:
        return list(range(1, min(page_count, 12) + 1))
    cleaned = sorted({int(p) for p in pages if isinstance(p, int) or str(p).isdigit()})
    return [p for p in cleaned if 1 <= p <= page_count]


def _extract_pages_from_v41(v41_payload: Dict[str, Any]) -> List[int]:
    intel = v41_payload.get("intelligence") or {}
    pages = []
    for key in ["pricing_pages", "specification_pages"]:
        for p in intel.get(key) or []:
            try:
                pages.append(int(p))
            except Exception:
                pass
    return sorted(set(pages))


def extract_pricing_tables_from_pdf(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    pages: Optional[List[int]] = None,
    v41_json_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    min_confidence: float = 0.45,
) -> Dict[str, Any]:
    started_at = _now_iso()
    input_path = Path(input_pdf)
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path

    if not input_path.exists():
        return {
            "status": "error", "service_version": SERVICE_VERSION,
            "message": "Input PDF not found.", "input_pdf": str(input_path),
            "buyer_rfq_number": buyer_rfq_number, "started_at": started_at,
            "completed_at": _now_iso(),
        }

    try:
        import fitz  # type: ignore
    except Exception as exc:
        return {
            "status": "error", "service_version": SERVICE_VERSION,
            "message": "PyMuPDF dependency is missing. Install with: pip install pymupdf",
            "input_pdf": str(input_path), "error": str(exc),
            "started_at": started_at, "completed_at": _now_iso(),
        }

    if v41_json_path:
        v41_path = Path(v41_json_path)
        if not v41_path.is_absolute():
            v41_path = Path.cwd() / v41_path
        if v41_path.exists():
            try:
                v41_payload = json.loads(v41_path.read_text(encoding="utf-8"))
                if not pages:
                    pages = _extract_pages_from_v41(v41_payload)
                if not buyer_rfq_number:
                    buyer_rfq_number = v41_payload.get("buyer_rfq_number")
            except Exception:
                pass

    out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not out_root.is_absolute():
        out_root = Path.cwd() / out_root
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(str(input_path))
        page_count = len(doc)
        scan_pages = _normalise_pages(pages, page_count)
        raw_candidates: List[Dict[str, Any]] = []
        line_items: List[ExtractedLineItem] = []

        for p in scan_pages:
            page = doc[p - 1]
            line_items.extend(_extract_table_rows_with_pymupdf(page, p))
            for line in _extract_text_lines_from_page(page):
                if _looks_like_pricing_text(line):
                    raw_candidates.append({"page": p, "text": line, "reason": "pricing-like text line"})
                    item = _build_line_item_from_text(line, p, source="text_line")
                    if item:
                        line_items.append(item)

        try:
            doc.close()
        except Exception:
            pass

        line_items = [x for x in _dedupe_line_items(line_items) if x.confidence >= min_confidence]
        total_incl = round(sum((x.total_incl_vat or 0) for x in line_items), 2)
        total_excl = round(sum((x.total_excl_vat or 0) for x in line_items), 2)
        total_vat = round(sum((x.vat_amount or 0) for x in line_items), 2)

        safe_rfq = re.sub(r"[^A-Za-z0-9_.-]+", "-", buyer_rfq_number or input_path.stem).strip("-") or "RFQ"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_path = out_root / f"{safe_rfq}__{SERVICE_VERSION}__{timestamp}.json"

        line_item_rows = [asdict(x) for x in line_items]
        requirement_rows = normalize_requirement_rows(
            line_item_rows,
            source_type="embedded_pricing_schedule",
            source_document=str(input_path),
            default_confidence=min_confidence,
            evidence=["pricing_table_extraction_v42"],
        )
        requirement_pack = build_requirement_pack(
            requirement_rows,
            reference_number=buyer_rfq_number or "",
            title=input_path.stem,
        )

        result = {
            "status": "ok", "service_version": SERVICE_VERSION,
            "message": "Pricing table extraction completed.",
            "input_pdf": str(input_path), "buyer_rfq_number": buyer_rfq_number,
            "page_count": page_count, "pages_scanned": scan_pages,
            "started_at": started_at, "completed_at": _now_iso(),
            "summary": {
                "line_items_count": len(line_items),
                "raw_candidates_count": len(raw_candidates),
                "total_excl_vat": total_excl,
                "total_vat": total_vat,
                "total_incl_vat": total_incl,
                "currency": "ZAR",
                "has_line_items": len(line_items) > 0,
                "used_v41_json": bool(v41_json_path),
            },
            "line_items": line_item_rows,
            "raw_candidates": raw_candidates[:200],
            "output_json": str(out_path),
            "v41_json_path": v41_json_path,
        }
        attach_requirement_pack_fields(result, requirement_pack)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result

    except Exception as exc:
        return {
            "status": "error", "service_version": SERVICE_VERSION,
            "message": "Pricing table extraction failed.",
            "input_pdf": str(input_path), "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc), "traceback": traceback.format_exc(),
            "started_at": started_at, "completed_at": _now_iso(),
        }


def extract_pricing_from_v41_json(
    v41_json_path: str,
    input_pdf: Optional[str] = None,
    output_dir: Optional[str] = None,
    min_confidence: float = 0.45,
) -> Dict[str, Any]:
    started_at = _now_iso()
    path = Path(v41_json_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        return {
            "status": "error", "service_version": SERVICE_VERSION,
            "message": "V41 JSON file not found.", "v41_json_path": str(path),
            "started_at": started_at, "completed_at": _now_iso(),
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pdf = input_pdf or payload.get("input_pdf")
        if not pdf:
            return {
                "status": "error", "service_version": SERVICE_VERSION,
                "message": "No input_pdf provided and V41 JSON does not contain input_pdf.",
                "v41_json_path": str(path), "started_at": started_at,
                "completed_at": _now_iso(),
            }
        return extract_pricing_tables_from_pdf(
            input_pdf=pdf,
            buyer_rfq_number=payload.get("buyer_rfq_number"),
            pages=_extract_pages_from_v41(payload),
            v41_json_path=str(path),
            output_dir=output_dir,
            min_confidence=min_confidence,
        )
    except Exception as exc:
        return {
            "status": "error", "service_version": SERVICE_VERSION,
            "message": "V42 extraction from V41 JSON failed.",
            "v41_json_path": str(path), "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at, "completed_at": _now_iso(),
        }


def analyse_pdf_with_v41_then_v42(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    max_pages_scan: int = 25,
    output_dir: Optional[str] = None,
    min_confidence: float = 0.45,
) -> Dict[str, Any]:
    started_at = _now_iso()
    try:
        from app.services.navigation_intelligence_v41_service import analyse_pdf_with_v40_then_v41

        v41_result = analyse_pdf_with_v40_then_v41(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            max_pages_scan=max_pages_scan,
            output_dir=None,
        )
        if v41_result.get("status") != "ok":
            return {
                "status": "error", "service_version": SERVICE_VERSION,
                "message": "V41 analysis failed, so V42 could not continue.",
                "v41_result": v41_result,
                "started_at": started_at, "completed_at": _now_iso(),
            }

        result = extract_pricing_tables_from_pdf(
            input_pdf=v41_result.get("input_pdf") or input_pdf,
            buyer_rfq_number=v41_result.get("buyer_rfq_number") or buyer_rfq_number,
            pages=_extract_pages_from_v41(v41_result),
            v41_json_path=v41_result.get("output_json"),
            output_dir=output_dir,
            min_confidence=min_confidence,
        )
        result["v41_result_summary"] = {
            "output_json": v41_result.get("output_json"),
            "pricing_pages": (v41_result.get("intelligence") or {}).get("pricing_pages"),
            "primary_submission_email": (v41_result.get("intelligence") or {}).get("primary_submission_email"),
            "must_handwrite_forms": ((v41_result.get("intelligence") or {}).get("form_filling") or {}).get("must_handwrite_forms"),
        }
        return result
    except Exception as exc:
        return {
            "status": "error", "service_version": SERVICE_VERSION,
            "message": "V42 PDF workflow failed.", "input_pdf": input_pdf,
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc), "traceback": traceback.format_exc(),
            "started_at": started_at, "completed_at": _now_iso(),
        }


def get_pricing_table_extraction_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V42 Pricing Table Extraction Engine",
        "description": "Extracts buyer pricing/BOQ table rows from pages identified by V41 and normalises them into quote-engine line_items.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "endpoints": {
            "status": "/v42-pricing-table-extraction/status",
            "extract_pdf": "/v42-pricing-table-extraction/extract-pdf",
            "extract_from_v41_json": "/v42-pricing-table-extraction/extract-from-v41-json",
            "analyse_pdf": "/v42-pricing-table-extraction/analyse-pdf",
        },
        "ready": True,
    }
