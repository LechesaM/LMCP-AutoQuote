from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from hashlib import sha256
from typing import Any, Dict, Iterable, List


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _stable_hash(*parts: Any) -> str:
    payload = "||".join(_normalize_text(part) for part in parts)
    return sha256(payload.encode("utf-8")).hexdigest()


def find_possible_duplicates(candidate: Dict[str, Any], existing_records: Iterable[Dict[str, Any]]) -> List[str]:
    payload = dict(candidate or {})
    reasons: list[str] = []
    reference = _normalize_text(payload.get("reference"))
    title = _normalize_text(payload.get("title"))
    buyer = _normalize_text(payload.get("buyer"))
    closing_date = _normalize_text(payload.get("closing_date"))
    source_url = _normalize_text(payload.get("source_url"))
    document_urls = [
        _normalize_text(doc.get("document_url") if isinstance(doc, dict) else doc)
        for doc in payload.get("documents", [])
    ]
    title_hash = _stable_hash(title, buyer, closing_date)
    source_hash = _stable_hash(source_url)
    document_hashes = {_stable_hash(url) for url in document_urls if url}

    for record in existing_records:
        record_reference = _normalize_text(record.get("reference"))
        record_title = _normalize_text(record.get("title"))
        record_buyer = _normalize_text(record.get("buyer"))
        record_closing_date = _normalize_text(record.get("closing_date"))
        record_source_url = _normalize_text(record.get("source_url"))
        record_doc_urls = [
            _normalize_text(doc.get("document_url") if isinstance(doc, dict) else doc)
            for doc in record.get("documents", [])
        ]
        if reference and record_reference and reference == record_reference:
            reasons.append("reference match")
            continue
        if title and record_title and SequenceMatcher(None, title, record_title).ratio() >= 0.92 and buyer == record_buyer:
            reasons.append("title similarity match")
        if _stable_hash(record_title, record_buyer, record_closing_date) == title_hash:
            reasons.append("buyer+closing-date+title hash match")
        if record_source_url and source_url and _stable_hash(record_source_url) == source_hash:
            reasons.append("source url hash match")
        if any(_stable_hash(url) in document_hashes for url in record_doc_urls if url):
            reasons.append("document url hash match")

    return list(dict.fromkeys(reasons))


def annotate_possible_duplicates(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen: List[Dict[str, Any]] = []
    for record in records:
        item = dict(record or {})
        reasons = find_possible_duplicates(item, seen)
        item["possible_duplicate"] = bool(reasons)
        item["duplicate_reasons"] = reasons
        result.append(item)
        seen.append(item)
    return result
