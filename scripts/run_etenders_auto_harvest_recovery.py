from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import threading
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime_paths import get_runtime_paths
from app.services.etenders_local_filter_v50_8_5_service import _fetch_page as fetch_etenders_page
from app.services.etenders_structured_json_parser_v50_8_3_service import (
    ETENDERS_OPPORTUNITIES,
    PAGINATED_ENDPOINT,
    _extract_filenames,
    _extract_guids,
    _extract_href_links,
    _extract_ids_from_row,
    _extract_js_routes,
)
from app.services.harvest_source_registry_service import CURATED_LIVE_SOURCE_FILE, load_harvest_sources
from app.services.live_rfq_store import upsert_rfq as persist_live_rfq
from app.services.rfq_document_acquisition_engine import acquire_rfq_documents
from app.services.tender_qualification import apply_qualification_to_opportunity, qualify_opportunity


DEFAULT_STATUS = "1"
DEFAULT_OUTPUT_DIR = "runtime/harvest_recovery"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_url(value: Any) -> str:
    text = _clean(value).lower()
    if not text:
        return ""
    return text.rstrip("/")


def _first_text(row: Dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        text = _clean(row.get(key))
        if text:
            return text
    return ""


def _append_debug_line(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str))
        handle.write("\n")


def _write_controlled_acquisition_progress(progress_dir: Path, payload: Dict[str, Any]) -> None:
    progress_dir.mkdir(parents=True, exist_ok=True)
    json_path = progress_dir / "controlled_acquisition_progress.json"
    md_path = progress_dir / "controlled_acquisition_progress.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    lines = [
        "# Controlled Acquisition Progress",
        "",
        f"Generated at: {_now_iso()}",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    for key in [
        "run_id",
        "last_step",
        "acquisition_started",
        "acquisition_completed",
        "acquisition_failed",
        "acquisition_timeout",
        "selected_rfq_id",
        "title",
        "buyer",
        "document_url",
        "detail_url",
        "timeout_seconds",
        "started_at",
        "completed_at",
        "exception_class",
        "exception_message",
        "acquisition_status",
        "acquisition_reason",
    ]:
        lines.append(f"| {key} | {payload.get(key, '')} |")
    lines.extend(["", "## Candidate URLs", ""])
    candidate_urls = payload.get("candidate_urls") or []
    if candidate_urls:
        for url in candidate_urls:
            lines.append(f"- {url}")
    else:
        lines.append("- None")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def _is_etenders_source(row: Dict[str, Any]) -> bool:
    blob = " ".join(
        [
            _clean(row.get("name")),
            _clean(row.get("source_name")),
            _clean(row.get("url")),
            _clean(row.get("list_url")),
            _clean(row.get("portal_name")),
        ]
    ).lower()
    return "etender" in blob or "national treasury" in blob or "www.etenders.gov.za" in blob


def _detect_registry_paths() -> List[Path]:
    runtime_paths = get_runtime_paths()
    project_root = runtime_paths.project_root
    runtime_root = runtime_paths.runtime_root
    env_paths = [
        _clean(Path(p).expanduser()) if p else ""
        for p in [
            os.getenv("LMCP_HARVEST_SOURCE_REGISTRY_PATH"),
            os.getenv("HARVEST_SOURCE_REGISTRY_PATH"),
            os.getenv("LMCP_SOURCE_REGISTRY_PATH"),
        ]
    ]
    candidates = [Path(value).expanduser() for value in env_paths if value]
    candidates.extend(
        [
            project_root / "app" / "data" / "harvest_sources.json",
            project_root / "app" / "data" / "smoke_harvest_sources.json",
            runtime_root / "manual_production" / "harvest_sources.json",
            runtime_root / "manual_production" / "harvest_sources.jsonl",
        ]
    )
    return candidates


def _load_registry_sources() -> Tuple[List[Dict[str, Any]], List[str], str]:
    checked_paths: List[str] = []
    for path in _detect_registry_paths():
        checked_paths.append(str(path))
        if not path.exists():
            continue
        try:
            return load_harvest_sources(path), checked_paths, str(path)
        except Exception:
            continue
    try:
        return load_harvest_sources(CURATED_LIVE_SOURCE_FILE), checked_paths, CURATED_LIVE_SOURCE_FILE
    except Exception:
        return [], checked_paths, CURATED_LIVE_SOURCE_FILE


def _select_etenders_sources(registry_sources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    seen = set()
    for row in registry_sources:
        if not isinstance(row, dict):
            continue
        if not _is_etenders_source(row):
            continue
        url = _normalize_url(row.get("url") or row.get("list_url"))
        key = url or _clean(row.get("name") or row.get("source_name")).lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    if selected:
        return selected
    return [
        {
            "name": "National Treasury eTenders",
            "source_name": "National Treasury eTenders",
            "url": ETENDERS_OPPORTUNITIES,
            "list_url": ETENDERS_OPPORTUNITIES,
            "category": "aggregator",
            "source_group": "aggregator",
            "category_group": "aggregator",
            "enabled": True,
        }
    ]


def _stable_key(item: Dict[str, Any]) -> str:
    for key in (
        "buyer_rfq_number",
        "rfq_number",
        "reference_number",
        "tender_number",
        "document_number",
        "rfq_id",
    ):
        value = _clean(item.get(key))
        if value:
            return f"{key}:{value.lower()}"
    title = _clean(item.get("title"))
    if title:
        return f"title:{title.lower()}"
    source_url = _normalize_url(item.get("source_url") or item.get("listing_url"))
    return f"url:{source_url}|{title.lower() if title else ''}"


def _row_blob(row: Dict[str, Any]) -> str:
    try:
        return json.dumps(row, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(row or "")


def _extract_candidate_urls(row: Dict[str, Any]) -> Tuple[List[str], List[str], List[str], List[str]]:
    blob = _row_blob(row)
    ids = _extract_ids_from_row(row, blob)
    guids = _extract_guids(blob)
    filenames = _extract_filenames(blob)
    hrefs = _extract_href_links(blob)
    routes = _extract_js_routes(blob, ids, guids)
    urls: List[str] = []
    for url in hrefs + routes:
        if url not in urls:
            urls.append(url)
    return ids, guids, filenames, urls


def _pick_first_url(urls: Iterable[str], *, include_terms: Sequence[str]) -> str:
    terms = [term.lower() for term in include_terms if term]
    for url in urls:
        low = url.lower()
        if any(term in low for term in terms):
            return url
    return ""


def _classify_url_discovery(
    *,
    explicit_detail: str,
    explicit_document: str,
    extracted_urls: Sequence[str],
    html_snippet: str,
) -> str:
    markup_blob = _clean(html_snippet).lower()
    has_markup_links = "<a " in markup_blob or "href=" in markup_blob or "onclick=" in markup_blob

    if explicit_detail or explicit_document:
        return "url_found_and_persisted"
    if extracted_urls and has_markup_links:
        return "url_hidden_in_markup"
    if extracted_urls and not has_markup_links:
        return "url_present_but_not_persisted"
    if any(token in markup_blob for token in ["tenderdetails", "download", "document", "href=", "onclick="]):
        return "url_hidden_in_markup"
    return "url_absent_from_source_page"


def _acquisition_seeds(item: Dict[str, Any]) -> List[str]:
    seeds: List[str] = []
    for key in ("document_url", "detail_url"):
        value = _clean(item.get(key))
        if value and value not in seeds:
            seeds.append(value)
    for value in item.get("document_candidate_urls") or []:
        cleaned = _clean(value)
        if cleaned and cleaned not in seeds:
            seeds.append(cleaned)
    return seeds


def _build_dry_acquisition_result(item: Dict[str, Any]) -> Dict[str, Any]:
    seeds = _acquisition_seeds(item)
    return {
        "status": "prepared",
        "reason": "dry_controlled_acquisition_enabled",
        "downloaded_count": 0,
        "seed_urls": seeds,
        "document_confidence_score": 0.0,
        "would_download_documents": False,
        "would_submit_externally": False,
        "prepared_package": {
            "rfq_id": item.get("rfq_id"),
            "buyer_name": item.get("buyer_name"),
            "submission_method": item.get("submission_method"),
            "qualified": bool(item.get("qualified")),
            "seed_urls": seeds,
            "document_url": item.get("document_url"),
            "detail_url": item.get("detail_url"),
            "document_links_detected": int(item.get("document_links_detected") or 0),
        },
    }


def _build_controlled_live_trace(
    *,
    raw_item: Dict[str, Any],
    filtered_item: Dict[str, Any],
    acquisition_result: Dict[str, Any],
    acquisition_mode: str,
    live_acquisitions_used: int,
    max_live_acquisitions: int,
) -> Dict[str, Any]:
    return {
        "rfq_id": raw_item.get("rfq_id"),
        "qualified": bool(filtered_item.get("qualified")),
        "rejected": bool(filtered_item.get("rejected")),
        "acquisition_mode": acquisition_mode,
        "document_url_present": bool(_clean(filtered_item.get("document_url"))),
        "detail_url_present": bool(_clean(filtered_item.get("detail_url"))),
        "document_candidate_count": len(filtered_item.get("document_candidate_urls") or []),
        "live_acquisitions_used": live_acquisitions_used,
        "max_live_acquisitions": max_live_acquisitions,
        "acquisition_status": _clean(acquisition_result.get("status")),
        "acquisition_reason": _clean(acquisition_result.get("reason")),
        "seed_urls": list(acquisition_result.get("seed_urls") or []),
    }


def _make_raw_item(
    row: Dict[str, Any],
    *,
    registry_source: Dict[str, Any],
    page_index: int,
    page_start: int,
    page_size: int,
    row_index: int,
    page_url: str,
) -> Dict[str, Any]:
    ids, guids, filenames, extracted_urls = _extract_candidate_urls(row)
    explicit_detail = _first_text(row, ["detail_url", "detailUrl", "tender_detail_url"])
    explicit_document = _first_text(row, ["document_url", "documentUrl", "download_url", "downloadUrl"])
    detail_url = explicit_detail or _pick_first_url(extracted_urls, include_terms=["tenderdetails", "detail"])
    document_url = explicit_document or _pick_first_url(
        extracted_urls,
        include_terms=["downloadspec", "downloaddocument", "downloadfile", "downloadtenderdocument", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"],
    )
    candidate_document_urls = [
        url for url in extracted_urls
        if any(term in url.lower() for term in ["download", "document", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"])
    ]
    detected_links = {url for url in candidate_document_urls if url}
    if explicit_detail:
        detected_links.add(explicit_detail)
    if explicit_document:
        detected_links.add(explicit_document)
    document_links_detected = len(detected_links)
    html_snippet = _first_text(row, ["actions", "action_html", "html", "document_html"])
    if not html_snippet and (extracted_urls or explicit_detail or explicit_document):
        html_snippet = _row_blob(row)[:1200]

    rfq_id = (
        _first_text(row, ["buyer_rfq_number", "rfq_number", "reference_number", "tenderNumber", "tender_No", "tenderNo", "id"])
        or _first_text(row, ["title", "description"])
    )
    title = _first_text(row, ["title", "description", "tenderDescription", "tenderNumber"]) or rfq_id
    buyer_name = _first_text(row, ["buyer_name", "buyerName", "organOfState", "department"]) or _clean(registry_source.get("name") or registry_source.get("source_name"))
    closing_at = _first_text(row, ["closing_at", "closing_Date", "closingDate", "deadline", "deadline_at"])
    published_at = _first_text(row, ["published_at", "date_Published", "publishedDate"])
    category = _first_text(row, ["category"]) or _clean(registry_source.get("category") or registry_source.get("source_group") or registry_source.get("category_group") or "eTenders")
    province = _first_text(row, ["province", "province_name"])
    source_url = _clean(registry_source.get("url") or registry_source.get("list_url") or ETENDERS_OPPORTUNITIES)
    listing_url = ETENDERS_OPPORTUNITIES
    url_classification = _classify_url_discovery(
        explicit_detail=detail_url,
        explicit_document=document_url,
        extracted_urls=extracted_urls,
        html_snippet=html_snippet,
    )

    submission_method = _first_text(row, ["submission_method", "submission_type"]) or "portal"

    raw_item = {
        "rfq_id": rfq_id,
        "buyer_rfq_number": rfq_id,
        "rfq_number": _first_text(row, ["rfq_number", "reference_number", "tenderNumber"]),
        "reference_number": _first_text(row, ["reference_number", "tenderNumber", "tender_No"]),
        "title": title,
        "description": _first_text(row, ["description", "tenderDescription"]),
        "buyer_name": buyer_name,
        "province": province,
        "category": category,
        "submission_type": submission_method,
        "submission_method": submission_method,
        "briefing_required": False,
        "published_at": published_at,
        "closing_at": closing_at,
        "source_name": _clean(registry_source.get("name") or registry_source.get("source_name") or "National Treasury eTenders"),
        "source_url": source_url,
        "portal_slug": _clean(registry_source.get("portal_slug") or "national_treasury_etenders"),
        "listing_url": listing_url,
        "page_url": page_url,
        "page_index": page_index,
        "page_start": page_start,
        "page_size": page_size,
        "visible_row_index": row_index,
        "document_url": document_url,
        "detail_url": detail_url,
        "html_snippet": html_snippet,
        "raw_html": _row_blob(row),
        "row_blob": _row_blob(row),
        "raw_row": deepcopy(row),
        "candidate_ids": ids,
        "candidate_guids": guids,
        "candidate_filenames": filenames,
        "candidate_urls": extracted_urls,
        "document_candidate_urls": candidate_document_urls,
        "document_links_detected": document_links_detected,
        "url_discovery_classification": url_classification,
        "source_mode": "auto_harvest_recovery",
        "portal_submission_disabled": True,
        "human_approval_required": True,
        "autonomous_submission_enabled": False,
        "final_submit_enabled": False,
        "qualification_threshold_changed": False,
    }
    return raw_item


def _persist_raw_then_filter(
    raw_item: Dict[str, Any],
    *,
    timeout: int,
    persist_fn,
    qualify_fn,
    apply_fn,
    acquire_fn,
    skip_acquisition: bool = False,
    acquisition_mode: str = "legacy",
    max_live_acquisitions: int = 1,
    live_acquisitions_used: int = 0,
    debug_controlled_live: bool = False,
    resolved_run_id: str = "",
    controlled_live_progress_dir: Optional[Path] = None,
    controlled_live_debug_path: Optional[Path] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    persist_fn(dict(raw_item))

    filtered_item = dict(raw_item)
    qualification = qualify_fn(filtered_item)
    apply_fn(filtered_item, qualification)
    filtered_item["qualification_result"] = qualification.to_dict() if hasattr(qualification, "to_dict") else qualification
    filtered_item["qualification_status"] = getattr(qualification, "qualification_status", _clean(filtered_item.get("qualification_status")))
    filtered_item["qualified"] = bool(getattr(qualification, "qualified", False))
    filtered_item["rejected"] = bool(getattr(qualification, "rejected", False))
    filtered_item["recommendation"] = "APPROVE" if filtered_item["qualified"] else "REJECT" if filtered_item["rejected"] else "REVIEW"

    acquisition_result: Dict[str, Any] = {
        "status": "not_attempted",
        "downloaded_count": 0,
        "seed_urls": [],
        "document_confidence_score": 0.0,
    }
    if skip_acquisition:
        acquisition_result = {
            "status": "skipped",
            "reason": "skip_acquisition_enabled",
            "downloaded_count": 0,
            "seed_urls": [],
            "document_confidence_score": 0.0,
        }
    elif acquisition_mode == "dry_controlled":
        if bool(filtered_item.get("qualified")):
            acquisition_result = _build_dry_acquisition_result(filtered_item)
        else:
            acquisition_result = {
                "status": "not_attempted",
                "reason": "not_qualified_for_controlled_acquisition",
                "downloaded_count": 0,
                "seed_urls": [],
                "document_confidence_score": 0.0,
            }
    elif acquisition_mode == "controlled_live":
        if bool(filtered_item.get("qualified")):
            if live_acquisitions_used < max_live_acquisitions and (
                filtered_item.get("document_url") or filtered_item.get("detail_url") or filtered_item.get("document_candidate_urls")
            ):
                live_acquisitions_used += 1
                progress_dir = controlled_live_progress_dir or get_runtime_paths().runtime_root / "harvest_recovery"
                progress_payload: Dict[str, Any] = {
                    "run_id": resolved_run_id,
                    "last_step": "before_acquire",
                    "acquisition_started": False,
                    "acquisition_completed": False,
                    "acquisition_failed": False,
                    "acquisition_timeout": False,
                    "selected_rfq_id": filtered_item.get("rfq_id"),
                    "title": filtered_item.get("title"),
                    "buyer": filtered_item.get("buyer_name"),
                    "document_url": filtered_item.get("document_url"),
                    "detail_url": filtered_item.get("detail_url"),
                    "candidate_urls": list(filtered_item.get("document_candidate_urls") or []),
                    "timeout_seconds": timeout,
                    "started_at": _now_iso(),
                    "completed_at": "",
                    "exception_class": "",
                    "exception_message": "",
                    "acquisition_status": "pending",
                    "acquisition_reason": "controlled_live_acquisition_pending",
                    "live_acquisitions_used": live_acquisitions_used,
                    "max_live_acquisitions": max_live_acquisitions,
                }
                _write_controlled_acquisition_progress(progress_dir, progress_payload)
                if debug_controlled_live and controlled_live_debug_path is not None:
                    _append_debug_line(
                        controlled_live_debug_path,
                        {
                            "stage": "before_acquire",
                            "timestamp": progress_payload["started_at"],
                            "rfq_id": filtered_item.get("rfq_id"),
                            "acquisition_mode": acquisition_mode,
                            "timeout_seconds": timeout,
                            "live_acquisitions_used": live_acquisitions_used - 1,
                            "max_live_acquisitions": max_live_acquisitions,
                            "document_url_present": bool(_clean(filtered_item.get("document_url"))),
                            "detail_url_present": bool(_clean(filtered_item.get("detail_url"))),
                            "document_candidate_count": len(filtered_item.get("document_candidate_urls") or []),
                            "seed_urls": _acquisition_seeds(filtered_item),
                        },
                    )
                acquisition_state: Dict[str, Any] = {"result": None, "error": None}

                def _run_acquisition() -> None:
                    try:
                        acquisition_state["result"] = acquire_fn(filtered_item, timeout_seconds=timeout)
                    except Exception as exc:  # pragma: no cover - runtime failure path
                        acquisition_state["error"] = exc

                worker = threading.Thread(target=_run_acquisition, daemon=True)
                worker.start()
                progress_payload["acquisition_started"] = True
                progress_payload["last_step"] = "acquisition_started"
                _write_controlled_acquisition_progress(progress_dir, progress_payload)

                deadline = time.monotonic() + max(1, int(timeout))
                while worker.is_alive() and time.monotonic() < deadline:
                    worker.join(timeout=1.0)
                    progress_payload["last_step"] = "waiting_for_acquisition"
                    progress_payload["heartbeat_at"] = _now_iso()
                    _write_controlled_acquisition_progress(progress_dir, progress_payload)

                if worker.is_alive():
                    acquisition_result = {
                        "status": "timeout",
                        "reason": "controlled_live_acquisition_timeout",
                        "downloaded_count": 0,
                        "seed_urls": _acquisition_seeds(filtered_item),
                        "document_confidence_score": 0.0,
                    }
                    progress_payload["acquisition_timeout"] = True
                    progress_payload["last_step"] = "acquisition_timeout"
                    progress_payload["completed_at"] = _now_iso()
                    progress_payload["acquisition_status"] = "timeout"
                    progress_payload["acquisition_reason"] = "controlled_live_acquisition_timeout"
                elif acquisition_state["error"] is not None:
                    exc = acquisition_state["error"]
                    acquisition_result = {
                        "status": "failed",
                        "reason": "controlled_live_acquisition_exception",
                        "error_class": exc.__class__.__name__,
                        "error_message": str(exc),
                        "downloaded_count": 0,
                        "seed_urls": _acquisition_seeds(filtered_item),
                        "document_confidence_score": 0.0,
                    }
                    progress_payload["acquisition_failed"] = True
                    progress_payload["last_step"] = "acquisition_failed"
                    progress_payload["completed_at"] = _now_iso()
                    progress_payload["exception_class"] = exc.__class__.__name__
                    progress_payload["exception_message"] = str(exc)
                    progress_payload["acquisition_status"] = "failed"
                    progress_payload["acquisition_reason"] = "controlled_live_acquisition_exception"
                else:
                    acquisition_result = acquisition_state["result"] or {
                        "status": "failed",
                        "reason": "controlled_live_acquisition_exception",
                        "downloaded_count": 0,
                        "seed_urls": _acquisition_seeds(filtered_item),
                        "document_confidence_score": 0.0,
                    }
                    progress_payload["acquisition_completed"] = True
                    progress_payload["last_step"] = "acquisition_completed"
                    progress_payload["completed_at"] = _now_iso()
                    progress_payload["acquisition_status"] = _clean(acquisition_result.get("status")) or "ok"
                    progress_payload["acquisition_reason"] = _clean(acquisition_result.get("reason"))

                _write_controlled_acquisition_progress(progress_dir, progress_payload)
                if debug_controlled_live and controlled_live_debug_path is not None:
                    _append_debug_line(
                        controlled_live_debug_path,
                        {
                            "stage": "after_acquire",
                            "timestamp": progress_payload["completed_at"],
                            "rfq_id": filtered_item.get("rfq_id"),
                            "acquisition_mode": acquisition_mode,
                            "timeout_seconds": timeout,
                            "live_acquisitions_used": live_acquisitions_used,
                            "max_live_acquisitions": max_live_acquisitions,
                            "acquisition_status": _clean(acquisition_result.get("status")),
                            "acquisition_reason": _clean(acquisition_result.get("reason")),
                            "downloaded_count": int(acquisition_result.get("downloaded_count") or 0),
                            "seed_urls": list(acquisition_result.get("seed_urls") or []),
                        },
                    )
            else:
                acquisition_result = {
                    "status": "deferred",
                    "reason": "controlled_live_acquisition_limit_reached",
                    "downloaded_count": 0,
                    "seed_urls": _acquisition_seeds(filtered_item),
                    "document_confidence_score": 0.0,
                }
        else:
            acquisition_result = {
                "status": "not_attempted",
                "reason": "not_qualified_for_controlled_acquisition",
                "downloaded_count": 0,
                "seed_urls": [],
                "document_confidence_score": 0.0,
            }
    elif filtered_item.get("document_url") or filtered_item.get("detail_url") or filtered_item.get("document_candidate_urls"):
        acquisition_result = acquire_fn(filtered_item, timeout_seconds=timeout)

    filtered_item["document_acquisition_result"] = acquisition_result
    if debug_controlled_live and acquisition_mode == "controlled_live":
        filtered_item["controlled_live_trace"] = _build_controlled_live_trace(
            raw_item=raw_item,
            filtered_item=filtered_item,
            acquisition_result=acquisition_result,
            acquisition_mode=acquisition_mode,
            live_acquisitions_used=live_acquisitions_used,
            max_live_acquisitions=max_live_acquisitions,
        )
    persist_fn(dict(filtered_item))
    return filtered_item, acquisition_result, live_acquisitions_used


def _page_plan(pages: int, limit: int) -> Tuple[int, int]:
    pages = max(1, int(pages or 1))
    limit = max(1, int(limit or 1))
    page_size = max(1, math.ceil(limit / pages))
    return pages, page_size


def _build_coverage_metrics(
    *,
    registry_sources: Sequence[Dict[str, Any]],
    etenders_sources: Sequence[Dict[str, Any]],
    pages_requested: int,
    pages_scanned: int,
    visible_rows_seen: int,
    extracted_count: int,
    persisted_count: int,
    duplicates_skipped: int,
    qualified_count: int,
    rejected_count: int,
    document_links_detected: int,
    acquisition_succeeded: int,
    acquisition_failed: int,
    acquisition_skipped: bool,
    acquisition_mode: str,
    acquisition_prepared: int,
    acquisition_deferred: int,
    live_acquisition_attempts: int,
    debug_controlled_live: bool,
    controlled_live_trace_count: int,
    page_failures: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    failure_counts = Counter()
    for failure in page_failures:
        failure_counts[failure.get("failure_type") or "unknown_error"] += 1
    coverage = round((pages_scanned / max(pages_requested, 1)) * 100.0, 2)
    return {
        "configured_sources": len(registry_sources),
        "etenders_sources": len(etenders_sources),
        "pages_requested": pages_requested,
        "pages_scanned": pages_scanned,
        "visible_rows_seen": visible_rows_seen,
        "rfqs_extracted": extracted_count,
        "rfqs_persisted": persisted_count,
        "duplicates_skipped": duplicates_skipped,
        "qualified_candidates": qualified_count,
        "rejected_candidates": rejected_count,
        "document_links_detected": document_links_detected,
        "acquisition_succeeded": acquisition_succeeded,
        "acquisition_failed": acquisition_failed,
        "acquisition_skipped": bool(acquisition_skipped),
        "acquisition_mode": acquisition_mode,
        "acquisition_prepared": acquisition_prepared,
        "acquisition_deferred": acquisition_deferred,
        "live_acquisition_attempts": live_acquisition_attempts,
        "debug_controlled_live": bool(debug_controlled_live),
        "controlled_live_trace_count": controlled_live_trace_count,
        "harvest_coverage_percent": coverage,
        "portal_submission_disabled": True,
        "human_approval_required": True,
        "autonomous_submission_enabled": False,
        "top_failure_types": failure_counts.most_common(),
    }


def _build_leaderboard(items: Sequence[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    leaderboard: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = _stable_key(item)
        bucket = leaderboard.setdefault(
            key,
            {
                "rfq_id": item.get("rfq_id") or item.get("buyer_rfq_number") or item.get("title"),
                "buyer_name": item.get("buyer_name"),
                "source_name": item.get("source_name"),
                "category": item.get("category"),
                "listing_url": item.get("listing_url"),
                "detail_url": item.get("detail_url"),
                "document_url": item.get("document_url"),
                "rfqs_extracted": 0,
                "qualified_candidates": 0,
                "rejected_candidates": 0,
                "document_links_detected": 0,
                "acquisition_succeeded": 0,
                "acquisition_failed": 0,
            },
        )
        bucket["rfqs_extracted"] += 1
        if item.get("qualified"):
            bucket["qualified_candidates"] += 1
        if item.get("rejected"):
            bucket["rejected_candidates"] += 1
        bucket["document_links_detected"] += int(item.get("document_links_detected") or 0)
        acquisition = item.get("document_acquisition_result") if isinstance(item.get("document_acquisition_result"), dict) else {}
        acq_status = _clean(acquisition.get("status")).lower()
        if acq_status == "ok" and int(acquisition.get("downloaded_count") or 0) > 0:
            bucket["acquisition_succeeded"] += 1
        elif acq_status not in {"not_attempted", "", "skipped"}:
            bucket["acquisition_failed"] += 1
    rows = list(leaderboard.values())
    rows.sort(
        key=lambda row: (
            -int(row["document_links_detected"]),
            -int(row["qualified_candidates"]),
            -int(row["rfqs_extracted"]),
            _clean(row["rfq_id"]).lower(),
        )
    )
    return rows[: max(1, limit)]


def _write_summary_md(path: Path, *, coverage: Dict[str, Any], leaderboard: Sequence[Dict[str, Any]], items: Sequence[Dict[str, Any]], page_failures: Sequence[Dict[str, Any]], registry_path: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = [
        "# Sprint 8A eTenders Auto-Harvest Recovery Summary",
        "",
        f"Generated at: {_now_iso()}",
        "",
        "## Guardrails",
        "",
        f"- Portal submission disabled: `{coverage['portal_submission_disabled']}`",
        f"- Human approval required: `{coverage['human_approval_required']}`",
        f"- Autonomous submission enabled: `{coverage['autonomous_submission_enabled']}`",
        f"- Registry path loaded: `{registry_path}`",
        "",
        "## Coverage Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in [
        "configured_sources",
        "etenders_sources",
        "pages_requested",
        "pages_scanned",
        "visible_rows_seen",
        "rfqs_extracted",
        "rfqs_persisted",
        "duplicates_skipped",
        "qualified_candidates",
        "rejected_candidates",
        "document_links_detected",
        "acquisition_succeeded",
        "acquisition_failed",
        "acquisition_prepared",
        "acquisition_deferred",
        "live_acquisition_attempts",
        "acquisition_skipped",
        "acquisition_mode",
        "harvest_coverage_percent",
    ]:
        lines.append(f"| {key} | {coverage[key]} |")
    lines.extend(["", "## Failure Types", ""])
    if coverage["top_failure_types"]:
        for failure_type, count in coverage["top_failure_types"]:
            lines.append(f"- {failure_type}: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Top Producers", "", "| RFQ ID | Buyer | Qualified | Rejected | Links | Acquisition |", "| --- | --- | ---: | ---: | ---: | --- |"])
    for item in leaderboard[:20]:
        acq = item.get("document_acquisition_result") if isinstance(item.get("document_acquisition_result"), dict) else {}
        acq_status = _clean(acq.get("status")) or "not_attempted"
        lines.append(
            f"| {item.get('rfq_id') or ''} | {item.get('buyer_name') or ''} | {int(item.get('qualified_candidates') or 0)} | {int(item.get('rejected_candidates') or 0)} | {int(item.get('document_links_detected') or 0)} | {acq_status} |"
        )
    lines.extend(["", "## Sample Items", "", "| RFQ ID | Page | URL Discovery | Acquisition |", "| --- | ---: | --- | --- |"])
    for item in items[:20]:
        acq = item.get("document_acquisition_result") if isinstance(item.get("document_acquisition_result"), dict) else {}
        lines.append(
            f"| {item.get('rfq_id') or ''} | {item.get('page_index', '')} | {item.get('url_discovery_classification') or ''} | {_clean(acq.get('status')) or 'not_attempted'} |"
        )
    lines.extend(["", "## Page Failures", ""])
    if page_failures:
        for failure in page_failures[:20]:
            lines.append(
                f"- page {failure.get('page_index')} start={failure.get('start')} status={failure.get('status')} failure={failure.get('failure_type')}"
            )
    else:
        lines.append("- None")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_etenders_auto_harvest_recovery(
    *,
    pages: int = 20,
    limit: int = 500,
    timeout: int = 20,
    output_dir: Optional[Path] = None,
    preserve_run: bool = False,
    run_id: Optional[str] = None,
    skip_acquisition: bool = False,
    dry_controlled_acquisition: bool = False,
    controlled_acquisition: bool = False,
    max_live_acquisitions: int = 1,
    debug_controlled_live: bool = False,
    fetch_page_fn=fetch_etenders_page,
    persist_fn=persist_live_rfq,
    qualify_fn=qualify_opportunity,
    apply_fn=apply_qualification_to_opportunity,
    acquire_fn=acquire_rfq_documents,
) -> Dict[str, Any]:
    registry_sources, checked_paths, registry_path = _load_registry_sources()
    etenders_sources = _select_etenders_sources(registry_sources)

    pages_requested, page_size = _page_plan(pages, limit)
    raw_items: List[Dict[str, Any]] = []
    page_summaries: List[Dict[str, Any]] = []
    page_failures: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    pages_scanned = 0
    visible_rows_seen = 0
    rfqs_extracted = 0
    rfqs_persisted = 0
    duplicates_skipped = 0
    qualified_candidates = 0
    rejected_candidates = 0
    document_links_detected = 0
    acquisition_succeeded = 0
    acquisition_failed = 0
    acquisition_prepared = 0
    acquisition_deferred = 0
    live_acquisition_attempts = 0
    controlled_live_trace_count = 0

    acquisition_mode = "legacy"
    if skip_acquisition:
        acquisition_mode = "skip"
    elif dry_controlled_acquisition:
        acquisition_mode = "dry_controlled"
    elif controlled_acquisition:
        acquisition_mode = "controlled_live"

    output_root = Path(output_dir) if output_dir else get_runtime_paths().runtime_root / "harvest_recovery"
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_run_id = _clean(run_id) or _default_run_id()
    run_root = output_root / "runs" / resolved_run_id if preserve_run else None
    if run_root is not None:
        run_root.mkdir(parents=True, exist_ok=True)
    controlled_live_progress_dir: Optional[Path] = run_root or output_root if (controlled_acquisition or dry_controlled_acquisition or debug_controlled_live) else None
    controlled_live_debug_path: Optional[Path] = (run_root or output_root) / "controlled_live_debug.jsonl" if debug_controlled_live else None
    if controlled_live_progress_dir is not None:
        _write_controlled_acquisition_progress(
            controlled_live_progress_dir,
            {
                "run_id": resolved_run_id,
                "last_step": "run_started",
                "acquisition_started": False,
                "acquisition_completed": False,
                "acquisition_failed": False,
                "acquisition_timeout": False,
                "selected_rfq_id": "",
                "title": "",
                "buyer": "",
                "document_url": "",
                "detail_url": "",
                "candidate_urls": [],
                "timeout_seconds": timeout,
                "started_at": _now_iso(),
                "completed_at": "",
                "exception_class": "",
                "exception_message": "",
                "acquisition_status": "pending",
                "acquisition_reason": "run_started",
                "live_acquisitions_used": 0,
                "max_live_acquisitions": max_live_acquisitions,
            },
        )

    page_url = f"{PAGINATED_ENDPOINT}?status={DEFAULT_STATUS}&start={{start}}&length={page_size}"

    for page_index in range(pages_requested):
        start = page_index * page_size
        pages_scanned += 1
        try:
            page = fetch_page_fn(DEFAULT_STATUS, start, page_size)
        except Exception as exc:
            page = {
                "ok": False,
                "status_code": 0,
                "url": page_url.format(start=start),
                "start": start,
                "length": page_size,
                "rows": [],
                "error": str(exc),
            }
        if debug_controlled_live and controlled_live_debug_path is not None:
            _append_debug_line(
                controlled_live_debug_path,
                {
                    "stage": "page_fetch",
                    "timestamp": _now_iso(),
                    "page_index": page_index,
                    "start": start,
                    "page_size": page_size,
                    "ok": bool(page.get("ok")) if isinstance(page, dict) else False,
                    "status_code": page.get("status_code") if isinstance(page, dict) else 0,
                    "url": page.get("url") if isinstance(page, dict) else page_url.format(start=start),
                    "error": page.get("error") if isinstance(page, dict) else "",
                },
            )
        rows = page.get("rows") if isinstance(page, dict) else []
        if not isinstance(rows, list):
            rows = []
        visible_rows_seen += len(rows)
        page_summaries.append(
            {
                "page_index": page_index,
                "start": start,
                "page_size": page_size,
                "row_count": len(rows),
                "ok": bool(page.get("ok")) if isinstance(page, dict) else False,
                "status_code": page.get("status_code") if isinstance(page, dict) else 0,
                "url": page.get("url") if isinstance(page, dict) else page_url.format(start=start),
                "error": page.get("error") if isinstance(page, dict) else "",
            }
        )
        if not page.get("ok", True) and not rows:
            page_failures.append(
                {
                    "page_index": page_index,
                    "start": start,
                    "status": page.get("status_code") if isinstance(page, dict) else 0,
                    "failure_type": "page_fetch_failed",
                    "error": page.get("error") if isinstance(page, dict) else "",
                }
            )
            continue

        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            raw_item = _make_raw_item(
                row,
                registry_source=etenders_sources[0] if etenders_sources else {},
                page_index=page_index,
                page_start=start,
                page_size=page_size,
                row_index=row_index,
                page_url=page.get("url") if isinstance(page, dict) and page.get("url") else page_url.format(start=start),
            )
            key = _stable_key(raw_item)
            if key in seen_keys:
                duplicates_skipped += 1
                continue
            seen_keys.add(key)
            rfqs_extracted += 1
            rfqs_persisted += 1
            document_links_detected += int(raw_item.get("document_links_detected") or 0)

            filtered_item, acquisition_result, live_acquisition_attempts = _persist_raw_then_filter(
                raw_item,
                timeout=timeout,
                persist_fn=persist_fn,
                qualify_fn=qualify_fn,
                apply_fn=apply_fn,
                acquire_fn=acquire_fn,
                skip_acquisition=skip_acquisition,
                acquisition_mode=acquisition_mode,
                max_live_acquisitions=max_live_acquisitions,
                live_acquisitions_used=live_acquisition_attempts,
                debug_controlled_live=debug_controlled_live,
                resolved_run_id=resolved_run_id,
                controlled_live_progress_dir=controlled_live_progress_dir,
                controlled_live_debug_path=controlled_live_debug_path,
            )
            if debug_controlled_live and acquisition_mode == "controlled_live":
                controlled_live_trace_count += 1

            if bool(filtered_item.get("qualified")):
                qualified_candidates += 1
            elif bool(filtered_item.get("rejected")):
                rejected_candidates += 1

            acq_status = _clean(acquisition_result.get("status")).lower()
            if acq_status == "skipped":
                pass
            elif acq_status == "prepared":
                acquisition_prepared += 1
            elif acq_status == "deferred":
                acquisition_deferred += 1
            elif acq_status == "ok" and int(acquisition_result.get("downloaded_count") or 0) > 0:
                acquisition_succeeded += 1
            elif acq_status not in {"not_attempted", ""}:
                acquisition_failed += 1

            raw_items.append(
                {
                    "identity": {
                        "rfq_id": raw_item.get("rfq_id"),
                        "buyer_rfq_number": raw_item.get("buyer_rfq_number"),
                        "source_name": raw_item.get("source_name"),
                        "source_url": raw_item.get("source_url"),
                        "listing_url": raw_item.get("listing_url"),
                    },
                    "page": {
                        "page_index": page_index,
                        "page_start": start,
                        "page_size": page_size,
                        "row_index": row_index,
                        "page_url": raw_item.get("page_url"),
                    },
                    "raw_extracted": deepcopy(raw_item),
                    "filtered": deepcopy(filtered_item),
                    "qualification": deepcopy(filtered_item.get("qualification_result") or {}),
                    "acquisition": deepcopy(acquisition_result),
                    "classification": {
                        "url_discovery_classification": raw_item.get("url_discovery_classification"),
                        "document_links_detected": raw_item.get("document_links_detected"),
                    },
                    "persist": {
                        "raw_upserted": True,
                        "filtered_upserted": True,
                    },
                }
            )

    coverage_metrics = _build_coverage_metrics(
        registry_sources=registry_sources,
        etenders_sources=etenders_sources,
        pages_requested=pages_requested,
        pages_scanned=pages_scanned,
        visible_rows_seen=visible_rows_seen,
        extracted_count=rfqs_extracted,
        persisted_count=rfqs_persisted,
        duplicates_skipped=duplicates_skipped,
        qualified_count=qualified_candidates,
        rejected_count=rejected_candidates,
        document_links_detected=document_links_detected,
        acquisition_succeeded=acquisition_succeeded,
        acquisition_failed=acquisition_failed,
        acquisition_skipped=skip_acquisition,
        acquisition_mode=acquisition_mode,
        acquisition_prepared=acquisition_prepared,
        acquisition_deferred=acquisition_deferred,
        live_acquisition_attempts=live_acquisition_attempts,
        debug_controlled_live=debug_controlled_live,
        controlled_live_trace_count=controlled_live_trace_count,
        page_failures=page_failures,
    )
    leaderboard = _build_leaderboard(raw_items, limit=20)

    coverage_path = output_root / "etenders_harvest_coverage.json"
    items_path = output_root / "etenders_harvest_items.json"
    summary_path = output_root / "etenders_harvest_summary.md"

    coverage_payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "registry_path": registry_path,
        "registry_paths_checked": checked_paths,
        "metrics": coverage_metrics,
        "guardrails": {
            "portal_submission_disabled": True,
            "human_approval_required": True,
            "autonomous_submission_enabled": False,
            "no_final_submit": True,
            "no_approval_injection": True,
            "no_qualification_threshold_changes": True,
        },
        "scope": {
            "sprint": "Sprint 8A",
            "focus": "eTenders Auto-Harvest Recovery",
            "notes": "Automatic RFQ inflow recovery only; no submission automation changes.",
        },
        "run_id": resolved_run_id,
        "acquisition_skipped": bool(skip_acquisition),
        "acquisition_mode": acquisition_mode,
        "controlled_acquisition": bool(dry_controlled_acquisition or controlled_acquisition),
        "max_live_acquisitions": int(max_live_acquisitions),
        "debug_controlled_live": bool(debug_controlled_live),
        "registry_context": {
            "configured_sources": len(registry_sources),
            "etenders_sources": len(etenders_sources),
            "selected_etenders_source_names": [
                _clean(source.get("name") or source.get("source_name")) for source in etenders_sources
            ],
        },
        "page_summaries": page_summaries,
        "page_failures": page_failures,
    }
    items_payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "count": len(raw_items),
        "items": raw_items,
    }
    leaderboard_payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "count": len(leaderboard),
        "leaderboard": leaderboard,
    }

    coverage_path.write_text(json.dumps(coverage_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    items_path.write_text(json.dumps(items_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    _write_summary_md(
        summary_path,
        coverage=coverage_metrics,
        leaderboard=leaderboard,
        items=raw_items,
        page_failures=page_failures,
        registry_path=registry_path,
    )
    if run_root is not None:
        (run_root / "etenders_harvest_coverage.json").write_text(json.dumps(coverage_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        (run_root / "etenders_harvest_items.json").write_text(json.dumps(items_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        _write_summary_md(
            run_root / "etenders_harvest_summary.md",
            coverage=coverage_metrics,
            leaderboard=leaderboard,
            items=raw_items,
            page_failures=page_failures,
            registry_path=registry_path,
        )

    return {
        "coverage": coverage_payload,
        "items": items_payload,
        "leaderboard": leaderboard_payload,
        "output_dir": str(output_root),
        "run_dir": str(run_root) if run_root is not None else "",
        "run_id": resolved_run_id,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sprint 8A eTenders Auto-Harvest Recovery")
    parser.add_argument("--pages", type=int, default=20, help="Number of eTenders pages to scan")
    parser.add_argument("--limit", type=int, default=500, help="Maximum rows to scan across the requested pages")
    parser.add_argument("--timeout", type=int, default=20, help="Acquisition timeout in seconds")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory for recovery reports")
    parser.add_argument("--run-id", type=str, default="", help="Optional run identifier for preserving a run-scoped copy")
    parser.add_argument("--preserve-run", action="store_true", help="Write a run-scoped copy under runtime/harvest_recovery/runs/<run-id>")
    parser.add_argument("--skip-acquisition", action="store_true", help="Persist and filter RFQs without downloading documents")
    acquisition_group = parser.add_mutually_exclusive_group()
    acquisition_group.add_argument("--dry-controlled-acquisition", action="store_true", help="Prepare acquisition bundles for qualified RFQs without downloading documents")
    acquisition_group.add_argument("--controlled-acquisition", action="store_true", help="Attempt controlled live acquisition for qualified RFQs")
    parser.add_argument("--max-live-acquisitions", type=int, default=1, help="Maximum live acquisitions to attempt per run in controlled mode")
    parser.add_argument("--live-timeout-seconds", type=int, default=0, help="Alias for --timeout when running controlled live acquisition")
    parser.add_argument("--debug-controlled-live", action="store_true", help="Attach controlled-live trace data to filtered items and coverage metrics")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_etenders_auto_harvest_recovery(
        pages=max(1, int(args.pages or 20)),
        limit=max(1, int(args.limit or 500)),
        timeout=max(1, int(args.live_timeout_seconds or args.timeout or 20)),
        output_dir=Path(args.output_dir),
        preserve_run=bool(args.preserve_run),
        run_id=_clean(args.run_id),
        skip_acquisition=bool(args.skip_acquisition),
        dry_controlled_acquisition=bool(args.dry_controlled_acquisition),
        controlled_acquisition=bool(args.controlled_acquisition),
        max_live_acquisitions=max(1, int(args.max_live_acquisitions or 1)),
        debug_controlled_live=bool(args.debug_controlled_live),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
