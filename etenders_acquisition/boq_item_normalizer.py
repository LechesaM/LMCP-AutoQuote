import json
import time
import uuid

from app.db.models import BOQExtraction, BOQItem
from app.db.session import SessionLocal


MAX_EXTRACTIONS = 20


UNIT_KEYWORDS = {
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
}


def now_ts():
    return time.time()


def clean(value):
    if value is None:
        return None

    text = str(value).strip()

    if text == "":
        return None

    return text


def to_float(value):
    if value is None:
        return None

    try:
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().replace(",", "")

        if text == "":
            return None

        return float(text)
    except Exception:
        return None


def detect_unit(values):
    for value in values:
        text = clean(value)

        if not text:
            continue

        key = text.lower()

        if key in UNIT_KEYWORDS:
            return UNIT_KEYWORDS[key]

    return None


def detect_quantity(values):
    for value in values:
        num = to_float(value)

        if num is not None and num > 0:
            return num

    return None


def detect_description(values):
    candidates = []

    for value in values:
        text = clean(value)

        if not text:
            continue

        # ignore obvious unit-only cells
        if text.lower() in UNIT_KEYWORDS:
            continue

        # ignore pure numbers
        if to_float(text) is not None:
            continue

        if len(text) >= 8:
            candidates.append(text)

    if not candidates:
        return None

    return max(candidates, key=len)


def detect_item_code(values):
    for value in values[:3]:
        text = clean(value)

        if not text:
            continue

        if len(text) <= 20:
            return text

    return None


def load_extraction_rows(raw_json):
    data = json.loads(raw_json or "{}")
    extraction = data.get("extraction", {})
    sheets = extraction.get("sheets", [])

    rows = []

    for sheet in sheets:
        sheet_name = sheet.get("sheet_name")
        for row in sheet.get("rows", []):
            rows.append({
                "sheet_name": sheet_name,
                "row_number": row.get("row_number"),
                "values": row.get("values", []),
            })

    return rows


def item_exists(session, extraction_id, sheet_name, row_number):
    return (
        session.query(BOQItem)
        .filter(
            BOQItem.extraction_id == extraction_id,
            BOQItem.sheet_name == sheet_name,
            BOQItem.row_number == row_number,
        )
        .first()
        is not None
    )


def main():
    processed_extractions = 0
    created_items = 0
    skipped_rows = 0

    ts = now_ts()

    with SessionLocal() as session:
        extractions = (
            session.query(BOQExtraction)
            .filter(BOQExtraction.extraction_status == "extracted")
            .limit(MAX_EXTRACTIONS)
            .all()
        )

        for extraction in extractions:
            processed_extractions += 1

            rows = load_extraction_rows(extraction.raw_json)

            for row in rows:
                sheet_name = row["sheet_name"]
                row_number = row["row_number"]
                values = row["values"]

                if item_exists(session, extraction.id, sheet_name, row_number):
                    skipped_rows += 1
                    continue

                description = detect_description(values)

                if not description:
                    skipped_rows += 1
                    continue

                item = BOQItem(
                    id=f"item-{uuid.uuid4().hex[:12]}",
                    extraction_id=extraction.id,
                    workflow_id=extraction.workflow_id,
                    tender_id=extraction.tender_id,
                    source_document_id=extraction.source_document_id,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    item_code=detect_item_code(values),
                    description=description,
                    unit=detect_unit(values),
                    quantity=detect_quantity(values),
                    raw_row_json=json.dumps(
                        {
                            "sheet_name": sheet_name,
                            "row_number": row_number,
                            "values": values,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                    created_at=ts,
                )

                session.add(item)
                created_items += 1

        session.commit()

    print(
        "BOQ item normalizer complete | "
        f"processed_extractions={processed_extractions} "
        f"created_items={created_items} "
        f"skipped_rows={skipped_rows}"
    )


if __name__ == "__main__":
    main()
