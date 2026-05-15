from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import csv
import hashlib
import json
import re

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


ENGINE_VERSION = "RFQ_BOQ_EXTRACTION_ENGINE_V1"

RUNTIME_DIR = Path("runtime/rfq_boq_extraction")
DOWNLOAD_DIR = RUNTIME_DIR / "downloads"
REPORT_DIR = RUNTIME_DIR / "reports"
EXTRACTED_DIR = RUNTIME_DIR / "extracted"

DEFAULT_TIMEOUT_SECONDS = 30
MAX_PDF_PAGES = 80
MAX_TEXT_CHARS = 500_000

KNOWN_UNITS = {
    "each", "ea", "unit", "units", "box", "boxes", "pack", "packs",
    "lot", "lots", "set", "sets", "pair", "pairs", "roll", "rolls",
    "ream", "reams", "kg", "g", "ton", "tons", "litre", "litres",
    "liter", "liters", "ml", "m", "mm", "cm", "metre", "metres",
    "meter", "meters", "month", "months", "year", "years",
}

BOQ_KEYWORDS = [
    "bill of quantities",
    "boq",
    "pricing schedule",
    "price schedule",
    "schedule of prices",
    "quotation schedule",
    "item description",
    "description of goods",
    "description/specification",
    "quantity",
    "unit of measure",
    "uom",
    "unit price",
    "total price",
]

RETURNABLE_KEYWORDS = [
    "returnable documents",
    "returnable schedules",
    "mandatory returnables",
    "compulsory returnables",
    "sbd",
    "tax compliance",
    "central supplier database",
    "csd",
    "b-bbee",
    "bbbee",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _slug(value: Any, limit: int = 100) -> str:
    text = _safe_str(value)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return (text[:limit].strip("-") or "rfq-boq")


def _ensure_dirs() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


def _unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        cleaned = _safe_str(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _to_float(value: Any) -> Optional[float]:
    raw = _safe_str(value)
    if not raw:
        return None
    raw = raw.replace(",", "")
    raw = re.sub(r"[^0-9.\-]", "", raw)
    if raw in {"", ".", "-", "-."}:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _clean_cell(value: Any) -> str:
    text = _safe_str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_document_links(item: Dict[str, Any]) -> List[str]:
    if not isinstance(item, dict):
        return []

    keys = (
        "document_url",
        "source_url",
        "detail_url",
        "pdf_url",
        "download_url",
        "attachment_url",
        "tender_document_url",
    )

    links: List[str] = []

    for key in keys:
        value = item.get(key)
        if isinstance(value, list):
            links.extend(_safe_str(v) for v in value)
        else:
            links.append(_safe_str(value))

    for key in ("documents", "attachments", "supporting_documents", "links", "downloads"):
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for inner_key in ("url", "href", "download_url", "document_url", "path"):
                        candidate = _safe_str(entry.get(inner_key))
                        if candidate.startswith("http"):
                            links.append(candidate)
                else:
                    links.append(_safe_str(entry))
        elif isinstance(value, dict):
            for inner_key in ("url", "href", "download_url", "document_url"):
                links.append(_safe_str(value.get(inner_key)))

    return [u for u in _unique_preserve_order(links) if _is_http_url(u)]


def _guess_extension(url: str, content_type: str = "") -> str:
    url_l = _safe_lower(url)
    type_l = _safe_lower(content_type)

    if ".pdf" in url_l or "application/pdf" in type_l or "pdf" in type_l:
        return ".pdf"
    if ".xlsx" in url_l or "spreadsheet" in type_l or "excel" in type_l:
        return ".xlsx"
    if ".xls" in url_l:
        return ".xls"
    if ".csv" in url_l or "text/csv" in type_l:
        return ".csv"
    if ".html" in url_l or "text/html" in type_l:
        return ".html"
    return ".html"


def download_document(url: str, title: str = "", timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    _ensure_dirs()

    url = _safe_str(url)
    if not _is_http_url(url):
        return {"status": "failed", "url": url, "error": "invalid_url"}

    if requests is None:
        return {"status": "failed", "url": url, "error": "requests_not_available"}

    headers = {
        "User-Agent": "LMCP-AutoQuote BOQ Extraction/1.0",
        "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml,text/csv,*/*;q=0.8",
    }

    try:
        response = requests.get(url, timeout=timeout_seconds, headers=headers, allow_redirects=True)
        status_code = int(response.status_code)
        content_type = response.headers.get("content-type", "")

        if status_code >= 400:
            return {
                "status": "failed",
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "error": "http_error",
            }

        ext = _guess_extension(str(response.url or url), content_type)
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:14]
        filename = f"{_slug(title or url)}__{digest}{ext}"
        path = DOWNLOAD_DIR / filename
        path.write_bytes(response.content)

        return {
            "status": "downloaded",
            "url": url,
            "final_url": str(response.url),
            "path": str(path),
            "filename": filename,
            "extension": ext,
            "content_type": content_type,
            "status_code": status_code,
            "size_bytes": len(response.content),
        }
    except Exception as exc:
        return {"status": "failed", "url": url, "error": str(exc)}


def _reuse_document_intelligence_downloads(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Reuse downloads from the RFQ Document Intelligence result when the harvester
    already attached it to the RFQ item.
    """
    if not isinstance(item, dict):
        return []

    result = item.get("document_intelligence_result")
    if not isinstance(result, dict):
        return []

    downloads = result.get("downloads")
    if not isinstance(downloads, list):
        return []

    reused: List[Dict[str, Any]] = []
    for d in downloads:
        if not isinstance(d, dict):
            continue
        path = Path(_safe_str(d.get("path")))
        if d.get("status") == "downloaded" and path.exists():
            copied = dict(d)
            copied["reused_from_document_intelligence"] = True
            reused.append(copied)
    return reused


def _extract_pdf_text(path: Path) -> str:
    try:
        import fitz
    except Exception:
        return ""

    try:
        doc = fitz.open(str(path))
        chunks: List[str] = []
        for index in range(min(len(doc), MAX_PDF_PAGES)):
            chunks.append(doc[index].get_text("text") or "")
        return "\n".join(chunks)[:MAX_TEXT_CHARS]
    except Exception:
        return ""


def _extract_pdf_tables(path: Path) -> List[List[List[str]]]:
    """
    Extract PDF tables using pdfplumber when available. Returns a list of tables,
    each table being a list of rows.
    """
    try:
        import pdfplumber
    except Exception:
        return []

    tables: List[List[List[str]]] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:MAX_PDF_PAGES]:
                page_tables = page.extract_tables() or []
                for table in page_tables:
                    cleaned_table: List[List[str]] = []
                    for row in table or []:
                        cleaned_row = [_clean_cell(cell) for cell in (row or [])]
                        if any(cleaned_row):
                            cleaned_table.append(cleaned_row)
                    if cleaned_table:
                        tables.append(cleaned_table)
    except Exception:
        return tables

    return tables


def _extract_html_text(path: Path) -> str:
    try:
        raw = path.read_text(errors="ignore")
    except Exception:
        return ""

    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"&nbsp;?", " ", raw, flags=re.I)
    raw = re.sub(r"&amp;?", "&", raw, flags=re.I)
    raw = re.sub(r"&lt;?", "<", raw, flags=re.I)
    raw = re.sub(r"&gt;?", ">", raw, flags=re.I)
    return re.sub(r"\s+", " ", raw).strip()[:MAX_TEXT_CHARS]


def _extract_html_tables(path: Path) -> List[List[List[str]]]:
    try:
        raw = path.read_text(errors="ignore")
    except Exception:
        return []

    tables: List[List[List[str]]] = []
    for table_html in re.findall(r"<table\b.*?</table>", raw, flags=re.I | re.S):
        rows: List[List[str]] = []
        for row_html in re.findall(r"<tr\b.*?</tr>", table_html, flags=re.I | re.S):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, flags=re.I | re.S)
            cleaned = []
            for cell in cells:
                cell = re.sub(r"<[^>]+>", " ", cell)
                cell = re.sub(r"&nbsp;?", " ", cell, flags=re.I)
                cell = re.sub(r"&amp;?", "&", cell, flags=re.I)
                cleaned.append(_clean_cell(cell))
            if any(cleaned):
                rows.append(cleaned)
        if rows:
            tables.append(rows)
    return tables


def _extract_csv_table(path: Path) -> List[List[List[str]]]:
    try:
        with path.open("r", errors="ignore", newline="") as f:
            rows = [[_clean_cell(c) for c in row] for row in csv.reader(f)]
            rows = [row for row in rows if any(row)]
            return [rows] if rows else []
    except Exception:
        return []


def extract_text_and_tables(download: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(download, dict) or download.get("status") != "downloaded":
        return {
            "status": "skipped",
            "reason": "not_downloaded",
            "text": "",
            "tables": [],
        }

    path = Path(_safe_str(download.get("path")))
    if not path.exists():
        return {
            "status": "failed",
            "reason": "file_missing",
            "path": str(path),
            "text": "",
            "tables": [],
        }

    ext = _safe_lower(path.suffix)
    text = ""
    tables: List[List[List[str]]] = []
    method = "unsupported"

    if ext == ".pdf":
        text = _extract_pdf_text(path)
        tables = _extract_pdf_tables(path)
        method = "pdf_text_tables"
    elif ext in {".html", ".htm"}:
        text = _extract_html_text(path)
        tables = _extract_html_tables(path)
        method = "html_text_tables"
    elif ext == ".csv":
        try:
            text = path.read_text(errors="ignore")[:MAX_TEXT_CHARS]
        except Exception:
            text = ""
        tables = _extract_csv_table(path)
        method = "csv_table"
    elif ext in {".txt"}:
        try:
            text = path.read_text(errors="ignore")[:MAX_TEXT_CHARS]
        except Exception:
            text = ""
        method = "plain_text"

    return {
        "status": "ok" if (text or tables) else "empty",
        "path": str(path),
        "extension": ext,
        "method": method,
        "text": text,
        "text_length": len(text),
        "tables": tables,
        "table_count": len(tables),
    }


def _table_has_boq_headers(row: List[str]) -> bool:
    joined = " ".join(_safe_lower(c) for c in row)
    return (
        ("description" in joined or "item" in joined or "specification" in joined)
        and ("qty" in joined or "quantity" in joined or "unit" in joined or "uom" in joined)
    )


def _column_indexes(header: List[str]) -> Dict[str, int]:
    indexes: Dict[str, int] = {}
    for i, cell in enumerate(header):
        c = _safe_lower(cell)
        if "item code" in c or c in {"code", "item no", "item number", "no"}:
            indexes.setdefault("item_code", i)
        if "description" in c or "specification" in c or "goods" in c or "service" in c:
            indexes.setdefault("description", i)
        if "qty" in c or "quantity" in c:
            indexes.setdefault("quantity", i)
        if c in {"unit", "uom", "unit of measure"} or "unit of measure" in c:
            indexes.setdefault("unit", i)
        if "specification" in c:
            indexes.setdefault("specification", i)
    return indexes


def _row_to_line_item(row: List[str], indexes: Dict[str, int], source: str) -> Optional[Dict[str, Any]]:
    def get(index_name: str) -> str:
        idx = indexes.get(index_name)
        if idx is None or idx >= len(row):
            return ""
        return _clean_cell(row[idx])

    description = get("description")
    specification = get("specification")
    item_code = get("item_code")
    quantity_raw = get("quantity")
    unit = get("unit")

    if not description and specification:
        description = specification

    quantity = _to_float(quantity_raw)

    if not unit:
        # Try to infer unit from quantity cell or row.
        joined = " ".join(row)
        m = re.search(r"\b\d+(?:[,.]\d+)?\s*(" + "|".join(re.escape(u) for u in sorted(KNOWN_UNITS, key=len, reverse=True)) + r")\b", joined, flags=re.I)
        if m:
            unit = m.group(1)

    if not description:
        return None

    # Reject rows that are clearly not buyer line items.
    desc_l = _safe_lower(description)
    if any(x in desc_l for x in ["subtotal", "total", "vat", "signature", "name of bidder", "company name"]):
        return None

    confidence = 0.35
    evidence: List[str] = [source]

    if quantity is not None:
        confidence += 0.25
        evidence.append("quantity_from_table")
    if unit:
        confidence += 0.15
        evidence.append("unit_from_table")
    if item_code:
        confidence += 0.10
        evidence.append("item_code_from_table")
    if len(description) >= 12:
        confidence += 0.10
        evidence.append("description_from_table")

    return {
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "item_code": item_code,
        "specification": specification if specification != description else "",
        "confidence": min(confidence, 0.95),
        "evidence": evidence,
        "source": source,
    }


def extract_line_items_from_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for table_index, table in enumerate(tables):
        if not table:
            continue

        header_index = -1
        for i, row in enumerate(table[:8]):
            if _table_has_boq_headers(row):
                header_index = i
                break

        if header_index < 0:
            continue

        header = table[header_index]
        indexes = _column_indexes(header)

        if "description" not in indexes:
            continue

        for row in table[header_index + 1:]:
            item = _row_to_line_item(row, indexes, source=f"table_{table_index}")
            if item:
                items.append(item)

    return items


def extract_line_items_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Conservative fallback extraction from text lines. It only returns items when
    a line contains clear quantity + unit evidence. It does not invent quantities.
    """
    text = _safe_str(text)
    if not text:
        return []

    items: List[Dict[str, Any]] = []
    unit_pattern = "|".join(re.escape(u) for u in sorted(KNOWN_UNITS, key=len, reverse=True))
    pattern = re.compile(
        rf"(?P<desc>[A-Za-z][A-Za-z0-9 ,./()&:%\-]{{8,180}}?)\s+"
        rf"(?P<qty>\d+(?:[,.]\d+)?)\s*(?P<unit>{unit_pattern})\b",
        flags=re.I,
    )

    for match in pattern.finditer(text):
        description = _clean_cell(match.group("desc"))
        quantity = _to_float(match.group("qty"))
        unit = _clean_cell(match.group("unit"))

        if quantity is None or not unit:
            continue

        desc_l = _safe_lower(description)
        if any(x in desc_l for x in ["closing date", "validity period", "bid box", "address", "telephone"]):
            continue

        items.append({
            "description": description[-180:],
            "quantity": quantity,
            "unit": unit,
            "item_code": "",
            "specification": "",
            "confidence": 0.55,
            "evidence": ["quantity_and_unit_from_text"],
            "source": "text_pattern",
        })

    return items[:100]


def _dedupe_line_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()

    for item in items:
        desc = _safe_lower(item.get("description"))
        qty = item.get("quantity")
        unit = _safe_lower(item.get("unit"))
        code = _safe_lower(item.get("item_code"))

        key = (desc[:120], qty, unit, code)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


def _detect_returnables(text: str) -> Dict[str, Any]:
    t = _safe_lower(text)

    sbd_forms = sorted(set(re.findall(r"\bSBD\s*([0-9](?:\.[0-9])?)\b", text, flags=re.I)))

    return {
        "returnables_mentioned": any(k in t for k in RETURNABLE_KEYWORDS),
        "sbd_forms_detected": [f"SBD {x}" for x in sbd_forms],
        "tax_compliance_mentioned": "tax compliance" in t or ("tax" in t and "pin" in t),
        "csd_mentioned": "central supplier database" in t or "csd" in t,
        "bbbee_mentioned": "b-bbee" in t or "bbbee" in t or "bbee" in t,
    }


def _detect_boq_context(text: str, tables: List[List[List[str]]]) -> Dict[str, Any]:
    t = _safe_lower(text)
    table_header_hits = 0
    for table in tables:
        for row in table[:8]:
            if _table_has_boq_headers(row):
                table_header_hits += 1
                break

    return {
        "boq_keywords_detected": [k for k in BOQ_KEYWORDS if k in t],
        "has_boq_or_pricing_schedule": any(k in t for k in BOQ_KEYWORDS) or table_header_hits > 0,
        "table_count": len(tables),
        "boq_like_table_count": table_header_hits,
    }


def _normalise_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalised: List[Dict[str, Any]] = []

    for item in items:
        quantity = item.get("quantity")
        if quantity is None:
            # Do not hallucinate missing quantities.
            continue

        description = _clean_cell(item.get("description"))
        if not description:
            continue

        normalised.append({
            "description": description,
            "quantity": float(quantity),
            "unit": _clean_cell(item.get("unit")),
            "item_code": _clean_cell(item.get("item_code")),
            "specification": _clean_cell(item.get("specification")),
            "confidence": float(item.get("confidence") or 0.0),
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
            "source": _safe_str(item.get("source")),
        })

    return normalised


def _overall_confidence(items: List[Dict[str, Any]], context: Dict[str, Any]) -> float:
    if not items:
        return 0.0

    avg = sum(float(i.get("confidence") or 0.0) for i in items) / max(len(items), 1)
    bonus = 0.0
    if context.get("has_boq_or_pricing_schedule"):
        bonus += 0.1
    if context.get("boq_like_table_count", 0) > 0:
        bonus += 0.15

    return round(min(avg + bonus, 0.98), 4)


def _write_json(path: Path, data: Dict[str, Any] | List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def extract_rfq_boq(item: Dict[str, Any], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Main entry point for REAL BUYER DOCUMENT EXTRACTION ENGINE.

    It returns only line items supported by document/table/text evidence. It does
    not generate fallback fake quantities.
    """
    _ensure_dirs()

    if not isinstance(item, dict):
        item = {}

    title = _safe_str(item.get("title") or item.get("buyer_rfq_number") or item.get("rfq_number") or "rfq")
    run_slug = _slug(title)
    run_dir = EXTRACTED_DIR / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)

    reused_downloads = _reuse_document_intelligence_downloads(item)
    links = extract_document_links(item)

    downloaded_urls = {_safe_str(d.get("url")) for d in reused_downloads}
    fresh_downloads = [
        download_document(url, title=title, timeout_seconds=timeout_seconds)
        for url in links
        if url not in downloaded_urls
    ]

    downloads = reused_downloads + fresh_downloads

    extraction_results: List[Dict[str, Any]] = []
    all_tables: List[List[List[str]]] = []
    combined_text_parts: List[str] = []

    for download in downloads:
        extracted = extract_text_and_tables(download)
        clean_extracted = dict(extracted)
        text = _safe_str(clean_extracted.pop("text", ""))
        tables = clean_extracted.pop("tables", [])

        extraction_results.append(clean_extracted)

        if text:
            combined_text_parts.append(text)
        if isinstance(tables, list):
            all_tables.extend(tables)

    combined_text = "\n\n".join(combined_text_parts)[:MAX_TEXT_CHARS]

    table_items = extract_line_items_from_tables(all_tables)
    text_items = extract_line_items_from_text(combined_text)

    extracted_items = _dedupe_line_items(table_items + text_items)
    normalised_items = _normalise_items(extracted_items)

    boq_context = _detect_boq_context(combined_text, all_tables)
    returnables = _detect_returnables(combined_text)
    confidence = _overall_confidence(normalised_items, boq_context)

    status = "ok"
    if not downloads:
        status = "no_documents"
    elif not normalised_items:
        status = "no_line_items_extracted"

    report: Dict[str, Any] = {
        "status": status,
        "engine_version": ENGINE_VERSION,
        "extracted_at": _now_iso(),
        "title": title,
        "buyer_name": _safe_str(item.get("buyer_name")),
        "buyer_rfq_number": _safe_str(item.get("buyer_rfq_number")),
        "links": links,
        "downloads": downloads,
        "extraction_results": extraction_results,
        "boq_context": boq_context,
        "returnables": returnables,
        "line_item_count": len(normalised_items),
        "confidence": confidence,
        "reject_fake_quantities": True,
        "line_items": normalised_items,
    }

    extracted_line_items_path = run_dir / "extracted_line_items.json"
    normalised_boq_path = run_dir / "normalized_boq.json"
    report_path = run_dir / "extraction_report.json"

    _write_json(extracted_line_items_path, normalised_items)
    _write_json(normalised_boq_path, {
        "title": title,
        "buyer_rfq_number": _safe_str(item.get("buyer_rfq_number")),
        "line_items": normalised_items,
        "confidence": confidence,
        "boq_context": boq_context,
    })
    _write_json(report_path, report)

    report["paths"] = {
        "extracted_line_items": str(extracted_line_items_path),
        "normalized_boq": str(normalised_boq_path),
        "extraction_report": str(report_path),
    }

    return report


def extract_boq_from_rfq(item: Dict[str, Any], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Alias for API compatibility.
    """
    return extract_rfq_boq(item, timeout_seconds=timeout_seconds)


def get_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "runtime_dir": str(RUNTIME_DIR),
        "download_dir": str(DOWNLOAD_DIR),
        "report_dir": str(REPORT_DIR),
        "extracted_dir": str(EXTRACTED_DIR),
        "capabilities": [
            "reuse_rfq_document_intelligence_downloads",
            "download_document_source_detail_urls",
            "pdf_text_extraction",
            "pdf_table_extraction_when_pdfplumber_available",
            "html_table_extraction",
            "csv_table_extraction",
            "boq_pricing_schedule_detection",
            "quantity_unit_detection",
            "mandatory_returnables_detection",
            "confidence_scoring",
            "reject_hallucinated_fake_quantities",
            "write_extracted_line_items_json",
            "write_normalized_boq_json",
            "write_extraction_report_json",
        ],
    }
