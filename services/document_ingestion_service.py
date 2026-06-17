from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None

try:
    import PyPDF2  # type: ignore
except Exception:
    PyPDF2 = None

from app.services.boq_cleanup_pipeline import run_boq_cleanup_pipeline
from app.services.boq_row_routing_service import attach_boq_routing_to_record
from app.services.buyer_pricing_schedule_mapper_service import attach_buyer_pricing_schedule_mapping_to_record
from app.services.quote_pricing_engine_service import attach_quote_pricing_to_record
from app.services.buyer_pricing_schedule_filler_service import attach_buyer_pricing_schedule_filler_to_record
from app.services.final_output_builder_service import attach_final_output_builder_to_record
from app.services.buyer_pricing_schedule_filler_service import attach_buyer_pricing_schedule_filler_to_record
from app.services.buyer_form_population_service import attach_buyer_form_population_to_record
from app.services.buyer_pdf_renderer_form_filler_service import attach_buyer_pdf_renderer_to_record
from app.services.quote_pack_builder_service import attach_quote_pack_builder_to_record
from app.services.submission_pack_assembler_service import attach_submission_pack_to_record
from app.services.email_submission_preparation_service import attach_email_submission_payload_to_record
from app.services.actual_email_send_service import attach_email_send_result_to_record
from app.services.smtp_preflight_service import attach_smtp_preflight_to_record
from app.services.submission_proof_artifact_service import attach_submission_proof_artifacts_to_record
from app.services.submission_log_dashboard_service import attach_submission_log_and_dashboard_to_record


@dataclass
class ExtractedLineItem:
    item_number: Optional[int]
    description: str
    specification: str = ""
    unit: str = ""
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    source_line: str = ""
    confidence: str = "low"


RFQ_NUMBER_PATTERNS = [
    re.compile(r"\b(?:TENDER NUMBER|TENDER NO\.?|BID NUMBER|RFQ NUMBER|REFERENCE NO\.?)\s*[:#-]?\s*([A-Z]+(?:/[A-Z]+)?\s*\d{1,5}/\d{2,4})\b", re.I),
    re.compile(r"\b([A-Z]+(?:/[A-Z]+)?\s*\d{1,5}/\d{2,4})\b"),
]

DATE_PATTERNS = [
    re.compile(r"\b(?:CLOSING DATE|BID CLOSING DATE|TENDER CLOSING DATE)\s*[:\-]?\s*(.+)", re.I),
]

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"\b(?:\+27|0)\d{2}[- ]?\d{3}[- ]?\d{4}\b")

SECTION_START_PATTERNS = [
    re.compile(r"^\s*16\.\s*PRICING SCHEDULE\b", re.I),
    re.compile(r"^\s*PRICING SCHEDULE\b", re.I),
    re.compile(r"^\s*BILL OF QUANTITIES\b", re.I),
    re.compile(r"^\s*SCHEDULE OF PRICES\b", re.I),
    re.compile(r"^\s*PRICE SCHEDULE\b", re.I),
]

SECTION_END_PATTERNS = [
    re.compile(r"^\s*17\.\s*DECLARATION BY TENDERER\b", re.I),
    re.compile(r"^\s*DECLARATION BY TENDERER\b", re.I),
    re.compile(r"^\s*SPECIAL CONDITIONS OF CONTRACT\b", re.I),
    re.compile(r"^\s*MBD\s*6\.1\b", re.I),
    re.compile(r"^\s*MBD\s*8\b", re.I),
    re.compile(r"^\s*MBD\s*9\b", re.I),
]

IGNORE_ITEM_PATTERNS = [
    re.compile(r"^\s*reference no[:.]?", re.I),
    re.compile(r"^\s*page\s+\d+\s+of\s+\d+", re.I),
    re.compile(r"^\s*\d+\.\s+[A-Z].{0,120}\.{3,}\s*\d+\s*$"),
    re.compile(r"^\s*(price|bbbee|b-bbee|locality|total points?)\s+\d+", re.I),
    re.compile(r"^\s*(closing date|closing time|telephone|email|fax|information)[: ]", re.I),
    re.compile(r"^\s*(tender number|tender no|description|note|bid notice)[: ]", re.I),
    re.compile(r"^\s*\d+(?:\.\d+)+\s"),
    re.compile(r"competition act", re.I),
    re.compile(r"general conditions of contract", re.I),
    re.compile(r"declaration of", re.I),
    re.compile(r"certificate of", re.I),
    re.compile(r"checklist", re.I),
]

LIKELY_ITEM_KEYWORDS = [
    "pen", "pencil", "paper", "envelope", "file", "lever arch", "stapler", "punch", "toner",
    "cartridge", "ink", "marker", "highlighter", "eraser", "ruler", "notebook", "book", "ream",
    "box", "a4", "a5", "stationery", "binder", "clip", "tape", "glue", "scissors", "correction",
]

TABLE_HEADER_PATTERNS = [
    re.compile(r"\bitem\b", re.I),
    re.compile(r"\bdescription\b", re.I),
    re.compile(r"\bqty\b|\bquantity\b", re.I),
    re.compile(r"\bunit price\b|\brate\b", re.I),
    re.compile(r"\btotal\b|\bamount\b", re.I),
]

CHECKLIST_FALSE_POSITIVE_PATTERNS = [
    re.compile(r"is the form duly completed", re.I),
    re.compile(r"\byes\s+no\b", re.I),
    re.compile(r"\bchecklist\b", re.I),
    re.compile(r"\bform of offer\b", re.I),
]

ITEM_START_PATTERN = re.compile(r"^\s*(\d{1,4})\s+(.+)$")
UNIT_TAIL_PATTERN = re.compile(
    r"\b(Each|Box(?:\s+of\s+\d+)?|Pack(?:\s+of\s+\d+)?|Pkt(?:\s+of\s+\d+)?|Ream|Roll(?:\s+of\s+\d+(?:m|mm)?)?|Set|Pair|Dozen|Book|Bottle|Tube|Pad|File|Unit|Units)\s+(\d+(?:[.,]\d+)?)\s*$",
    re.I,
)
SPEC_NUMBER_PATTERN = re.compile(
    r"(\b\d{1,4}/\d{1,4}\b|\b\d+(?:[.,]\d+)?\s*mm\b|\b\d+(?:[.,]\d+)?\s*g(?:/m2)?\b|\b\d+(?:[.,]\d+)?\s*ml\b|\b\d+(?:[.,]\d+)?\s*mic\b|\bA[3456]\b)",
    re.I,
)

PAGE_BREAK_LINE_PATTERNS = [
    re.compile(r"^\s*pricing\s*$", re.I),
    re.compile(r"^\s*schedule\s*$", re.I),
    re.compile(r"^\s*reference no:\s*", re.I),
    re.compile(r"^\s*page \d+ of \d+\s*$", re.I),
    re.compile(r"^\s*item\s*$", re.I),
    re.compile(r"^\s*number\s*$", re.I),
    re.compile(r"^\s*description(?: item specification unit)?\s*$", re.I),
    re.compile(r"^\s*measurement\s*$", re.I),
    re.compile(r"^\s*estimated\s*$", re.I),
    re.compile(r"^\s*quantity\s*$", re.I),
    re.compile(r"^\s*unit price\s*$", re.I),
    re.compile(r"^\s*total\s*$", re.I),
    re.compile(r"^\s*price\s*$", re.I),
    re.compile(r"^\s*\(incl\. vat\)\s*$", re.I),
]

PAGE_BREAK_MULTI_PATTERNS = [
    re.compile(r"reference no:\s*.+page\s+\d+\s+of\s+\d+", re.I),
    re.compile(r"description item specification unit", re.I),
    re.compile(r"unit price\s*\(incl\. vat\)", re.I),
    re.compile(r"total\s*price\s*\(incl\. vat\)", re.I),
]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _coerce_float(value: str) -> Optional[float]:
    text = _clean(value)
    if not text:
        return None
    text = text.replace("R", "").replace(" ", "")
    if text.count(",") > 0 and text.count(".") == 0:
        text = text.replace(",", ".")
    elif text.count(",") > 0 and text.count(".") > 0:
        text = text.replace(",", "")
    try:
        return float(text)
    except Exception:
        return None


def normalize_document_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(record or {})
    normalized["title"] = _clean(normalized.get("title"))
    normalized["url"] = _clean(normalized.get("url"))
    normalized["source_url"] = _clean(normalized.get("source_url"))
    normalized["rfq_number"] = _clean(
        normalized.get("rfq_number")
        or normalized.get("buyer_rfq_number")
        or normalized.get("reference_number")
        or normalized.get("document_number")
    )
    normalized["buyer_name"] = _clean(normalized.get("buyer_name"))
    normalized["closing_date"] = _clean(normalized.get("closing_date"))
    normalized["description"] = _clean(normalized.get("description"))
    normalized["document_links"] = normalized.get("document_links") or []
    normalized["items"] = normalized.get("items") or []
    normalized["line_items"] = normalized.get("line_items") or normalized["items"]
    return normalized


def extract_links_from_html(html: str) -> List[Dict[str, str]]:
    html = html or ""
    links: List[Dict[str, str]] = []
    pattern = re.compile(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for href, text in pattern.findall(html):
        link_text = re.sub(r"<[^>]+>", " ", text)
        links.append({"text": _clean(unescape(link_text)), "href": _clean(unescape(href))})
    return links


def extract_tender_candidates_from_html(html: str, *, source_url: str = "") -> List[Dict[str, Any]]:
    html = html or ""
    links = extract_links_from_html(html)
    results: List[Dict[str, Any]] = []
    for link in links:
        text = _clean(link.get("text"))
        href = _clean(link.get("href"))
        if not text:
            continue
        if any(keyword in text.lower() for keyword in ["tender", "rfq", "bid", "quotation", "request for"]):
            results.append(
                normalize_document_record(
                    {"title": text, "url": urljoin(source_url, href) if source_url else href, "source_url": source_url}
                )
            )
    return results


def _read_pdf_text_with_pypdf(path: Path) -> str:
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(str(path))
        parts: List[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)
    except Exception:
        return ""


def _read_pdf_text_with_pypdf2(path: Path) -> str:
    if PyPDF2 is None:
        return ""
    try:
        reader = PyPDF2.PdfReader(str(path))
        parts: List[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)
    except Exception:
        return ""


def extract_text_from_pdf(path: str | Path) -> str:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = _read_pdf_text_with_pypdf(pdf_path)
    if text.strip():
        return text

    text = _read_pdf_text_with_pypdf2(pdf_path)
    if text.strip():
        return text

    return ""


def _split_lines(text: str) -> List[str]:
    raw_lines = text.replace("\r", "\n").split("\n")
    lines: List[str] = []
    for line in raw_lines:
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return lines


def _strip_page_break_lines(lines: List[str]) -> Tuple[List[str], List[str]]:
    cleaned: List[str] = []
    removed: List[str] = []

    for line in lines:
        if any(p.search(line) for p in PAGE_BREAK_LINE_PATTERNS):
            removed.append(line)
            continue
        if any(p.search(line) for p in PAGE_BREAK_MULTI_PATTERNS):
            removed.append(line)
            continue
        cleaned.append(line)

    return cleaned, removed


def extract_rfq_number(text: str) -> str:
    for pattern in RFQ_NUMBER_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return _clean(match.group(1))
    return ""


def extract_closing_date(text: str) -> str:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return _clean(match.group(1))
    return ""


def extract_emails(text: str) -> List[str]:
    return sorted({m.group(0) for m in EMAIL_PATTERN.finditer(text or "")})


def extract_phone_numbers(text: str) -> List[str]:
    return sorted({m.group(0) for m in PHONE_PATTERN.finditer(text or "")})


def extract_buyer_name(text: str) -> str:
    lines = _split_lines(text)
    for i, line in enumerate(lines[:60]):
        lowered = line.lower()
        if "municipality hereby invites you" in lowered:
            return line.split("HEREBY INVITES", 1)[0].strip(" :")
        if lowered.startswith("stellenbosch municipality"):
            return "STELLENBOSCH MUNICIPALITY"
        if "municipality" in lowered and len(line) < 120 and "invites" not in lowered:
            return line.strip(" :")
        if "organ of state" in lowered and ":" in line:
            return _clean(line.split(":", 1)[1])
        if lowered == "bid notice" and i + 1 < len(lines):
            nxt = lines[i + 1]
            if "municipality" in nxt.lower():
                return nxt.split("HEREBY INVITES", 1)[0].strip(" :")
    return ""


def idx_safe(lines: List[str], idx: int) -> bool:
    return 0 <= idx < len(lines)


def extract_title(text: str, pdf_name: str = "") -> str:
    lines = _split_lines(text)
    for i, line in enumerate(lines[:80]):
        lowered = line.lower()
        if lowered.startswith("description:"):
            value = _clean(line.split(":", 1)[1])
            if idx_safe(lines, i + 1) and len(value) < 30:
                value = f"{value} {lines[i + 1]}"
            return _clean(value)
        if "hereby invites you to tender for" in lowered:
            after = re.split(r"hereby invites you to tender for", line, flags=re.I)
            if len(after) > 1:
                title = after[1]
                title = re.sub(r"^[A-Z]+(?:/[A-Z]+)?\s*\d{1,5}/\d{2,4}\s*:\s*", "", title, flags=re.I)
                if idx_safe(lines, i + 1) and len(title) < 30:
                    title = f"{title} {lines[i + 1]}"
                return _clean(title)
    candidate_prefixes = ["supply and delivery", "appointment", "request for bid", "request for quotation", "quotation", "tender"]
    for idx, line in enumerate(lines[:80]):
        lowered = line.lower()
        if any(prefix in lowered for prefix in candidate_prefixes) and len(line) > 12:
            if idx_safe(lines, idx + 1) and len(line) < 50 and len(lines[idx + 1]) > 20:
                return _clean(f"{line} {lines[idx + 1]}")
            return line
    return Path(pdf_name).stem.replace("_", " ").strip()


def _is_toc_like_line(line: str) -> bool:
    line = _clean(line)
    lowered = line.lower()
    if "..." in line:
        return True
    if re.search(r"\.{5,}\s*\d+\s*$", line):
        return True
    if re.match(r"^\s*\d+\.\s+.+\.{3,}\s*\d+\s*$", line):
        return True
    if lowered.startswith("reference no:") and "page" in lowered:
        return True
    return False


def _is_real_section_header(line: str) -> bool:
    if _is_toc_like_line(line):
        return False
    if len(_clean(line)) > 180:
        return False
    return True


def _is_checklist_false_positive(lines: List[str], idx: int) -> bool:
    window = " ".join(lines[idx:min(idx + 6, len(lines))])
    return any(p.search(window) for p in CHECKLIST_FALSE_POSITIVE_PATTERNS)


def find_pricing_schedule_section(text: str) -> Dict[str, Any]:
    lines = _split_lines(text)
    start_idx = -1
    end_idx = len(lines)
    skipped_toc_hits: List[Dict[str, Any]] = []
    skipped_checklist_hits: List[Dict[str, Any]] = []

    for idx, line in enumerate(lines):
        if any(pattern.search(line) for pattern in SECTION_START_PATTERNS):
            if not _is_real_section_header(line):
                skipped_toc_hits.append({"index": idx, "line": line})
                continue
            if _is_checklist_false_positive(lines, idx):
                skipped_checklist_hits.append({"index": idx, "line": line})
                continue
            start_idx = idx
            break

    if start_idx == -1:
        return {
            "found": False,
            "start_index": -1,
            "end_index": -1,
            "section_text": "",
            "section_lines": [],
            "reason": "Pricing schedule section not found.",
            "skipped_toc_hits": skipped_toc_hits,
            "skipped_checklist_hits": skipped_checklist_hits,
        }

    for idx in range(start_idx + 1, len(lines)):
        line = lines[idx]
        if any(pattern.search(line) for pattern in SECTION_END_PATTERNS):
            if _is_real_section_header(line):
                end_idx = idx
                break

    section_lines = lines[start_idx:end_idx]

    return {
        "found": True,
        "start_index": start_idx,
        "end_index": end_idx,
        "section_text": "\n".join(section_lines),
        "section_lines": section_lines,
        "reason": "",
        "skipped_toc_hits": skipped_toc_hits,
        "skipped_checklist_hits": skipped_checklist_hits,
    }


def _extract_qty_unit(line: str) -> Tuple[Optional[float], str]:
    match = UNIT_TAIL_PATTERN.search(line)
    if not match:
        return None, ""
    return _coerce_float(match.group(2)), _clean(match.group(1))


def _line_should_be_ignored(line: str) -> bool:
    lowered = line.lower()
    if len(line) < 2:
        return True
    if any(p.search(line) for p in IGNORE_ITEM_PATTERNS):
        return True
    if _is_toc_like_line(line):
        return True
    if any(p.search(line) for p in PAGE_BREAK_LINE_PATTERNS):
        return True
    if any(p.search(line) for p in PAGE_BREAK_MULTI_PATTERNS):
        return True
    if lowered in {"yes", "no", "n/a", "vat", "inclusive of vat", "pricing", "schedule", "number", "description item specification unit"}:
        return True
    if re.fullmatch(r"[\d\s./-]+", line):
        return True
    return False


def _table_header_score(window_lines: List[str]) -> int:
    text = " ".join(window_lines)
    score = 0
    for pattern in TABLE_HEADER_PATTERNS:
        if pattern.search(text):
            score += 1
    return score


def find_pricing_table_section(text: str) -> Dict[str, Any]:
    lines = _split_lines(text)
    best_start = -1
    best_score = -1

    for idx in range(len(lines)):
        window = lines[idx:min(idx + 6, len(lines))]
        score = _table_header_score(window)
        if score > best_score:
            best_score = score
            best_start = idx

    if best_score < 3:
        return {
            "found": False,
            "start_index": -1,
            "end_index": -1,
            "section_lines": [],
            "section_text": "",
            "header_score": best_score,
            "reason": "No strong pricing table header found.",
        }

    end_idx = min(best_start + 220, len(lines))
    for idx in range(best_start + 1, min(best_start + 260, len(lines))):
        line = lines[idx]
        lowered = line.lower()
        if any(p.search(line) for p in SECTION_END_PATTERNS):
            end_idx = idx
            break
        if "declaration by tenderer" in lowered:
            end_idx = idx
            break

    section_lines = lines[best_start:end_idx]
    cleaned_lines, removed_page_break_lines = _strip_page_break_lines(section_lines)

    return {
        "found": True,
        "start_index": best_start,
        "end_index": end_idx,
        "section_lines": cleaned_lines,
        "section_text": "\n".join(cleaned_lines),
        "header_score": best_score,
        "reason": "",
        "removed_page_break_lines": removed_page_break_lines,
    }


def _find_next_item_start(lines: List[str], start_idx: int) -> Optional[int]:
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        match = ITEM_START_PATTERN.match(line)
        if not match:
            continue
        item_num = int(match.group(1))
        # Guard against phantom item numbers caused by dimensions or page artifacts
        if item_num > 1500:
            continue
        return idx
    return None


def _is_continuation_line(line: str) -> bool:
    if _line_should_be_ignored(line):
        return False
    if ITEM_START_PATTERN.match(line):
        return False
    return True


def _extract_unit_and_quantity(block_text: str) -> Tuple[str, Optional[float]]:
    match = UNIT_TAIL_PATTERN.search(block_text)
    if not match:
        return "", None
    unit = _clean(match.group(1))
    qty = _coerce_float(match.group(2))
    return unit, qty


def _strip_unit_quantity_tail(block_text: str) -> str:
    match = UNIT_TAIL_PATTERN.search(block_text)
    if not match:
        return block_text
    return block_text[:match.start()].strip()


def _split_description_and_spec(core_text: str) -> Tuple[str, str]:
    parts = [p.strip(" -") for p in re.split(r"\s{2,}|\s-\s", core_text) if p.strip()]
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])

    words = core_text.split()
    if len(words) <= 6:
        return core_text, ""

    desc_words: List[str] = []
    spec_words: List[str] = []
    switched = False
    for word in words:
        token = word.lower()
        if not switched and (
            SPEC_NUMBER_PATTERN.search(word)
            or token in {"uses", "size", "box", "pack", "printed", "metal", "plastic", "hard", "cover", "sheets", "micron", "plain", "colour", "color", "self-adhesive", "adjustable", "bound", "pages", "ruled", "spine"}
        ):
            switched = True
        if switched:
            spec_words.append(word)
        else:
            desc_words.append(word)

    description = " ".join(desc_words).strip()
    specification = " ".join(spec_words).strip()
    if not description:
        description = core_text
        specification = ""
    return description, specification


def _parse_item_block(block_lines: List[str]) -> Optional[Dict[str, Any]]:
    if not block_lines:
        return None

    cleaned_block_lines, _ = _strip_page_break_lines(block_lines)
    if not cleaned_block_lines:
        return None

    first = cleaned_block_lines[0]
    match = ITEM_START_PATTERN.match(first)
    if not match:
        return None

    item_number = int(match.group(1))
    payload = match.group(2).strip()

    continuation_lines = [line for line in cleaned_block_lines[1:] if _is_continuation_line(line)]
    combined = " ".join([payload] + continuation_lines)
    combined = re.sub(r"\s+", " ", combined).strip()

    unit, quantity = _extract_unit_and_quantity(combined)
    core = _strip_unit_quantity_tail(combined)

    description, specification = _split_description_and_spec(core)

    if len(description) < 3:
        return None

    confidence = "medium" if unit and quantity is not None else "low"
    return asdict(
        ExtractedLineItem(
            item_number=item_number,
            description=description,
            specification=specification,
            unit=unit,
            quantity=quantity,
            unit_price=None,
            line_total=None,
            source_line="\n".join(cleaned_block_lines),
            confidence=confidence,
        )
    )


def extract_line_items_from_pricing_section(section_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    raw_lines = _split_lines(section_text)
    lines, removed_page_break_lines = _strip_page_break_lines(raw_lines)

    items: List[Dict[str, Any]] = []
    idx = 0
    seen_numbers = set()

    while idx < len(lines):
        line = lines[idx]
        if _line_should_be_ignored(line):
            idx += 1
            continue

        start_idx = _find_next_item_start(lines, idx)
        if start_idx is None:
            break

        next_start = _find_next_item_start(lines, start_idx + 1)
        block_lines = lines[start_idx:next_start] if next_start is not None else lines[start_idx:]
        item = _parse_item_block(block_lines)

        if item:
            num = item.get("item_number")
            if num not in seen_numbers:
                seen_numbers.add(num)
                items.append(item)

        idx = next_start if next_start is not None else len(lines)

    return items, removed_page_break_lines


def ingest_document(path: str | Path, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    doc_path = Path(path)
    metadata = metadata or {}

    if not doc_path.exists():
        raise FileNotFoundError(f"Document not found: {doc_path}")

    suffix = doc_path.suffix.lower()
    extracted_text = ""
    doc_type = "unknown"

    if suffix == ".pdf":
        doc_type = "pdf"
        extracted_text = extract_text_from_pdf(doc_path)
    elif suffix in {".html", ".htm"}:
        doc_type = "html"
        extracted_text = doc_path.read_text(encoding="utf-8", errors="ignore")
    else:
        doc_type = suffix.lstrip(".") or "unknown"
        extracted_text = doc_path.read_text(encoding="utf-8", errors="ignore")

    lines = _split_lines(extracted_text)
    rfq_number = extract_rfq_number(extracted_text)
    buyer_name = extract_buyer_name(extracted_text)
    closing_date = extract_closing_date(extracted_text)
    emails = extract_emails(extracted_text)
    phones = extract_phone_numbers(extracted_text)
    title = extract_title(extracted_text, pdf_name=doc_path.name)

    pricing_section = find_pricing_schedule_section(extracted_text)
    table_section = find_pricing_table_section(extracted_text)

    items: List[Dict[str, Any]] = []
    removed_page_break_lines: List[str] = []
    extraction_strategy = "none"

    if pricing_section["found"]:
        items, removed_page_break_lines = extract_line_items_from_pricing_section(pricing_section["section_text"])
        extraction_strategy = "pricing_schedule_section"

    if (not items) and table_section["found"]:
        items, removed_page_break_lines = extract_line_items_from_pricing_section(table_section["section_text"])
        extraction_strategy = "table_locator_engine"

    raw_items = items or []
    cleanup_result = run_boq_cleanup_pipeline(
        raw_items,
        attach_debug=False,
        include_debug_meta=False,
        drop_empty_rows=True,
    )
    normalized_items = cleanup_result.get("rows", [])

    record: Dict[str, Any] = {
        "status": "ok",
        "document_path": str(doc_path),
        "document_name": doc_path.name,
        "document_type": doc_type,
        "document_size": doc_path.stat().st_size,
        "title": title or _clean(metadata.get("title")),
        "buyer_name": buyer_name or _clean(metadata.get("buyer_name")),
        "rfq_number": rfq_number or _clean(metadata.get("buyer_rfq_number")),
        "reference_number": rfq_number or _clean(metadata.get("reference_number")),
        "document_number": rfq_number or _clean(metadata.get("document_number")),
        "closing_date": closing_date or _clean(metadata.get("closing_date")),
        "emails": emails,
        "phone_numbers": phones,
        "description": "\n".join(lines[:25]),
        "text_preview": "\n".join(lines[:50]),
        "raw_text_excerpt": extracted_text[:8000],
        "page_text_available": bool(extracted_text.strip()),
        "pricing_schedule_found": pricing_section["found"],
        "pricing_schedule_start_index": pricing_section["start_index"],
        "pricing_schedule_end_index": pricing_section["end_index"],
        "pricing_schedule_preview": "\n".join(pricing_section.get("section_lines", [])[:40]),
        "pricing_schedule_skipped_toc_hits": pricing_section.get("skipped_toc_hits", []),
        "pricing_schedule_skipped_checklist_hits": pricing_section.get("skipped_checklist_hits", []),
        "table_locator_found": table_section["found"],
        "table_locator_start_index": table_section["start_index"],
        "table_locator_end_index": table_section["end_index"],
        "table_locator_header_score": table_section.get("header_score", -1),
        "table_locator_preview": "\n".join(table_section.get("section_lines", [])[:40]),
        "page_break_lines_removed": removed_page_break_lines,
        "extraction_strategy": extraction_strategy,
        "items_raw_count": len(raw_items),
        "items": normalized_items,
        "line_items": normalized_items,
        "item_count": len(normalized_items),
        "boq_cleanup_pipeline": cleanup_result.get("stats", {}),
        "items_ready_count": sum(1 for r in normalized_items if r.get("row_ready_status") == "ready"),
        "items_needs_review_count": sum(1 for r in normalized_items if r.get("row_ready_status") == "needs_review"),
        "items_unusable_count": sum(1 for r in normalized_items if r.get("row_ready_status") == "unusable"),
        "document_links": [],
        "source_url": _clean(metadata.get("source_url")),
        "source_name": _clean(metadata.get("source_name")),
        "metadata": metadata,
    }

    record = attach_boq_routing_to_record(record, items_key="items", include_review_payload=True)
    record = attach_buyer_pricing_schedule_mapping_to_record(
        record,
        pricing_ready_rows_key="pricing_ready_rows",
        review_rows_key="review_rows",
    )
    record = attach_quote_pricing_to_record(
        record,
        buyer_schedule_rows_key="buyer_pricing_schedule_rows",
        metadata_key="metadata",
    )
    record = attach_buyer_pricing_schedule_filler_to_record(
        record,
        priced_rows_key="priced_buyer_schedule_rows",
        include_source_meta=False,
    )
    record = attach_final_output_builder_to_record(
        record,
        final_schedule_items_key="final_buyer_schedule_items",
        review_rows_key="review_rows",
        metadata_key="metadata",
    )
    record = attach_final_output_builder_to_record(record, metadata_key="metadata")
    record = attach_buyer_form_population_to_record(
        record,
        final_output_rows_key="final_output_rows",
        metadata_key="metadata",
        quote_pack_payload_key="quote_pack_payload",
        quote_pack_summary_key="quote_pack_summary",
        review_rows_key="review_rows",
    )
    record = attach_buyer_pdf_renderer_to_record(
        record,
        buyer_form_payload_key="buyer_form_payload",
        populated_form_rows_key="populated_form_rows",
        metadata_key="metadata",
    )
    record = attach_quote_pack_builder_to_record(record)
    record = attach_submission_pack_to_record(record)
    record = attach_email_submission_payload_to_record(record)
    record = attach_smtp_preflight_to_record(record)
    record = attach_email_send_result_to_record(record)
    record = attach_submission_proof_artifacts_to_record(record)
    record = attach_submission_log_and_dashboard_to_record(record)

    return normalize_document_record(record)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python document_ingestion_service.py <document_path>")

    result = ingest_document(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))




