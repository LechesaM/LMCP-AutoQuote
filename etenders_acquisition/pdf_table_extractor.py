import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

from app.db.models import BOQExtraction, BOQItem, TenderDocument
from app.db.session import SessionLocal


MAX_PDFS = 25
MAX_PAGES = 40
MAX_TABLE_ROWS_PER_PDF = 1500

MAX_REASONABLE_QTY = 100_000
MAX_REASONABLE_RATE = 1_000_000
MAX_REASONABLE_LINE_TOTAL = 50_000_000
MAX_DIGITS_IN_NUMBER = 10


PRICEABLE_HINTS = [
    "supply",
    "deliver",
    "delivery",
    "install",
    "installation",
    "repair",
    "replace",
    "construct",
    "excavate",
    "paint",
    "test",
    "commission",
    "maintain",
    "service",
    "remove",
    "provide",
    "clean",
    "refurbish",
    "upgrade",
    "manufacture",
]

UNIT_WORDS = {
    "m": "m",
    "m2": "m2",
    "m²": "m2",
    "m3": "m3",
    "m³": "m3",
    "no": "No",
    "nr": "No",
    "each": "No",
    "item": "Item",
    "sum": "Sum",
    "lot": "Lot",
    "kg": "kg",
    "ton": "ton",
    "l": "L",
    "hr": "hr",
    "day": "day",
}

NON_PRICEABLE_PATTERNS = [
    r"table of contents",
    r"invitation to tender",
    r"conditions of tender",
    r"signature",
    r"company name",
    r"tax compliance",
    r"declaration",
    r"cidb",
    r"returnable schedule",
    r"form of offer",
    r"subtotal",
    r"grand total",
    r"total carried",
]


def now_ts() -> float:
    return time.time()


def clean(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize_numeric_token(value: Any, max_value: float) -> Optional[float]:
    """
    Safe numeric parser for PDF table values.

    Rejects:
    - scientific notation explosions
    - merged-column numeric strings
    - absurd digit lengths
    - negative or zero values
    - values above threshold
    """
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if "e+" in text.lower() or "e-" in text.lower():
        return None

    text = text.replace(",", "")
    text = text.replace("R", "")
    text = text.replace("r", "")
    text = text.replace(" ", "")

    # Reject dates and long reference-like strings.
    if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text):
        return None

    digits = re.sub(r"[^\d]", "", text)

    if not digits:
        return None

    if len(digits) > MAX_DIGITS_IN_NUMBER:
        return None

    # Keep only one clean number token.
    matches = re.findall(r"-?\d+(?:\.\d+)?", text)

    if len(matches) != 1:
        return None

    try:
        number = float(matches[0])
    except Exception:
        return None

    if number <= 0:
        return None

    if number > max_value:
        return None

    return number


def safe_quantity(value: Any) -> Optional[float]:
    return normalize_numeric_token(value, MAX_REASONABLE_QTY)


def safe_money(value: Any) -> Optional[float]:
    return normalize_numeric_token(value, MAX_REASONABLE_LINE_TOTAL)


def is_unit(value: Any) -> bool:
    text = clean(value)

    if not text:
        return False

    key = text.lower().replace(".", "").strip()
    return key in UNIT_WORDS


def detect_unit(values: List[str]) -> Optional[str]:
    for value in values:
        text = clean(value)

        if not text:
            continue

        key = text.lower().replace(".", "").strip()

        if key in UNIT_WORDS:
            return UNIT_WORDS[key]

    return None


def detect_quantity(values: List[str]) -> Optional[float]:
    """
    Conservative quantity detection.

    Only use small/medium values. Avoid grabbing tender numbers,
    dates, telephone numbers, totals, and merged OCR garbage.
    """
    candidates = []

    for value in values:
        text = clean(value)

        if not text:
            continue

        number = safe_quantity(text)

        if number is None:
            continue

        # Avoid year-like quantities unless explicitly small.
        if 1900 <= number <= 2100:
            continue

        candidates.append(number)

    if not candidates:
        return None

    # Prefer the first safe numeric token in BOQ-like rows.
    return candidates[0]


def detect_rate(values: List[str]) -> Optional[float]:
    money_values = []

    for value in values:
        number = safe_money(value)

        if number is not None and number <= MAX_REASONABLE_RATE:
            money_values.append(number)

    if len(money_values) < 2:
        return None

    # Usually after quantity; keep conservative.
    return money_values[-2]


def detect_line_total(values: List[str]) -> Optional[float]:
    money_values = []

    for value in values:
        number = safe_money(value)

        if number is not None:
            money_values.append(number)

    if not money_values:
        return None

    return money_values[-1]


def looks_like_header(text: str) -> bool:
    lower = text.lower()

    header_words = [
        "description",
        "quantity",
        "qty",
        "unit",
        "rate",
        "amount",
        "total",
        "price",
        "schedule",
        "bill of quantities",
    ]

    hits = sum(1 for word in header_words if word in lower)

    return hits >= 2


def detect_description(values: List[str]) -> Optional[str]:
    candidates = []

    for value in values:
        text = clean(value)

        if not text:
            continue

        if is_unit(text):
            continue

        if safe_quantity(text) is not None:
            continue

        if safe_money(text) is not None:
            continue

        if len(text) < 12:
            continue

        if looks_like_header(text):
            continue

        candidates.append(text)

    if not candidates:
        return None

    return max(candidates, key=len)


def detect_item_code(values: List[str]) -> Optional[str]:
    for value in values[:3]:
        text = clean(value)

        if not text:
            continue

        if is_unit(text):
            continue

        if safe_quantity(text) is not None:
            continue

        if len(text) <= 25:
            return text

    return None


def is_priceable_description(description: Optional[str]) -> bool:
    desc = clean(description)

    if not desc:
        return False

    lower = desc.lower()

    if len(desc) < 15:
        return False

    if looks_like_header(desc):
        return False

    for pattern in NON_PRICEABLE_PATTERNS:
        if re.search(pattern, lower):
            return False

    return any(hint in lower for hint in PRICEABLE_HINTS)


def normalize_table_row(row: List[Any]) -> Optional[Dict[str, Any]]:
    values = [clean(v) for v in row]
    values = [v for v in values if v is not None]

    if not values:
        return None

    description = detect_description(values)

    if not description:
        return None

    unit = detect_unit(values)
    quantity = detect_quantity(values)
    unit_rate = detect_rate(values)
    line_total = detect_line_total(values)

    # Reject rows where the only numeric value is clearly corrupted.
    sanity_flags = []

    raw_numbers = [
        str(v)
        for v in values
        if re.search(r"\d", str(v))
    ]

    rejected_numeric_tokens = 0

    for token in raw_numbers:
        digits = re.sub(r"[^\d]", "", token)

        if "e+" in token.lower() or len(digits) > MAX_DIGITS_IN_NUMBER:
            rejected_numeric_tokens += 1

    if rejected_numeric_tokens:
        sanity_flags.append("rejected_corrupt_numeric_token")

    priceable = (
        is_priceable_description(description)
        or quantity is not None
        or unit is not None
    )

    if not priceable:
        return None

    return {
        "item_code": detect_item_code(values),
        "description": description,
        "unit": unit,
        "quantity": quantity,
        "unit_rate": unit_rate,
        "line_total": line_total,
        "values": values,
        "priceable": priceable,
        "sanity_flags": sanity_flags,
    }


def extract_tables_from_pdf(path: Path) -> List[Dict[str, Any]]:
    extracted_rows = []

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "edge_min_length": 3,
        "min_words_vertical": 2,
        "min_words_horizontal": 1,
        "intersection_tolerance": 3,
        "text_tolerance": 3,
    }

    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages[:MAX_PAGES], start=1):
            try:
                tables = page.extract_tables(table_settings=table_settings)
            except Exception:
                try:
                    tables = page.extract_tables()
                except Exception:
                    tables = []

            for table_index, table in enumerate(tables or [], start=1):
                if not table:
                    continue

                for row_index, row in enumerate(table, start=1):
                    normalized = normalize_table_row(row or [])

                    if not normalized:
                        continue

                    normalized["page"] = page_number
                    normalized["table_index"] = table_index
                    normalized["row_index"] = row_index

                    extracted_rows.append(normalized)

                    if len(extracted_rows) >= MAX_TABLE_ROWS_PER_PDF:
                        return extracted_rows

    return extracted_rows


def item_exists(session, extraction_id: str, page: int, table_index: int, row_index: int) -> bool:
    marker = f'"table_index": {table_index}'
    marker2 = f'"row_index": {row_index}'

    return (
        session.query(BOQItem)
        .filter(
            BOQItem.extraction_id == extraction_id,
            BOQItem.row_number == float(page),
            BOQItem.raw_row_json.like(f"%{marker}%"),
            BOQItem.raw_row_json.like(f"%{marker2}%"),
        )
        .first()
        is not None
    )


def main() -> None:
    processed = 0
    extracted = 0
    failed = 0
    items_created = 0
    rows_rejected = 0

    ts = now_ts()

    with SessionLocal() as session:
        candidates = (
            session.query(BOQExtraction)
            .join(TenderDocument, BOQExtraction.source_document_id == TenderDocument.id)
            .filter(
                BOQExtraction.extraction_status.in_(
                    [
                        "candidate",
                        "pdf_no_priceable_lines",
                        "pdf_extracted",
                        "pdf_table_no_rows",
                    ]
                )
            )
            .filter(TenderDocument.filename.ilike("%.pdf"))
            .limit(MAX_PDFS)
            .all()
        )

        for bx in candidates:
            processed += 1

            doc = (
                session.query(TenderDocument)
                .filter(TenderDocument.id == bx.source_document_id)
                .first()
            )

            try:
                if not doc or not doc.local_path:
                    raise Exception("Missing local_path")

                path = Path(doc.local_path)

                if not path.exists():
                    raise Exception(f"File not found: {path}")

                rows = extract_tables_from_pdf(path)
                created_for_doc = 0

                for row in rows:
                    page = row["page"]
                    table_index = row["table_index"]
                    row_index = row["row_index"]

                    if row.get("quantity") is None and row.get("unit") is None:
                        rows_rejected += 1
                        continue

                    if item_exists(session, bx.id, page, table_index, row_index):
                        continue

                    item = BOQItem(
                        id=f"item-{uuid.uuid4().hex[:12]}",
                        extraction_id=bx.id,
                        workflow_id=bx.workflow_id,
                        tender_id=bx.tender_id,
                        source_document_id=bx.source_document_id,
                        sheet_name=f"PDF table p{page} t{table_index}",
                        row_number=float(page),
                        item_code=row.get("item_code"),
                        description=row.get("description"),
                        unit=row.get("unit"),
                        quantity=row.get("quantity") or 1.0,
                        raw_row_json=json.dumps(
                            {
                                "source": "pdf_table",
                                "page": page,
                                "table_index": table_index,
                                "row_index": row_index,
                                "values": row.get("values"),
                                "unit_rate": row.get("unit_rate"),
                                "line_total": row.get("line_total"),
                                "priceable": bool(row.get("priceable")),
                                "sanity_flags": row.get("sanity_flags", []),
                                "extraction_confidence": 0.75
                                if row.get("quantity") is not None and row.get("unit") is not None
                                else 0.55,
                            },
                            ensure_ascii=False,
                            default=str,
                        ),
                        created_at=ts,
                    )

                    session.add(item)
                    items_created += 1
                    created_for_doc += 1

                bx.extraction_status = (
                    "pdf_table_extracted"
                    if created_for_doc > 0
                    else "pdf_table_no_rows"
                )
                bx.item_count = float(created_for_doc)
                bx.confidence = 0.75 if created_for_doc > 0 else 0.15
                bx.raw_json = json.dumps(
                    {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "local_path": doc.local_path,
                        "table_rows_created": created_for_doc,
                        "rows_detected": len(rows),
                        "rows_rejected": rows_rejected,
                        "sample_rows": rows[:20],
                    },
                    ensure_ascii=False,
                    default=str,
                )
                bx.updated_at = ts

                extracted += 1

            except Exception as e:
                bx.extraction_status = "pdf_table_extraction_failed"
                bx.confidence = 0.0
                bx.raw_json = json.dumps(
                    {
                        "document_id": bx.source_document_id,
                        "error": str(e),
                    },
                    ensure_ascii=False,
                )
                bx.updated_at = ts
                failed += 1

        session.commit()

    print(
        "PDF table extractor complete | "
        f"processed={processed} "
        f"extracted={extracted} "
        f"failed={failed} "
        f"items_created={items_created} "
        f"rows_rejected={rows_rejected}"
    )


if __name__ == "__main__":
    main()
