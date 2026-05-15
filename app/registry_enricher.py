from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

REQUEST_TIMEOUT: Tuple[int, int] = (6, 12)
MAX_TEXT_SCAN = 6000
DEFAULT_OUTPUT_PATH = Path("app/entity_source_status.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

PROCUREMENT_KEYWORDS = [
    "tender",
    "tenders",
    "rfq",
    "quotation",
    "request for quotation",
    "request for proposal",
    "request for proposals",
    "bid",
    "bids",
    "supply",
    "delivery",
    "procurement",
    "supplier",
    "suppliers",
    "panel of suppliers",
    "framework agreement",
    "supply chain management",
]

COMMON_PROCUREMENT_PATHS = [
    "/tenders",
    "/tender",
    "/procurement",
    "/procurement/",
    "/procurement/tenders",
    "/procurement/tender",
    "/procurement-opportunities",
    "/supply-chain-management",
    "/supply-chain-management/",
    "/supply-chain-management/tenders",
    "/supply-chain-management/bids",
    "/bids",
    "/bid",
    "/rfq",
    "/quotations",
    "/open-tenders",
    "/tenders-and-rfqs",
    "/available-tenders",
]

DOCUMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
)

# Known direct overrides for important entities.
# Add to this over time as you discover better procurement URLs.
DIRECT_PROCUREMENT_OVERRIDES: Dict[str, List[str]] = {
    "National Treasury": [
        "https://www.etenders.gov.za/Home/opportunities",
        "https://www.treasury.gov.za/tenders/default.aspx",
    ],
    "Department of Public Works and Infrastructure": [
        "https://www.publicworks.gov.za/tenders.html",
    ],
    "Department of Health": [
        "https://www.health.gov.za/tenders/",
    ],
    "Department of Transport": [
        "https://www.transport.gov.za/tenders",
    ],
    "Department of Human Settlements": [
        "https://www.dhs.gov.za/content/tenders",
    ],
    "Eskom Holdings SOC Ltd": [
        "https://www.eskom.co.za/procurement/",
    ],
    "Transnet SOC Ltd": [
        "https://www.transnet.net/TransnetTenders",
    ],
    "Passenger Rail Agency of South Africa (PRASA)": [
        "https://www.prasa.com/Tenders/",
    ],
    "South African National Parks (SANParks)": [
        "https://www.sanparks.org/corporate/tenders",
    ],
    "Development Bank of Southern Africa (DBSA)": [
        "https://www.dbsa.org/procurement",
    ],
    "Council for Scientific and Industrial Research (CSIR)": [
        "https://www.csir.co.za/work-with-us/tenders",
    ],
    "NECSA Group": [
        "https://www.necsa.co.za/tenders/",
    ],
}

# -------------------------------------------------------------------
# Safe imports from your existing registries
# -------------------------------------------------------------------

try:
    from app.department_registry import DEPARTMENT_SOURCES as NATIONAL_DEPARTMENTS
except Exception:
    NATIONAL_DEPARTMENTS = []

try:
    from app.public_entity_registry import PUBLIC_ENTITY_REGISTRY
except Exception:
    PUBLIC_ENTITY_REGISTRY = []

try:
    from app.municipality_registry import MUNICIPALITY_REGISTRY
except Exception:
    MUNICIPALITY_REGISTRY = []

try:
    from app.provincial_registry import PROVINCIAL_REGISTRY
except Exception:
    PROVINCIAL_REGISTRY = []

# -------------------------------------------------------------------
# Data model
# -------------------------------------------------------------------


@dataclass
class EntityCandidate:
    entity_name: str
    entity_type: str
    base_url: str
    candidate_url: str
    source_registry: str
    score: int = 0


@dataclass
class EntitySourceStatus:
    entity_name: str
    entity_type: str
    source_registry: str
    base_url: str
    tested_url: str
    final_url: str
    http_status: Optional[int]
    content_type: str
    status: str
    procurement_confidence: int
    procurement_keywords_found: List[str]
    page_title: str
    notes: str


# -------------------------------------------------------------------
# Utility functions
# -------------------------------------------------------------------


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).strip()


def _normalize_name(raw: str) -> str:
    return _clean_text(raw).replace("[ Department of ]", "").strip()


def _normalize_url(url: str) -> str:
    clean = _clean_text(url)
    if not clean:
        return ""
    return clean.rstrip("/")


def _is_document_url(url: str) -> bool:
    lowered = (url or "").lower()
    return lowered.endswith(DOCUMENT_EXTENSIONS)


def _find_keywords(text: str) -> List[str]:
    lowered = text.lower()
    hits = [kw for kw in PROCUREMENT_KEYWORDS if kw in lowered]
    return sorted(set(hits))


def _score_candidate_url(url: str) -> int:
    lowered = url.lower()
    score = 0

    for kw in ["tender", "procurement", "supply-chain-management", "bids", "rfq", "quotations"]:
        if kw in lowered:
            score += 20

    if lowered.endswith("/"):
        score += 1

    if _is_document_url(lowered):
        score += 8

    return score


def _dedupe_candidates(items: Iterable[EntityCandidate]) -> List[EntityCandidate]:
    seen = set()
    result: List[EntityCandidate] = []

    for item in sorted(items, key=lambda x: x.score, reverse=True):
        key = (
            item.entity_name.strip().lower(),
            item.candidate_url.strip().rstrip("/").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


def _build_common_paths(base_url: str) -> List[str]:
    if not base_url:
        return []
    base = base_url.rstrip("/") + "/"
    return [urljoin(base, path.lstrip("/")) for path in COMMON_PROCUREMENT_PATHS]


def _extract_base_url(record: Dict[str, Any]) -> str:
    return _normalize_url(
        record.get("homepage_url")
        or record.get("base_url")
        or record.get("url")
        or ""
    )


def _extract_direct_procurement_url(record: Dict[str, Any]) -> Optional[str]:
    for field in ["procurement_url", "rfq_url", "tender_url", "source_url"]:
        value = _normalize_url(record.get(field, ""))
        if value:
            return value
    return None


def _record_to_entity(record: Dict[str, Any], default_type: str, registry_name: str) -> Optional[Dict[str, str]]:
    name = _normalize_name(record.get("name", ""))
    base_url = _extract_base_url(record)
    direct_url = _extract_direct_procurement_url(record)

    if not name:
        return None

    return {
        "entity_name": name,
        "entity_type": _clean_text(record.get("entity_type") or default_type),
        "base_url": base_url,
        "direct_url": direct_url or "",
        "source_registry": registry_name,
    }


def _load_all_entities() -> List[Dict[str, str]]:
    entities: List[Dict[str, str]] = []

    for record in NATIONAL_DEPARTMENTS:
        entity = _record_to_entity(record, "national_department", "department_registry")
        if entity:
            entities.append(entity)

    for record in PROVINCIAL_REGISTRY:
        entity = _record_to_entity(record, "provincial_department", "provincial_registry")
        if entity:
            entities.append(entity)

    for record in MUNICIPALITY_REGISTRY:
        entity = _record_to_entity(record, "municipality", "municipality_registry")
        if entity:
            entities.append(entity)

    for record in PUBLIC_ENTITY_REGISTRY:
        entity = _record_to_entity(record, "public_entity", "public_entity_registry")
        if entity:
            entities.append(entity)

    return entities


# -------------------------------------------------------------------
# Candidate generation
# -------------------------------------------------------------------


def build_entity_candidates() -> List[EntityCandidate]:
    raw_entities = _load_all_entities()
    candidates: List[EntityCandidate] = []

    for entity in raw_entities:
        name = entity["entity_name"]
        entity_type = entity["entity_type"]
        base_url = entity["base_url"]
        direct_url = entity["direct_url"]
        source_registry = entity["source_registry"]

        candidate_urls: List[str] = []

        overrides = DIRECT_PROCUREMENT_OVERRIDES.get(name, [])
        candidate_urls.extend(overrides)

        if direct_url:
            candidate_urls.append(direct_url)

        if base_url:
            candidate_urls.append(base_url)
            candidate_urls.extend(_build_common_paths(base_url))

        # Remove blanks and duplicates first
        seen = set()
        deduped_urls: List[str] = []
        for url in candidate_urls:
            clean = _normalize_url(url)
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_urls.append(clean)

        for url in deduped_urls:
            score = _score_candidate_url(url)
            if url in overrides:
                score += 100
            if url == direct_url:
                score += 80
            if url == base_url:
                score += 10

            candidates.append(
                EntityCandidate(
                    entity_name=name,
                    entity_type=entity_type,
                    base_url=base_url,
                    candidate_url=url,
                    source_registry=source_registry,
                    score=score,
                )
            )

    return _dedupe_candidates(candidates)


# -------------------------------------------------------------------
# URL testing
# -------------------------------------------------------------------


def _fetch_url(session: requests.Session, url: str) -> Tuple[Optional[requests.Response], str]:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        return response, ""
    except requests.RequestException as exc:
        return None, str(exc)


def _analyze_html(response: requests.Response) -> Tuple[str, int, List[str], str]:
    content_type = _clean_text(response.headers.get("Content-Type", ""))
    text = response.text or ""
    title = ""

    try:
        soup = BeautifulSoup(text, "html.parser")
        title = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
        body_text = _clean_text(" ".join(soup.stripped_strings))[:MAX_TEXT_SCAN]
        link_text = " ".join(
            _clean_text(link.get_text(" ", strip=True))
            for link in soup.find_all("a")
            if _clean_text(link.get_text(" ", strip=True))
        )[:MAX_TEXT_SCAN]
        combined_text = f"{title} {body_text} {link_text}"
    except Exception:
        combined_text = text[:MAX_TEXT_SCAN]

    hits = _find_keywords(combined_text)
    confidence = min(100, len(hits) * 18)

    return content_type, confidence, hits, title


def _classify_status(
    candidate_url: str,
    final_url: str,
    http_status: Optional[int],
    content_type: str,
    procurement_confidence: int,
    hits: List[str],
) -> Tuple[str, str]:
    lowered_type = content_type.lower()

    if http_status is None:
        return "dead", "Request failed or site unreachable"

    if http_status >= 400:
        return "dead", f"HTTP {http_status}"

    if _is_document_url(final_url):
        return "working", "Direct procurement document detected"

    if "pdf" in lowered_type or "msword" in lowered_type or "spreadsheet" in lowered_type:
        return "working", "Procurement document content type detected"

    parsed = urlparse(final_url)
    path = parsed.path.lower()

    if procurement_confidence >= 36:
        return "working", f"Procurement signals found: {', '.join(hits[:5])}"

    if any(token in path for token in ["tender", "procurement", "bid", "rfq", "quotation"]):
        return "homepage_only", "Procurement-like path exists but weak page signals"

    if candidate_url != final_url:
        return "needs_custom_parser", "Redirected; may need source-specific handling"

    return "homepage_only", "Homepage reachable but procurement signals weak"


def test_entity_candidates(limit_per_entity: int = 4) -> List[EntitySourceStatus]:
    candidates = build_entity_candidates()

    # Keep only top N candidates per entity so it stays efficient.
    grouped: Dict[str, List[EntityCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.entity_name, []).append(candidate)

    limited_candidates: List[EntityCandidate] = []
    for entity_name, entity_candidates in grouped.items():
        top = sorted(entity_candidates, key=lambda x: x.score, reverse=True)[:limit_per_entity]
        limited_candidates.extend(top)

    session = requests.Session()
    session.headers.update(HEADERS)

    results: List[EntitySourceStatus] = []

    for item in limited_candidates:
        response, error = _fetch_url(session, item.candidate_url)

        if response is None:
            results.append(
                EntitySourceStatus(
                    entity_name=item.entity_name,
                    entity_type=item.entity_type,
                    source_registry=item.source_registry,
                    base_url=item.base_url,
                    tested_url=item.candidate_url,
                    final_url=item.candidate_url,
                    http_status=None,
                    content_type="",
                    status="dead",
                    procurement_confidence=0,
                    procurement_keywords_found=[],
                    page_title="",
                    notes=error or "Request failed",
                )
            )
            continue

        http_status = response.status_code
        final_url = str(response.url)
        content_type, confidence, hits, page_title = _analyze_html(response)
        status, notes = _classify_status(
            candidate_url=item.candidate_url,
            final_url=final_url,
            http_status=http_status,
            content_type=content_type,
            procurement_confidence=confidence,
            hits=hits,
        )

        results.append(
            EntitySourceStatus(
                entity_name=item.entity_name,
                entity_type=item.entity_type,
                source_registry=item.source_registry,
                base_url=item.base_url,
                tested_url=item.candidate_url,
                final_url=final_url,
                http_status=http_status,
                content_type=content_type,
                status=status,
                procurement_confidence=confidence,
                procurement_keywords_found=hits,
                page_title=page_title,
                notes=notes,
            )
        )

    return results


# -------------------------------------------------------------------
# Status consolidation
# -------------------------------------------------------------------


def best_status_per_entity(statuses: List[EntitySourceStatus]) -> List[EntitySourceStatus]:
    ranking = {
        "working": 4,
        "homepage_only": 3,
        "needs_custom_parser": 2,
        "dead": 1,
    }

    best: Dict[str, EntitySourceStatus] = {}

    for item in statuses:
        current = best.get(item.entity_name)
        if current is None:
            best[item.entity_name] = item
            continue

        current_rank = ranking.get(current.status, 0)
        new_rank = ranking.get(item.status, 0)

        if new_rank > current_rank:
            best[item.entity_name] = item
            continue

        if new_rank == current_rank and item.procurement_confidence > current.procurement_confidence:
            best[item.entity_name] = item

    return sorted(best.values(), key=lambda x: (x.entity_type, x.entity_name))


def summary_from_statuses(statuses: List[EntitySourceStatus]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total_tested": len(statuses),
        "working": 0,
        "homepage_only": 0,
        "needs_custom_parser": 0,
        "dead": 0,
        "by_entity_type": {},
    }

    for item in statuses:
        summary[item.status] = summary.get(item.status, 0) + 1

        entity_type = item.entity_type or "unknown"
        summary["by_entity_type"].setdefault(entity_type, 0)
        summary["by_entity_type"][entity_type] += 1

    return summary


def save_statuses_to_json(
    statuses: List[EntitySourceStatus],
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "summary": summary_from_statuses(statuses),
        "items": [asdict(item) for item in statuses],
    }

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


# -------------------------------------------------------------------
# Public entry points
# -------------------------------------------------------------------


def run_registry_enrichment(
    limit_per_entity: int = 4,
    best_only: bool = False,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Dict[str, Any]:
    logger.info("Starting registry enrichment")
    tested = test_entity_candidates(limit_per_entity=limit_per_entity)

    if best_only:
        final_items = best_status_per_entity(tested)
    else:
        final_items = tested

    saved_path = save_statuses_to_json(final_items, output_path=output_path)
    summary = summary_from_statuses(final_items)

    return {
        "status": "success",
        "output_path": str(saved_path),
        "items_saved": len(final_items),
        "summary": summary,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_registry_enrichment(limit_per_entity=4, best_only=False)
    print(json.dumps(result, indent=2))
