import json
import re
import time
import uuid
from pathlib import Path

from pypdf import PdfReader

from app.db.models import BOQExtraction, BOQItem, TenderDocument
from app.db.session import SessionLocal


MAX_PDFS = 20
MAX_PAGES = 30
MAX_LINES_PER_PDF = 1000


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
]


NON_PRICEABLE_PATTERNS = [
    r"table of contents",
    r"invitation to tender",
    r"conditions of tender",
    r"signature",
    r"company name",
    r"page \d+",
    r"returnable",
    r"declaration",
    r"tax compliance",
    r"cidb",
]


def now_ts():
    return time.time()


def clean(text):
    if text is None:
        return None
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text or None


def is_priceable_line(line):
    line = clean(line)
    if not line:
        return False

    lower = line.lower()

    if len(line) < 20:
        return False

    for pattern in NON_PRICEABLE_PATTERNS:
        if re.search(pattern, lower):
            return False

    return any(h in lower for h in PRICEABLE_HINTS)


def extract_pdf_lines(path):
    reader = PdfReader(str(path))
    lines = []

    for page_index, page in enumerate(reader.pages[:MAX_PAGES], start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue

        for line in text.splitlines():
            line = clean(line)
            if not line:
                continue

            lines.append({
                "page": page_index,
                "text": line,
            })

            if len(lines) >= MAX_LINES_PER_PDF:
                return lines

    return lines


def item_exists(session, extraction_id, page, text):
    return (
        session.query(BOQItem)
        .filter(
            BOQItem.extraction_id == extraction_id,
            BOQItem.row_number == float(page),
            BOQItem.description == text,
        )
        .first()
        is not None
    )


def main():
    processed = 0
    extracted = 0
    failed = 0
    items_created = 0

    ts = now_ts()

    with SessionLocal() as session:
        candidates = (
            session.query(BOQExtraction)
            .join(TenderDocument, BOQExtraction.source_document_id == TenderDocument.id)
            .filter(BOQExtraction.extraction_status == "candidate")
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

                lines = extract_pdf_lines(path)

                priceable_lines = [
                    line for line in lines
                    if is_priceable_line(line.get("text"))
                ]

                for line in priceable_lines:
                    text = line["text"]
                    page = line["page"]

                    if item_exists(session, bx.id, page, text):
                        continue

                    item = BOQItem(
                        id=f"item-{uuid.uuid4().hex[:12]}",
                        extraction_id=bx.id,
                        workflow_id=bx.workflow_id,
                        tender_id=bx.tender_id,
                        source_document_id=bx.source_document_id,
                        sheet_name=f"PDF page {page}",
                        row_number=float(page),
                        item_code=None,
                        description=text,
                        unit=None,
                        quantity=1.0,
                        raw_row_json=json.dumps(
                            {
                                "source": "pdf_text",
                                "page": page,
                                "text": text,
                                "priceable": True,
                            },
                            ensure_ascii=False,
                        ),
                        created_at=ts,
                    )

                    session.add(item)
                    items_created += 1

                bx.extraction_status = (
                    "pdf_extracted" if priceable_lines else "pdf_no_priceable_lines"
                )
                bx.item_count = len(priceable_lines)
                bx.confidence = 0.45 if priceable_lines else 0.1
                bx.raw_json = json.dumps(
                    {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "local_path": doc.local_path,
                        "total_lines": len(lines),
                        "priceable_lines": len(priceable_lines),
                        "sample": priceable_lines[:20],
                    },
                    ensure_ascii=False,
                    default=str,
                )
                bx.updated_at = ts

                extracted += 1

            except Exception as e:
                bx.extraction_status = "pdf_extraction_failed"
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
        "PDF BOQ extractor complete | "
        f"processed={processed} "
        f"extracted={extracted} "
        f"failed={failed} "
        f"items_created={items_created}"
    )


if __name__ == "__main__":
    main()
