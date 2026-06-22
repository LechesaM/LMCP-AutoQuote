import json
import time
import uuid
from pathlib import Path

from app.db.models import TenderDocument, BOQExtraction
from app.db.session import SessionLocal


MAX_ITEMS = 100


BOQ_KEYWORDS = [
    "boq",
    "bill of quantities",
    "pricing",
    "price",
    "schedule",
    "priced",
    "rates",
    "rate",
    "returnable",
    "tender document",
    "bid document",
    "scope of work",
    "sow",
    "works",
    "construction",
    "civil",
    "roads",
    "stormwater",
    "paving",
    "electrical",
    "mechanical",
    "hvac",
]


def now_ts():
    return time.time()


def is_likely_boq_document(doc):
    text = " ".join([
        str(doc.filename or ""),
        str(doc.local_path or ""),
        str(doc.tender_id or ""),
    ]).lower()

    return any(keyword in text for keyword in BOQ_KEYWORDS)


def classify_document_type(path):
    suffix = Path(path or "").suffix.lower()

    if suffix == ".pdf":
        return "pdf"

    if suffix in [".xls", ".xlsx"]:
        return "spreadsheet"

    if suffix in [".doc", ".docx"]:
        return "word"

    if suffix == ".zip":
        return "zip"

    return "unknown"


def get_unprocessed_downloaded_docs(session):
    processed_doc_ids = [
        row[0]
        for row in session.query(BOQExtraction.source_document_id).all()
        if row[0]
    ]

    query = (
        session.query(TenderDocument)
        .filter(TenderDocument.status == "downloaded")
    )

    if processed_doc_ids:
        query = query.filter(~TenderDocument.id.in_(processed_doc_ids))

    return query.limit(MAX_ITEMS).all()


def main():
    scanned = 0
    created = 0
    skipped = 0

    ts = now_ts()

    with SessionLocal() as session:
        docs = get_unprocessed_downloaded_docs(session)

        for doc in docs:
            scanned += 1

            likely_boq = is_likely_boq_document(doc)
            document_type = classify_document_type(doc.local_path)

            status = "candidate" if likely_boq else "not_boq"

            raw = {
                "document_id": doc.id,
                "tender_id": doc.tender_id,
                "workflow_id": doc.workflow_id,
                "filename": doc.filename,
                "local_path": doc.local_path,
                "document_type": document_type,
                "likely_boq": likely_boq,
                "reason": (
                    "Matched BOQ/pricing keyword"
                    if likely_boq
                    else "No BOQ/pricing keyword match"
                ),
            }

            extraction = BOQExtraction(
                id=f"boq-{uuid.uuid4().hex[:12]}",
                workflow_id=doc.workflow_id,
                tender_id=doc.tender_id,
                source_document_id=doc.id,
                extraction_status=status,
                item_count=0,
                confidence=0.25 if likely_boq else 0.0,
                raw_json=json.dumps(raw, ensure_ascii=False),
                created_at=ts,
                updated_at=ts,
            )

            session.add(extraction)
            created += 1

        if scanned == 0:
            skipped = 0

        session.commit()

    print(
        "BOQ extraction worker complete | "
        f"scanned={scanned} "
        f"created={created} "
        f"skipped={skipped}"
    )


if __name__ == "__main__":
    main()
