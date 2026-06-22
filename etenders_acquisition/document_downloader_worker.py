import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.db.models import TenderDocument
from app.db.session import SessionLocal


DOWNLOAD_DIR = Path("/Users/cash/Documents/runtime/downloaded_tender_documents")

MAX_ITEMS = 25
TIMEOUT = 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}


def safe_name(value):
    value = str(value or "document")
    return "".join(c if c.isalnum() or c in ("-", "_", ".", " ") else "_" for c in value)[:120]


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def download_file(url, output_path):
    with requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def main():
    downloaded = 0
    failed = 0
    skipped = 0

    now = time.time()

    with SessionLocal() as session:
        docs = (
            session.query(TenderDocument)
            .filter(TenderDocument.status == "discovered")
            .limit(MAX_ITEMS)
            .all()
        )

        for doc in docs:
            try:
                tender_folder = safe_name(doc.tender_id)
                filename = safe_name(doc.filename)

                if not filename.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")):
                    parsed = urlparse(doc.document_url or "")
                    suffix = Path(parsed.path).suffix or ".bin"
                    filename = filename + suffix

                output_path = DOWNLOAD_DIR / tender_folder / filename

                if output_path.exists() and output_path.stat().st_size > 0:
                    doc.local_path = str(output_path)
                    doc.sha256 = sha256_file(output_path)
                    doc.status = "downloaded"
                    doc.updated_at = now
                    skipped += 1
                    continue

                download_file(doc.document_url, output_path)

                doc.local_path = str(output_path)
                doc.sha256 = sha256_file(output_path)
                doc.status = "downloaded"
                doc.updated_at = now

                downloaded += 1

            except Exception as e:
                doc.status = "download_failed"
                doc.updated_at = now
                failed += 1
                print(f"Download failed | tender_id={doc.tender_id} file={doc.filename} error={e}")

        session.commit()

    print(
        "Document downloader complete | "
        f"downloaded={downloaded} "
        f"skipped={skipped} "
        f"failed={failed}"
    )


if __name__ == "__main__":
    main()
