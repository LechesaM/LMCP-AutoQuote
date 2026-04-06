import io
import mimetypes
import re
from typing import Iterable, Tuple

import requests
from pypdf import PdfReader

from app.classify import extract_emails

PDF_MAGIC = b"%PDF"

def _guess_content_type(url: str, headers: dict) -> str:
    ct = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ct:
        return ct
    mt, _ = mimetypes.guess_type(url)
    return (mt or "").lower()

def download(url: str, timeout: int = 45) -> Tuple[bytes, str]:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    ct = _guess_content_type(url, r.headers)
    return r.content, ct

def extract_text_from_pdf(pdf_bytes: bytes, max_chars: int = 400_000) -> str:
    # Safety: cap output size to protect DB + memory
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t:
            texts.append(t)
        if sum(len(x) for x in texts) >= max_chars:
            break
    out = "\n\n".join(texts)
    if len(out) > max_chars:
        out = out[:max_chars]
    return out

def process_document(title: str, url: str) -> dict:
    content, ct = download(url)
    size = len(content)

    extracted_text = ""
    emails = []

    # Detect PDFs even if content-type is wrong
    is_pdf = (ct == "application/pdf") or content[:4] == PDF_MAGIC or url.lower().endswith(".pdf")
    if is_pdf:
        extracted_text = extract_text_from_pdf(content)
        emails = extract_emails(title, url, extracted_text)

    return {
        "doc_title": title or "",
        "doc_url": url,
        "content_type": ct,
        "bytes_size": size,
        "extracted_text": extracted_text,
        "extracted_emails": ",".join(emails),
    }
