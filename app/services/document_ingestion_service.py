from __future__ import annotations

import re
from html import unescape
from typing import Any, Dict, List


ABSOLUTE_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
ANCHOR_RE = re.compile(
    r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    text = TAG_RE.sub(" ", value or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _looks_like_tender_text(value: str) -> bool:
    text = (value or "").lower()
    keywords = [
        "tender",
        "bid",
        "rfq",
        "request for quotation",
        "quotation",
        "supply",
        "delivery",
        "closing date",
        "advert",
    ]
    return any(keyword in text for keyword in keywords)


def extract_links_from_html(html: str) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []

    for match in ANCHOR_RE.finditer(html or ""):
        href = (match.group("href") or "").strip()
        label = _strip_html(match.group("label") or "")
        if href:
            results.append({"url": href, "label": label})

    for raw_url in ABSOLUTE_URL_RE.findall(html or ""):
        results.append({"url": raw_url.strip(), "label": ""})

    unique: List[Dict[str, str]] = []
    seen = set()
    for item in results:
        key = (item["url"], item["label"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def extract_tender_candidates_from_html(html: str, *, source_url: str = "") -> List[Dict[str, Any]]:
    text = _strip_html(html or "")
    lines = [line.strip() for line in re.split(r"[.\n\r]+", text) if line.strip()]

    candidates: List[Dict[str, Any]] = []
    for line in lines:
        if _looks_like_tender_text(line):
            candidates.append(
                {
                    "title": line[:250],
                    "description": line[:1200],
                    "source_url": source_url,
                    "document_type": "html_notice",
                }
            )

    links = extract_links_from_html(html or "")
    for link in links:
        label = link.get("label", "")
        if _looks_like_tender_text(label) or any(
            token in link.get("url", "").lower() for token in ["tender", "rfq", "quotation", "bid"]
        ):
            candidates.append(
                {
                    "title": label or "Tender document",
                    "description": label or link.get("url", ""),
                    "source_url": link.get("url", ""),
                    "document_type": "linked_document",
                }
            )

    unique: List[Dict[str, Any]] = []
    seen = set()
    for item in candidates:
        key = (item.get("title"), item.get("source_url"))
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def normalize_document_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": str(record.get("title", "")).strip(),
        "description": str(record.get("description", "")).strip(),
        "source_url": str(record.get("source_url", "")).strip(),
        "document_type": str(record.get("document_type", "unknown")).strip(),
    }
