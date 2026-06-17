from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urljoin
import re
import requests

SERVICE_VERSION = "V49.1_DETAIL_PAGE_FOLLOW_ENGINE"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(v: Any) -> str:
    return str(v or "").strip()


def _lower(v: Any) -> str:
    return _clean(v).lower()


def _extract_links(html: str, base_url: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    matches = re.findall(
        r'<a[^>]+href=["\\\']([^"\\\']+)["\\\'][^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    )

    for href, label in matches:
        full = urljoin(base_url, href)
        label = re.sub(r"<[^>]+>", " ", label)
        label = re.sub(r"\s+", " ", label).strip()

        results.append({
            "url": full,
            "label": label,
        })

    return results


def follow_detail_pages(payload: Dict[str, Any]) -> Dict[str, Any]:
    explicit_ref = _clean(
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("reference_number")
    )

    candidate_links = payload.get("candidate_detail_links") or []

    result: Dict[str, Any] = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "follow_started_at": _now(),
        "explicit_reference": explicit_ref,
        "detail_pages_checked": 0,
        "matching_document_links": [],
        "verified_detail_pages": [],
        "recommended_document_url": None,
        "exact_reference_match_found": False,
    }

    explicit_ref_lower = explicit_ref.lower()

    if not explicit_ref_lower:
        result["status"] = "skipped"
        result["reason"] = "missing_explicit_reference"
        result["follow_finished_at"] = _now()
        return result

    for candidate in candidate_links[:10]:
        url = _clean(candidate.get("url"))

        if not url:
            continue

        try:
            resp = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "LMCP-V49.1/1.0"},
            )

            result["detail_pages_checked"] += 1

            if resp.status_code >= 400:
                continue

            html = resp.text or ""
            html_lower = html.lower()

            if explicit_ref_lower not in html_lower:
                continue

            result["verified_detail_pages"].append(url)

            child_links = _extract_links(html, url)

            for link in child_links:
                full = _clean(link.get("url"))
                low = full.lower()

                if explicit_ref_lower not in low:
                    continue

                if not any(
                    ext in low
                    for ext in [".zip", ".pdf", ".docx", ".doc", ".xlsx", ".xls"]
                ):
                    continue

                link["exact_reference_match"] = True
                result["matching_document_links"].append(link)

        except Exception as exc:
            result.setdefault("errors", []).append({"url": url, "error": str(exc)})
            continue

    if result["matching_document_links"]:
        result["exact_reference_match_found"] = True
        result["matching_document_links"].sort(
            key=lambda x: (
                ".zip" not in _lower(x.get("url")),
                len(_lower(x.get("url"))),
            )
        )
        result["recommended_document_url"] = result["matching_document_links"][0].get("url")

    result["follow_finished_at"] = _now()
    return result


def get_v49_1_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "engine": "Detail Page Follow Engine",
        "ready": True,
        "updated_at": _now(),
    }
