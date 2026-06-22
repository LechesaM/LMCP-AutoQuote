import json
import time
from pathlib import Path

import openpyxl

from app.db.models import TenderDocument, BOQExtraction
from app.db.session import SessionLocal


MAX_ITEMS = 20
MAX_ROWS_PER_SHEET = 500


def now_ts():
    return time.time()


def row_values(row):
    return [
        cell.value
        for cell in row
    ]


def is_non_empty_row(values):
    return any(v is not None and str(v).strip() != "" for v in values)


def extract_workbook(path):
    workbook = openpyxl.load_workbook(path, data_only=True)

    extracted = {
        "sheets": [],
        "total_rows": 0,
    }

    for sheet in workbook.worksheets:
        sheet_rows = []

        for idx, row in enumerate(sheet.iter_rows(), start=1):
            if idx > MAX_ROWS_PER_SHEET:
                break

            values = row_values(row)

            if not is_non_empty_row(values):
                continue

            sheet_rows.append({
                "row_number": idx,
                "values": values,
            })

        if sheet_rows:
            extracted["sheets"].append({
                "sheet_name": sheet.title,
                "rows": sheet_rows,
                "row_count": len(sheet_rows),
            })

            extracted["total_rows"] += len(sheet_rows)

    return extracted


def main():
    processed = 0
    extracted_count = 0
    failed = 0

    ts = now_ts()

    with SessionLocal() as session:
        candidates = (
            session.query(BOQExtraction)
            .join(
                TenderDocument,
                BOQExtraction.source_document_id == TenderDocument.id,
            )
            .filter(BOQExtraction.extraction_status == "candidate")
            .filter(TenderDocument.filename.ilike("%.xlsx"))
            .limit(MAX_ITEMS)
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

                data = extract_workbook(path)

                item_count = data.get("total_rows", 0)

                raw = {
                    "document_id": doc.id,
                    "tender_id": doc.tender_id,
                    "workflow_id": doc.workflow_id,
                    "filename": doc.filename,
                    "local_path": doc.local_path,
                    "document_type": "spreadsheet",
                    "extraction": data,
                }

                bx.extraction_status = (
                    "extracted" if item_count > 0 else "empty_spreadsheet"
                )
                bx.item_count = item_count
                bx.confidence = 0.75 if item_count > 0 else 0.2
                bx.raw_json = json.dumps(raw, ensure_ascii=False, default=str)
                bx.updated_at = ts

                extracted_count += 1

            except Exception as e:
                bx.extraction_status = "extraction_failed"
                bx.confidence = 0.0
                bx.raw_json = json.dumps({
                    "document_id": bx.source_document_id,
                    "error": str(e),
                })
                bx.updated_at = ts

                failed += 1

        session.commit()

    print(
        "Spreadsheet BOQ extractor complete | "
        f"processed={processed} "
        f"extracted={extracted_count} "
        f"failed={failed}"
    )


if __name__ == "__main__":
    main()
