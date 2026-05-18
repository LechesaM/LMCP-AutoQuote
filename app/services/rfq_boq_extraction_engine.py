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
MAX_LOCAL_FILE_BYTES = 50 * 1024 * 1024

KNOWN_UNITS = {
    "each", "ea", "unit", "units", "box", "boxes", "pack", "packs",
    "lot", "lots", "set", "sets", "pair", "pairs", "roll", "rolls",
    "ream", "reams", "kg", "g", "ton", "tons", "litre", "litres",
    "liter", "liters", "ml", "m", "mm", "cm", "metre", "metres",
    "meter", "meters", "month", "months", "year", "years",
}

TIME_PERIOD_UNITS = {
    "day", "days", "week", "weeks", "month", "months", "year", "years",
}

PRICE_CONTEXT_TERMS = [
    "pricing schedule",
    "price schedule",
    "schedule of prices",
    "quotation schedule",
    "bill of quantities",
    "boq",
    "unit price",
    "total price",
    "price",
    "amount",
    "rate",
    "item description",
    "description of goods",
    "description/specification",
]

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


def _extract_local_document_paths(item: Dict[str, Any]) -> List[str]:
    if not isinstance(item, dict):
        return []

    candidates: List[str] = []
    for key in ("local_document_paths", "document_paths", "uploaded_files", "files"):
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for inner_key in ("path", "local_path", "file_path"):
                        candidates.append(_safe_str(entry.get(inner_key)))
                else:
                    candidates.append(_safe_str(entry))
        elif isinstance(value, dict):
            for inner_key in ("path", "local_path", "file_path"):
                candidates.append(_safe_str(value.get(inner_key)))
        else:
            candidates.append(_safe_str(value))

    paths: List[str] = []
    for candidate in _unique_preserve_order(candidates):
        if not candidate:
            continue
        try:
            path = Path(candidate).expanduser().resolve()
        except Exception:
            continue
        if not path.exists() or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_LOCAL_FILE_BYTES:
                continue
        except Exception:
            continue
        paths.append(str(path))
    return paths


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


def _extract_spreadsheet_tables(path: Path) -> List[List[List[str]]]:
    try:
        from openpyxl import load_workbook
    except Exception:
        return []

    tables: List[List[List[str]]] = []
    try:
        workbook = load_workbook(filename=str(path), data_only=True, read_only=True)
    except Exception:
        return []

    try:
        for sheet in workbook.worksheets:
            rows: List[List[str]] = []
            for row in sheet.iter_rows(values_only=True):
                cleaned = [_clean_cell(cell) for cell in (row or [])]
                if any(cleaned):
                    rows.append(cleaned)
            if rows:
                tables.append(rows)
    except Exception:
        return tables
    finally:
        try:
            workbook.close()
        except Exception:
            pass

    return tables


def _spreadsheet_tables_to_text(tables: List[List[List[str]]]) -> str:
    lines: List[str] = []
    for table in tables:
        for row in table:
            line = " | ".join(cell for cell in row if cell)
            if line:
                lines.append(line)
    return "\n".join(lines)[:MAX_TEXT_CHARS]


def _extract_docx_tables(path: Path) -> Tuple[str, List[List[List[str]]]]:
    try:
        from docx import Document
    except Exception:
        return "", []

    try:
        doc = Document(str(path))
    except Exception:
        return "", []

    paragraphs: List[str] = []
    for paragraph in doc.paragraphs:
        text = _clean_cell(paragraph.text)
        if text:
            paragraphs.append(text)

    tables: List[List[List[str]]] = []
    for table in doc.tables:
        rows: List[List[str]] = []
        for row in table.rows:
            cells = [_clean_cell(cell.text) for cell in row.cells]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)

    table_text: List[str] = []
    for table in tables:
        for row in table:
            line = " | ".join(cell for cell in row if cell)
            if line:
                table_text.append(line)

    text = "\n".join(paragraphs + table_text)[:MAX_TEXT_CHARS]
    return text, tables


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
    elif ext in {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}:
        tables = _extract_spreadsheet_tables(path)
        text = _spreadsheet_tables_to_text(tables)
        method = "spreadsheet_table"
    elif ext == ".docx":
        text, tables = _extract_docx_tables(path)
        method = "docx_table_text"
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
        if "unit price" in c or c in {"rate", "price", "estimated unit price", "estimated price"}:
            indexes.setdefault("unit_price", i)
        if "line total" in c or "total excl" in c or "total ex vat" in c or "amount excl" in c or "amount ex vat" in c:
            indexes.setdefault("line_total", i)
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
    unit_price_raw = get("unit_price")
    line_total_raw = get("line_total")

    if not description and specification:
        description = specification

    quantity = _to_float(quantity_raw)
    unit_price = _to_float(unit_price_raw)
    line_total = _to_float(line_total_raw)

    if unit_price is None and line_total is not None and quantity not in (None, 0):
        try:
            unit_price = round(float(line_total) / float(quantity), 4)
        except Exception:
            unit_price = None

    if line_total is None and unit_price is not None and quantity not in (None, 0):
        try:
            line_total = round(float(unit_price) * float(quantity), 2)
        except Exception:
            line_total = None

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
    if unit_price is not None:
        confidence += 0.20
        evidence.append("unit_price_from_table")
    if line_total is not None:
        confidence += 0.15
        evidence.append("line_total_from_table")

    return {
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "item_code": item_code,
        "specification": specification if specification != description else "",
        "unit_price": unit_price,
        "line_total": line_total,
        "pricing_status": "priced" if unit_price not in (None, 0) and line_total not in (None, 0) else "pending_price",
        "pricing_source": "buyer_boq_table",
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

        table_blob = " ".join(" ".join(_safe_lower(cell) for cell in row) for row in table[:12])
        if not any(term in table_blob for term in PRICE_CONTEXT_TERMS):
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
    text_lower = _safe_lower(text)
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
        window_start = max(0, match.start() - 140)
        window_end = min(len(text), match.end() + 140)
        context = _safe_lower(text[window_start:window_end])

        if quantity is None or not unit:
            continue

        desc_l = _safe_lower(description)
        if any(x in desc_l for x in [
            "closing date",
            "validity period",
            "bid box",
            "address",
            "telephone",
            "envelope",
            "copy",
            "confidential",
            "confidentiality",
            "response must",
            "physical size",
            "bid response",
            "returnable",
            "sbd",
            "terms and conditions",
            "total price",
            "price for",
            "total amount",
            "grand total",
            "subtotal",
        ]):
            continue
        if desc_l in {"quantity", "quantity:", "unit", "unit:", "unit price", "line total", "price", "amount"}:
            continue
        if desc_l.startswith(("quantity ", "quantity:", "unit ", "unit:", "price ", "price:", "line total", "amount ")):
            continue
        if unit.lower() in TIME_PERIOD_UNITS and any(
            marker in desc_l
            for marker in (
                "period of",
                "valid for",
                "validity period",
                "for a period",
                "months after",
                "days after",
                "delivery within",
                "lead time",
                "completion within",
                "response within",
                "price for",
                "total price",
            )
        ):
            continue
        if not any(term in context for term in PRICE_CONTEXT_TERMS):
            continue

        items.append({
            "description": description[-180:],
            "quantity": quantity,
            "unit": unit,
            "item_code": "",
            "specification": "",
            "unit_price": None,
            "line_total": None,
            "pricing_status": "pending_price",
            "pricing_source": "buyer_boq_text",
            "confidence": 0.55,
            "evidence": ["quantity_and_unit_from_text"],
            "source": "text_pattern",
        })

    if any(term in text_lower for term in BOQ_KEYWORDS):
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        item_header = re.compile(r"^(?:item|line item|lot|section)\s*(?P<num>\d+)?\s*[:.\-]?\s*(?P<desc>.+)$", flags=re.I)
        numbered_header = re.compile(r"^(?P<num>\d+)\.\s*(?P<desc>.+)$", flags=re.I)
        field_patterns = {
            "quantity": re.compile(r"^quantity\s*[:\-]\s*(?P<value>.+)$", flags=re.I),
            "unit": re.compile(r"^unit\s*(?:of measure|uom)?\s*[:\-]\s*(?P<value>.+)$", flags=re.I),
            "unit_price": re.compile(r"^(?:unit price|rate|price|estimated unit price)\s*[:\-]\s*(?P<value>.+)$", flags=re.I),
            "line_total": re.compile(r"^(?:line total|total|amount)\s*[:\-]\s*(?P<value>.+)$", flags=re.I),
            "specification": re.compile(r"^specification\s*[:\-]\s*(?P<value>.+)$", flags=re.I),
        }

        def _finalise_section(section: Dict[str, Any]) -> None:
            description = _clean_cell(section.get("description"))
            quantity = _to_float(section.get("quantity"))
            unit = _clean_cell(section.get("unit")) or "Each"
            if not description or quantity is None:
                return
            unit_price = _to_float(section.get("unit_price"))
            line_total = _to_float(section.get("line_total"))
            if unit_price is None and line_total is not None and quantity not in (None, 0):
                try:
                    unit_price = round(float(line_total) / float(quantity), 4)
                except Exception:
                    unit_price = None
            if line_total is None and unit_price is not None and quantity not in (None, 0):
                try:
                    line_total = round(float(unit_price) * float(quantity), 2)
                except Exception:
                    line_total = None
            priced = unit_price is not None and unit_price > 0 and line_total is not None and line_total > 0
            items.append({
                "description": description[-180:],
                "quantity": quantity,
                "unit": unit,
                "item_code": "",
                "specification": _clean_cell(section.get("specification")),
                "unit_price": unit_price,
                "line_total": line_total,
                "pricing_status": "priced" if priced else "pending_price",
                "pricing_source": "buyer_boq_text",
                "confidence": 0.60 if priced else 0.50,
                "evidence": ["section_header", "quantity_and_unit_from_text"],
                "source": "text_section",
            })

        def _next_non_empty_index(start_index: int) -> Optional[int]:
            for j in range(start_index + 1, len(lines)):
                if lines[j].strip():
                    return j
            return None

        def _looks_like_item_title(index: int) -> bool:
            line = lines[index].strip()
            if not line:
                return False
            if item_header.match(line) or numbered_header.match(line):
                return False
            if any(pattern.match(line) for pattern in field_patterns.values()):
                return False
            next_idx = _next_non_empty_index(index)
            if next_idx is None:
                return False
            next_line = lines[next_idx].strip()
            if any(pattern.match(next_line) for pattern in field_patterns.values()):
                return True
            # Allow a short run of non-field lines before the quantity block.
            for j in range(next_idx, min(len(lines), next_idx + 4)):
                candidate = lines[j].strip()
                if not candidate:
                    continue
                if any(pattern.match(candidate) for pattern in field_patterns.values()):
                    return True
                if item_header.match(candidate) or numbered_header.match(candidate):
                    return False
            return False

        current: Optional[Dict[str, Any]] = None
        for idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue

            item_line_match = item_header.match(line)
            if item_line_match:
                if current:
                    _finalise_section(current)
                current = {
                    "description": _clean_cell(item_line_match.group("desc")),
                    "quantity": None,
                    "unit": "",
                    "unit_price": None,
                    "line_total": None,
                    "specification": "",
                }
                continue

            if numbered_header.match(line):
                # Ignore summary headings like "1. Backpack" and
                # "3. Ruler" when they are followed by more numbered headings.
                next_idx = _next_non_empty_index(idx)
                if next_idx is not None and numbered_header.match(lines[next_idx].strip()):
                    continue

            if _looks_like_item_title(idx):
                if current:
                    _finalise_section(current)
                current = {
                    "description": _clean_cell(line),
                    "quantity": None,
                    "unit": "",
                    "unit_price": None,
                    "line_total": None,
                    "specification": "",
                }
                continue

            if current is None:
                continue

            matched_field = False
            for field_name, field_pattern in field_patterns.items():
                match = field_pattern.match(line)
                if not match:
                    continue
                current[field_name] = match.group("value")
                matched_field = True
                break

            if matched_field:
                continue

        if current:
            _finalise_section(current)

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


def _classify_document_artifact(filename: str, text: str, tables: List[List[List[str]]]) -> Dict[str, Any]:
    name = _safe_lower(filename)
    blob = f"{name} {text}".lower()
    has_tables = bool(tables)
    spreadsheet_hint = any(ext in name for ext in (".xlsx", ".xls", ".csv"))
    pricing_terms = any(term in blob for term in BOQ_KEYWORDS if term in {"pricing schedule", "price schedule", "schedule of prices", "quotation schedule"}) or any(
        term in blob for term in ("pricing schedule", "price schedule", "schedule of prices", "quotation schedule", "form of offer", "rate schedule", "unit price", "total price")
    )
    boq_terms = any(term in blob for term in ("bill of quantities", "boq", "quantity", "uom", "unit of measure"))
    sbd_terms = any(term in blob for term in ("sbd", "standard bidding document", "declaration of interest", "bidder's disclosure"))
    returnable_terms = any(term in blob for term in ("returnable", "mandatory returnables", "compulsory returnables", "tax compliance", "csd", "b-bbee", "bbbee", "bbee"))
    technical_terms = any(term in blob for term in ("technical specification", "scope of work", "terms of reference", "specification", "specifications", "delivery", "deliver"))

    pricing_schedule_confidence = 0.0
    boq_confidence = 0.0
    returnable_confidence = 0.0
    technical_confidence = 0.0

    if spreadsheet_hint:
        pricing_schedule_confidence += 0.45
        boq_confidence += 0.35
    if has_tables:
        pricing_schedule_confidence += 0.15
        boq_confidence += 0.15
    if pricing_terms:
        pricing_schedule_confidence += 0.25
    if boq_terms:
        boq_confidence += 0.25
    if "unit price" in blob or "total price" in blob or "rate" in blob:
        pricing_schedule_confidence += 0.15
        boq_confidence += 0.10
    if sbd_terms:
        returnable_confidence += 0.25
    if returnable_terms:
        returnable_confidence += 0.35
    if technical_terms:
        technical_confidence += 0.35
    if "specification" in blob or "scope of work" in blob:
        technical_confidence += 0.25

    pricing_schedule_confidence = round(min(pricing_schedule_confidence, 1.0), 4)
    boq_confidence = round(min(boq_confidence, 1.0), 4)
    returnable_confidence = round(min(returnable_confidence, 1.0), 4)
    technical_confidence = round(min(technical_confidence, 1.0), 4)

    role_candidates = {
        "pricing_schedule": pricing_schedule_confidence,
        "boq": boq_confidence,
        "commercial_returnable": returnable_confidence,
        "technical_document": technical_confidence,
    }
    role = max(role_candidates.items(), key=lambda pair: pair[1])[0]
    if role_candidates[role] <= 0.0:
        role = "supporting_document"

    if role == "pricing_schedule" and pricing_schedule_confidence < 0.65:
        # SBD pricing sections often mention pricing but do not contain a real commercial schedule.
        role = "pricing_schedule_shell" if sbd_terms else "commercial_returnable"
    elif role == "boq" and boq_confidence < 0.65:
        role = "boq_shell"
    elif sbd_terms and role not in {"pricing_schedule", "boq"}:
        role = "sbd_form"

    return {
        "document_role": role,
        "pricing_schedule_confidence": pricing_schedule_confidence,
        "boq_confidence": boq_confidence,
        "commercial_returnable_confidence": returnable_confidence,
        "technical_document_confidence": technical_confidence,
        "has_spreadsheet_hint": spreadsheet_hint,
        "has_tables": has_tables,
        "signals": {
            "pricing_terms": pricing_terms,
            "boq_terms": boq_terms,
            "sbd_terms": sbd_terms,
            "returnable_terms": returnable_terms,
            "technical_terms": technical_terms,
        },
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
            "unit": _clean_cell(item.get("unit")) or "Each",
            "item_code": _clean_cell(item.get("item_code")),
            "specification": _clean_cell(item.get("specification")),
            "unit_price": _to_float(item.get("unit_price")),
            "line_total": _to_float(item.get("line_total")),
            "pricing_status": _safe_str(item.get("pricing_status")) or ("priced" if _to_float(item.get("unit_price")) not in (None, 0) and _to_float(item.get("line_total")) not in (None, 0) else "pending_price"),
            "pricing_source": _safe_str(item.get("pricing_source")) or "buyer_boq_extraction",
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
    local_downloads = [
        {
            "status": "downloaded",
            "url": f"file://{path}",
            "final_url": f"file://{path}",
            "path": path,
            "filename": Path(path).name,
            "extension": Path(path).suffix.lower(),
            "content_type": "application/octet-stream",
            "status_code": 200,
            "size_bytes": Path(path).stat().st_size if Path(path).exists() else 0,
            "source": "local_file",
        }
        for path in _extract_local_document_paths(item)
    ]
    links = extract_document_links(item)

    downloaded_urls = {_safe_str(d.get("url")) for d in reused_downloads + local_downloads}
    fresh_downloads = [
        download_document(url, title=title, timeout_seconds=timeout_seconds)
        for url in links
        if url not in downloaded_urls
    ]

    downloads = reused_downloads + local_downloads + fresh_downloads

    extraction_results: List[Dict[str, Any]] = []
    document_classifications: List[Dict[str, Any]] = []
    all_tables: List[List[List[str]]] = []
    combined_text_parts: List[str] = []

    for download in downloads:
        extracted = extract_text_and_tables(download)
        clean_extracted = dict(extracted)
        text = _safe_str(clean_extracted.pop("text", ""))
        tables = clean_extracted.pop("tables", [])
        classification = _classify_document_artifact(_safe_str(download.get("filename") or Path(_safe_str(download.get("path"))).name), text, tables)
        clean_extracted.update(classification)

        extraction_results.append(clean_extracted)
        document_classifications.append({
            "filename": _safe_str(download.get("filename") or Path(_safe_str(download.get("path"))).name),
            "path": _safe_str(download.get("path")),
            "extension": _safe_str(download.get("extension")),
            "status": _safe_str(download.get("status")),
            **classification,
        })

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
    pricing_schedule_files = [row for row in document_classifications if row.get("document_role") in {"pricing_schedule", "pricing_schedule_shell"}]
    boq_files = [row for row in document_classifications if row.get("document_role") in {"boq", "boq_shell"}]
    commercial_returnable_files = [row for row in document_classifications if row.get("document_role") in {"commercial_returnable", "sbd_form"}]
    technical_files = [row for row in document_classifications if row.get("document_role") == "technical_document"]
    pricing_schedule_confidence = round(max([row.get("pricing_schedule_confidence", 0.0) for row in document_classifications] + [0.0]), 4)
    boq_confidence = round(max([row.get("boq_confidence", 0.0) for row in document_classifications] + [0.0]), 4)
    commercial_returnables_confidence = round(max([row.get("commercial_returnable_confidence", 0.0) for row in document_classifications] + [0.0]), 4)
    technical_document_confidence = round(max([row.get("technical_document_confidence", 0.0) for row in document_classifications] + [0.0]), 4)
    confidence = _overall_confidence(normalised_items, boq_context)
    if pricing_schedule_confidence >= 0.65:
        confidence = round(min(1.0, max(confidence, pricing_schedule_confidence)), 4)
    if boq_confidence >= 0.65:
        confidence = round(min(1.0, max(confidence, boq_confidence)), 4)

    status = "ok"
    if not downloads:
        status = "no_documents"
    elif not normalised_items:
        status = "no_line_items_extracted"

    warnings: List[str] = []
    if status == "no_line_items_extracted":
        if any(str(doc.get("extension") or "").lower() == ".pdf" for doc in document_classifications):
            warnings.append("source PDF text extraction failed or produced no RFQ items.")
        else:
            warnings.append("source document extraction produced no RFQ items.")

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
        "document_classifications": document_classifications,
        "boq_context": boq_context,
        "returnables": returnables,
        "combined_text_length": len(combined_text),
        "combined_text_excerpt": combined_text[:4000],
        "line_item_count": len(normalised_items),
        "pricing_schedule_confidence": pricing_schedule_confidence,
        "boq_confidence": boq_confidence,
        "commercial_returnables_confidence": commercial_returnables_confidence,
        "technical_document_confidence": technical_document_confidence,
        "pricing_schedule_files": pricing_schedule_files,
        "boq_files": boq_files,
        "commercial_returnable_files": commercial_returnable_files,
        "technical_files": technical_files,
        "confidence": confidence,
        "reject_fake_quantities": True,
        "warnings": warnings,
        "manual_pricing_required_reason": (
            "Commercial schedule detected but no verified line items were extracted."
            if status == "no_line_items_extracted" and max(pricing_schedule_confidence, boq_confidence) >= 0.65
            else (
                "Pricing schedule shell detected but no verified line items were extracted."
                if status == "no_line_items_extracted" and boq_context.get("has_boq_or_pricing_schedule")
                else (
                    "No buyer pricing schedule detected; manual pricing schedule required."
                    if status == "no_line_items_extracted"
                    else ""
                )
            )
        ),
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
            "local_file_document_ingestion",
            "download_document_source_detail_urls",
            "pdf_text_extraction",
            "pdf_table_extraction_when_pdfplumber_available",
            "html_table_extraction",
            "csv_table_extraction",
            "spreadsheet_table_extraction",
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
