import json
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from app.db.models import Tender, TenderDocument
from app.db.session import SessionLocal


RUNTIME_DIR = Path("/Users/cash/Documents/runtime/manual_production")
WORKFLOW_STATE_FILE = RUNTIME_DIR / "workflow_state.jsonl"

MAX_ITEMS = 100

DOWNLOAD_BASE_URL = "https://www.etenders.gov.za/home/Download/"


def read_jsonl(path):
    rows = []

    if not path.exists():
        return rows

    with open(path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    return rows


def latest_workflows(rows):
    latest = {}

    for row in rows:
        workflow_id = row.get("workflow_id")

        if not workflow_id:
            continue

        latest[workflow_id] = row

    return list(latest.values())


def load_tender_raw(session, tender_id):
    if not tender_id:
        return None

    tender = (
        session.query(Tender)
        .filter(Tender.tender_id == tender_id)
        .first()
    )

    if not tender or not tender.raw_json:
        return None

    try:
        return json.loads(tender.raw_json)
    except Exception:
        return None


def build_download_url(support_id, filename, extension):
    filename = filename or "document"
    extension = extension or ""

    if extension and not extension.startswith("."):
        extension = "." + extension

    blob_name = f"{support_id}{extension}"
    downloaded_name = quote(filename)

    return (
        f"{DOWNLOAD_BASE_URL}"
        f"?blobName={blob_name}"
        f"&downloadedFileName={downloaded_name}"
    )


def extract_support_documents(raw):
    docs = []

    support_docs = raw.get("supportDocument") or []

    if not isinstance(support_docs, list):
        return docs

    for doc in support_docs:
        if not isinstance(doc, dict):
            continue

        support_id = doc.get("supportDocumentID")
        filename = doc.get("fileName") or "document"
        extension = doc.get("extension") or ""

        if not support_id:
            continue

        docs.append({
            "support_document_id": support_id,
            "filename": filename,
            "extension": extension,
            "document_url": build_download_url(
                support_id=support_id,
                filename=filename,
                extension=extension,
            ),
        })

    return docs


def document_exists(session, workflow_id, document_url):
    return (
        session.query(TenderDocument)
        .filter(
            TenderDocument.workflow_id == workflow_id,
            TenderDocument.document_url == document_url,
        )
        .first()
        is not None
    )


def main():
    rows = read_jsonl(WORKFLOW_STATE_FILE)
    workflows = latest_workflows(rows)

    candidates = [
        wf for wf in workflows
        if wf.get("quote_ready") is True
        and wf.get("stage") == "quote_generated"
    ]

    scanned = 0
    created = 0
    missing_raw = 0
    missing_docs = 0

    now = time.time()

    with SessionLocal() as session:
        for wf in candidates[:MAX_ITEMS]:
            scanned += 1

            workflow_id = wf.get("workflow_id")
            tender_id = wf.get("tender_id")

            raw = load_tender_raw(session, tender_id)

            if not raw:
                missing_raw += 1
                continue

            docs = extract_support_documents(raw)

            if not docs:
                missing_docs += 1
                continue

            for d in docs:
                url = d["document_url"]

                if document_exists(session, workflow_id, url):
                    continue

                doc = TenderDocument(
                    id=f"doc-{uuid.uuid4().hex[:12]}",
                    tender_id=tender_id,
                    workflow_id=workflow_id,
                    document_url=url,
                    filename=d["filename"],
                    local_path=None,
                    sha256=None,
                    status="discovered",
                    created_at=now,
                    updated_at=now,
                )

                session.add(doc)
                created += 1

        session.commit()

    print(
        "Document discovery complete | "
        f"scanned={scanned} "
        f"created={created} "
        f"missing_raw={missing_raw} "
        f"missing_docs={missing_docs}"
    )


if __name__ == "__main__":
    main()
