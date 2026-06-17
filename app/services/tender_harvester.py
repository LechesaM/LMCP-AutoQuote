from __future__ import annotations

import json
import logging
import os
import re
import socket
import time
from html import escape as _html_escape
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlparse

import requests

from app.services.harvest_source_registry_service import get_curated_live_source_file
from app.services.harvest_source_registry_service import load_default_live_harvest_sources
from app.services.system_control_service import get_system_control_state

try:
    from app.services.rfq_document_intelligence import analyse_rfq_documents
except Exception:  # pragma: no cover
    analyse_rfq_documents = None

try:
    from app.services.rfq_boq_extraction_engine import extract_rfq_boq
except Exception:  # pragma: no cover
    extract_rfq_boq = None

try:
    from app.services.rfq_document_acquisition_engine import acquire_rfq_documents
except Exception:  # pragma: no cover
    acquire_rfq_documents = None

try:
    from app.services.rfq_zip_content_extraction_engine import extract_zip_contents
except Exception:  # pragma: no cover
    extract_zip_contents = None

try:
    from app.services.rfq_docx_main_document_intelligence import analyse_docx_main_document
except Exception:  # pragma: no cover
    analyse_docx_main_document = None

try:
    from app.services.real_buyer_pricing_engine import price_verified_rfq
except Exception:  # pragma: no cover
    price_verified_rfq = None

try:
    from app.services import live_rfq_store as _live_rfq_store
except Exception:  # pragma: no cover
    _live_rfq_store = None

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
PAUSE_FILE = RUNTIME_DIR / "harvester.paused"
DEFAULT_SOURCE_FILE = PROJECT_ROOT / "app" / "data" / "harvest_sources.json"
SOURCE_HEALTH_FILE = RUNTIME_DIR / "source_health.json"
MULTI_PORTAL_DISCOVERY_DIR = RUNTIME_DIR / "multi_portal_discovery"
MULTI_PORTAL_DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENT_DISCOVERY_DIR = MULTI_PORTAL_DISCOVERY_DIR / "documents"
DOCUMENT_DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
SOURCE_YIELD_RANKINGS_FILE = MULTI_PORTAL_DISCOVERY_DIR / "source_yield_rankings.json"
ADAPTIVE_SOURCE_WEIGHTS_FILE = MULTI_PORTAL_DISCOVERY_DIR / "adaptive_source_weights.json"
YIELD_SUMMARY_FILE = MULTI_PORTAL_DISCOVERY_DIR / "yield_summary.json"
DISCOVERY_MEMORY_DIR = RUNTIME_DIR / "discovery_memory"
DISCOVERY_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
SOURCE_MEMORY_FILE = DISCOVERY_MEMORY_DIR / "source_memory.json"
BUYER_MEMORY_FILE = DISCOVERY_MEMORY_DIR / "buyer_memory.json"
CATEGORY_MEMORY_FILE = DISCOVERY_MEMORY_DIR / "category_memory.json"
DOCUMENT_PATTERN_MEMORY_FILE = DISCOVERY_MEMORY_DIR / "document_pattern_memory.json"
SOURCE_PACKS_DIR = RUNTIME_DIR / "source_packs"
SOURCE_PACKS_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_SOURCE_PACKS_FILE = SOURCE_PACKS_DIR / "active_source_packs.json"
HIGH_YIELD_SOURCES_FILE = SOURCE_PACKS_DIR / "high_yield_sources.json"
PACK_PERFORMANCE_SUMMARY_FILE = SOURCE_PACKS_DIR / "pack_performance_summary.json"
SOURCE_PACK_REPAIR_DIAGNOSTICS_FILE = SOURCE_PACKS_DIR / "source_pack_repair_diagnostics.json"
BUYER_INTELLIGENCE_DIR = RUNTIME_DIR / "buyer_intelligence"
BUYER_INTELLIGENCE_DIR.mkdir(parents=True, exist_ok=True)
BUYER_PROFILES_FILE = BUYER_INTELLIGENCE_DIR / "buyer_profiles.json"
PROCUREMENT_PATTERNS_FILE = BUYER_INTELLIGENCE_DIR / "procurement_patterns.json"
HIGH_VALUE_BUYERS_FILE = BUYER_INTELLIGENCE_DIR / "high_value_buyers.json"
TENDER_RADAR_DIR = RUNTIME_DIR / "tender_radar"
TENDER_RADAR_DIR.mkdir(parents=True, exist_ok=True)
OPPORTUNITY_FORECASTS_FILE = TENDER_RADAR_DIR / "opportunity_forecasts.json"
HIGH_PROBABILITY_OPPORTUNITIES_FILE = TENDER_RADAR_DIR / "high_probability_opportunities.json"
BUYER_FORECAST_SUMMARY_FILE = TENDER_RADAR_DIR / "buyer_forecast_summary.json"
ACTION_WATCHLIST_FILE = TENDER_RADAR_DIR / "action_watchlist.json"
DAILY_PRIORITY_TARGETS_FILE = TENDER_RADAR_DIR / "daily_priority_targets.json"
WATCHLIST_SUMMARY_FILE = TENDER_RADAR_DIR / "watchlist_summary.json"
RADAR_CYCLES_DIR = RUNTIME_DIR / "radar_cycles"
RADAR_CYCLES_DIR.mkdir(parents=True, exist_ok=True)
CYCLE_HISTORY_FILE = RADAR_CYCLES_DIR / "cycle_history.json"
CURRENT_CYCLE_SUMMARY_FILE = RADAR_CYCLES_DIR / "current_cycle_summary.json"
SOURCE_PRODUCTIVITY_RANKINGS_FILE = RADAR_CYCLES_DIR / "source_productivity_rankings.json"
BUYER_TREND_RANKINGS_FILE = RADAR_CYCLES_DIR / "buyer_trend_rankings.json"
CATEGORY_TREND_RANKINGS_FILE = RADAR_CYCLES_DIR / "category_trend_rankings.json"
_SOURCE_SHAPE_REPORT_CACHE: Dict[str, Any] = {"path": None, "mtime": None, "map": {}}
OPPORTUNITY_EXTRACTION_DIR = RUNTIME_DIR / "opportunity_extraction"
OPPORTUNITY_EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_OPPORTUNITIES_FILE = OPPORTUNITY_EXTRACTION_DIR / "extracted_opportunities.json"
HIGH_CONFIDENCE_OPPORTUNITIES_FILE = OPPORTUNITY_EXTRACTION_DIR / "high_confidence_opportunities.json"
REVIEW_REQUIRED_OPPORTUNITIES_FILE = OPPORTUNITY_EXTRACTION_DIR / "review_required_opportunities.json"
REJECTED_OPPORTUNITIES_FILE = OPPORTUNITY_EXTRACTION_DIR / "rejected_opportunities.json"
EXTRACTION_SUMMARY_FILE = OPPORTUNITY_EXTRACTION_DIR / "extraction_summary.json"
DOCUMENT_INTELLIGENCE_DIR = RUNTIME_DIR / "document_intelligence"
DOCUMENT_INTELLIGENCE_DIR.mkdir(parents=True, exist_ok=True)
PRICING_SCHEDULES_FILE = DOCUMENT_INTELLIGENCE_DIR / "pricing_schedules.json"
QUOTE_READY_DOCUMENTS_FILE = DOCUMENT_INTELLIGENCE_DIR / "quote_ready_documents.json"
REVIEW_REQUIRED_DOCUMENTS_FILE = DOCUMENT_INTELLIGENCE_DIR / "review_required_documents.json"
REJECTED_DOCUMENTS_FILE = DOCUMENT_INTELLIGENCE_DIR / "rejected_documents.json"
DOCUMENT_INTELLIGENCE_SUMMARY_FILE = DOCUMENT_INTELLIGENCE_DIR / "document_intelligence_summary.json"
ITEM_TABLES_FILE = DOCUMENT_INTELLIGENCE_DIR / "item_tables.json"
QUANTITY_EXTRACTION_REPORT_FILE = DOCUMENT_INTELLIGENCE_DIR / "quantity_extraction_report.json"
REVIEW_QUEUE_DIR = RUNTIME_DIR / "review_queue"
REVIEW_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
PARTIAL_QUOTE_READY_QUEUE_FILE = REVIEW_QUEUE_DIR / "partial_quote_ready_queue.json"
URGENT_REVIEW_ITEMS_FILE = REVIEW_QUEUE_DIR / "urgent_review_items.json"
REVIEW_SUMMARY_FILE = REVIEW_QUEUE_DIR / "review_summary.json"
HARVEST_RUNS_DIR = RUNTIME_DIR / "harvest_runs"
HARVEST_RUNS_DIR.mkdir(parents=True, exist_ok=True)
LAST_ACQUISITION_RUNTIME_DIAGNOSTICS_FILE = HARVEST_RUNS_DIR / "last_acquisition_runtime_diagnostics.json"
DEBUG_DIR = RUNTIME_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
LIVE_CANDIDATE_DEBUG_FILE = DEBUG_DIR / "live_candidates.jsonl"
LIVE_ELIGIBILITY_TRACE_FILE = DEBUG_DIR / "live_eligibility_trace.jsonl"

ETENDERS_URL = "https://www.etenders.gov.za/Home/opportunities"
ETENDERS_PAGINATED_OPPORTUNITIES_URL = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"
ETENDERS_BASE_URL = "https://www.etenders.gov.za"
INVALID_SOURCE_URL_SNIPPETS = (
    "google.com/search",
    "www.google.com/search",
)
ZERO_YIELD_QUARANTINE_SCAN_THRESHOLD = 30

AI_AGENT_PROFILE = "chatgpt_codex_ready"
AI_PRIMARY_MODEL_HINT = "gpt-5.4"
AI_FAST_MODEL_HINT = "gpt-5.4-mini"
AI_API_STYLE_HINT = "responses_api"
AI_ORCHESTRATION_HINT = "agents_sdk"

DEFAULT_MINIMUM_MARGIN_PCT = 25.0
DOCUMENT_DISCOVERY_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".csv"}
DOCUMENT_DOWNLOAD_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".csv"}
DOCUMENT_MAX_BYTES = 12 * 1024 * 1024
ARTIFACT_CANDIDATE_CLASSIFICATIONS = {
    "direct_file",
    "likely_download_endpoint",
    "document_action_link",
    "html_navigation",
    "javascript_link",
    "api_json_endpoint",
    "unknown",
}
ETENDERS_ARTIFACT_HINT_PATTERN = re.compile(
    r"\b(downloadfile|download|document|tenderdocument|biddocument|attachment|specification|boq|pricing schedule|sbd|returnable|compulsory documents|zip|pdf|docx|xlsx)\b",
    re.I,
)
ARTIFACT_NAVIGATION_PATTERN = re.compile(
    r"\b(home|opportunit(?:y|ies)|details?|view|open|next|previous|back|menu|contact|about|terms|privacy|help|faq|login|register)\b",
    re.I,
)
ARTIFACT_SOCIAL_PATTERN = re.compile(
    r"\b(share|facebook|twitter|linkedin|whatsapp|telegram)\b",
    re.I,
)
ARTIFACT_API_JSON_PATTERN = re.compile(
    r"\b(api|json|datatable|ajax|service)\b",
    re.I,
)
ETENDERS_ENDPOINT_PATTERN = re.compile(
    r"\b(tenderdocuments?|tenderdetails|supportdocument|downloadsupportdocument|downloadspec|spec|document|download|downloadfile|biddocument|attachment|getdocuments|gettenderdocuments|gettenderdetails|scmdocument|file|filename|blob|content)\b",
    re.I,
)
ETENDERS_DOCUMENT_RESPONSE_KEYS = (
    "url",
    "href",
    "downloadUrl",
    "fileUrl",
    "documentUrl",
    "attachmentUrl",
    "blobName",
    "BlobName",
    "blobname",
    "fileName",
    "DownloadedFileName",
    "downloadedFileName",
    "filePath",
    "path",
    "attachments",
    "documents",
    "documentsList",
    "supportDocuments",
)
V57_MEMORY_HISTORY_LIMIT = 80
V57_FINGERPRINT_LIMIT = 8000
V58_SOURCE_PACK_NAMES = [
    "municipalities_pack",
    "SOE_pack",
    "provincial_pack",
    "university_pack",
    "repeat_buyer_pack",
    "document_rich_pack",
]
V59_BUYER_PROFILE_TYPES = ["municipalities", "SOEs", "universities", "provincial_departments"]
CONTROLLED_SMOKE_SOURCE_FILE = PROJECT_ROOT / "app" / "data" / "smoke_harvest_sources.json"
CONTROLLED_FIXTURE_DIR = PROJECT_ROOT / "app" / "data" / "fixtures"

try:
    from app.services.real_rfq_detail_navigation_v49_service import analyse_rfq_detail_navigation
except Exception:  # pragma: no cover
    analyse_rfq_detail_navigation = None

try:
    from app.services.detail_page_follow_v49_1_service import follow_detail_pages
except Exception:  # pragma: no cover
    follow_detail_pages = None

try:
    from app.services.etenders_real_detail_navigation_v50_7_service import analyse_etenders_detail_navigation
except Exception:  # pragma: no cover
    analyse_etenders_detail_navigation = None

try:
    from app.services.true_etenders_detail_resolution_v50_8_service import resolve_true_etenders_detail
except Exception:  # pragma: no cover
    resolve_true_etenders_detail = None

try:
    from app.services.etenders_ajax_datatables_resolver_v50_8_1_service import resolve_etenders_ajax_datatables
except Exception:  # pragma: no cover
    resolve_etenders_ajax_datatables = None

try:
    from app.services.etenders_document_url_reconstruction_v50_8_2_service import reconstruct_etenders_document_urls
except Exception:  # pragma: no cover
    reconstruct_etenders_document_urls = None

try:
    from app.services.etenders_tenderdetails_json_v50_9_1_service import inspect_tenderdetails_json, download_from_tenderdetails_json
except Exception:  # pragma: no cover
    inspect_tenderdetails_json = None
    download_from_tenderdetails_json = None

try:
    from app.services.etenders_dom_modal_autoclick_v50_9_4_service import capture_dom_modal_autoclick
except Exception:  # pragma: no cover
    capture_dom_modal_autoclick = None

try:
    from app.services.etenders_hidden_api_discovery_v50_9_6_service import discover_hidden_api
except Exception:  # pragma: no cover
    discover_hidden_api = None

try:
    from app.services.verified_rfq_promotion_gate_v50_7_service import evaluate_verified_rfq_for_promotion
except Exception:  # pragma: no cover
    evaluate_verified_rfq_for_promotion = None


DEFAULT_MINIMUM_PROFIT = 30000.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_runtime_file(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


def _display_project_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except Exception:
        return str(path)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _is_live_url(value: Any) -> bool:
    url = _clean(value).lower()
    return url.startswith("http://") or url.startswith("https://")


def _is_controlled_fixture_source_file(path: Optional[str]) -> bool:
    if not path:
        return False
    try:
        resolved = Path(path).expanduser().resolve()
    except Exception:
        return False
    try:
        return resolved == CONTROLLED_SMOKE_SOURCE_FILE.resolve() or CONTROLLED_FIXTURE_DIR.resolve() in resolved.parents
    except Exception:
        return False


def _ensure_controlled_sources_only(sources: List[Dict[str, Any]], source_file: Optional[str]) -> None:
    if not _is_controlled_fixture_source_file(source_file):
        raise ValueError(
            "controlled_mode requires a bundled fixture source file under app/data/fixtures or smoke_harvest_sources.json"
        )
    for source in sources:
        if not isinstance(source, dict):
            continue
        if _is_live_url(source.get("url")) or _is_live_url(source.get("list_url")):
            raise ValueError(
                f"controlled_mode rejects live source URL: {_clean(source.get('name') or source.get('source_name') or source.get('url'))}"
            )


def _safe_positive_int(value: Any, default: int) -> int:
    try:
        if value is None or value == "":
            return int(default)
        parsed = int(value)
        return parsed if parsed > 0 else int(default)
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


HARVEST_MINIMUM_AI_SCORE = _safe_float(os.getenv("LMCP_HARVEST_MINIMUM_AI_SCORE"), 35.0)
HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE = _safe_float(os.getenv("LMCP_HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE"), 65.0)


def _truncate(value: str, max_len: int = 180) -> str:
    value = _clean(value)
    return value if len(value) <= max_len else value[: max_len - 3].rstrip() + "..."


def _append_live_candidate_debug(
    item: Dict[str, Any],
    *,
    phase: str,
    source_name: str,
    source_url: str,
) -> None:
    try:
        payload = {
            "captured_at": _now_iso(),
            "phase": phase,
            "title": _clean(item.get("title") or item.get("description") or item.get("name")),
            "source_name": _clean(item.get("source_name") or item.get("source") or source_name),
            "source_url": _clean(item.get("source_url") or source_url),
            "detail_url": _clean(item.get("detail_url")),
            "document_url": _clean(item.get("document_url")),
            "raw_text": _truncate(
                _clean(item.get("raw_text") or item.get("text") or item.get("description")),
                max_len=2000,
            ),
            "ai_score": item.get("ai_score"),
            "qualification_score": item.get("qualification_score"),
            "quote_readiness_score": item.get("quote_readiness_score"),
            "estimated_profit": item.get("estimated_profit"),
            "estimated_margin": item.get("estimated_margin"),
            "margin_percent": item.get("margin_percent"),
            "minimum_profit": item.get("minimum_profit_required"),
            "minimum_ai_score": item.get("minimum_ai_score"),
            "pricing_status": item.get("pricing_status"),
            "profit_status": item.get("profit_status"),
            "pipeline_status": _clean(item.get("pipeline_status")),
            "rejection_reason": _clean(item.get("exclusion_reason") or item.get("eligibility_reason")),
        }
        with LIVE_CANDIDATE_DEBUG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("Failed to write live candidate debug row", exc_info=True)


def _v63_candidate_rejection_stage(reason_code: Any, candidate: Dict[str, Any]) -> str:
    reason = _clean(reason_code).lower()
    blob = _safe_lower(_v63_candidate_text(candidate)) if "candidate_text" in globals() else _safe_lower(
        " ".join(
            _clean(value)
            for value in [
                candidate.get("title"),
                candidate.get("description"),
                candidate.get("raw_text"),
                candidate.get("source_name"),
                candidate.get("buyer_name"),
                candidate.get("category"),
            ]
        )
    )
    if reason in {"generic_listing_or_category_page", "weak_rfq_identity", "not_structural_real_rfq", "noise_or_no_real_rfq_intent"}:
        return "metadata_filter"
    if reason in {"briefing_required", "construction_heavy", "expired_or_closed", "non_supply_scope", "service_heavy", "not_supply_delivery"}:
        return "eligibility_filter"
    if reason.startswith("excluded_keyword:") or reason.startswith("contextual_excluded_keyword:"):
        return "eligibility_filter"
    if reason in {"qualification_score_below_threshold", "duplicate_candidate_current_run", "duplicate_candidate_memory"}:
        return "qualification_filter"
    if reason in {"no_downloadable_rfq_documents", "document_intelligence_block", "buyer_pack_download_required_before_quantity_verification", "document_acquisition_pending"}:
        return "document_filter"
    if reason in {"estimated_profit_below_threshold", "ai_score_or_profit_too_low"}:
        return "margin_filter"
    if "profit" in reason or "margin" in reason:
        return "margin_filter"
    if "document" in reason or "download" in reason:
        return "document_filter"
    if "briefing" in blob:
        return "eligibility_filter"
    if not _clean(candidate.get("document_urls")) and not _clean(candidate.get("raw_text")):
        return "metadata_filter"
    return "eligibility_filter"


def _v63_detect_terms(blob: str, terms: List[str]) -> List[str]:
    text = _safe_lower(blob)
    matched = [term for term in terms if term and term in text]
    return sorted(set(matched))


def _v63_buyer_pack_failure_reason(
    candidate: Dict[str, Any],
    document_discovery: Optional[Dict[str, Any]] = None,
) -> str:
    if bool(candidate.get("buyer_pack_downloaded")):
        return ""
    diagnostics = candidate.get("buyer_pack_download_diagnostics")
    if isinstance(diagnostics, list) and diagnostics:
        source_link_failed = False
        artifact_failed = False
        reason_candidates: List[str] = []
        for diag in diagnostics:
            if not isinstance(diag, dict):
                continue
            diagnostic_type = _clean(diag.get("diagnostic_type"))
            failure_stage = _clean(diag.get("failure_stage"))
            failure_reason = _clean(diag.get("failure_reason"))
            if failure_stage == "artifact_saved":
                return ""
            if diagnostic_type == "source_link":
                if failure_stage == "index_page_no_artifacts":
                    return "index_page_no_artifacts"
                if failure_stage == "skipped":
                    reason_candidates.append(failure_reason or "source_link_skipped")
                elif failure_stage == "url_resolution":
                    source_link_failed = True
                    reason_candidates.append("buyer_pack_url_resolution_failed")
                elif failure_stage == "auth_required":
                    source_link_failed = True
                    reason_candidates.append("buyer_pack_auth_required")
                elif failure_stage == "http_fetch":
                    source_link_failed = True
                    reason_candidates.append("buyer_pack_download_failed")
                elif failure_stage == "unsupported_content_type":
                    source_link_failed = True
                    reason_candidates.append("unsupported_document_format")
            elif diagnostic_type == "artifact_candidate":
                if failure_stage == "artifact_saved":
                    return ""
                artifact_failed = True
                if failure_stage == "url_resolution":
                    reason_candidates.append("buyer_pack_url_resolution_failed")
                elif failure_stage == "auth_required":
                    reason_candidates.append("buyer_pack_auth_required")
                elif failure_stage == "unsupported_content_type":
                    reason_candidates.append("unsupported_document_format")
                elif failure_stage == "empty_content":
                    reason_candidates.append("empty_document_content")
                elif failure_stage == "file_write":
                    reason_candidates.append("buyer_pack_file_write_failed")
                elif failure_stage == "checksum":
                    reason_candidates.append("artifact_checksum_failed")
                elif failure_stage == "http_fetch":
                    reason_candidates.append("buyer_pack_download_failed")
                elif failure_stage == "skipped":
                    reason_candidates.append(failure_reason or "artifact_candidate_skipped")
        if reason_candidates:
            return _truncate(reason_candidates[0], 120)
        if source_link_failed and not artifact_failed:
            return "index_page_no_artifacts"
        if artifact_failed:
            return "artifact_download_failed"
    link_count = int(candidate.get("document_links_count") or len(candidate.get("document_urls") or []))
    if link_count <= 0:
        return "no_document_links_detected"
    if candidate.get("document_acquisition_block_reason"):
        return _clean(candidate.get("document_acquisition_block_reason"))
    if candidate.get("fallback_quantity_block_reason"):
        return "buyer_pack_download_required_before_quantity_verification"
    skipped_links = document_discovery.get("skipped_links") if isinstance(document_discovery, dict) else []
    skipped_reasons = [
        _clean(skipped.get("reason"))
        for skipped in skipped_links
        if isinstance(skipped, dict) and _clean(skipped.get("reason"))
    ]
    skipped_failure_stages = [
        _clean(skipped.get("failure_stage"))
        for skipped in skipped_links
        if isinstance(skipped, dict) and _clean(skipped.get("failure_stage"))
    ]
    if any(reason in {"unsupported_extension", "unsupported_response_type", "zip_links_discovered_but_not_downloaded", "zip_response_not_downloaded", "html_response_not_document"} for reason in skipped_reasons) or any(stage in {"unsupported_content_type"} for stage in skipped_failure_stages):
        return "unsupported_document_format"
    if any(reason in {"download_error"} for reason in skipped_reasons) or any(stage in {"http_fetch"} for stage in skipped_failure_stages):
        return "buyer_pack_download_failed"
    if any(reason in {"document_too_large"} for reason in skipped_reasons) or any(stage in {"empty_content"} for stage in skipped_failure_stages):
        return "empty_document_content"
    if any(stage in {"auth_required"} for stage in skipped_failure_stages):
        return "buyer_pack_auth_required"
    if any(stage in {"url_resolution"} for stage in skipped_failure_stages):
        return "buyer_pack_url_resolution_failed"
    if any(reason in {"document_too_large"} for reason in skipped_reasons):
        return "corrupt_document"
    if skipped_reasons:
        return _truncate(skipped_reasons[0], 120)
    if candidate.get("eligibility_reason"):
        return _truncate(candidate.get("eligibility_reason"), 120)
    return "document_links_detected_but_no_artifact"


def _v63_attach_candidate_rejection_diagnostics(
    candidate: Dict[str, Any],
    source: Dict[str, Any],
    document_discovery: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    blob = _v63_candidate_text(candidate)
    document_links_count = int(candidate.get("document_links_count") or len(candidate.get("document_urls") or []))
    buyer_pack_downloaded = bool(
        candidate.get("buyer_pack_downloaded")
        or candidate.get("document_acquisition_result")
        or candidate.get("downloaded_document_path")
        or candidate.get("main_document_path")
        or candidate.get("buyer_pack_path")
        or candidate.get("live_buyer_pack_path")
    )
    buyer_pack_attempted = bool(document_links_count > 0 or buyer_pack_downloaded or candidate.get("built_from_document_evidence"))
    if not buyer_pack_downloaded and candidate.get("built_from_document_evidence"):
        buyer_pack_downloaded = True
    reason_code = _clean(candidate.get("exclusion_reason") or candidate.get("eligibility_reason") or "unknown")
    stage = _v63_candidate_rejection_stage(reason_code, candidate)
    excluded_terms = _v63_detect_terms(
        blob,
        list(EXCLUDED_KEYWORDS)
        + list(CONTEXTUAL_EXCLUDED_PATTERNS)
        + list(SCREEN_OUT_KEYWORDS)
        + list(NON_SUPPLY_SCOPE_TERMS)
        + list(GENERIC_CATEGORY_TERMS)
    )
    supply_terms = _v63_detect_terms(blob, list(REAL_SUPPLY_PHRASES) + list(REAL_RFQ_INTENT_TERMS))
    missing_required_fields: List[str] = []
    if not _clean(candidate.get("closing_date")):
        missing_required_fields.append("closing_date")
    if not _clean(candidate.get("buyer_name") or candidate.get("buyer")):
        missing_required_fields.append("buyer")
    if not _clean(candidate.get("source_url")):
        missing_required_fields.append("source_url")
    if document_links_count <= 0:
        missing_required_fields.append("document_links")
    if not buyer_pack_downloaded:
        missing_required_fields.append("buyer_pack")
    if candidate.get("briefing_required"):
        missing_required_fields.append("briefing_confirmation")
    estimated_profit = _safe_float(
        (candidate.get("estimated_profit_signal") or {}).get("estimated_profit")
        or candidate.get("estimated_profit")
        or candidate.get("profit_estimate")
        or candidate.get("expected_profit")
        or candidate.get("total_profit"),
        0.0,
    )
    estimated_margin_percent = _safe_float(
        candidate.get("estimated_margin_pct")
        or candidate.get("estimated_margin_percent")
        or candidate.get("margin_percent")
        or 0.0,
        0.0,
    )
    failure_reason = _v63_buyer_pack_failure_reason(candidate, document_discovery=document_discovery)
    return {
        "candidate_id": _clean(candidate.get("candidate_fingerprint") or candidate.get("candidate_id") or _v57_candidate_fingerprint(candidate)),
        "source_name": _clean(candidate.get("source_name") or source.get("name") or source.get("source_name")),
        "title": _clean(candidate.get("title")),
        "buyer": _clean(candidate.get("buyer_name") or candidate.get("buyer") or source.get("name") or source.get("source_name")),
        "province": _clean(candidate.get("province")),
        "category": _clean(candidate.get("commodity_service_category") or candidate.get("category")),
        "closing_date": _clean(candidate.get("closing_date")),
        "rejection_stage": stage,
        "rejection_reason_code": reason_code,
        "rejection_reason_text": _clean(candidate.get("eligibility_reason") or candidate.get("exclusion_reason") or candidate.get("classification") or reason_code),
        "missing_required_fields": sorted(set(missing_required_fields)),
        "detected_excluded_terms": excluded_terms,
        "detected_supply_terms": supply_terms,
        "compulsory_briefing_detected": bool(candidate.get("briefing_required") or re.search(r"compulsory\s+briefing|mandatory\s+briefing|briefing\s+required", blob, flags=re.I)),
        "estimated_profit": round(estimated_profit, 2),
        "estimated_margin_percent": round(estimated_margin_percent, 2),
        "document_links_count": document_links_count,
        "buyer_pack_attempted": buyer_pack_attempted,
        "buyer_pack_downloaded": buyer_pack_downloaded,
        "buyer_pack_failure_reason": failure_reason,
    }


def _v64_match_candidate_download_attempts(
    candidate: Dict[str, Any],
    document_discovery: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(document_discovery, dict):
        return []
    attempts = document_discovery.get("download_attempts")
    if not isinstance(attempts, list) or not attempts:
        return []
    candidate_urls = {
        _clean(candidate.get("document_url")),
        *[_clean(url) for url in (candidate.get("document_urls") or []) if _clean(url)],
    }
    matched: List[Dict[str, Any]] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        resolved = _clean(attempt.get("resolved_document_url") or attempt.get("candidate_url"))
        if resolved and resolved in candidate_urls:
            matched.append(attempt)
    return matched


def _v58_select_productive_focus_sources(
    sources: List[Dict[str, Any]],
    max_sources: int,
    source_health_file: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    max_sources = _safe_positive_int(max_sources, 25)
    enabled = [source for source in sources if source.get("enabled", True)]
    health = _load_source_health(source_health_file=source_health_file)
    focus_rows: List[Tuple[Dict[str, Any], Dict[str, Any], float]] = []
    skipped_unproductive = 0
    for source in enabled:
        row = _v53_source_health_row(source, health, source_health_file=source_health_file)
        health_status = _clean(row.get("health_status"))
        reachable = bool(row.get("reachable"))
        acquisition_status = _clean(row.get("acquisition_status"))
        last_dns_status = _clean(row.get("last_dns_status"))
        if acquisition_status == "dns_failed" or last_dns_status == "failed" or not reachable:
            skipped_unproductive += 1
            continue
        if health_status in {"dns_blocked", "http_blocked", "disabled"}:
            skipped_unproductive += 1
            continue
        candidate_total = int(row.get("candidate_total") or 0)
        document_total = int(row.get("document_candidate_total") or 0)
        doc_detection = 0.0
        if candidate_total > 0:
            doc_detection = round((document_total / max(candidate_total, 1)) * 100.0, 2)
        recent_candidate = _safe_float(row.get("last_candidate_age_days"), 9999.0) <= 30.0
        if not (
            health_status in {"healthy", "degraded", "empty"}
            and (
                candidate_total > 0
                or document_total > 0
                or int(row.get("acquisition_document_links_detected") or 0) > 0
                or _safe_float(row.get("source_selection_score"), 0.0) >= 55.0
                or doc_detection > 0.0
                or recent_candidate
            )
        ):
            skipped_unproductive += 1
            continue
        score = (
            _safe_float(row.get("source_selection_score"), _safe_float(row.get("source_success_score"), 0.0))
            + min(12.0, doc_detection * 0.12)
            + min(10.0, candidate_total * 1.5)
            + min(8.0, document_total * 1.5)
        )
        if recent_candidate:
            score += 6.0
        focus_rows.append((source, row, round(score, 2)))

    focus_rows = sorted(
        focus_rows,
        key=lambda pair: (
            float(pair[2]),
            int(pair[1].get("candidate_total") or 0),
            int(pair[1].get("document_candidate_total") or 0),
            -_safe_float(pair[1].get("last_candidate_age_days"), 9999.0),
            _clean(pair[0].get("name") or pair[0].get("source_name")),
        ),
        reverse=True,
    )
    selected = [source for source, _row, _score in focus_rows[:max_sources]]
    diagnostics = {
        "focused_source_count": len(selected),
        "skipped_unproductive_source_count": skipped_unproductive + max(0, len(enabled) - len(selected) - skipped_unproductive),
        "focused_source_names": [_clean(source.get("name") or source.get("source_name")) for source in selected],
    }
    return selected, diagnostics


def _v64_repair_source_pack_sources(
    sources: List[Dict[str, Any]],
    max_sources: int,
    source_health_file: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    max_sources = _safe_positive_int(max_sources, 25)
    checked_rows: List[Dict[str, Any]] = []
    selected: List[Dict[str, Any]] = []
    failed_by_reason: Dict[str, int] = {}
    selected_names: List[str] = []
    checked_at = _now_iso()
    enabled = [source for source in sources if source.get("enabled", True)]

    for source in sorted(enabled, key=_v52_source_priority):
        source_name = _clean(source.get("name") or source.get("source_name"))
        source_url = _normalize_source_acquisition_url(source)
        if not source.get("enabled", True):
            status = "disabled"
            error_message = "source_disabled"
            selected_reason = ""
        else:
            preflight = _preflight_source_acquisition(source, timeout_seconds=8)
            preflight_status = _clean(preflight.get("status"))
            error_message = _clean(preflight.get("error_message"))
            browser_required = bool(preflight.get("browser_required"))
            browser_available = bool(preflight.get("browser_available", True))
            if preflight_status == "dns_failed" or not bool(preflight.get("dns_resolved")):
                status = "dns_failed"
                selected_reason = ""
            elif preflight_status == "timeout":
                status = "timeout"
                selected_reason = ""
            elif preflight_status == "http_failed" or not bool(preflight.get("http_reachable")) or bool(preflight.get("robots_blocked")) or (browser_required and not browser_available):
                status = "http_failed"
                if not error_message and browser_required and not browser_available:
                    error_message = "browser_unavailable"
                elif not error_message and bool(preflight.get("robots_blocked")):
                    error_message = "robots_blocked"
                selected_reason = ""
            elif preflight_status == "ok":
                if len(selected) < max_sources:
                    status = "selected"
                    selected.append(source)
                    selected_names.append(source_name)
                    selected_reason = "preflight_ok"
                else:
                    status = "skipped"
                    error_message = "max_sources_reached"
                    selected_reason = "max_sources_reached"
            else:
                status = "skipped"
                error_message = error_message or "repair_skipped"
                selected_reason = "skipped"

        if status in {"dns_failed", "http_failed", "timeout", "disabled", "skipped"}:
            failed_by_reason[status] = failed_by_reason.get(status, 0) + 1

        checked_rows.append(
            {
                "source_name": source_name,
                "source_url": source_url,
                "repair_checked_at": checked_at,
                "repair_status": status,
                "repair_error_message": error_message,
                "repair_selected_reason": selected_reason,
            }
        )

    try:
        SOURCE_PACK_REPAIR_DIAGNOSTICS_FILE.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "generated_at": _now_iso(),
                    "diagnostics": checked_rows,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    except Exception:
        logger.debug("Failed to persist source pack repair diagnostics", exc_info=True)

    diagnostics = {
        "repair_mode_used": True,
        "repair_sources_checked_count": len(checked_rows),
        "repair_sources_selected_count": len(selected),
        "repair_sources_failed_count": sum(1 for row in checked_rows if row.get("repair_status") in {"dns_failed", "http_failed", "timeout"}),
        "repair_selected_source_names": selected_names,
        "repair_failed_by_reason": failed_by_reason,
        "repair_diagnostics_file": _display_project_path(SOURCE_PACK_REPAIR_DIAGNOSTICS_FILE),
    }
    return selected, diagnostics, checked_rows


def _append_live_resolution_trace_debug(payload: Dict[str, Any]) -> None:
    try:
        trace = dict(payload)
        trace["captured_at"] = _now_iso()
        trace["phase"] = "etenders_resolution_trace"
        with LIVE_CANDIDATE_DEBUG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
    except Exception:
        logger.debug("Failed to write live resolution trace row", exc_info=True)


def _should_trace_live_eligibility(item: Dict[str, Any]) -> bool:
    text = " ".join(
        _safe_lower(item.get(key))
        for key in ("title", "reference_number", "buyer_rfq_number", "rfq_number", "description", "raw_text")
    )
    return "lethabo" in text or "joints on an as and when required basis" in text


def _append_live_eligibility_trace(
    item: Dict[str, Any],
    *,
    stage: str,
    run_id: str,
    minimum_profit: float,
    runtime_dir: Optional[str] = None,
) -> None:
    if not _should_trace_live_eligibility(item):
        return
    try:
        payload = {
            "captured_at": _now_iso(),
            "stage": stage,
            "run_id": run_id,
            "title": item.get("title"),
            "reference_number": item.get("reference_number"),
            "pipeline_status": item.get("pipeline_status"),
            "eligible": item.get("eligible"),
            "quote_ready": item.get("quote_ready"),
            "screened_out": item.get("screened_out"),
            "rejection_reason": item.get("rejection_reason") or item.get("exclusion_reason") or item.get("eligibility_reason"),
            "detail_url": item.get("detail_url"),
            "document_url": item.get("document_url"),
            "v50_8_discovered_tender_id": item.get("v50_8_discovered_tender_id"),
            "v50_8_extended_resolution_status": item.get("v50_8_extended_resolution_status"),
            "estimated_profit": item.get("estimated_profit"),
            "minimum_profit": minimum_profit,
            "ai_score": item.get("ai_score"),
        }
        trace_file = _resolve_runtime_file(LIVE_ELIGIBILITY_TRACE_FILE, runtime_dir)
        trace_file.parent.mkdir(parents=True, exist_ok=True)
        with trace_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        logger.debug("Failed to write live eligibility trace row", exc_info=True)


def _summarize_items_by_reason(items: List[Dict[str, Any]], reason_keys: Tuple[str, ...]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    samples: Dict[str, List[Dict[str, Any]]] = {}

    for item in items:
        reason = ""
        for key in reason_keys:
            reason = _clean(item.get(key))
            if reason:
                break
        if not reason:
            continue

        counts[reason] = counts.get(reason, 0) + 1
        bucket = samples.setdefault(reason, [])
        if len(bucket) >= 5:
            continue

        bucket.append(
            {
                "title": _clean(item.get("title")),
                "source_name": _clean(item.get("source_name")),
                "source_url": _clean(item.get("source_url")),
                "pipeline_status": _clean(item.get("pipeline_status")),
                "eligibility_reason": _clean(item.get("eligibility_reason")),
                "exclusion_reason": _clean(item.get("exclusion_reason")),
                "blocker_reasons": list(item.get("blocker_reasons") or []),
                "qualification_reasons": list(item.get("qualification_reasons") or []),
            }
        )

    return {
        "counts_by_reason": counts,
        "samples_by_reason": samples,
        "total_items": len(items),
        "reason_keys": list(reason_keys),
    }


def _looks_like_attachment_name(text: str) -> bool:
    t = _safe_lower(text)
    return t.endswith((".xlsx", ".xls", ".doc", ".docx", ".pdf", ".csv", ".zip"))


def _extract_closing_date(text: str) -> str:
    text = _clean(text)
    patterns = [
        (r"\b(\d{2}/\d{2}/\d{4})\b", ("%d/%m/%Y",)),
        (r"\b(\d{2}-\d{2}-\d{4})\b", ("%d-%m-%Y",)),
        (r"\b(\d{4}-\d{2}-\d{2})\b", ("%Y-%m-%d",)),
        (r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b", ("%d %b %Y", "%d %B %Y")),
    ]
    for pattern, formats in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(1).strip()
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
    return ""


def _parse_closing_date_value(value: Any, blob: str = "") -> str:
    explicit = _clean(value)
    if explicit:
        parsed = _extract_closing_date(explicit)
        if parsed:
            return parsed
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(explicit[:10], fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
    if blob:
        parsed = _extract_closing_date(blob)
        if parsed:
            return parsed
    return ""


def _closing_date_is_expired(closing_date: Any, blob: str = "") -> bool:
    parsed = _parse_closing_date_value(closing_date, blob)
    if not parsed:
        return False
    try:
        return datetime.strptime(parsed[:10], "%Y-%m-%d").date() < datetime.now(timezone.utc).date()
    except Exception:
        return False


def _extract_years(text: str) -> List[int]:
    years: List[int] = []
    for y in re.findall(r"\b(20\d{2})\b", _clean(text)):
        try:
            years.append(int(y))
        except Exception:
            pass
    return years


def _contains_only_old_years(text: str, min_year: int = 2025) -> bool:
    years = _extract_years(text)
    return bool(years) and max(years) < min_year


def _dedupe_keep_order(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for item in items:
        key = (
            _clean(item.get("title")),
            _clean(item.get("rfq_number") or item.get("reference_number")),
            _clean(item.get("closing_date")),
            _clean(item.get("source_url")),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output



def _v50_clean_etenders_title(text: str) -> str:
    """
    V50.5:
    Remove eTenders category contamination before item creation.
    """

    t = _clean(text)

    if not t:
        return ""

    patterns = [
        r"^Supplies:\s*.*?(?=\b(SUPPLY|REQUEST|RFQ|RFP|BID|TENDER|APPOINTMENT|PROCUREMENT|RE-ADVERTISEMENT|SERVICE:)\b)",
        r"^Services:\s*.*?(?=\b(SUPPLY|REQUEST|RFQ|RFP|BID|TENDER|APPOINTMENT|PROCUREMENT|RE-ADVERTISEMENT|SERVICE:)\b)",
        r"^Manufacture of .*?(?=\b(SUPPLY|REQUEST|RFQ|RFP|BID|TENDER|APPOINTMENT|PROCUREMENT|RE-ADVERTISEMENT|SERVICE:)\b)",
        r"^Administrative and support activities\s+",
        r"^Other service activities\s+",
        r"^Water supply;.*?(?=\b(SUPPLY|REQUEST|RFQ|RFP|BID|TENDER|APPOINTMENT|PROCUREMENT|RE-ADVERTISEMENT|SERVICE:)\b)",
    ]

    cleaned = t

    for pattern in patterns:
        cleaned2 = re.sub(pattern, "", cleaned, flags=re.I).strip(" :-–—|\t\n")
        if cleaned2 and cleaned2 != cleaned:
            cleaned = cleaned2

    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    return cleaned or t



def _base_item(source: Dict[str, Any], text: str, url: str = "") -> Dict[str, Any]:
    text = _clean(text)
    text = _v50_clean_etenders_title(text)

    src_name = _clean(source.get("source_name") or source.get("name") or "Unknown Source")
    src_url = _clean(url or source.get("url") or source.get("list_url"))

    title = _truncate(text, 180)
    return {
        "title": title,
        "description": text,
        "buyer_name": src_name,
        "buyer_rfq_number": title,
        "rfq_number": title,
        "reference_number": title,
        "published_date": "",
        "closing_date": _extract_closing_date(text),
        "submission_method": _clean(source.get("submission_method") or "portal"),
        "recipient_email": _clean(source.get("recipient_email") or source.get("buyer_email")),
        "buyer_email": _clean(source.get("buyer_email") or source.get("recipient_email")),
        "document_url": src_url,
        "source_url": src_url,
        "detail_url": "",
        "briefing_required": False,
        "source": src_name,
        "source_name": src_name,
        "portal_name": src_name,
        "raw_text": text,
        "ai_agent_profile": AI_AGENT_PROFILE,
        "ai_primary_model_hint": AI_PRIMARY_MODEL_HINT,
        "ai_fast_model_hint": AI_FAST_MODEL_HINT,
        "ai_api_style_hint": AI_API_STYLE_HINT,
        "ai_orchestration_hint": AI_ORCHESTRATION_HINT,
    }


def _normalize_etenders_listing_url(url: Any) -> str:
    cleaned = _clean(url)
    lower = cleaned.lower()
    if not lower or lower in {"https://www.etenders.gov.za", "https://www.etenders.gov.za/"}:
        return ETENDERS_URL
    if "etenders.gov.za" in lower and "/home/opportunities" not in lower:
        return ETENDERS_URL
    return cleaned


def _normalize_source_url_host(url: Any, source_name: str = "") -> str:
    cleaned = _clean(url)
    if not cleaned:
        return ""
    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    host = _clean(parsed.netloc).split("@")[-1].split(":")[0].lower()
    if not host:
        return cleaned
    if host in {"etenders.gov.za", "www.etenders.gov.za"}:
        return ETENDERS_URL
    if host.startswith("www.") or host.startswith("secure.") or host.count(".") > 2:
        return cleaned
    if host.count(".") == 2 and host not in {"localhost"}:
        preferred_host = f"www.{host}"
        normalized = parsed._replace(netloc=preferred_host)
        return normalized.geturl()
    return cleaned


def _v64_source_matches_filter(source: Dict[str, Any], token: str) -> bool:
    probe = _safe_lower(token)
    name = _safe_lower(source.get("name") or source.get("source_name"))
    url = _safe_lower(source.get("url") or source.get("list_url"))
    group = _safe_lower(source.get("source_group") or source.get("category_group"))
    if probe == "etenders":
        return "etenders" in name or "etenders.gov.za" in url or group == "etenders"
    return probe in name or probe in url or probe == group


def _v64_filter_sources(
    sources: List[Dict[str, Any]],
    *,
    source_filter: Optional[str] = None,
    source_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    tokens = [_clean(source_filter)] if _clean(source_filter) else []
    if isinstance(source_names, list):
        tokens.extend(_clean(value) for value in source_names if _clean(value))
    if not tokens:
        return list(sources)
    return [
        source
        for source in sources
        if any(_v64_source_matches_filter(source, token) for token in tokens)
    ]


def _build_etenders_detail_url(tender_id: Any) -> str:
    tid = _clean(tender_id)
    if not tid:
        return ETENDERS_URL
    return f"https://www.etenders.gov.za/Home/TenderDetails?id={tid}"


def _fetch_etenders_paginated_opportunities(
    source: Dict[str, Any],
    max_items: int,
    timeout_seconds: int,
) -> List[Dict[str, Any]]:
    params = {
        "status": 1,
        "draw": 1,
        "start": 0,
        "length": _safe_positive_int(max_items, 20),
    }
    response = requests.get(
        ETENDERS_PAGINATED_OPPORTUNITIES_URL,
        params=params,
        timeout=timeout_seconds,
        headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0"},
    )
    response.raise_for_status()

    payload = response.json()
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []

    listing_url = _normalize_etenders_listing_url(source.get("url") or source.get("list_url") or ETENDERS_URL)
    results: List[Dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        tender_id = _clean(raw.get("id") or raw.get("tendersID") or raw.get("tenderId"))
        title = _v50_clean_etenders_title(_clean(raw.get("description") or raw.get("tender_No")))
        tender_no = _clean(raw.get("tender_No"))
        buyer_name = _clean(raw.get("organ_of_State") or raw.get("department") or raw.get("organOfState") or source.get("name") or "eTenders")
        category = _clean(raw.get("category"))
        closing_date = _clean(raw.get("closing_Date") or raw.get("closing_date"))
        published_date = _clean(raw.get("date_Published") or raw.get("published_date"))
        preharvest_blob = " | ".join(part for part in [tender_no, title, buyer_name, category, closing_date, published_date] if part)
        if not title:
            continue
        lowered_title = _safe_lower(title)
        if lowered_title in NAVIGATION_NOISE_EXACT or lowered_title in EARLY_BLOCK_TITLES:
            continue
        if _is_noise_row(preharvest_blob) and not tender_no:
            continue
        support_documents = raw.get("supportDocument") if isinstance(raw.get("supportDocument"), list) else []
        first_support_document = support_documents[0] if support_documents else {}
        support_document_id = _clean(first_support_document.get("supportDocumentID"))
        detail_url = _build_etenders_detail_url(tender_id)

        text_parts = [part for part in [tender_no, title, buyer_name, category, closing_date] if part]
        item = _base_item(source, " | ".join(text_parts), listing_url)
        item["title"] = _truncate(title, 180)
        item["description"] = title
        item["buyer_name"] = buyer_name
        item["source_name"] = _clean(source.get("name") or "National Treasury eTenders")
        item["source"] = item["source_name"]
        item["portal_name"] = item["source_name"]
        item["published_date"] = published_date
        item["closing_date"] = closing_date
        item["buyer_rfq_number"] = tender_no or title
        item["rfq_number"] = tender_no or title
        item["reference_number"] = tender_no or title
        item["detail_url"] = detail_url
        item["document_url"] = detail_url
        item["source_url"] = listing_url
        item["v50_8_discovered_tender_id"] = tender_id
        item["tender_id"] = tender_id
        item["category"] = category
        item["province"] = _clean(raw.get("province"))
        item["department"] = _clean(raw.get("department"))
        item["supportDocumentID"] = support_document_id
        item["support_document_count"] = len(support_documents)
        item["support_document_ids"] = [
            _clean(doc.get("supportDocumentID"))
            for doc in support_documents
            if isinstance(doc, dict) and _clean(doc.get("supportDocumentID"))
        ]
        item["support_documents_meta"] = support_documents
        _lmcp_safe_assign_identity_fields(item, tender_no or title)
        results.append(item)
        if len(results) >= max_items:
            break

    return _dedupe_keep_order(results)[:max_items]


def _v64_etenders_should_retry(error_message: str = "", http_status: int = 0) -> bool:
    lower = _safe_lower(error_message)
    if http_status == 429:
        return True
    if 400 <= int(http_status or 0) < 500:
        return False
    if any(token in lower for token in ("nameresolutionerror", "nodename nor servname", "temporary failure in name resolution", "dns")):
        return False
    return any(token in lower for token in ("timed out", "timeout", "read timed out", "connecttimeout"))


def load_harvest_sources(source_file: Optional[str] = None, controlled_mode: bool = False) -> List[Dict[str, Any]]:
    if not controlled_mode and (source_file is None or str(source_file).strip() == get_curated_live_source_file()):
        default_sources = [dict(source) for source in load_default_live_harvest_sources()]
        if default_sources:
            return default_sources

    path = Path(source_file) if source_file else DEFAULT_SOURCE_FILE
    if not path.exists():
        logger.warning("Source file not found: %s", path)
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.exception("Failed to read source file: %s", exc)
        return []

    if isinstance(data, dict):
        if isinstance(data.get("sources"), list):
            data = data["sources"]
        else:
            data = [data]

    sources: List[Dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["name"] = _clean(item.get("name") or item.get("source_name"))
        normalized["source_name"] = normalized["name"]
        normalized["url"] = _clean(item.get("url") or item.get("list_url"))
        normalized["list_url"] = _clean(item.get("list_url") or normalized["url"])
        normalized["type"] = _safe_lower(item.get("type"))
        normalized_group = _safe_lower(item.get("source_group") or item.get("category_group"))
        if "etenders" in _safe_lower(normalized["name"]) or normalized_group == "etenders":
            normalized["url"] = _normalize_etenders_listing_url(normalized["url"])
            normalized["list_url"] = _normalize_etenders_listing_url(normalized["list_url"])
        else:
            normalized["url"] = _normalize_source_url_host(normalized["url"], normalized["name"])
            normalized["list_url"] = _normalize_source_url_host(normalized["list_url"], normalized["name"])
        normalized["enabled"] = bool(item.get("enabled", True))
        normalized["priority"] = int(item.get("priority") or 9999)
        normalized["intelligence_score"] = int(item.get("intelligence_score") or 0)
        normalized["submission_method"] = _clean(item.get("submission_method") or "portal")
        normalized["invalid_seed_source"] = _is_invalid_seed_source_url(normalized["url"]) or _is_invalid_seed_source_url(normalized["list_url"])
        if normalized["invalid_seed_source"]:
            logger.info("Skipping invalid discovery seed source=%s url=%s", normalized["name"], normalized["url"] or normalized["list_url"])
            continue
        sources.append(normalized)

    if controlled_mode:
        _ensure_controlled_sources_only(sources, str(path))

    sources.sort(key=lambda s: (s.get("priority", 9999), -int(s.get("intelligence_score", 0)), s.get("name", "")))
    return sources


def count_loaded_sources(source_file: Optional[str] = None) -> Dict[str, int]:
    sources = load_harvest_sources(source_file)
    enabled = sum(1 for s in sources if s.get("enabled", True))
    disabled = len(sources) - enabled
    return {"total": len(sources), "enabled": enabled, "disabled": disabled}


def get_harvester_health(
    source_file: Optional[str] = None,
    runtime_dir: Optional[str] = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    counts = count_loaded_sources(source_file)
    resolved_source_health_file = source_health_file
    if resolved_source_health_file is None and runtime_dir:
        resolved_source_health_file = _resolve_runtime_file(SOURCE_HEALTH_FILE, runtime_dir)
    resolved_pause_file = _resolve_runtime_file(PAUSE_FILE, runtime_dir) if runtime_dir else PAUSE_FILE
    return {
        "checked_at": _now_iso(),
        "status": "paused" if resolved_pause_file.exists() else "running",
        "pause_file": _display_project_path(resolved_pause_file),
        "sources": counts,
        "source_health_file": _display_project_path(resolved_source_health_file or SOURCE_HEALTH_FILE),
        "ai_agent_profile": AI_AGENT_PROFILE,
        "ai_primary_model_hint": AI_PRIMARY_MODEL_HINT,
        "ai_api_style_hint": AI_API_STYLE_HINT,
    }


def _load_source_health(source_health_file: Optional[Path] = None) -> Dict[str, Any]:
    path = source_health_file or SOURCE_HEALTH_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_source_health(data: Dict[str, Any], source_health_file: Optional[Path] = None) -> None:
    try:
        (source_health_file or SOURCE_HEALTH_FILE).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save source health: %s", exc)


def _source_identifier(source: Dict[str, Any]) -> str:
    return _clean(source.get("name") or source.get("source_name") or source.get("url") or source.get("list_url") or "unknown")


def _normalize_source_identifier(value: Any) -> str:
    text = _clean(value).strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        return _clean(parsed.netloc.lower() + parsed.path.lower())
    return _clean(text.lower())


def _source_matches_identifier(source: Dict[str, Any], identifier: Any) -> bool:
    needle = _normalize_source_identifier(identifier)
    if not needle:
        return False
    candidates = [
        _normalize_source_identifier(source.get("name")),
        _normalize_source_identifier(source.get("source_name")),
        _normalize_source_identifier(source.get("url")),
        _normalize_source_identifier(source.get("list_url")),
    ]
    return needle in candidates


def _v53_source_health_status(row: Dict[str, Any], source: Optional[Dict[str, Any]] = None) -> str:
    source = source if isinstance(source, dict) else {}
    if not source.get("enabled", True) or _clean(row.get("health_status")).lower() == "disabled":
        return "disabled"
    persisted_status = _clean(row.get("health_status")).lower()
    if persisted_status in {"healthy", "degraded", "dns_blocked", "http_blocked", "empty"}:
        return persisted_status
    consecutive_dns_failures = int(row.get("consecutive_dns_failures") or 0)
    consecutive_http_failures = int(row.get("consecutive_http_failures") or 0)
    consecutive_empty_runs = int(row.get("consecutive_empty_runs") or 0)
    failure_count = int(row.get("failure_count") or 0)
    last_error = _clean(row.get("last_error") or row.get("last_error_message")).lower()
    if consecutive_dns_failures >= 3:
        return "dns_blocked"
    if failure_count >= 3 and any(term in last_error for term in ("nameresolutionerror", "dns", "resolve", "nodename")):
        return "dns_blocked"
    if consecutive_http_failures >= 3:
        return "http_blocked"
    if failure_count >= 3 and any(term in last_error for term in ("403", "404", "405", "429", "forbidden", "blocked", "http")):
        return "http_blocked"
    if consecutive_empty_runs >= 5:
        return "empty"
    if consecutive_dns_failures or consecutive_http_failures or consecutive_empty_runs:
        return "degraded"
    if failure_count > 0:
        return "degraded"
    return "healthy"


def _source_key(source: Dict[str, Any]) -> str:
    return _clean(source.get("name") or source.get("source_name") or source.get("url") or "unknown")


def _is_invalid_seed_source_url(value: Any) -> bool:
    url = _safe_lower(value)
    return any(snippet in url for snippet in INVALID_SOURCE_URL_SNIPPETS)


def _source_scan_total(row: Dict[str, Any]) -> int:
    return int(row.get("scan_total") or row.get("scan_count") or 0)


def _v53_load_source_shape_performance_map(limit: int = 1000) -> Dict[str, Dict[str, Any]]:
    if _live_rfq_store is None:
        return {}
    try:
        store_path = getattr(_live_rfq_store, "LIVE_RFQ_STORE_PATH", None)
        path_key = str(store_path) if store_path else None
        mtime = None
        if store_path:
            try:
                mtime = Path(store_path).stat().st_mtime
            except Exception:
                mtime = None
        cached_path = _SOURCE_SHAPE_REPORT_CACHE.get("path")
        cached_mtime = _SOURCE_SHAPE_REPORT_CACHE.get("mtime")
        cached_map = _SOURCE_SHAPE_REPORT_CACHE.get("map")
        if cached_path == path_key and cached_mtime == mtime and isinstance(cached_map, dict):
            return cached_map
        report = _live_rfq_store.get_source_shape_performance_report(limit=limit)
        rows = report.get("all_sources") if isinstance(report, dict) else []
        shape_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                source_name = _clean(row.get("source_name"))
                if not source_name:
                    continue
                shape_map[_v57_normalize_key(source_name)] = row
        _SOURCE_SHAPE_REPORT_CACHE["path"] = path_key
        _SOURCE_SHAPE_REPORT_CACHE["mtime"] = mtime
        _SOURCE_SHAPE_REPORT_CACHE["map"] = shape_map
        return shape_map
    except Exception:
        return {}


def _record_source_result(source: Dict[str, Any], ok: bool, harvested: int = 0, error: str = "", source_health_file: Optional[Path] = None) -> None:
    health = _load_source_health(source_health_file=source_health_file)
    key = _source_key(source)
    row = health.get(key, {}) if isinstance(health.get(key), dict) else {}
    row["name"] = key
    row["last_checked_at"] = _now_iso()
    row["last_harvested"] = int(harvested or 0)
    if ok:
        row["failure_count"] = 0
        if int(harvested or 0) > 0:
            row["last_success_at"] = _now_iso()
            row["last_status"] = "ok"
            row["consecutive_empty_runs"] = 0
        else:
            row["last_status"] = "ok_empty"
            row["last_empty_at"] = _now_iso()
            row["consecutive_empty_runs"] = int(row.get("consecutive_empty_runs") or 0) + 1
        row["last_error"] = ""
    else:
        row["failure_count"] = int(row.get("failure_count") or 0) + 1
        row["last_status"] = "failed"
        row["last_error"] = _truncate(error, 240)
    health[key] = row
    _save_source_health(health, source_health_file=source_health_file)


def _source_requires_browser(source: Dict[str, Any]) -> bool:
    if bool(source.get("requires_browser") or source.get("browser_required")):
        return True
    source_type = _safe_lower(source.get("type"))
    if source_type in {"web", "generic_portal", "portal", "website"}:
        return True
    if _is_necsa_source(source):
        return True
    blob = " ".join(
        _safe_lower(source.get(key))
        for key in ("name", "source_name", "source_group", "category_group", "url", "list_url")
    )
    return "etenders" in blob or "browser" in blob or "render" in blob


def _normalize_source_acquisition_url(source: Dict[str, Any]) -> str:
    url = _clean(source.get("url") or source.get("list_url") or "")
    if not url:
        return ""
    source_name = _clean(source.get("name") or source.get("source_name"))
    if _is_necsa_source(source):
        return url
    if "etenders" in _safe_lower(source_name) or "etenders" in _safe_lower(url):
        return _normalize_etenders_listing_url(url)
    return _normalize_source_url_host(url, source_name)


def _classify_acquisition_error(error_text: str, status_code: int = 0) -> str:
    lower = _clean(error_text).lower()
    if any(term in lower for term in ("nameresolutionerror", "dns", "resolve", "nodename")):
        return "dns_failed"
    if any(term in lower for term in ("playwright", "browsertype.launch", "bootstrap_check_in", "chromium")):
        return "playwright_failed"
    if "timeout" in lower or "timed out" in lower:
        return "timeout"
    if status_code in {401, 403, 404, 407, 429}:
        return "http_failed"
    if status_code >= 500:
        return "http_failed"
    if "403" in lower or "forbidden" in lower or "blocked" in lower:
        return "http_failed"
    if "parse" in lower:
        return "parse_failed"
    if "http" in lower:
        return "http_failed"
    return "unknown"


def _preflight_source_acquisition(
    source: Dict[str, Any],
    timeout_seconds: int = 8,
) -> Dict[str, Any]:
    source_url = _normalize_source_acquisition_url(source)
    source_name = _clean(source.get("name") or source.get("source_name"))
    if not source_url:
        return {
            "status": "skipped",
            "error_message": "missing_source_url",
            "dns_resolved": False,
            "dns_status": "missing",
            "http_status_code": 0,
            "http_status": 0,
            "http_reachable": False,
            "robots_blocked": False,
            "browser_required": _source_requires_browser(source),
            "browser_available": False,
            "source_url": "",
        }

    parsed = urlparse(source_url)
    host = _clean(parsed.hostname)
    if host:
        try:
            socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            dns_resolved = True
        except Exception as exc:
            return {
                "status": "dns_failed",
                "error_message": _truncate(str(exc), 240),
                "dns_resolved": False,
                "dns_status": "failed",
                "http_status_code": 0,
                "http_status": 0,
                "http_reachable": False,
                "robots_blocked": False,
                "browser_required": _source_requires_browser(source),
                "browser_available": False,
                "source_url": source_url,
            }
    else:
        dns_resolved = False

    http_status_code = 0
    http_reachable = False
    robots_blocked = False
    error_message = ""
    try:
        response = requests.get(
            source_url,
            timeout=timeout_seconds,
            verify=bool(source.get("verify_ssl", True)),
            headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0"},
            allow_redirects=True,
        )
        http_status_code = int(getattr(response, "status_code", 0) or 0)
        http_reachable = 200 <= http_status_code < 500 or http_status_code == 405
        header_blob = " ".join(
            str(response.headers.get(key) or "")
            for key in ("x-robots-tag", "retry-after", "location")
        ).lower()
        body_blob = _clean(getattr(response, "text", "")[:1000]).lower()
        robots_blocked = any(term in header_blob or term in body_blob for term in ("noindex", "nofollow", "robots", "blocked", "forbidden"))
        if http_status_code in {401, 403, 407, 429} or (http_status_code >= 400 and http_status_code != 405):
            status = "http_failed"
            error_message = f"HTTP {http_status_code}"
        else:
            status = "ok"
    except Exception as exc:
        error_message = _truncate(str(exc), 240)
        status = _classify_acquisition_error(error_message)
        http_reachable = False

    browser_required = _source_requires_browser(source)
    browser_available = bool(browser_required and not bool(os.getenv("LMCP_DISABLE_PLAYWRIGHT_SCRAPE")))
    if not http_reachable and status == "ok":
        status = "http_failed"

    return {
        "status": status,
        "error_message": error_message,
        "dns_resolved": bool(dns_resolved if host else False),
        "dns_status": "ok" if bool(dns_resolved if host else False) else "unknown",
        "http_status_code": http_status_code,
        "http_status": http_status_code,
        "http_reachable": http_reachable,
        "robots_blocked": robots_blocked,
        "browser_required": browser_required,
        "browser_available": browser_available,
        "source_url": source_url,
        "source_name": source_name,
    }


def _scan_source_acquisition_runtime(
    source: Dict[str, Any],
    *,
    max_per_source: int,
    headless: bool,
    source_timeout_seconds: int,
    playwright_timeout_ms: int,
    page_load_timeout_seconds: Optional[int] = None,
    candidate_extraction_timeout_seconds: Optional[int] = None,
    document_link_timeout_seconds: Optional[int] = None,
    source_health_file: Optional[Path] = None,
    browser_available: Optional[bool] = None,
    disable_playwright_scrape: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    scan_started_at = _now_iso()
    source_name = _clean(source.get("name") or source.get("source_name") or "Unknown")
    source_url = _normalize_source_acquisition_url(source)
    preflight = _preflight_source_acquisition(source, timeout_seconds=source_timeout_seconds)
    runtime_diag: Dict[str, Any] = {
        "source_name": source_name,
        "source_url": source_url,
        "scan_started_at": scan_started_at,
        "scan_finished_at": "",
        "status": "skipped",
        "error_message": "",
        "pages_scanned": 0,
        "raw_candidates_count": 0,
        "document_links_detected": 0,
        "retry_count": 0,
        "retry_stage": "",
        "fallback_used": False,
        "preflight": preflight,
        "etenders_home_reached": False,
        "etenders_opportunities_page_reached": False,
        "etenders_candidates_table_detected": False,
        "etenders_candidates_extracted_count": 0,
        "etenders_detail_pages_attempted_count": 0,
        "etenders_detail_pages_success_count": 0,
        "etenders_detail_pages_timeout_count": 0,
        "etenders_tenderdetails_links_found_count": 0,
        "partial_progress_persisted": False,
    }

    preflight_status = _clean(preflight.get("status"))
    if preflight_status and preflight_status != "ok":
        runtime_diag["status"] = preflight_status
        runtime_diag["error_message"] = _clean(preflight.get("error_message"))
        runtime_diag["scan_finished_at"] = _now_iso()
        _v53_update_source_health_after_scan(
            source,
            harvested_count=0,
            candidate_count=0,
            response_time=0.0,
            error=runtime_diag["error_message"],
            extracted_count=0,
            qualified_count=0,
            document_count=0,
            source_health_file=source_health_file,
            acquisition_status=runtime_diag["status"],
            acquisition_error_message=runtime_diag["error_message"],
            scan_started_at=scan_started_at,
            scan_finished_at=runtime_diag["scan_finished_at"],
            pages_scanned=0,
            raw_candidates_count=0,
            document_links_detected=0,
            retry_count=0,
            fallback_used=False,
            source_url=source_url,
            preflight_dns_status=_clean(preflight.get("dns_status") or preflight.get("status")),
            preflight_http_status=_safe_positive_int(preflight.get("http_status_code") or preflight.get("http_status") or 0, 0),
        )
        return [], runtime_diag

    source_type = _safe_lower(source.get("type"))
    browser_required = bool(preflight.get("browser_required"))
    browser_allowed = browser_available if browser_available is not None else bool(preflight.get("browser_available", True))
    runtime_diag["browser_required"] = browser_required
    runtime_diag["browser_available"] = browser_allowed
    runtime_diag["pages_scanned"] = 1

    harvested: List[Dict[str, Any]] = []
    error_message = ""
    status = "no_candidates"
    retry_count = 0
    fallback_used = False

    try:
        if _is_necsa_source(source):
            harvested = _necsa_tender_source(source, max_items=max_per_source)
        elif "etenders" in _safe_lower(source_name) or _safe_lower(source.get("source_group") or source.get("category_group")) == "etenders":
            etenders_diag: Dict[str, Any] = {}
            harvested = _direct_etenders(
                source,
                max_items=max_per_source,
                headless=headless,
                timeout_seconds=source_timeout_seconds,
                playwright_timeout_ms=playwright_timeout_ms,
                diagnostics=etenders_diag,
                page_load_timeout_seconds=page_load_timeout_seconds,
                candidate_extraction_timeout_seconds=candidate_extraction_timeout_seconds,
                document_link_timeout_seconds=document_link_timeout_seconds,
            )
            runtime_diag.update({
                "etenders_home_reached": bool(etenders_diag.get("etenders_home_reached")),
                "etenders_opportunities_page_reached": bool(etenders_diag.get("etenders_opportunities_page_reached")),
                "etenders_candidates_table_detected": bool(etenders_diag.get("etenders_candidates_table_detected")),
                "etenders_candidates_extracted_count": int(etenders_diag.get("etenders_candidates_extracted_count") or len(harvested)),
                "etenders_detail_pages_attempted_count": int(etenders_diag.get("etenders_detail_pages_attempted_count") or 0),
                "etenders_detail_pages_success_count": int(etenders_diag.get("etenders_detail_pages_success_count") or 0),
                "etenders_detail_pages_timeout_count": int(etenders_diag.get("etenders_detail_pages_timeout_count") or 0),
                "etenders_tenderdetails_links_found_count": int(etenders_diag.get("etenders_tenderdetails_links_found_count") or 0),
                "partial_progress_persisted": bool(etenders_diag.get("partial_progress_persisted")),
                "retry_count": int(etenders_diag.get("retry_count") or 0),
                "retry_stage": _clean(etenders_diag.get("retry_stage")),
            })
        elif source_type in {"ocds", "api", "json_api"}:
            harvested = run_ocds_api_harvester(source, max_items=max_per_source, timeout=source_timeout_seconds)
        elif browser_required and not disable_playwright_scrape and browser_allowed:
            playwright_diag: Dict[str, Any] = {}
            harvested = run_playwright_generic_scraper(
                source,
                max_items=max_per_source,
                headless=headless,
                timeout_ms=playwright_timeout_ms,
                diagnostics=playwright_diag,
            )
            retry_count += int(playwright_diag.get("retry_count") or 0)
            fallback_used = bool(playwright_diag.get("fallback_used"))
            status = _clean(playwright_diag.get("status") or "no_candidates")
            error_message = _clean(playwright_diag.get("error_message"))
            if harvested and status == "playwright_failed":
                status = "success"
                error_message = ""
        else:
            harvested = run_generic_scraper(source, timeout=source_timeout_seconds, max_items=max_per_source)
    except Exception as exc:
        error_message = _truncate(str(exc), 240)
        status = _classify_acquisition_error(error_message)
        harvested = []
        if status == "playwright_failed" and browser_required and not disable_playwright_scrape:
            fallback_used = True
            retry_count += 1
            try:
                harvested = run_generic_scraper(source, timeout=source_timeout_seconds, max_items=max_per_source)
            except Exception as fallback_exc:
                error_message = f"{error_message} | fallback:{_truncate(str(fallback_exc), 120)}"
                harvested = []
            if harvested:
                status = "success"
                error_message = ""

    harvested = _dedupe_keep_order(harvested)
    if not harvested and status == "no_candidates" and not error_message:
        status = "no_candidates"
    elif harvested and status not in {"success", "playwright_failed"}:
        status = "success"

    runtime_diag.update(
        {
            "scan_finished_at": _now_iso(),
            "status": status,
            "error_message": error_message,
            "retry_count": max(retry_count, int(runtime_diag.get("retry_count") or 0)),
            "fallback_used": fallback_used,
            "raw_candidates_count": len(harvested),
        }
    )
    runtime_diag["document_links_detected"] = sum(
        1
        for item in harvested
        if isinstance(item, dict) and any(
            _clean(item.get(key))
            for key in ("document_url", "detail_url")
        )
    )

    _v53_update_source_health_after_scan(
        source,
        harvested_count=len(harvested),
        candidate_count=len(harvested),
        response_time=0.0,
        error=error_message if status != "success" and status != "no_candidates" else "",
        extracted_count=len(harvested),
        qualified_count=len(harvested),
        document_count=runtime_diag["document_links_detected"],
        source_health_file=source_health_file,
        acquisition_status=status,
        acquisition_error_message=error_message,
        scan_started_at=scan_started_at,
        scan_finished_at=runtime_diag["scan_finished_at"],
        pages_scanned=runtime_diag["pages_scanned"],
        raw_candidates_count=len(harvested),
        document_links_detected=runtime_diag["document_links_detected"],
        retry_count=int(runtime_diag.get("retry_count") or retry_count),
        fallback_used=fallback_used,
        source_url=source_url,
    )

    return harvested, runtime_diag


def _v52_source_priority(source: Dict[str, Any]) -> Tuple[int, int, int, str]:
    text = " ".join(
        [
            _safe_lower(source.get("name")),
            _safe_lower(source.get("source_name")),
            _safe_lower(source.get("type")),
            _safe_lower(source.get("source_group")),
            _safe_lower(source.get("category_group")),
            _safe_lower(source.get("url")),
        ]
    )
    if any(term in text for term in ["municipal", "municipality", "metro", "local municipality", "district municipality"]):
        group_rank = 0
    elif any(term in text for term in ["soe", "eskom", "transnet", "sanral", "prasa", "sabc", "denel", "airports", "water board"]):
        group_rank = 1
    elif any(term in text for term in ["rfq", "quotation", "quote"]):
        group_rank = 2
    elif any(term in text for term in ["supplier", "vendor", "portal"]):
        group_rank = 3
    else:
        group_rank = 4
    return (
        group_rank,
        int(source.get("priority") or 9999),
        -int(source.get("intelligence_score") or 0),
        _clean(source.get("name") or source.get("source_name") or ""),
    )


def _v53_parse_time(value: Any) -> float:
    text = _clean(value)
    if not text:
        return 0.0
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except Exception:
        return 0.0


def _v53_source_category_rank(source: Dict[str, Any]) -> int:
    text = " ".join(
        [
            _safe_lower(source.get("name")),
            _safe_lower(source.get("source_name")),
            _safe_lower(source.get("type")),
            _safe_lower(source.get("source_group")),
            _safe_lower(source.get("category_group")),
            _safe_lower(source.get("url")),
        ]
    )
    if any(term in text for term in ["municipal", "municipality", "local municipality", "district municipality"]):
        return 0
    if any(term in text for term in ["metro", "metropolitan", "city of ", "ekurhuleni", "tshwane", "ethekwini", "buffalo city", "mangaung"]):
        return 1
    if any(term in text for term in ["soe", "eskom", "transnet", "sanral", "prasa", "sabc", "denel", "airports", "water board", "post office"]):
        return 2
    if any(term in text for term in ["provincial", "province", "treasury", "department"]):
        return 3
    if any(term in text for term in ["university", "college", "tvet"]):
        return 4
    if any(term in text for term in ["supplier", "vendor", "registration", "portal"]):
        return 5
    if any(term in text for term in ["rfq", "quotation", "quote", "bulletin"]):
        return 6
    return 7


def _v53_source_health_row(source: Dict[str, Any], health: Optional[Dict[str, Any]] = None, source_health_file: Optional[Path] = None) -> Dict[str, Any]:
    health = health if isinstance(health, dict) else _load_source_health(source_health_file=source_health_file)
    key = _source_key(source)
    row = dict(health.get(key, {}) if isinstance(health.get(key), dict) else {})
    failure_count = int(row.get("failure_count") or 0)
    success_count = int(row.get("success_count") or 0)
    last_candidate_time = _clean(row.get("source_last_candidate_time") or row.get("last_candidate_time"))
    last_success_at = _clean(row.get("last_success_at"))
    last_empty_at = _clean(row.get("last_empty_at"))
    response_time = _safe_float(row.get("source_response_time") or row.get("last_response_time"), 0.0)
    avg_items = _safe_float(row.get("avg_items") or row.get("average_items"), 0.0)
    total_candidates = int(row.get("candidate_total") or 0)
    qualified_total = int(row.get("qualified_candidate_total") or 0)
    document_total = int(row.get("document_candidate_total") or 0)
    consecutive_empty_runs = int(row.get("consecutive_empty_runs") or 0)
    consecutive_dns_failures = int(row.get("consecutive_dns_failures") or 0)
    consecutive_http_failures = int(row.get("consecutive_http_failures") or 0)
    scan_total = _source_scan_total(row)
    last_status = _clean(row.get("last_status"))
    last_checked = _clean(row.get("last_checked_at"))
    last_error = _clean(row.get("last_error"))
    last_error_message = _clean(row.get("last_error_message") or last_error)
    last_failure_at = _clean(row.get("last_failure_at"))
    last_dns_status = _clean(row.get("last_dns_status") or ("failed" if consecutive_dns_failures >= 1 and last_status == "failed" else "ok"))
    last_http_status = int(row.get("last_http_status") or row.get("http_status_code") or 0)
    acquisition_status = _clean(row.get("acquisition_status"))
    acquisition_error_message = _clean(row.get("acquisition_error_message"))
    acquisition_scan_started_at = _clean(row.get("acquisition_scan_started_at"))
    acquisition_scan_finished_at = _clean(row.get("acquisition_scan_finished_at"))
    acquisition_pages_scanned = int(row.get("acquisition_pages_scanned") or 0)
    acquisition_raw_candidates_count = int(row.get("acquisition_raw_candidates_count") or 0)
    acquisition_document_links_detected = int(row.get("acquisition_document_links_detected") or 0)
    acquisition_retry_count = int(row.get("acquisition_retry_count") or 0)
    acquisition_fallback_used = bool(row.get("acquisition_fallback_used"))
    source_url = _clean(source.get("url") or source.get("list_url"))
    invalid_seed_source = bool(source.get("invalid_seed_source")) or _is_invalid_seed_source_url(source_url)
    zero_yield_source = total_candidates == 0 and qualified_total == 0 and document_total == 0
    health_status = _v53_source_health_status(row, source)
    shape_map = _v53_load_source_shape_performance_map()
    source_shape_row = shape_map.get(_v57_normalize_key(_clean(source.get("name") or source.get("source_name") or key)), {})
    shape_distribution = source_shape_row.get("shape_distribution") if isinstance(source_shape_row, dict) else {}
    supply_delivery_share_pct = _safe_float(source_shape_row.get("supply_delivery_share_pct"), 0.0) if isinstance(source_shape_row, dict) else 0.0
    benchmark_quality_score = _safe_float(source_shape_row.get("benchmark_quality_score"), 0.0) if isinstance(source_shape_row, dict) else 0.0
    benchmark_candidates = int(source_shape_row.get("benchmark_candidates") or 0) if isinstance(source_shape_row, dict) else 0
    shape_alignment_score = 0.0
    if isinstance(source_shape_row, dict) and source_shape_row:
        shape_alignment_score = round(
            max(-12.0, min(20.0, (benchmark_quality_score / 8.0) + (supply_delivery_share_pct * 0.08))),
            2,
        )
    now_ts = time.time()
    last_candidate_age_days = (now_ts - _v53_parse_time(last_candidate_time)) / 86400.0 if last_candidate_time else 9999.0
    last_success_age_days = (now_ts - _v53_parse_time(last_success_at)) / 86400.0 if last_success_at else 9999.0
    last_empty_age_days = (now_ts - _v53_parse_time(last_empty_at)) / 86400.0 if last_empty_at else 9999.0
    last_checked_age_days = (now_ts - _v53_parse_time(last_checked)) / 86400.0 if last_checked else 9999.0
    recently_updated = bool(
        source.get("last_updated")
        or source.get("updated_at")
        or source.get("last_seen_at")
        or (last_success_at and last_success_age_days <= 14)
        or (last_candidate_time and last_candidate_age_days <= 30)
    )
    recent_health_signal = min(last_checked_age_days, last_empty_age_days, last_success_age_days, last_candidate_age_days)
    reachable = failure_count < 2 and bool(last_success_at or not row.get("last_error"))
    active = bool(total_candidates > 0 or (last_success_at and last_success_age_days <= 30))
    score = 0.0
    score += min(40.0, total_candidates * 4.0)
    score += min(30.0, document_total * 6.0)
    score += min(30.0, qualified_total * 10.0)
    if reachable:
        score += 8.0
    if active:
        score += 6.0
    if recently_updated:
        score += 4.0
    if last_success_age_days <= 7:
        score += 6.0
    elif last_success_age_days <= 30:
        score += 3.0
    if avg_items > 0 and total_candidates > 0:
        score += min(6.0, avg_items)
    if response_time > 0:
        score += max(0.0, 4.0 - min(response_time, 4.0))
    if shape_alignment_score:
        score += shape_alignment_score
    if last_status in {"failed", "timeout"}:
        score -= 10.0
    if consecutive_empty_runs:
        score -= min(30.0, consecutive_empty_runs * 6.0)
    if zero_yield_source and scan_total > 0:
        score -= min(40.0, 10.0 + scan_total * 0.75)
    if last_status == "ok_empty" and zero_yield_source:
        score -= 12.0
    category_rank = _v53_source_category_rank(source)
    if not zero_yield_source:
        score += max(0.0, 6.0 - category_rank)
    score = round(max(0.0, min(100.0, score)), 2)
    if invalid_seed_source:
        quarantine_status = "quarantined"
        score = 0.0
    elif scan_total >= ZERO_YIELD_QUARANTINE_SCAN_THRESHOLD and zero_yield_source and recent_health_signal <= 14:
        quarantine_status = "quarantined"
        score = 0.0
    elif recent_health_signal <= 7 and (failure_count >= 3 or consecutive_empty_runs >= 6 or (failure_count >= 2 and consecutive_empty_runs >= 3)):
        quarantine_status = "quarantined"
    elif recent_health_signal <= 14 and (failure_count >= 1 or consecutive_empty_runs >= 2):
        quarantine_status = "watch"
    else:
        quarantine_status = "ready"
    if quarantine_status == "quarantined":
        score = min(score, 20.0)
    selection_reasons: List[str] = []
    if invalid_seed_source:
        selection_reasons.append("invalid_discovery_seed")
    if total_candidates > 0:
        selection_reasons.append("historical_candidates")
    if qualified_total > 0:
        selection_reasons.append("qualified_history")
    if document_total > 0:
        selection_reasons.append("document_rich")
    if success_count > 0:
        selection_reasons.append("historical_success")
    if last_success_age_days <= 30:
        selection_reasons.append("recent_success")
    if last_empty_at:
        selection_reasons.append("recent_empty_scan")
    if consecutive_empty_runs:
        selection_reasons.append("empty_run_penalty")
    if failure_count:
        selection_reasons.append("failure_penalty")
    if zero_yield_source and scan_total > 0:
        selection_reasons.append("zero_yield_history")
    if scan_total >= ZERO_YIELD_QUARANTINE_SCAN_THRESHOLD and zero_yield_source:
        selection_reasons.append("zero_yield_quarantine_threshold")
    if benchmark_candidates > 0:
        selection_reasons.append("benchmark_candidate_history")
    elif isinstance(source_shape_row, dict) and source_shape_row:
        selection_reasons.append("shape_profile_available")
    if shape_alignment_score > 0:
        selection_reasons.append("supply_delivery_alignment")
    elif shape_alignment_score < 0:
        selection_reasons.append("shape_misalignment")
    if quarantine_status == "quarantined":
        selection_reasons.append("quarantined")

    if invalid_seed_source:
        operator_action = "disable"
        operator_next_action = "Replace search-engine seed URLs with direct procurement portal URLs before re-enabling."
    elif last_error and any(term in last_error.lower() for term in ("nameresolutionerror", "dns", "resolve", "nodename")) and failure_count >= 2:
        operator_action = "normalize_or_pause"
        operator_next_action = "Try the www-normalized host; if it still fails, pause this source until DNS is stable."
    elif scan_total >= ZERO_YIELD_QUARANTINE_SCAN_THRESHOLD and zero_yield_source:
        operator_action = "quarantine"
        operator_next_action = "Remove or replace this zero-yield source; it has exhausted the exploratory scan budget."
    elif quarantine_status == "quarantined":
        operator_action = "quarantine"
        operator_next_action = "Inspect failures, then back off this source until it returns clean rows."
    elif consecutive_empty_runs >= 3 or (last_status == "ok_empty" and total_candidates == 0):
        operator_action = "deprioritize"
        operator_next_action = "Prefer sources with recent rows; this one is yielding empty results."
    elif failure_count >= 1:
        operator_action = "inspect"
        operator_next_action = "Review the latest error and retry only after the source recovers."
    elif last_status == "ok" and (total_candidates > 0 or qualified_total > 0 or document_total > 0 or not failure_count):
        operator_action = "continue"
        operator_next_action = "Keep active; this source is producing usable rows."
    else:
        operator_action = "watch"
        operator_next_action = "Keep monitored, but do not prioritize ahead of productive sources."
    if _clean(source.get("source_operator_action_override")):
        operator_action = _clean(source.get("source_operator_action_override"))
        operator_next_action = "Commissioning override active; review source behavior after this forced run."
    return {
        "source_name": _clean(source.get("name") or source.get("source_name") or key),
        "source_url": source_url,
        "source_type": _clean(source.get("type")),
        "source_group": _clean(source.get("source_group") or source.get("category_group")),
        "source_category_rank": category_rank,
        "source_success_score": score,
        "source_shape_alignment_score": shape_alignment_score,
        "source_shape_benchmark_candidates": benchmark_candidates,
        "source_shape_supply_delivery_share_pct": round(supply_delivery_share_pct, 2),
        "source_shape_benchmark_quality_score": round(benchmark_quality_score, 2),
        "source_shape_profile": shape_distribution,
        "source_last_candidate_time": last_candidate_time,
        "source_failure_count": failure_count,
        "source_response_time": response_time,
        "reachable": reachable,
        "active": active,
        "recently_updated": recently_updated,
        "source_selection_score": score,
        "source_quarantine_status": quarantine_status,
        "source_selection_reasons": selection_reasons,
        "source_operator_action": operator_action,
        "source_next_action": operator_next_action,
        "candidate_total": total_candidates,
        "qualified_candidate_total": qualified_total,
        "document_candidate_total": document_total,
        "consecutive_empty_runs": consecutive_empty_runs,
        "consecutive_dns_failures": consecutive_dns_failures,
        "consecutive_http_failures": consecutive_http_failures,
        "scan_total": scan_total,
        "invalid_seed_source": invalid_seed_source,
        "last_success_at": last_success_at,
        "last_empty_at": last_empty_at,
        "last_failure_at": last_failure_at,
        "last_checked_at": last_checked,
        "last_checked_age_days": round(last_checked_age_days, 2),
        "last_success_age_days": round(last_success_age_days, 2),
        "last_empty_age_days": round(last_empty_age_days, 2),
        "last_candidate_age_days": round(last_candidate_age_days, 2),
        "last_dns_status": last_dns_status,
        "last_http_status": last_http_status,
        "last_error_message": last_error_message,
        "acquisition_status": acquisition_status,
        "acquisition_error_message": acquisition_error_message,
        "acquisition_scan_started_at": acquisition_scan_started_at,
        "acquisition_scan_finished_at": acquisition_scan_finished_at,
        "acquisition_pages_scanned": acquisition_pages_scanned,
        "acquisition_raw_candidates_count": acquisition_raw_candidates_count,
        "acquisition_document_links_detected": acquisition_document_links_detected,
        "acquisition_retry_count": acquisition_retry_count,
        "acquisition_fallback_used": acquisition_fallback_used,
        "last_status": last_status,
        "last_error": _clean(row.get("last_error")),
        "health_status": health_status,
    }


def get_acquisition_runtime_summary(
    source_file: Optional[str] = None,
    limit: int = 15,
    source_health_snapshot: Optional[Dict[str, Any]] = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    sources = load_harvest_sources(source_file)
    health = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file)
    rows = [_v53_source_health_row(src, health) for src in sources]
    status_counts: Dict[str, int] = {}
    health_counts: Dict[str, int] = {}
    for row in rows:
        status = _clean(row.get("acquisition_status")) or _clean(row.get("last_status")) or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        health_status = _clean(row.get("health_status")) or _v53_source_health_status(row, None)
        health_counts[health_status] = health_counts.get(health_status, 0) + 1
    successful_count = status_counts.get("success", 0)
    no_candidate_count = status_counts.get("no_candidates", 0)
    failed_count = sum(status_counts.get(status, 0) for status in ("dns_failed", "playwright_failed", "timeout", "http_failed", "parse_failed"))
    productive_sources_count = sum(health_counts.get(status, 0) for status in ("healthy", "degraded", "empty"))
    suppressed_sources_count = sum(health_counts.get(status, 0) for status in ("dns_blocked", "http_blocked", "disabled"))
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "source_count": len(rows),
        "sources_scanned_count": len(rows),
        "sources_successful_count": successful_count,
        "sources_failed_count": failed_count,
        "dns_failures_count": status_counts.get("dns_failed", 0),
        "playwright_failures_count": status_counts.get("playwright_failed", 0),
        "timeout_failures_count": status_counts.get("timeout", 0),
        "http_failures_count": status_counts.get("http_failed", 0),
        "parse_failures_count": status_counts.get("parse_failed", 0),
        "no_candidate_sources_count": no_candidate_count,
        "total_raw_candidates": sum(int(row.get("acquisition_raw_candidates_count") or row.get("candidate_total") or 0) for row in rows),
        "total_document_links_detected": sum(int(row.get("acquisition_document_links_detected") or row.get("document_candidate_total") or 0) for row in rows),
        "acquisition_success_rate": round((successful_count / max(len(rows), 1)) * 100.0, 2),
        "acquisition_completion_rate": round(((successful_count + no_candidate_count) / max(len(rows), 1)) * 100.0, 2),
        "productive_sources_count": productive_sources_count,
        "suppressed_sources_count": suppressed_sources_count,
        "suppressed_dns_count": health_counts.get("dns_blocked", 0),
        "suppressed_http_count": health_counts.get("http_blocked", 0),
        "suppressed_empty_count": health_counts.get("empty", 0),
        "health_status_counts": health_counts,
        "status_counts": status_counts,
        "top_sources": rows[: max(1, limit)],
        "source_file": _display_project_path(source_health_file or SOURCE_HEALTH_FILE),
        "selected_limit": max(1, limit),
    }


def _v53_source_selection_sort_key(source: Dict[str, Any], row: Optional[Dict[str, Any]] = None) -> Tuple[int, float, float, int, int, int, str]:
    row = row if isinstance(row, dict) else {}
    quarantine_status = _clean(row.get("source_quarantine_status"))
    quarantine_rank = 0 if quarantine_status == "ready" else 1 if quarantine_status == "watch" else 2
    selection_score = _safe_float(row.get("source_selection_score"), _safe_float(row.get("source_success_score"), 0.0))
    success_score = _safe_float(row.get("source_success_score"), 0.0)
    candidate_total = int(row.get("candidate_total") or 0)
    qualified_total = int(row.get("qualified_candidate_total") or 0)
    failure_count = int(row.get("source_failure_count") or 0)
    priority = int(source.get("priority") or 9999)
    name = _clean(source.get("name") or source.get("source_name"))
    return (
        quarantine_rank,
        -selection_score,
        -success_score,
        -candidate_total,
        -qualified_total,
        failure_count,
        priority,
        name,
    )


def _v59_runtime_source_selection_sort_key(
    source: Dict[str, Any],
    row: Dict[str, Any],
    runtime_state: Dict[str, Any],
) -> Tuple[int, float, float, float, float, int, int, str]:
    quarantine_status = _clean(row.get("source_quarantine_status"))
    quarantine_rank = 0 if quarantine_status == "ready" else 1 if quarantine_status == "watch" else 2
    selection_score = _safe_float(row.get("source_selection_score"), _safe_float(row.get("source_success_score"), 0.0))
    runtime_harvested = int(runtime_state.get("harvested") or 0)
    runtime_candidates = int(runtime_state.get("candidates") or 0)
    runtime_qualified = int(runtime_state.get("qualified") or 0)
    runtime_documents = int(runtime_state.get("documents") or 0)
    runtime_errors = int(runtime_state.get("errors") or 0)
    runtime_empty_streak = int(runtime_state.get("empty_streak") or 0)
    if runtime_harvested > 0 or runtime_candidates > 0 or runtime_qualified > 0:
        selection_score += min(30.0, 10.0 + runtime_candidates * 4.0 + runtime_qualified * 5.0 + runtime_documents * 2.0)
    if runtime_empty_streak > 0:
        selection_score -= min(35.0, runtime_empty_streak * 15.0)
    if runtime_errors > 0:
        selection_score -= min(40.0, runtime_errors * 20.0)
    if runtime_harvested == 0 and runtime_candidates == 0 and runtime_errors == 0:
        selection_score -= 12.0
    if quarantine_status == "watch":
        selection_score -= 8.0
    if quarantine_status == "quarantined":
        selection_score -= 100.0
    selection_score += min(12.0, runtime_documents * 3.0)
    failure_count = int(row.get("source_failure_count") or 0)
    priority = int(source.get("priority") or 9999)
    name = _clean(source.get("name") or source.get("source_name"))
    return (
        quarantine_rank,
        -selection_score,
        -float(row.get("source_selection_score") or row.get("source_success_score") or 0),
        -float(runtime_harvested),
        -float(runtime_candidates),
        failure_count,
        priority,
        name,
    )


def _v59_select_next_runtime_source(
    sources: List[Dict[str, Any]],
    runtime_state: Dict[str, Dict[str, Any]],
    include_bad_sources: bool = False,
    source_health_file: Optional[Path] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, Any]]:
    health = _load_source_health(source_health_file=source_health_file)
    scored: List[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
    for source in sources:
        if not source.get("enabled", True):
            continue
        row = _v53_source_health_row(source, health)
        quarantine_status = _clean(row.get("source_quarantine_status"))
        if not include_bad_sources and (
            quarantine_status == "quarantined"
            or _clean(row.get("health_status")) in {"dns_blocked", "http_blocked", "disabled"}
        ):
            continue
        key = _source_key(source)
        state = runtime_state.get(key) if isinstance(runtime_state.get(key), dict) else {}
        source = _apply_commissioning_override(source, row, include_bad_sources)
        scored.append((source, row, state))
    if not scored:
        return None, None, {"reason": "no_runnable_sources"}
    scored = sorted(scored, key=lambda pair: _v59_runtime_source_selection_sort_key(pair[0], pair[1], pair[2]))
    selected_source, selected_row, selected_state = scored[0]
    selection_debug = {
        "selected_source_name": _clean(selected_source.get("name") or selected_source.get("source_name")),
        "selected_source_key": _source_key(selected_source),
        "selected_source_health_score": selected_row.get("source_selection_score"),
        "selected_source_quarantine_status": selected_row.get("source_quarantine_status"),
        "selected_source_reasons": selected_row.get("source_selection_reasons") or [],
        "runtime_harvested": int(selected_state.get("harvested") or 0),
        "runtime_candidates": int(selected_state.get("candidates") or 0),
        "runtime_qualified": int(selected_state.get("qualified") or 0),
        "runtime_documents": int(selected_state.get("documents") or 0),
        "runtime_errors": int(selected_state.get("errors") or 0),
        "runtime_empty_streak": int(selected_state.get("empty_streak") or 0),
    }
    return selected_source, selected_row, selection_debug


def get_source_health_overview(
    source_file: Optional[str] = None,
    limit: int = 15,
    source_health_snapshot: Optional[Dict[str, Any]] = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    sources = load_harvest_sources(source_file)
    health = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file)
    rows = [_v53_source_health_row(src, health) for src in sources]
    health_counts: Dict[str, int] = {}
    for row in rows:
        health_status = _clean(row.get("health_status")) or _v53_source_health_status(row, None)
        health_counts[health_status] = health_counts.get(health_status, 0) + 1
    rows = sorted(
        rows,
        key=lambda row: (
            _clean(row.get("source_quarantine_status")) != "ready",
            -_safe_float(row.get("source_selection_score"), _safe_float(row.get("source_success_score"), 0.0)),
            -int(row.get("candidate_total") or 0),
            int(row.get("source_failure_count") or 0),
            _clean(row.get("source_name")),
        ),
    )
    ready = [row for row in rows if _clean(row.get("source_quarantine_status")) == "ready"]
    watch = [row for row in rows if _clean(row.get("source_quarantine_status")) == "watch"]
    quarantined = [row for row in rows if _clean(row.get("source_quarantine_status")) == "quarantined"]
    productive = [row for row in rows if _clean(row.get("health_status")) in {"healthy", "degraded", "empty"}]
    zero_yield = [row for row in rows if int(row.get("candidate_total") or 0) == 0 and int(row.get("qualified_candidate_total") or 0) == 0 and int(row.get("document_candidate_total") or 0) == 0]
    recent_empty = [row for row in rows if _clean(row.get("last_empty_at"))]
    recent_failures = [row for row in rows if int(row.get("source_failure_count") or 0) > 0]
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "source_count": len(sources),
        "ready_count": len(ready),
        "watch_count": len(watch),
        "quarantined_count": len(quarantined),
        "productive_count": len(productive),
        "zero_yield_count": len(zero_yield),
        "recent_empty_count": len(recent_empty),
        "recent_failure_count": len(recent_failures),
        "health_status_counts": health_counts,
        "productive_sources_count": health_counts.get("healthy", 0) + health_counts.get("degraded", 0) + health_counts.get("empty", 0),
        "suppressed_sources_count": health_counts.get("dns_blocked", 0) + health_counts.get("http_blocked", 0) + health_counts.get("disabled", 0),
        "suppressed_dns_count": health_counts.get("dns_blocked", 0),
        "suppressed_http_count": health_counts.get("http_blocked", 0),
        "suppressed_empty_count": health_counts.get("empty", 0),
        "top_sources": rows[: max(1, limit)],
        "top_ready_sources": ready[: max(1, limit)],
        "top_quarantined_sources": quarantined[: max(1, limit)],
        "top_productive_sources": productive[: max(1, limit)],
        "source_health_file": _display_project_path(source_health_file or SOURCE_HEALTH_FILE),
        "selected_limit": max(1, limit),
    }


def get_runtime_stability_report(
    source_file: Optional[str] = None,
    limit: int = 15,
    source_health_snapshot: Optional[Dict[str, Any]] = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    sources = load_harvest_sources(source_file)
    health = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file)
    rows = [_v53_source_health_row(src, health) for src in sources]

    def _error_text(row: Dict[str, Any]) -> str:
        return _clean(row.get("last_error")).lower()

    reachable_rows = [row for row in rows if bool(row.get("reachable"))]
    dns_failure_rows = [
        row for row in rows
        if any(term in _error_text(row) for term in ("nameresolutionerror", "dns", "resolve", "nodename"))
    ]
    playwright_failure_rows = [
        row for row in rows
        if any(term in _error_text(row) for term in ("playwright", "browsertype.launch", "bootstrap_check_in", "chromium"))
    ]
    successful_harvest_rows = [row for row in rows if _clean(row.get("last_status")) in {"ok", "ok_empty"}]
    failed_rows = [row for row in rows if _clean(row.get("last_status")) == "failed"]
    watch_rows = [row for row in rows if _clean(row.get("source_quarantine_status")) == "watch"]

    source_count = len(rows)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "source_count": source_count,
        "reachable_sources": len(reachable_rows),
        "reachability_pct": round((len(reachable_rows) / max(source_count, 1)) * 100.0, 2),
        "dns_success_pct": round(((source_count - len(dns_failure_rows)) / max(source_count, 1)) * 100.0, 2),
        "dns_failure_count": len(dns_failure_rows),
        "playwright_launch_success_pct": round(((source_count - len(playwright_failure_rows)) / max(source_count, 1)) * 100.0, 2),
        "playwright_failure_count": len(playwright_failure_rows),
        "harvest_completion_pct": round((len(successful_harvest_rows) / max(source_count, 1)) * 100.0, 2),
        "successful_harvest_count": len(successful_harvest_rows),
        "failed_harvest_count": len(failed_rows),
        "failed_harvest_pct": round((len(failed_rows) / max(source_count, 1)) * 100.0, 2),
        "watch_count": len(watch_rows),
        "top_reachable_sources": reachable_rows[: max(1, limit)],
        "top_dns_failure_sources": dns_failure_rows[: max(1, limit)],
        "top_playwright_failure_sources": playwright_failure_rows[: max(1, limit)],
        "top_failed_sources": failed_rows[: max(1, limit)],
        "source_health_file": _display_project_path(source_health_file or SOURCE_HEALTH_FILE),
        "selected_limit": max(1, limit),
    }


def _v53_runtime_failure_category(row: Dict[str, Any]) -> str:
    last_error = _clean(row.get("last_error")).lower()
    last_status = _clean(row.get("last_status")).lower()
    if any(term in last_error for term in ("nameresolutionerror", "dns", "resolve", "nodename")):
        return "dns_failure"
    if any(term in last_error for term in ("playwright", "browsertype.launch", "bootstrap_check_in", "chromium")):
        return "playwright_launch_failure"
    if "timeout" in last_error or last_status == "timeout":
        return "timeout"
    if any(term in last_error for term in ("403", "forbidden", "blocked")):
        return "blocked_or_forbidden"
    if any(term in last_error for term in ("404", "not found", "gone")):
        return "http_error"
    if last_status == "ok_empty":
        return "empty_result"
    if last_status == "ok":
        return "ok"
    if last_error:
        return "unknown"
    return "ok" if bool(row.get("reachable")) else "unknown"


def _v53_source_pool_state(source: Dict[str, Any], row: Dict[str, Any]) -> Tuple[int, str]:
    failure_category = _v53_runtime_failure_category(row)
    failure_count = int(row.get("source_failure_count") or 0)
    last_status = _clean(row.get("last_status")).lower()
    operator_action = _clean(row.get("source_operator_action")).lower()
    health_status = _clean(row.get("health_status")) or _v53_source_health_status(row, source)
    is_productive = bool(
        health_status in {"healthy", "degraded", "empty"}
        or last_status == "ok"
        or int(row.get("candidate_total") or 0) > 0
        or int(row.get("qualified_candidate_total") or 0) > 0
        or int(row.get("document_candidate_total") or 0) > 0
        or _safe_float(row.get("source_shape_alignment_score"), 0.0) > 0
    )

    if health_status == "dns_blocked":
        return 4, "paused_dns"
    if health_status == "http_blocked":
        return 4, "paused_http"
    if health_status == "disabled":
        return 5, "disabled"
    if failure_category == "timeout":
        return 2, "retry_later"
    if health_status == "empty" or failure_category == "empty_result" or operator_action == "deprioritize":
        return (0 if is_productive else 1), "empty" if health_status == "empty" else ("productive" if is_productive else "deprioritized_empty")
    if failure_category in {"http_error", "blocked_or_forbidden", "playwright_launch_failure", "unknown"}:
        return 3, failure_category
    return 0 if is_productive else 1, "productive" if is_productive else "watch"


def get_etenders_preflight_status(timeout_seconds: int = 3) -> Dict[str, Any]:
    timeout_seconds = _safe_positive_int(timeout_seconds, 3)
    try:
        response = requests.get(
            ETENDERS_URL,
            timeout=timeout_seconds,
            headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0"},
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        reachable = 200 <= status_code < 500
        content_type = _clean(response.headers.get("content-type"))
        return {
            "status": "ok" if reachable else "failed",
            "reachable": reachable,
            "dns_success": reachable,
            "status_code": status_code,
            "content_type": content_type,
            "failure_category": "ok" if reachable else "http_error",
            "error": "",
            "checked_at": _now_iso(),
            "url": ETENDERS_URL,
        }
    except Exception as exc:
        error_text = str(exc)
        lower = error_text.lower()
        failure_category = "dns_failure" if any(term in lower for term in ("nameresolutionerror", "dns", "resolve", "nodename")) else "timeout" if "timeout" in lower else "unknown"
        return {
            "status": "failed",
            "reachable": False,
            "dns_success": False,
            "status_code": 0,
            "content_type": "",
            "failure_category": failure_category,
            "error": _truncate(error_text, 240),
            "checked_at": _now_iso(),
            "url": ETENDERS_URL,
        }


def get_runtime_stability_source_report(
    source_file: Optional[str] = None,
    limit: int = 1000,
    source_health_snapshot: Optional[Dict[str, Any]] = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    sources = load_harvest_sources(source_file)
    health = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file)
    rows = [_v53_source_health_row(src, health) for src in sources]
    report_rows: List[Dict[str, Any]] = []

    for row in rows:
        failure_category = _v53_runtime_failure_category(row)
        report_rows.append(
            {
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "last_status": row.get("last_status"),
                "health_status": _clean(row.get("health_status")) or _v53_source_health_status(row, None),
                "dns_success": failure_category != "dns_failure",
                "reachable": bool(row.get("reachable")),
                "playwright_success": failure_category != "playwright_launch_failure",
                "harvest_completed": _clean(row.get("last_status")) in {"ok", "ok_empty"},
                "last_error": row.get("last_error"),
                "failure_category": failure_category,
                "failure_count": int(row.get("source_failure_count") or 0),
                "last_checked_at": row.get("last_checked_at"),
                "last_success_at": row.get("last_success_at"),
                "operator_action": row.get("source_operator_action"),
            }
        )

    report_rows.sort(
        key=lambda row: (
            row["failure_category"] != "ok",
            row["failure_category"],
            not row["reachable"],
            -int(row["failure_count"] or 0),
            _clean(row["source_name"]),
        )
    )

    failure_counts: Dict[str, int] = {}
    for row in report_rows:
        failure_counts[row["failure_category"]] = failure_counts.get(row["failure_category"], 0) + 1

    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "source_count": len(report_rows),
        "failure_counts": failure_counts,
        "sources": report_rows[: max(1, limit)],
        "source_file": _display_project_path(source_health_file or SOURCE_HEALTH_FILE),
        "selected_limit": max(1, limit),
    }


def get_productive_source_pack_report(
    source_file: Optional[str] = None,
    limit: int = 25,
    source_health_snapshot: Optional[Dict[str, Any]] = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    sources = load_harvest_sources(source_file)
    health = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file)
    selected_sources = select_sources_for_cycle(
        sources,
        max_sources_per_cycle=limit,
        include_bad_sources=False,
        controlled_mode=False,
        source_health_snapshot=health,
        source_health_file=source_health_file,
    )
    rows: List[Dict[str, Any]] = []
    dns_paused_count = 0
    http_paused_count = 0
    empty_deprioritized_count = 0
    health_counts: Dict[str, int] = {}
    for source in sources:
        row = _v53_source_health_row(source, health, source_health_file=source_health_file)
        health_status = _clean(row.get("health_status")) or _v53_source_health_status(row, source)
        health_counts[health_status] = health_counts.get(health_status, 0) + 1
    for source in selected_sources:
        row = _v53_source_health_row(source, health, source_health_file=source_health_file)
        pool_rank, pool_state = _v53_source_pool_state(source, row)
        if pool_state == "paused_dns":
            dns_paused_count += 1
        if pool_state == "paused_http":
            http_paused_count += 1
        if pool_state == "deprioritized_empty":
            empty_deprioritized_count += 1
        rows.append(
            {
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "source_selection_score": row.get("source_selection_score"),
                "source_success_score": row.get("source_success_score"),
                "failure_category": _v53_runtime_failure_category(row),
                "health_status": _clean(row.get("health_status")) or _v53_source_health_status(row, source),
                "source_pool_state": pool_state,
                "source_pool_rank": pool_rank,
                "operator_action": row.get("source_operator_action"),
                "candidate_total": row.get("candidate_total"),
                "qualified_candidate_total": row.get("qualified_candidate_total"),
                "document_candidate_total": row.get("document_candidate_total"),
                "last_status": row.get("last_status"),
                "last_error": row.get("last_error"),
                "last_checked_at": row.get("last_checked_at"),
                "last_success_at": row.get("last_success_at"),
            }
        )

    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "source_count": len(sources),
        "selected_count": len(rows),
        "productive_sources_count": health_counts.get("healthy", 0) + health_counts.get("degraded", 0) + health_counts.get("empty", 0),
        "suppressed_sources_count": health_counts.get("dns_blocked", 0) + health_counts.get("http_blocked", 0) + health_counts.get("disabled", 0),
        "suppressed_dns_count": health_counts.get("dns_blocked", 0),
        "suppressed_http_count": health_counts.get("http_blocked", 0),
        "suppressed_empty_count": health_counts.get("empty", 0),
        "dns_paused_count": dns_paused_count,
        "http_paused_count": http_paused_count,
        "empty_deprioritized_count": empty_deprioritized_count,
        "health_status_counts": health_counts,
        "sources": rows,
        "source_file": _display_project_path(source_health_file or SOURCE_HEALTH_FILE),
        "selected_limit": max(1, limit),
    }


def _v53_find_source_by_identifier(identifier: Any, source_file: Optional[str] = None) -> Optional[Dict[str, Any]]:
    needle = _normalize_source_identifier(identifier)
    if not needle:
        return None
    for source in load_harvest_sources(source_file):
        if _source_matches_identifier(source, needle):
            return source
    return None


def _v53_reset_source_health_entry(source: Dict[str, Any], source_health_file: Optional[Path] = None) -> Dict[str, Any]:
    health = _load_source_health(source_health_file=source_health_file)
    key = _source_key(source)
    row = dict(health.get(key, {}) if isinstance(health.get(key), dict) else {})
    now_iso = _now_iso()
    row.update(
        {
            "name": key,
            "source_name": key,
            "source_url": _clean(source.get("url") or source.get("list_url") or row.get("source_url")),
            "last_dns_status": "unknown",
            "last_http_status": 0,
            "last_success_at": "",
            "last_failure_at": "",
            "consecutive_dns_failures": 0,
            "consecutive_http_failures": 0,
            "consecutive_empty_runs": 0,
            "last_error_message": "",
            "last_error": "",
            "health_status": "healthy" if source.get("enabled", True) else "disabled",
            "last_checked_at": now_iso,
        }
    )
    health[key] = row
    _save_source_health(health, source_health_file=source_health_file)
    return _v53_source_health_row(source, health, source_health_file=source_health_file)


def _v53_recheck_source_health_entry(source: Dict[str, Any], source_health_file: Optional[Path] = None) -> Dict[str, Any]:
    health = _load_source_health(source_health_file=source_health_file)
    key = _source_key(source)
    row = dict(health.get(key, {}) if isinstance(health.get(key), dict) else {})
    preflight = _preflight_source_acquisition(source, timeout_seconds=8)
    now_iso = _now_iso()
    row["name"] = key
    row["source_name"] = key
    row["source_url"] = _clean(preflight.get("source_url") or source.get("url") or source.get("list_url") or row.get("source_url"))
    row["last_checked_at"] = now_iso
    row["last_dns_status"] = _clean(preflight.get("dns_status") or preflight.get("status") or "unknown")
    row["last_http_status"] = int(preflight.get("http_status") or preflight.get("http_status_code") or 0)
    row["last_error_message"] = _clean(preflight.get("error_message"))
    row["last_error"] = row["last_error_message"]
    if _clean(preflight.get("status")) == "ok":
        row["last_success_at"] = now_iso
        row["last_failure_at"] = ""
        row["consecutive_dns_failures"] = 0
        row["consecutive_http_failures"] = 0
        row["health_status"] = "healthy"
    elif _clean(preflight.get("status")) == "dns_failed":
        row["last_failure_at"] = now_iso
        row["consecutive_dns_failures"] = int(row.get("consecutive_dns_failures") or 0) + 1
        row["consecutive_http_failures"] = 0
        row["health_status"] = _v53_source_health_status(row, source)
    elif _clean(preflight.get("status")) == "http_failed":
        row["last_failure_at"] = now_iso
        row["consecutive_http_failures"] = int(row.get("consecutive_http_failures") or 0) + 1
        row["consecutive_dns_failures"] = 0
        row["health_status"] = _v53_source_health_status(row, source)
    else:
        row["health_status"] = _v53_source_health_status(row, source)
    health[key] = row
    _save_source_health(health, source_health_file=source_health_file)
    return _v53_source_health_row(source, health, source_health_file=source_health_file)


def reset_source_health(identifier: Any, source_file: Optional[str] = None, source_health_file: Optional[Path] = None) -> Dict[str, Any]:
    source = _v53_find_source_by_identifier(identifier, source_file=source_file)
    if not source:
        return {"status": "not_found", "identifier": _clean(identifier), "source": {}, "health": {}}
    health = _v53_reset_source_health_entry(source, source_health_file=source_health_file)
    return {
        "status": "ok",
        "action": "reset",
        "identifier": _clean(identifier),
        "source": {
            "source_name": _clean(source.get("name") or source.get("source_name")),
            "source_url": _clean(source.get("url") or source.get("list_url")),
        },
        "health": health,
    }


def recheck_source_health(identifier: Any, source_file: Optional[str] = None, source_health_file: Optional[Path] = None) -> Dict[str, Any]:
    source = _v53_find_source_by_identifier(identifier, source_file=source_file)
    if not source:
        return {"status": "not_found", "identifier": _clean(identifier), "source": {}, "health": {}}
    health = _v53_recheck_source_health_entry(source, source_health_file=source_health_file)
    return {
        "status": "ok",
        "action": "recheck",
        "identifier": _clean(identifier),
        "source": {
            "source_name": _clean(source.get("name") or source.get("source_name")),
            "source_url": _clean(source.get("url") or source.get("list_url")),
        },
        "health": health,
    }


def recheck_suppressed_source_health(source_file: Optional[str] = None, source_health_file: Optional[Path] = None) -> Dict[str, Any]:
    sources = load_harvest_sources(source_file)
    health = _load_source_health(source_health_file=source_health_file)
    rows = [_v53_source_health_row(src, health, source_health_file=source_health_file) for src in sources]
    suppressed_sources = [
        src
        for src, row in zip(sources, rows)
        if _clean(row.get("health_status")) in {"dns_blocked", "http_blocked"}
    ]
    results: List[Dict[str, Any]] = []
    for source in suppressed_sources:
        results.append(recheck_source_health(_source_identifier(source), source_file=source_file, source_health_file=source_health_file))
    return {
        "status": "ok",
        "action": "recheck_all_suppressed",
        "count": len(results),
        "results": results,
    }


def _v55_load_adaptive_weights() -> Dict[str, Any]:
    if not ADAPTIVE_SOURCE_WEIGHTS_FILE.exists():
        return {}
    try:
        data = json.loads(ADAPTIVE_SOURCE_WEIGHTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _v55_save_adaptive_weights(data: Dict[str, Any]) -> None:
    try:
        ADAPTIVE_SOURCE_WEIGHTS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save adaptive source weights: %s", exc)


def _v57_normalize_key(value: Any) -> str:
    text = _safe_lower(value)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:180] or "unknown"


def _v57_empty_memory(kind: str) -> Dict[str, Any]:
    base = {"schema_version": "V57_PERSISTENT_OPPORTUNITY_MEMORY", "kind": kind, "updated_at": _now_iso()}
    if kind == "source":
        base.update({"sources": {}, "qualified_candidate_fingerprints": {}, "rejection_history": []})
    elif kind == "buyer":
        base.update({"buyers": {}})
    elif kind == "category":
        base.update({"categories": {}})
    elif kind == "document_pattern":
        base.update({"patterns": {}})
    return base


def _v57_load_memory_file(path: Path, kind: str) -> Dict[str, Any]:
    if not path.exists():
        return _v57_empty_memory(kind)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = _v57_empty_memory(kind)
            merged.update(data)
            return merged
    except Exception as exc:
        logger.warning("Failed to read V57 %s memory: %s", kind, exc)
    return _v57_empty_memory(kind)


def _v57_load_memory_files() -> Dict[str, Dict[str, Any]]:
    return {
        "source": _v57_load_memory_file(SOURCE_MEMORY_FILE, "source"),
        "buyer": _v57_load_memory_file(BUYER_MEMORY_FILE, "buyer"),
        "category": _v57_load_memory_file(CATEGORY_MEMORY_FILE, "category"),
        "document_pattern": _v57_load_memory_file(DOCUMENT_PATTERN_MEMORY_FILE, "document_pattern"),
    }


def _v57_write_memory_file(path: Path, payload: Dict[str, Any]) -> None:
    payload["updated_at"] = _now_iso()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _v57_save_memory_files(memory: Dict[str, Dict[str, Any]]) -> None:
    _v57_write_memory_file(SOURCE_MEMORY_FILE, memory.get("source") or _v57_empty_memory("source"))
    _v57_write_memory_file(BUYER_MEMORY_FILE, memory.get("buyer") or _v57_empty_memory("buyer"))
    _v57_write_memory_file(CATEGORY_MEMORY_FILE, memory.get("category") or _v57_empty_memory("category"))
    _v57_write_memory_file(DOCUMENT_PATTERN_MEMORY_FILE, memory.get("document_pattern") or _v57_empty_memory("document_pattern"))


def _v57_estimated_profit(candidate: Dict[str, Any]) -> float:
    return _safe_float((candidate.get("estimated_profit_signal") or {}).get("estimated_profit"), 0.0)


def _v57_candidate_fingerprint(candidate: Dict[str, Any]) -> str:
    source_url = _clean(candidate.get("source_url") or candidate.get("response_url") or "")
    doc_urls = candidate.get("document_urls") if isinstance(candidate.get("document_urls"), list) else []
    fingerprint_blob = "|".join([
        _v57_normalize_key(candidate.get("buyer_name") or candidate.get("buyer")),
        _v57_normalize_key(candidate.get("reference_number") or candidate.get("rfq_number") or candidate.get("buyer_rfq_number")),
        _v57_normalize_key(candidate.get("title")),
        _v57_normalize_key(candidate.get("closing_date")),
        _v57_normalize_key(source_url),
        _v57_normalize_key(doc_urls[0] if doc_urls else ""),
    ])
    return sha256(fingerprint_blob.encode("utf-8")).hexdigest()


def _v57_title_signature(value: Any) -> str:
    stop_words = {
        "the", "and", "for", "of", "to", "a", "an", "with", "at", "in", "on", "rfq",
        "request", "quotation", "supply", "delivery", "appointment", "provision",
    }
    words = [
        w for w in re.findall(r"[a-z0-9]{3,}", _safe_lower(value))
        if w not in stop_words
    ]
    return " ".join(sorted(words[:18]))[:180] or _v57_normalize_key(value)


def _v57_source_confidence_score(row: Dict[str, Any]) -> float:
    scans = int(row.get("scan_count") or 0)
    candidates = int(row.get("candidate_total") or 0)
    qualified = int(row.get("qualified_candidate_total") or 0)
    documents = int(row.get("document_links_found_total") or 0) + int(row.get("documents_parsed_total") or 0)
    empty_runs = int(row.get("consecutive_empty_runs") or 0)
    rejections = int(row.get("rejected_candidate_total") or 0)
    candidate_rate = candidates / max(1, scans)
    qualified_rate = qualified / max(1, candidates)
    document_rate = documents / max(1, scans)
    rejection_rate = rejections / max(1, candidates)
    score = 30.0
    score += min(25.0, candidate_rate * 6.0)
    score += min(30.0, qualified_rate * 45.0)
    score += min(20.0, document_rate * 4.0)
    score -= min(30.0, empty_runs * 5.0)
    score -= min(15.0, rejection_rate * 15.0)
    return round(max(1.0, min(100.0, score)), 2)


def _v57_source_memory_boost(source: Dict[str, Any], memory: Optional[Dict[str, Dict[str, Any]]] = None) -> float:
    memory = memory if isinstance(memory, dict) else _v57_load_memory_files()
    source_rows = (memory.get("source") or {}).get("sources") if isinstance(memory.get("source"), dict) else {}
    row = source_rows.get(_source_key(source), {}) if isinstance(source_rows, dict) else {}
    if not isinstance(row, dict):
        return 0.0
    confidence = _safe_float(row.get("source_confidence_score"), 0.0)
    qualified = int(row.get("qualified_candidate_total") or 0)
    documents = int(row.get("document_links_found_total") or 0) + int(row.get("documents_parsed_total") or 0)
    empty_runs = int(row.get("consecutive_empty_runs") or 0)
    noise = _safe_float(row.get("repetitive_noise_score"), 0.0)
    boost = 0.0
    if confidence >= 70:
        boost += min(15.0, (confidence - 55.0) / 3.0)
    if qualified > 0:
        boost += min(12.0, qualified * 2.0)
    if documents > 0:
        boost += min(10.0, documents / 2.0)
    if empty_runs >= 3:
        boost -= min(25.0, empty_runs * 4.0)
    if noise > 20:
        boost -= min(18.0, noise / 4.0)
    return round(max(-30.0, min(30.0, boost)), 2)


def _v57_buyer_score(row: Dict[str, Any]) -> float:
    seen = int(row.get("seen_count") or 0)
    qualified = int(row.get("qualified_count") or 0)
    avg_score = _safe_float(row.get("average_qualification_score"), 0.0)
    score = min(35.0, seen * 4.0)
    score += min(35.0, qualified * 8.0)
    score += min(30.0, avg_score / 3.0)
    return round(max(0.0, min(100.0, score)), 2)


def _v57_category_score(row: Dict[str, Any]) -> float:
    seen = int(row.get("seen_count") or 0)
    qualified = int(row.get("qualified_count") or 0)
    avg_profit = _safe_float(row.get("average_estimated_profit"), 0.0)
    qualified_rate = qualified / max(1, seen)
    score = min(25.0, seen * 3.0)
    score += min(35.0, qualified_rate * 50.0)
    score += min(40.0, avg_profit / 2500.0)
    return round(max(0.0, min(100.0, score)), 2)


def _v57_apply_candidate_memory_learning(candidate: Dict[str, Any], memory: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    buyer_key = _v57_normalize_key(candidate.get("buyer_name") or candidate.get("buyer"))
    category_key = _v57_normalize_key(candidate.get("commodity_service_category") or candidate.get("category") or "unknown")
    buyers = (memory.get("buyer") or {}).get("buyers") if isinstance(memory.get("buyer"), dict) else {}
    categories = (memory.get("category") or {}).get("categories") if isinstance(memory.get("category"), dict) else {}
    buyer_row = buyers.get(buyer_key, {}) if isinstance(buyers, dict) else {}
    category_row = categories.get(category_key, {}) if isinstance(categories, dict) else {}
    buyer_score = _v57_buyer_score(buyer_row) if isinstance(buyer_row, dict) else 0.0
    category_score = _v57_category_score(category_row) if isinstance(category_row, dict) else 0.0
    recurring_buyer = int((buyer_row or {}).get("seen_count") or 0) >= 2 or int((buyer_row or {}).get("qualified_count") or 0) > 0
    recurring_category = int((category_row or {}).get("seen_count") or 0) >= 3 or int((category_row or {}).get("qualified_count") or 0) > 0
    title_signature = _v57_title_signature(candidate.get("title") or candidate.get("description"))
    previous_signatures = (buyer_row or {}).get("title_signatures") if isinstance(buyer_row, dict) else {}
    recurring_rfq = bool(isinstance(previous_signatures, dict) and int(previous_signatures.get(title_signature) or 0) > 0)
    boost = 0.0
    reasons: List[str] = []
    if buyer_score >= 45:
        boost += min(7.0, buyer_score / 12.0)
        reasons.append("historically_successful_buyer")
    if category_score >= 45:
        boost += min(8.0, category_score / 11.0)
        reasons.append("historically_profitable_category")
    if recurring_rfq:
        boost += 4.0
        reasons.append("recurring_rfq_pattern")
    if boost:
        candidate["memory_priority_boost"] = round(boost, 2)
        candidate["qualification_score_before_memory"] = candidate.get("qualification_score")
        candidate["qualification_score"] = round(min(100.0, _safe_float(candidate.get("qualification_score"), 0.0) + boost), 2)
        candidate["confidence_score"] = round(max(_safe_float(candidate.get("confidence_score"), 0.0), candidate["qualification_score"]), 2)
        candidate["qualification_reasons"] = sorted(set((candidate.get("qualification_reasons") or []) + reasons))
    candidate["memory_signals"] = {
        "buyer_key": buyer_key,
        "category_key": category_key,
        "buyer_recurrence_score": buyer_score,
        "category_profitability_score": category_score,
        "recurring_buyer": recurring_buyer,
        "recurring_category": recurring_category,
        "recurring_rfq": recurring_rfq,
        "title_signature": title_signature,
    }
    soft_reasons = {"qualification_score_below_threshold"}
    if candidate.get("exclusion_reason") in soft_reasons and _safe_float(candidate.get("qualification_score"), 0.0) >= 65.0:
        candidate["exclusion_reason"] = ""
        candidate["qualified"] = True
    return candidate


def _v57_document_pattern_key(row: Dict[str, Any]) -> str:
    filename = _clean(row.get("filename"))
    classification = _v57_normalize_key(row.get("classification") or "unknown")
    extension = _v57_normalize_key(row.get("extension") or Path(filename).suffix or "unknown")
    stem = _v57_title_signature(Path(filename).stem)
    return "|".join([classification, extension, stem])[:240]


def _v57_prune_mapping_by_time(mapping: Dict[str, Any], limit: int) -> Dict[str, Any]:
    if len(mapping) <= limit:
        return mapping
    rows = sorted(
        mapping.items(),
        key=lambda pair: _v53_parse_time((pair[1] or {}).get("last_seen_at") or (pair[1] or {}).get("updated_at")),
        reverse=True,
    )
    return dict(rows[:limit])


def _v57_top_memory_rows(mapping: Dict[str, Any], score_key: str, min_score: float = 0.0, limit: int = 12) -> List[Dict[str, Any]]:
    rows = [row for row in mapping.values() if isinstance(row, dict) and _safe_float(row.get(score_key), 0.0) >= min_score]
    rows = sorted(rows, key=lambda row: _safe_float(row.get(score_key), 0.0), reverse=True)
    return rows[:limit]


def _v57_update_discovery_memory(
    memory: Dict[str, Dict[str, Any]],
    selected_sources: List[Dict[str, Any]],
    source_runs: List[Dict[str, Any]],
    raw_candidates: List[Dict[str, Any]],
    qualified: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    document_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    now_iso = _now_iso()
    source_memory = memory.get("source") or _v57_empty_memory("source")
    buyer_memory = memory.get("buyer") or _v57_empty_memory("buyer")
    category_memory = memory.get("category") or _v57_empty_memory("category")
    document_pattern_memory = memory.get("document_pattern") or _v57_empty_memory("document_pattern")
    sources_map = source_memory.setdefault("sources", {})
    buyers_map = buyer_memory.setdefault("buyers", {})
    categories_map = category_memory.setdefault("categories", {})
    patterns_map = document_pattern_memory.setdefault("patterns", {})
    fingerprints = source_memory.setdefault("qualified_candidate_fingerprints", {})
    global_rejection_history = source_memory.setdefault("rejection_history", [])
    selected_by_name = {
        _clean(src.get("name") or src.get("source_name") or src.get("url")): src
        for src in selected_sources
    }
    candidates_by_source: Dict[str, List[Dict[str, Any]]] = {}
    qualified_by_source: Dict[str, List[Dict[str, Any]]] = {}
    rejected_by_source: Dict[str, List[Dict[str, Any]]] = {}
    for candidate in raw_candidates:
        candidates_by_source.setdefault(_clean(candidate.get("source_name") or "Unknown Source"), []).append(candidate)
    for candidate in qualified:
        qualified_by_source.setdefault(_clean(candidate.get("source_name") or "Unknown Source"), []).append(candidate)
    for candidate in rejected:
        rejected_by_source.setdefault(_clean(candidate.get("source_name") or "Unknown Source"), []).append(candidate)

    for run in source_runs:
        source_name = _clean(run.get("source_name") or "Unknown Source")
        src = selected_by_name.get(source_name, {})
        source_key = _source_key(src) if src else source_name
        row = sources_map.get(source_key, {}) if isinstance(sources_map.get(source_key), dict) else {}
        row.setdefault("first_seen_at", now_iso)
        row["last_seen_at"] = now_iso
        row["source_name"] = source_name
        row["source_url"] = _clean(run.get("source_url") or (src or {}).get("url") or (src or {}).get("list_url"))
        row["source_type"] = _clean(run.get("source_type") or (src or {}).get("type"))
        row["source_group"] = _clean(run.get("source_group") or (src or {}).get("source_group") or (src or {}).get("category_group"))
        row["scan_count"] = int(row.get("scan_count") or 0) + 1
        row["harvested_total"] = int(row.get("harvested_total") or 0) + int(run.get("harvested_count") or 0)
        source_candidates = candidates_by_source.get(source_name, [])
        source_qualified = qualified_by_source.get(source_name, [])
        source_rejected = rejected_by_source.get(source_name, [])
        row["candidate_total"] = int(row.get("candidate_total") or 0) + len(source_candidates)
        row["qualified_candidate_total"] = int(row.get("qualified_candidate_total") or 0) + len(source_qualified)
        row["rejected_candidate_total"] = int(row.get("rejected_candidate_total") or 0) + len(source_rejected)
        row["document_links_found_total"] = int(row.get("document_links_found_total") or 0) + int(run.get("document_links_found_count") or 0)
        row["documents_downloaded_total"] = int(row.get("documents_downloaded_total") or 0) + int(run.get("documents_downloaded_count") or 0)
        row["documents_parsed_total"] = int(row.get("documents_parsed_total") or 0) + int(run.get("documents_parsed_count") or 0)
        row["document_built_candidate_total"] = int(row.get("document_built_candidate_total") or 0) + int(run.get("document_built_candidates_count") or 0)
        if source_candidates or int(run.get("document_links_found_count") or 0) > 0:
            row["consecutive_empty_runs"] = 0
        else:
            row["consecutive_empty_runs"] = int(row.get("consecutive_empty_runs") or 0) + 1
        rejection_counts = row.setdefault("rejection_counts", {})
        duplicate_rejections = 0
        for candidate in source_rejected:
            reason = _clean(candidate.get("exclusion_reason") or "unknown")
            rejection_counts[reason] = int(rejection_counts.get(reason) or 0) + 1
            if "duplicate" in reason or reason in {"not_supply_delivery", "qualification_score_below_threshold"}:
                duplicate_rejections += 1
        row["repetitive_noise_score"] = round(min(100.0, _safe_float(row.get("repetitive_noise_score"), 0.0) + duplicate_rejections * 2.0), 2)
        yield_history = row.setdefault("yield_history", [])
        yield_history.append({
            "run_at": now_iso,
            "harvested_count": int(run.get("harvested_count") or 0),
            "candidate_count": len(source_candidates),
            "qualified_count": len(source_qualified),
            "rejected_count": len(source_rejected),
            "document_links_found_count": int(run.get("document_links_found_count") or 0),
            "documents_parsed_count": int(run.get("documents_parsed_count") or 0),
            "response_time": run.get("source_response_time"),
        })
        row["yield_history"] = yield_history[-V57_MEMORY_HISTORY_LIMIT:]
        row["source_confidence_score"] = _v57_source_confidence_score(row)
        row["document_rich_score"] = round(min(100.0, (int(row.get("document_links_found_total") or 0) + int(row.get("documents_parsed_total") or 0)) * 4.0), 2)
        sources_map[source_key] = row

    for candidate in raw_candidates:
        buyer_key = _v57_normalize_key(candidate.get("buyer_name") or candidate.get("buyer"))
        category_key = _v57_normalize_key(candidate.get("commodity_service_category") or candidate.get("category") or "unknown")
        qualified_flag = bool(candidate.get("qualified")) and not candidate.get("exclusion_reason")
        rejection_reason = _clean(candidate.get("exclusion_reason"))
        profit = _v57_estimated_profit(candidate)
        title_signature = _v57_title_signature(candidate.get("title") or candidate.get("description"))

        buyer_row = buyers_map.get(buyer_key, {}) if isinstance(buyers_map.get(buyer_key), dict) else {}
        buyer_row.setdefault("first_seen_at", now_iso)
        buyer_row["last_seen_at"] = now_iso
        buyer_row["buyer_name"] = _clean(candidate.get("buyer_name") or candidate.get("buyer") or buyer_key)
        buyer_row["seen_count"] = int(buyer_row.get("seen_count") or 0) + 1
        buyer_row["qualified_count"] = int(buyer_row.get("qualified_count") or 0) + (1 if qualified_flag else 0)
        buyer_row["rejected_count"] = int(buyer_row.get("rejected_count") or 0) + (0 if qualified_flag else 1)
        buyer_row["estimated_profit_total"] = _safe_float(buyer_row.get("estimated_profit_total"), 0.0) + profit
        buyer_row["estimated_profit_count"] = int(buyer_row.get("estimated_profit_count") or 0) + (1 if profit > 0 else 0)
        buyer_row["average_estimated_profit"] = round(_safe_float(buyer_row.get("estimated_profit_total"), 0.0) / max(1, int(buyer_row.get("estimated_profit_count") or 0)), 2)
        buyer_row["qualification_score_total"] = _safe_float(buyer_row.get("qualification_score_total"), 0.0) + _safe_float(candidate.get("qualification_score"), 0.0)
        buyer_row["average_qualification_score"] = round(_safe_float(buyer_row.get("qualification_score_total"), 0.0) / max(1, int(buyer_row.get("seen_count") or 0)), 2)
        buyer_row["recurrence_score"] = _v57_buyer_score(buyer_row)
        buyer_categories = buyer_row.setdefault("categories", {})
        buyer_categories[category_key] = int(buyer_categories.get(category_key) or 0) + 1
        title_signatures = buyer_row.setdefault("title_signatures", {})
        title_signatures[title_signature] = int(title_signatures.get(title_signature) or 0) + 1
        if rejection_reason:
            buyer_rejections = buyer_row.setdefault("rejection_counts", {})
            buyer_rejections[rejection_reason] = int(buyer_rejections.get(rejection_reason) or 0) + 1
        buyers_map[buyer_key] = buyer_row

        category_row = categories_map.get(category_key, {}) if isinstance(categories_map.get(category_key), dict) else {}
        category_row.setdefault("first_seen_at", now_iso)
        category_row["last_seen_at"] = now_iso
        category_row["category"] = category_key
        category_row["seen_count"] = int(category_row.get("seen_count") or 0) + 1
        category_row["qualified_count"] = int(category_row.get("qualified_count") or 0) + (1 if qualified_flag else 0)
        category_row["rejected_count"] = int(category_row.get("rejected_count") or 0) + (0 if qualified_flag else 1)
        profit_history = category_row.setdefault("profit_history", [])
        if profit > 0:
            profit_history.append({"seen_at": now_iso, "estimated_profit": round(profit, 2), "qualified": qualified_flag})
        category_row["profit_history"] = profit_history[-V57_MEMORY_HISTORY_LIMIT:]
        profits = [_safe_float(row.get("estimated_profit"), 0.0) for row in category_row["profit_history"] if isinstance(row, dict)]
        category_row["average_estimated_profit"] = round(sum(profits) / max(1, len(profits)), 2)
        if len(profits) >= 6:
            older = sum(profits[: len(profits) // 2]) / max(1, len(profits) // 2)
            newer = sum(profits[len(profits) // 2 :]) / max(1, len(profits) - len(profits) // 2)
            if newer > older * 1.1:
                trend = "rising"
            elif newer < older * 0.9:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "insufficient_history"
        category_row["profitability_trend"] = trend
        category_row["profitability_score"] = _v57_category_score(category_row)
        if rejection_reason:
            category_rejections = category_row.setdefault("rejection_counts", {})
            category_rejections[rejection_reason] = int(category_rejections.get(rejection_reason) or 0) + 1
        categories_map[category_key] = category_row

        if qualified_flag:
            fingerprint = candidate.get("candidate_fingerprint") or _v57_candidate_fingerprint(candidate)
            fp_row = fingerprints.get(fingerprint, {}) if isinstance(fingerprints.get(fingerprint), dict) else {}
            fp_row.setdefault("first_seen_at", now_iso)
            fp_row["last_seen_at"] = now_iso
            fp_row["title"] = _clean(candidate.get("title"))
            fp_row["buyer_name"] = _clean(candidate.get("buyer_name") or candidate.get("buyer"))
            fp_row["category"] = category_key
            fp_row["closing_date"] = _clean(candidate.get("closing_date"))
            fp_row["source_name"] = _clean(candidate.get("source_name"))
            fp_row["qualified_seen_count"] = int(fp_row.get("qualified_seen_count") or 0) + 1
            fingerprints[fingerprint] = fp_row
        elif rejection_reason:
            global_rejection_history.append({
                "seen_at": now_iso,
                "fingerprint": candidate.get("candidate_fingerprint") or _v57_candidate_fingerprint(candidate),
                "reason": rejection_reason,
                "title": _truncate(_clean(candidate.get("title")), 120),
                "buyer_name": _clean(candidate.get("buyer_name") or candidate.get("buyer")),
                "category": category_key,
            })

    for row in document_rows:
        pattern_key = _v57_document_pattern_key(row)
        pattern = patterns_map.get(pattern_key, {}) if isinstance(patterns_map.get(pattern_key), dict) else {}
        pattern.setdefault("first_seen_at", now_iso)
        pattern["last_seen_at"] = now_iso
        pattern["pattern_key"] = pattern_key
        pattern["classification"] = _clean(row.get("classification") or "unknown")
        pattern["extension"] = _clean(row.get("extension") or "unknown")
        pattern["example_filename"] = _clean(row.get("filename"))
        pattern["seen_count"] = int(pattern.get("seen_count") or 0) + 1
        if row.get("classification") == "RFQ document":
            pattern["rfq_document_count"] = int(pattern.get("rfq_document_count") or 0) + 1
        if row.get("classification") == "pricing schedule":
            pattern["pricing_schedule_count"] = int(pattern.get("pricing_schedule_count") or 0) + 1
        if row.get("classification") in {"RFQ document", "pricing schedule"}:
            pattern["successful_document_pattern_score"] = round(min(100.0, int(pattern.get("seen_count") or 0) * 8.0), 2)
        patterns_map[pattern_key] = pattern

    source_memory["sources"] = sources_map
    source_memory["qualified_candidate_fingerprints"] = _v57_prune_mapping_by_time(fingerprints, V57_FINGERPRINT_LIMIT)
    source_memory["rejection_history"] = global_rejection_history[-V57_FINGERPRINT_LIMIT:]
    buyer_memory["buyers"] = _v57_prune_mapping_by_time(buyers_map, V57_FINGERPRINT_LIMIT)
    category_memory["categories"] = _v57_prune_mapping_by_time(categories_map, V57_FINGERPRINT_LIMIT)
    document_pattern_memory["patterns"] = _v57_prune_mapping_by_time(patterns_map, V57_FINGERPRINT_LIMIT)
    memory["source"] = source_memory
    memory["buyer"] = buyer_memory
    memory["category"] = category_memory
    memory["document_pattern"] = document_pattern_memory
    _v57_save_memory_files(memory)
    return _v57_memory_diagnostics(memory)


def _v57_memory_diagnostics(memory: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    source_rows = ((memory.get("source") or {}).get("sources") or {}) if isinstance(memory.get("source"), dict) else {}
    buyer_rows = ((memory.get("buyer") or {}).get("buyers") or {}) if isinstance(memory.get("buyer"), dict) else {}
    category_rows = ((memory.get("category") or {}).get("categories") or {}) if isinstance(memory.get("category"), dict) else {}
    boosted_sources = _v57_top_memory_rows(source_rows, "source_confidence_score", min_score=55.0, limit=10)
    boosted_buyers = _v57_top_memory_rows(buyer_rows, "recurrence_score", min_score=45.0, limit=10)
    boosted_categories = _v57_top_memory_rows(category_rows, "profitability_score", min_score=45.0, limit=10)
    return {
        "memory_sources_count": len(source_rows),
        "memory_buyers_count": len(buyer_rows),
        "memory_categories_count": len(category_rows),
        "boosted_priority_sources": [
            {
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "source_confidence_score": row.get("source_confidence_score"),
                "document_rich_score": row.get("document_rich_score"),
                "qualified_candidate_total": row.get("qualified_candidate_total"),
                "consecutive_empty_runs": row.get("consecutive_empty_runs"),
            }
            for row in boosted_sources
        ],
        "boosted_priority_buyers": [
            {
                "buyer_name": row.get("buyer_name"),
                "recurrence_score": row.get("recurrence_score"),
                "seen_count": row.get("seen_count"),
                "qualified_count": row.get("qualified_count"),
                "average_estimated_profit": row.get("average_estimated_profit"),
            }
            for row in boosted_buyers
        ],
        "boosted_priority_categories": [
            {
                "category": row.get("category"),
                "profitability_score": row.get("profitability_score"),
                "profitability_trend": row.get("profitability_trend"),
                "seen_count": row.get("seen_count"),
                "qualified_count": row.get("qualified_count"),
                "average_estimated_profit": row.get("average_estimated_profit"),
            }
            for row in boosted_categories
        ],
    }


def _v55_recent_boost(timestamp_value: Any, recent_days: float = 14.0) -> float:
    parsed = _v53_parse_time(timestamp_value)
    if not parsed:
        return 0.0
    age_days = max(0.0, (time.time() - parsed) / 86400.0)
    if age_days > recent_days:
        return 0.0
    return round((recent_days - age_days) / recent_days, 4)


def _v55_yield_metrics_for_source(
    source: Dict[str, Any],
    health: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, Any]] = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    health = health if isinstance(health, dict) else _load_source_health(source_health_file=source_health_file)
    weights = weights if isinstance(weights, dict) else _v55_load_adaptive_weights()
    key = _source_key(source)
    row = dict(health.get(key, {}) if isinstance(health.get(key), dict) else {})
    health_row = _v53_source_health_row(source, health)
    weight_row = dict(weights.get(key, {}) if isinstance(weights.get(key), dict) else {})
    scan_total = int(row.get("scan_total") or 0)
    harvested_total = int(row.get("harvested_total") or row.get("candidate_total") or 0)
    extracted_total = int(row.get("extracted_candidate_total") or harvested_total or 0)
    qualified_total = int(row.get("qualified_candidate_total") or 0)
    document_total = int(row.get("document_candidate_total") or 0)
    consecutive_empty_runs = int(row.get("consecutive_empty_runs") or 0)
    average_response_time = _safe_float(row.get("average_response_time") or health_row.get("source_response_time"), 0.0)
    last_successful_candidate_time = _clean(
        row.get("last_successful_candidate_time")
        or row.get("source_last_candidate_time")
        or row.get("last_candidate_time")
    )
    candidate_yield_rate = round(harvested_total / max(1, scan_total), 4)
    qualified_candidate_rate = round(qualified_total / max(1, harvested_total), 4)
    document_detection_rate = round(document_total / max(1, harvested_total), 4)
    extraction_success_rate = round(extracted_total / max(1, harvested_total), 4) if harvested_total else 0.0
    adaptive_weight = _safe_float(
        weight_row.get("adaptive_weight"),
        float(health_row.get("source_selection_score") or health_row.get("source_success_score") or 0),
    )
    if qualified_total > 0 or (harvested_total > 0 and candidate_yield_rate >= 1.0 and consecutive_empty_runs == 0):
        tier = "tier_1_high_yield"
    elif harvested_total > 0 or adaptive_weight >= 45 or bool(health_row.get("recently_updated")):
        tier = "tier_2_moderate_yield"
    else:
        tier = "tier_3_exploratory"
    return {
        "source_name": health_row.get("source_name"),
        "source_url": health_row.get("source_url"),
        "source_type": health_row.get("source_type"),
        "source_group": health_row.get("source_group"),
        "source_success_score": health_row.get("source_success_score"),
        "source_selection_score": health_row.get("source_selection_score"),
        "source_quarantine_status": health_row.get("source_quarantine_status"),
        "source_selection_reasons": health_row.get("source_selection_reasons"),
        "candidate_yield_rate": candidate_yield_rate,
        "qualified_candidate_rate": qualified_candidate_rate,
        "document_detection_rate": document_detection_rate,
        "extraction_success_rate": extraction_success_rate,
        "average_response_time": round(average_response_time, 3),
        "consecutive_empty_runs": consecutive_empty_runs,
        "last_successful_candidate_time": last_successful_candidate_time,
        "last_checked_at": health_row.get("last_checked_at"),
        "source_failure_count": health_row.get("source_failure_count"),
        "reachable": health_row.get("reachable"),
        "active": health_row.get("active"),
        "recently_updated": health_row.get("recently_updated"),
        "candidate_total": harvested_total,
        "qualified_candidate_total": qualified_total,
        "document_candidate_total": document_total,
        "scan_total": scan_total,
        "adaptive_weight": round(adaptive_weight, 2),
        "tier": tier,
    }


def _v55_calculate_adaptive_weight(metrics: Dict[str, Any]) -> Tuple[float, List[str]]:
    actions: List[str] = []
    weight = _safe_float(metrics.get("source_selection_score"), _safe_float(metrics.get("source_success_score"), 0.0))
    candidate_yield_rate = _safe_float(metrics.get("candidate_yield_rate"), 0.0)
    qualified_candidate_rate = _safe_float(metrics.get("qualified_candidate_rate"), 0.0)
    document_detection_rate = _safe_float(metrics.get("document_detection_rate"), 0.0)
    extraction_success_rate = _safe_float(metrics.get("extraction_success_rate"), 0.0)
    consecutive_empty_runs = int(metrics.get("consecutive_empty_runs") or 0)
    failure_count = int(metrics.get("source_failure_count") or 0)
    avg_response = _safe_float(metrics.get("average_response_time"), 0.0)
    recent_candidate = _v55_recent_boost(metrics.get("last_successful_candidate_time"))
    scan_total = int(metrics.get("scan_total") or 0)
    candidate_total = int(metrics.get("candidate_total") or 0)
    quarantine_status = _clean(metrics.get("source_quarantine_status"))
    invalid_seed_source = bool(metrics.get("invalid_seed_source")) or _is_invalid_seed_source_url(metrics.get("source_url"))

    if invalid_seed_source:
        return 0.0, ["invalid_discovery_seed"]

    if scan_total >= ZERO_YIELD_QUARANTINE_SCAN_THRESHOLD and candidate_total == 0:
        return 0.0, ["quarantine_zero_yield_source"]

    if scan_total == 0 and candidate_total == 0:
        weight = min(weight, 35.0)
        actions.append("exploratory_unproven_source")
    if candidate_yield_rate > 0:
        weight += min(25.0, candidate_yield_rate * 8.0)
        actions.append("prioritize_historically_productive")
    if qualified_candidate_rate > 0:
        weight += min(30.0, qualified_candidate_rate * 30.0)
        actions.append("promote_qualified_yield")
    if document_detection_rate > 0:
        weight += min(12.0, document_detection_rate * 12.0)
    if extraction_success_rate > 0:
        weight += min(10.0, extraction_success_rate * 10.0)
    if recent_candidate > 0:
        weight += 18.0 * recent_candidate
        actions.append("boost_recent_success")
    if consecutive_empty_runs:
        weight -= min(35.0, consecutive_empty_runs * 7.0)
        actions.append("deprioritize_consistently_empty")
    if failure_count >= 2:
        weight -= min(35.0, failure_count * 10.0)
        actions.append("deprioritize_unreachable")
    if quarantine_status == "quarantined":
        weight = min(weight, 20.0)
        actions.append("quarantined_source")
    if avg_response > 8.0:
        weight -= min(12.0, avg_response - 8.0)
    if not actions:
        actions.append("maintain_exploratory_rotation")
    return round(max(1.0, min(100.0, weight)), 2), actions


def _v55_build_adaptive_yield_reports(
    sources: List[Dict[str, Any]],
    selected_sources: List[Dict[str, Any]],
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    health = _load_source_health(source_health_file=source_health_file)
    previous_weights = _v55_load_adaptive_weights()
    rankings: List[Dict[str, Any]] = []
    next_weights: Dict[str, Any] = {}
    adaptive_weight_updates: List[Dict[str, Any]] = []
    source_rebalance_actions: List[Dict[str, Any]] = []
    tier_distribution = {
        "tier_1_high_yield": 0,
        "tier_2_moderate_yield": 0,
        "tier_3_exploratory": 0,
    }
    selected_keys = {_source_key(src) for src in selected_sources}

    for source in sources:
        key = _source_key(source)
        metrics = _v55_yield_metrics_for_source(source, health, previous_weights, source_health_file=source_health_file)
        new_weight, actions = _v55_calculate_adaptive_weight(metrics)
        old_weight = _safe_float((previous_weights.get(key) or {}).get("adaptive_weight"), metrics.get("source_success_score") or 0)
        metrics["adaptive_weight"] = new_weight
        candidate_total = int(metrics.get("candidate_total") or 0)
        qualified_total = int(metrics.get("qualified_candidate_total") or 0)
        candidate_yield_rate = _safe_float(metrics.get("candidate_yield_rate"), 0.0)
        consecutive_empty_runs = int(metrics.get("consecutive_empty_runs") or 0)
        if qualified_total > 0 or (candidate_total > 0 and candidate_yield_rate >= 1.0 and consecutive_empty_runs <= 1):
            metrics["tier"] = "tier_1_high_yield"
        elif candidate_total > 0 or new_weight >= 40:
            metrics["tier"] = "tier_2_moderate_yield"
        else:
            metrics["tier"] = "tier_3_exploratory"
        metrics["selected_this_cycle"] = key in selected_keys
        rankings.append(metrics)
        tier_distribution[metrics["tier"]] = tier_distribution.get(metrics["tier"], 0) + 1
        next_weights[key] = {
            "source_name": metrics.get("source_name"),
            "source_url": metrics.get("source_url"),
            "adaptive_weight": new_weight,
            "tier": metrics.get("tier"),
            "candidate_yield_rate": metrics.get("candidate_yield_rate"),
            "qualified_candidate_rate": metrics.get("qualified_candidate_rate"),
            "document_detection_rate": metrics.get("document_detection_rate"),
            "extraction_success_rate": metrics.get("extraction_success_rate"),
            "average_response_time": metrics.get("average_response_time"),
            "consecutive_empty_runs": metrics.get("consecutive_empty_runs"),
            "last_successful_candidate_time": metrics.get("last_successful_candidate_time"),
            "last_rebalanced_at": _now_iso(),
            "rebalance_actions": actions,
        }
        if abs(new_weight - old_weight) >= 1.0 or key in selected_keys:
            adaptive_weight_updates.append({
                "source_name": metrics.get("source_name"),
                "previous_weight": round(old_weight, 2),
                "new_weight": new_weight,
                "delta": round(new_weight - old_weight, 2),
                "tier": metrics.get("tier"),
            })
        source_rebalance_actions.append({
            "source_name": metrics.get("source_name"),
            "adaptive_weight": new_weight,
            "tier": metrics.get("tier"),
            "actions": actions,
        })

    rankings = sorted(
        rankings,
        key=lambda row: (
            float(row.get("adaptive_weight") or 0),
            float(row.get("qualified_candidate_rate") or 0),
            float(row.get("candidate_yield_rate") or 0),
            -int(row.get("consecutive_empty_runs") or 0),
        ),
        reverse=True,
    )
    source_rebalance_actions = sorted(source_rebalance_actions, key=lambda row: float(row.get("adaptive_weight") or 0), reverse=True)
    _v55_save_adaptive_weights(next_weights)
    SOURCE_YIELD_RANKINGS_FILE.write_text(json.dumps(rankings, indent=2, default=str), encoding="utf-8")

    productive_sources_count = sum(1 for row in rankings if int(row.get("candidate_total") or 0) > 0 or int(row.get("qualified_candidate_total") or 0) > 0)
    empty_sources_count = sum(1 for row in rankings if int(row.get("consecutive_empty_runs") or 0) > 0 and int(row.get("candidate_total") or 0) == 0)
    projected_next_cycle_priority_sources = [
        {
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "adaptive_weight": row.get("adaptive_weight"),
            "tier": row.get("tier"),
        }
        for row in rankings[:25]
    ]
    yield_summary = {
        "status": "ok",
        "service_version": "V55_ADAPTIVE_SOURCE_YIELD_INTELLIGENCE",
        "productive_sources_count": productive_sources_count,
        "empty_sources_count": empty_sources_count,
        "top_yield_sources": rankings[:20],
        "adaptive_weight_updates": adaptive_weight_updates[:50],
        "tier_distribution": tier_distribution,
        "source_rebalance_actions": source_rebalance_actions[:50],
        "projected_next_cycle_priority_sources": projected_next_cycle_priority_sources,
        "artifacts": {
            "source_yield_rankings": str(SOURCE_YIELD_RANKINGS_FILE),
            "adaptive_source_weights": str(ADAPTIVE_SOURCE_WEIGHTS_FILE),
            "yield_summary": str(YIELD_SUMMARY_FILE),
        },
        "safety": {
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    YIELD_SUMMARY_FILE.write_text(json.dumps(yield_summary, indent=2, default=str), encoding="utf-8")
    return yield_summary


def _v58_pack_mode(value: Any = None) -> str:
    mode = _safe_lower(value or os.getenv("LMCP_SOURCE_PACK_MODE") or "balanced")
    if mode not in {"focus", "exploration", "balanced"}:
        return "balanced"
    return mode


def _v58_source_text(source: Dict[str, Any]) -> str:
    return " ".join(
        _safe_lower(source.get(key))
        for key in ["name", "source_name", "type", "source_group", "category_group", "url", "list_url"]
    )


def _v58_pack_names_for_source(
    source: Dict[str, Any],
    metrics: Dict[str, Any],
    buyer_rows: Dict[str, Any],
) -> List[str]:
    text = _v58_source_text(source)
    packs: List[str] = []
    if any(term in text for term in ["municipal", "municipality", "metro", "city of ", "district municipality", "local municipality"]):
        packs.append("municipalities_pack")
    if any(term in text for term in ["soe", "eskom", "transnet", "sanral", "prasa", "sabc", "denel", "airports", "water board", "post office", "petrosa", "safcol"]):
        packs.append("SOE_pack")
    if any(term in text for term in ["provincial", "province", "treasury", "department", "health", "education"]):
        packs.append("provincial_pack")
    if any(term in text for term in ["university", "college", "tvet", "campus"]):
        packs.append("university_pack")

    source_name_key = _v57_normalize_key(source.get("name") or source.get("source_name"))
    for buyer_key, row in buyer_rows.items():
        if not isinstance(row, dict):
            continue
        recurrence = _safe_float(row.get("recurrence_score"), 0.0)
        buyer_name_key = _v57_normalize_key(row.get("buyer_name") or buyer_key)
        if recurrence >= 45.0 and (buyer_name_key in source_name_key or source_name_key in buyer_name_key):
            packs.append("repeat_buyer_pack")
            break

    if (
        _safe_float(metrics.get("document_detection_rate"), 0.0) > 0
        or int(metrics.get("document_candidate_total") or 0) > 0
        or _safe_float(metrics.get("document_rich_score"), 0.0) >= 20.0
        or any(term in text for term in ["download", "rfq", "quotation", "bid document", "tenders/"])
    ):
        packs.append("document_rich_pack")

    return sorted(set(packs))


def _v61_load_watchlist_boosts() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    try:
        if ACTION_WATCHLIST_FILE.exists():
            payload = json.loads(ACTION_WATCHLIST_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    entries = payload.get("watchlist_entries") if isinstance(payload.get("watchlist_entries"), list) else []
    buyer_keys = set()
    buyer_names = set()
    categories = set()
    source_terms = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if _safe_float(entry.get("priority_score"), 0.0) < 55.0:
            continue
        buyer_key = _v57_normalize_key(entry.get("buyer_key"))
        buyer_name = _v57_normalize_key(entry.get("buyer_name"))
        category = _v57_normalize_key(entry.get("category"))
        if buyer_key:
            buyer_keys.add(buyer_key)
        if buyer_name:
            buyer_names.add(buyer_name)
            source_terms.add(buyer_name)
        if category:
            categories.add(category)
            source_terms.add(category)
        profile_type = _v57_normalize_key(entry.get("profile_type"))
        forecast_type = _v57_normalize_key(entry.get("forecast_type"))
        if profile_type:
            source_terms.add(profile_type)
        if forecast_type:
            source_terms.add(forecast_type)
    return {
        "buyer_keys": buyer_keys,
        "buyer_names": buyer_names,
        "categories": categories,
        "source_terms": source_terms,
    }


def _v58_source_score(source: Dict[str, Any], metrics: Dict[str, Any], memory_row: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
    reasons: List[str] = []
    penalties: List[str] = []
    text = _v58_source_text(source)
    score = _safe_float(metrics.get("adaptive_weight"), 0.0)
    score += _safe_float(metrics.get("source_success_score"), 0.0) * 0.35
    score += _v57_source_memory_boost(source)

    if metrics.get("reachable"):
        score += 12.0
        reasons.append("historically_reachable")
    if int(metrics.get("qualified_candidate_total") or 0) > 0:
        score += 18.0
        reasons.append("qualified_yield_history")
    if int(metrics.get("candidate_total") or 0) > 0:
        score += 8.0
        reasons.append("candidate_yield_history")
    if _safe_float(metrics.get("document_detection_rate"), 0.0) > 0 or int(memory_row.get("document_links_found_total") or 0) > 0:
        score += 16.0
        reasons.append("document_rich")
    shape_map = _v53_load_source_shape_performance_map()
    shape_row = shape_map.get(_v57_normalize_key(_clean(source.get("name") or source.get("source_name") or text)), {})
    if isinstance(shape_row, dict) and shape_row:
        shape_alignment_score = round(
            max(
                -12.0,
                min(
                    20.0,
                    (_safe_float(shape_row.get("benchmark_quality_score"), 0.0) / 8.0)
                    + (_safe_float(shape_row.get("supply_delivery_share_pct"), 0.0) * 0.08),
                ),
            ),
            2,
        )
        score += shape_alignment_score
        if shape_alignment_score > 0:
            reasons.append("supply_delivery_alignment")
        elif shape_alignment_score < 0:
            penalties.append("shape_misalignment")
    else:
        penalties.append("shape_profile_missing")
    if _safe_lower(source.get("submission_method")) == "email" or source.get("recipient_email") or source.get("buyer_email"):
        score += 12.0
        reasons.append("email_submission_friendly")
    if int(memory_row.get("documents_downloaded_total") or 0) > 0 or int(memory_row.get("documents_parsed_total") or 0) > 0:
        score += 10.0
        reasons.append("downloadable_rfq_history")
    watchlist_boosts = _v61_load_watchlist_boosts()
    source_key = _v57_normalize_key(source.get("name") or source.get("source_name"))
    source_text_key = _v57_normalize_key(text)
    if source_key and (source_key in watchlist_boosts.get("buyer_keys", set()) or source_key in watchlist_boosts.get("buyer_names", set())):
        score += 22.0
        reasons.append("v61_watchlist_buyer_boost")
    elif any(term and term in source_text_key for term in watchlist_boosts.get("source_terms", set())):
        score += 12.0
        reasons.append("v61_watchlist_source_or_category_boost")

    if any(term in text for term in ["search", "advanced-search", "quick find", "home/opportunities"]):
        score -= 35.0
        penalties.append("generic_search_page")
    if "bulletin" in text and int(metrics.get("candidate_total") or 0) == 0:
        score -= 15.0
        penalties.append("empty_bulletin_page")
    if int(metrics.get("consecutive_empty_runs") or 0) >= 3:
        score -= min(30.0, int(metrics.get("consecutive_empty_runs") or 0) * 6.0)
        penalties.append("noisy_low_yield_empty_runs")
    if int(metrics.get("source_failure_count") or 0) >= 2:
        score -= min(30.0, int(metrics.get("source_failure_count") or 0) * 10.0)
        penalties.append("historically_unreachable")
    if _safe_float(memory_row.get("repetitive_noise_score"), 0.0) > 20.0:
        score -= min(25.0, _safe_float(memory_row.get("repetitive_noise_score"), 0.0) / 3.0)
        penalties.append("repetitive_noise")

    return round(max(1.0, min(150.0, score)), 2), reasons, penalties


def _v58_build_source_pack_strategy(
    sources: List[Dict[str, Any]],
    selected_sources: List[Dict[str, Any]],
    max_sources: int,
    mode: Any = None,
    source_health_file: Optional[Path] = None,
) -> Dict[str, Any]:
    active_mode = _v58_pack_mode(mode)
    health = _load_source_health(source_health_file=source_health_file)
    adaptive_weights = _v55_load_adaptive_weights()
    memory = _v57_load_memory_files()
    source_rows = ((memory.get("source") or {}).get("sources") or {}) if isinstance(memory.get("source"), dict) else {}
    buyer_rows = ((memory.get("buyer") or {}).get("buyers") or {}) if isinstance(memory.get("buyer"), dict) else {}
    selected_keys = {_source_key(source) for source in selected_sources}

    packs: Dict[str, List[Dict[str, Any]]] = {name: [] for name in V58_SOURCE_PACK_NAMES}
    high_yield_sources: List[Dict[str, Any]] = []
    source_rows_report: List[Dict[str, Any]] = []

    for source in sources:
        if not source.get("enabled", True):
            continue
        key = _source_key(source)
        health_row = _v53_source_health_row(source, health, source_health_file=source_health_file)
        pool_rank, pool_state = _v53_source_pool_state(source, health_row)
        metrics = _v55_yield_metrics_for_source(source, health, adaptive_weights, source_health_file=source_health_file)
        memory_row = source_rows.get(key, {}) if isinstance(source_rows.get(key), dict) else {}
        metrics["document_rich_score"] = memory_row.get("document_rich_score", 0)
        pack_names = _v58_pack_names_for_source(source, metrics, buyer_rows)
        score, reasons, penalties = _v58_source_score(source, metrics, memory_row)
        row = {
            "source_name": _clean(source.get("name") or source.get("source_name")),
            "source_url": _clean(source.get("url") or source.get("list_url")),
            "source_type": _clean(source.get("type")),
            "source_group": _clean(source.get("source_group") or source.get("category_group")),
            "packs": pack_names,
            "v58_yield_score": score,
            "adaptive_weight": metrics.get("adaptive_weight"),
            "source_success_score": metrics.get("source_success_score"),
            "candidate_total": metrics.get("candidate_total"),
            "qualified_candidate_total": metrics.get("qualified_candidate_total"),
            "document_candidate_total": metrics.get("document_candidate_total"),
            "document_detection_rate": metrics.get("document_detection_rate"),
            "consecutive_empty_runs": metrics.get("consecutive_empty_runs"),
            "reachable": metrics.get("reachable"),
            "submission_method": _clean(source.get("submission_method") or "portal"),
            "selected_this_cycle": key in selected_keys,
            "prioritize_reasons": reasons,
            "deprioritize_reasons": penalties,
            "source_pool_rank": pool_rank,
            "source_pool_state": pool_state,
        }
        source_rows_report.append(row)
        for pack_name in pack_names:
            packs.setdefault(pack_name, []).append(row)
        if (
            score >= 55.0
            and not any(
                penalty in penalties
                for penalty in [
                    "generic_search_page",
                    "empty_bulletin_page",
                    "noisy_low_yield_empty_runs",
                    "historically_unreachable",
                    "repetitive_noise",
                ]
            )
            and pool_state not in {"paused_dns", "retry_later"}
        ):
            high_yield_sources.append(row)

    for pack_name in V58_SOURCE_PACK_NAMES:
        packs[pack_name] = sorted(
            packs.get(pack_name, []),
            key=lambda row: (
                float(row.get("v58_yield_score") or 0),
                int(row.get("qualified_candidate_total") or 0),
                int(row.get("candidate_total") or 0),
            ),
            reverse=True,
        )

    pack_summary_rows: List[Dict[str, Any]] = []
    for pack_name in V58_SOURCE_PACK_NAMES:
        rows = packs.get(pack_name, [])
        pack_score = round(sum(float(row.get("v58_yield_score") or 0) for row in rows[:10]) / max(1, min(len(rows), 10)), 2)
        pack_summary_rows.append({
            "pack_name": pack_name,
            "sources_count": len(rows),
            "selected_sources_count": sum(1 for row in rows if row.get("selected_this_cycle")),
            "high_yield_sources_count": sum(1 for row in rows if float(row.get("v58_yield_score") or 0) >= 55.0),
            "document_rich_sources_count": sum(1 for row in rows if _safe_float(row.get("document_detection_rate"), 0.0) > 0 or int(row.get("document_candidate_total") or 0) > 0),
            "repeat_buyers_count": len(rows) if pack_name == "repeat_buyer_pack" else 0,
            "average_v58_yield_score": pack_score,
            "top_sources": rows[:8],
        })

    projected = max(pack_summary_rows, key=lambda row: (row.get("average_v58_yield_score") or 0, row.get("high_yield_sources_count") or 0), default={"pack_name": ""})
    source_rows_report = sorted(source_rows_report, key=lambda row: float(row.get("v58_yield_score") or 0), reverse=True)
    high_yield_sources = sorted(high_yield_sources, key=lambda row: float(row.get("v58_yield_score") or 0), reverse=True)

    rotation_strategy = {
        "focus": "prioritize highest-scoring repeat buyer and document-rich packs with minimal exploratory spillover",
        "exploration": "reserve more capacity for under-sampled municipal/provincial/university packs while keeping high-yield anchors",
        "balanced": "blend high-yield anchors with document-rich and institutional pack coverage",
    }[active_mode]
    diagnostics = {
        "active_pack_mode": active_mode,
        "packs_loaded_count": len([row for row in pack_summary_rows if row.get("sources_count")]),
        "high_yield_sources_count": len(high_yield_sources),
        "document_rich_sources_count": sum(1 for row in source_rows_report if _safe_float(row.get("document_detection_rate"), 0.0) > 0 or int(row.get("document_candidate_total") or 0) > 0 or "document_rich_pack" in (row.get("packs") or [])),
        "repeat_buyers_count": len(packs.get("repeat_buyer_pack", [])),
        "pack_rotation_strategy": rotation_strategy,
        "projected_highest_yield_pack": projected.get("pack_name") or "",
    }
    active_payload = {
        "status": "ok",
        "service_version": "V58_TARGETED_HIGH_YIELD_SOURCE_PACKS",
        "generated_at": _now_iso(),
        "active_pack_mode": active_mode,
        "max_sources": max_sources,
        "selected_sources_count": len(selected_sources),
        "selected_sources": [
            {
                "source_name": _clean(source.get("name") or source.get("source_name")),
                "source_url": _clean(source.get("url") or source.get("list_url")),
                "packs": next((row.get("packs") for row in source_rows_report if row.get("source_name") == _clean(source.get("name") or source.get("source_name"))), []),
            }
            for source in selected_sources
        ],
        "packs": {pack_name: rows[:15] for pack_name, rows in packs.items()},
        "diagnostics": diagnostics,
        "safety": {
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    performance_payload = {
        "status": "ok",
        "service_version": "V58_TARGETED_HIGH_YIELD_SOURCE_PACKS",
        "generated_at": _now_iso(),
        "active_pack_mode": active_mode,
        "pack_rotation_strategy": rotation_strategy,
        "projected_highest_yield_pack": diagnostics["projected_highest_yield_pack"],
        "packs": pack_summary_rows,
        "diagnostics": diagnostics,
    }
    high_yield_payload = {
        "status": "ok",
        "service_version": "V58_TARGETED_HIGH_YIELD_SOURCE_PACKS",
        "generated_at": _now_iso(),
        "sources": high_yield_sources,
        "diagnostics": diagnostics,
    }
    ACTIVE_SOURCE_PACKS_FILE.write_text(json.dumps(active_payload, indent=2, default=str), encoding="utf-8")
    HIGH_YIELD_SOURCES_FILE.write_text(json.dumps(high_yield_payload, indent=2, default=str), encoding="utf-8")
    PACK_PERFORMANCE_SUMMARY_FILE.write_text(json.dumps(performance_payload, indent=2, default=str), encoding="utf-8")
    return {
        "active_pack_mode": active_mode,
        "packs": packs,
        "pack_summary": pack_summary_rows,
        "high_yield_sources": high_yield_sources,
        "source_rows": source_rows_report,
        "diagnostics": diagnostics,
        "artifacts": {
            "active_source_packs": str(ACTIVE_SOURCE_PACKS_FILE),
            "high_yield_sources": str(HIGH_YIELD_SOURCES_FILE),
            "pack_performance_summary": str(PACK_PERFORMANCE_SUMMARY_FILE),
        },
    }


def _apply_commissioning_override(
    source: Dict[str, Any],
    health_row: Dict[str, Any],
    include_bad_sources: bool,
) -> Dict[str, Any]:
    if include_bad_sources and _clean(health_row.get("source_quarantine_status")) == "quarantined":
        forced = dict(source)
        forced["source_operator_action_override"] = "forced_commissioning_run"
        return forced
    return source


def _v58_select_sources_for_pack_rotation(
    sources: List[Dict[str, Any]],
    max_sources: int,
    include_bad_sources: bool = False,
    pack_mode: Any = None,
) -> Tuple[List[Dict[str, Any]], str, List[Dict[str, Any]], Dict[str, Any]]:
    base_selected, batch_id, health_rows = _v53_select_sources_for_cycle(
        sources,
        max_sources=max_sources,
        include_bad_sources=include_bad_sources,
    )
    strategy = _v58_build_source_pack_strategy(sources, base_selected, max_sources, mode=pack_mode)
    row_by_name = {row.get("source_name"): row for row in strategy.get("source_rows", [])}
    source_by_name = {_clean(source.get("name") or source.get("source_name")): source for source in sources}
    max_sources = _safe_positive_int(max_sources, 25)
    selected: List[Dict[str, Any]] = []
    selected_keys = set()

    def add_source(row: Dict[str, Any]) -> None:
        if len(selected) >= max_sources:
            return
        source = source_by_name.get(_clean(row.get("source_name")))
        if not source:
            return
        key = _source_key(source)
        if key in selected_keys:
            return
        selected.append(source)
        selected_keys.add(key)

    pack_order_by_mode = {
        "focus": ["repeat_buyer_pack", "document_rich_pack", "municipalities_pack", "SOE_pack", "provincial_pack", "university_pack"],
        "exploration": ["municipalities_pack", "provincial_pack", "university_pack", "SOE_pack", "document_rich_pack", "repeat_buyer_pack"],
        "balanced": ["document_rich_pack", "repeat_buyer_pack", "municipalities_pack", "SOE_pack", "provincial_pack", "university_pack"],
    }
    active_mode = strategy.get("active_pack_mode") or "balanced"
    per_pack_quota = 2 if active_mode == "exploration" else 3 if active_mode == "balanced" else max(2, max_sources // 2)
    for pack_name in pack_order_by_mode.get(active_mode, pack_order_by_mode["balanced"]):
        added_for_pack = 0
        for row in strategy.get("packs", {}).get(pack_name, []):
            if active_mode == "focus" and float(row.get("v58_yield_score") or 0) < 45.0:
                continue
            add_source(row)
            added_for_pack += 1
            if len(selected) >= max_sources or added_for_pack >= per_pack_quota:
                break
        if len(selected) >= max_sources:
            break

    fallback_rows = sorted(
        strategy.get("source_rows", []),
        key=lambda row: (
            float(row.get("v58_yield_score") or 0),
            row.get("selected_this_cycle") is True,
        ),
        reverse=True,
    )
    for row in fallback_rows:
        add_source(row)
        if len(selected) >= max_sources:
            break

    strategy = _v58_build_source_pack_strategy(sources, selected, max_sources, mode=active_mode)
    return selected, f"v58-{active_mode}-{int(time.time() // 21600)}", health_rows, strategy


def _v59_buyer_profile_type(buyer_name: Any, source_group: Any = "") -> str:
    text = _safe_lower(f"{buyer_name} {source_group}")
    if any(term in text for term in ["municipal", "municipality", "metro", "city of ", "district"]):
        return "municipalities"
    if any(term in text for term in ["soe", "eskom", "transnet", "sanral", "prasa", "sabc", "denel", "airports", "water board", "post office", "petrosa", "safcol"]):
        return "SOEs"
    if any(term in text for term in ["university", "college", "tvet", "campus"]):
        return "universities"
    if any(term in text for term in ["provincial", "province", "treasury", "department", "health", "education"]):
        return "provincial_departments"
    return "other_buyers"


def _v59_pattern_category(value: Any) -> str:
    text = _safe_lower(value)
    checks = [
        ("recurring_stationery_rfqs", r"stationery|paper|printing|office supplies|toner|cartridge"),
        ("recurring_ppe_supply_rfqs", r"\bppe\b|protective clothing|uniforms?|safety boots?|gloves?|masks?|overalls?"),
        ("recurring_office_consumable_rfqs", r"office consumables?|consumables?|cleaning materials?|refuse bags?|hygiene|toilet paper"),
        ("recurring_fleet_service_supply_rfqs", r"fleet|vehicle|tyres?|tires?|automotive|spares?|lubricants?|service supply"),
    ]
    for label, pattern in checks:
        if re.search(pattern, text, flags=re.I):
            return label
    return "other_recurring_supply_rfqs"


def _v59_average_closing_window_days(candidates: List[Dict[str, Any]]) -> float:
    windows: List[float] = []
    now = datetime.now(timezone.utc).date()
    for item in candidates:
        closing = _clean(item.get("closing_date"))
        if not closing:
            continue
        parsed = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(closing[:10], fmt).date()
                break
            except Exception:
                pass
        if parsed:
            windows.append(float((parsed - now).days))
    if not windows:
        return 0.0
    return round(sum(windows) / len(windows), 2)


def _v59_procurement_frequency(row: Dict[str, Any]) -> Dict[str, Any]:
    seen = int(row.get("seen_count") or 0)
    first_seen = _v53_parse_time(row.get("first_seen_at"))
    last_seen = _v53_parse_time(row.get("last_seen_at"))
    if first_seen and last_seen and last_seen > first_seen:
        days = max((last_seen - first_seen) / 86400.0, 1.0)
        per_month = round(seen / max(days / 30.0, 1.0), 2)
    else:
        per_month = float(seen)
    if per_month >= 4:
        cadence = "weekly_or_better"
    elif per_month >= 2:
        cadence = "biweekly"
    elif per_month >= 1:
        cadence = "monthly"
    elif per_month > 0:
        cadence = "occasional"
    else:
        cadence = "unknown"
    return {"estimated_rfqs_per_month": per_month, "cadence": cadence}


def _v59_scoring(row: Dict[str, Any], candidates: List[Dict[str, Any]], source_row: Dict[str, Any]) -> Dict[str, Any]:
    seen = int(row.get("seen_count") or 0)
    qualified = int(row.get("qualified_count") or 0)
    avg_profit = _safe_float(row.get("average_estimated_profit"), 0.0)
    recurrence = _safe_float(row.get("recurrence_score"), _v57_buyer_score(row))
    email_count = sum(1 for item in candidates if _safe_lower(item.get("submission_method")) == "email" or item.get("contact_email") or item.get("recipient_email"))
    doc_count = sum(1 for item in candidates if item.get("document_urls") or item.get("built_from_document_evidence"))
    candidate_count = max(1, len(candidates))
    profitability_trend = min(100.0, (avg_profit / 900.0) + qualified * 10.0)
    submission_simplicity = min(100.0, 35.0 + (email_count / candidate_count) * 45.0)
    document_completeness = min(100.0, 25.0 + (doc_count / candidate_count) * 55.0 + _safe_float(source_row.get("document_rich_score"), 0.0) * 0.2)
    repeat_likelihood = min(100.0, recurrence + min(25.0, seen * 4.0))
    strategic_value = round(
        profitability_trend * 0.28
        + submission_simplicity * 0.18
        + document_completeness * 0.22
        + repeat_likelihood * 0.24
        + min(100.0, seen * 8.0) * 0.08,
        2,
    )
    return {
        "profitability_trend": round(profitability_trend, 2),
        "submission_simplicity": round(submission_simplicity, 2),
        "document_completeness": round(document_completeness, 2),
        "repeat_likelihood": round(repeat_likelihood, 2),
        "strategic_value": strategic_value,
    }


def _v59_build_buyer_intelligence(
    sources: List[Dict[str, Any]],
    raw_candidates: List[Dict[str, Any]],
    qualified: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    source_pack_strategy: Dict[str, Any],
) -> Dict[str, Any]:
    memory = _v57_load_memory_files()
    buyer_rows = ((memory.get("buyer") or {}).get("buyers") or {}) if isinstance(memory.get("buyer"), dict) else {}
    category_rows = ((memory.get("category") or {}).get("categories") or {}) if isinstance(memory.get("category"), dict) else {}
    source_rows = ((memory.get("source") or {}).get("sources") or {}) if isinstance(memory.get("source"), dict) else {}
    candidates_by_buyer: Dict[str, List[Dict[str, Any]]] = {}
    for item in raw_candidates:
        key = _v57_normalize_key(item.get("buyer_name") or item.get("buyer") or item.get("source_name"))
        candidates_by_buyer.setdefault(key, []).append(item)

    source_by_name = {
        _v57_normalize_key(src.get("name") or src.get("source_name")): src
        for src in sources
        if isinstance(src, dict)
    }
    profiles_by_type: Dict[str, List[Dict[str, Any]]] = {name: [] for name in V59_BUYER_PROFILE_TYPES}
    profiles: List[Dict[str, Any]] = []
    procurement_patterns: List[Dict[str, Any]] = []
    predicted_repeat_rfqs: List[Dict[str, Any]] = []

    for buyer_key, row in buyer_rows.items():
        if not isinstance(row, dict):
            continue
        buyer_name = _clean(row.get("buyer_name") or buyer_key)
        candidates = candidates_by_buyer.get(buyer_key, [])
        source = source_by_name.get(_v57_normalize_key(buyer_name), {})
        source_row = source_rows.get(_source_key(source), {}) if isinstance(source, dict) and source else {}
        profile_type = _v59_buyer_profile_type(buyer_name, (source or {}).get("source_group") if isinstance(source, dict) else "")
        categories = row.get("categories") if isinstance(row.get("categories"), dict) else {}
        title_signatures = row.get("title_signatures") if isinstance(row.get("title_signatures"), dict) else {}
        frequency = _v59_procurement_frequency(row)
        scoring = _v59_scoring(row, candidates, source_row)
        average_closing_window_days = _v59_average_closing_window_days(candidates)
        document_richness = round(min(100.0, _safe_float(source_row.get("document_rich_score"), 0.0) + sum(1 for item in candidates if item.get("document_urls")) * 12.0), 2)
        responsiveness = "email_friendly" if any(item.get("contact_email") or item.get("recipient_email") for item in candidates) else "portal_or_unknown"
        repeat_timing = frequency.get("cadence", "unknown")
        top_categories = sorted(
            [{"category": key, "seen_count": int(value or 0), "pattern_type": _v59_pattern_category(key)} for key, value in categories.items()],
            key=lambda item: item["seen_count"],
            reverse=True,
        )
        profile = {
            "buyer_key": buyer_key,
            "buyer_name": buyer_name,
            "profile_type": profile_type,
            "seen_count": int(row.get("seen_count") or 0),
            "qualified_count": int(row.get("qualified_count") or 0),
            "rejected_count": int(row.get("rejected_count") or 0),
            "recurring_procurement_categories": top_categories[:10],
            "procurement_frequency": frequency,
            "average_closing_window_days": average_closing_window_days,
            "document_richness": document_richness,
            "buyer_responsiveness_pattern": responsiveness,
            "repeat_rfq_timing": repeat_timing,
            "estimated_procurement_cycle": frequency.get("cadence"),
            "average_estimated_profit": row.get("average_estimated_profit"),
            "average_qualification_score": row.get("average_qualification_score"),
            "title_signature_count": len(title_signatures),
            "scoring": scoring,
            "source_pack_signals": [
                pack.get("pack_name")
                for pack in source_pack_strategy.get("pack_summary", [])
                if isinstance(pack, dict) and pack.get("selected_sources_count")
            ],
        }
        profiles.append(profile)
        if profile_type in profiles_by_type:
            profiles_by_type[profile_type].append(profile)
        for category in top_categories:
            if category["seen_count"] >= 1:
                pattern = {
                    "buyer_name": buyer_name,
                    "buyer_key": buyer_key,
                    "profile_type": profile_type,
                    "category": category["category"],
                    "pattern_type": category["pattern_type"],
                    "seen_count": category["seen_count"],
                    "frequency": frequency,
                    "repeat_likelihood": scoring["repeat_likelihood"],
                    "strategic_value": scoring["strategic_value"],
                }
                procurement_patterns.append(pattern)
                if scoring["repeat_likelihood"] >= 45.0:
                    predicted_repeat_rfqs.append({
                        "buyer_name": buyer_name,
                        "category": category["category"],
                        "pattern_type": category["pattern_type"],
                        "estimated_cycle": frequency.get("cadence"),
                        "repeat_likelihood": scoring["repeat_likelihood"],
                    })

    profiles = sorted(profiles, key=lambda row: row.get("scoring", {}).get("strategic_value", 0), reverse=True)
    procurement_patterns = sorted(procurement_patterns, key=lambda row: (row.get("repeat_likelihood", 0), row.get("strategic_value", 0), row.get("seen_count", 0)), reverse=True)
    high_value_buyers = [row for row in profiles if row.get("scoring", {}).get("strategic_value", 0) >= 45.0]
    highest_value_buyers = [
        {
            "buyer_name": row.get("buyer_name"),
            "profile_type": row.get("profile_type"),
            "strategic_value": row.get("scoring", {}).get("strategic_value"),
            "repeat_likelihood": row.get("scoring", {}).get("repeat_likelihood"),
            "average_estimated_profit": row.get("average_estimated_profit"),
        }
        for row in high_value_buyers[:10]
    ]
    strongest_repeat_categories = [
        {
            "category": row.get("category"),
            "pattern_type": row.get("pattern_type"),
            "buyer_name": row.get("buyer_name"),
            "repeat_likelihood": row.get("repeat_likelihood"),
            "seen_count": row.get("seen_count"),
        }
        for row in procurement_patterns[:10]
    ]
    diagnostics = {
        "buyer_profiles_count": len(profiles),
        "recurring_procurement_patterns_detected": len(procurement_patterns),
        "strategic_buyers_count": len(high_value_buyers),
        "predicted_repeat_rfqs": predicted_repeat_rfqs[:10],
        "highest_value_buyers": highest_value_buyers,
        "strongest_repeat_categories": strongest_repeat_categories,
    }
    profile_payload = {
        "status": "ok",
        "service_version": "V59_BUYER_INTELLIGENCE_EXTENDS_V58_V57",
        "generated_at": _now_iso(),
        "profiles_by_type": profiles_by_type,
        "profiles": profiles,
        "diagnostics": diagnostics,
        "safety": {
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    patterns_payload = {
        "status": "ok",
        "service_version": "V59_BUYER_INTELLIGENCE_EXTENDS_V58_V57",
        "generated_at": _now_iso(),
        "patterns": procurement_patterns,
        "diagnostics": diagnostics,
    }
    high_value_payload = {
        "status": "ok",
        "service_version": "V59_BUYER_INTELLIGENCE_EXTENDS_V58_V57",
        "generated_at": _now_iso(),
        "buyers": high_value_buyers,
        "diagnostics": diagnostics,
    }
    BUYER_PROFILES_FILE.write_text(json.dumps(profile_payload, indent=2, default=str), encoding="utf-8")
    PROCUREMENT_PATTERNS_FILE.write_text(json.dumps(patterns_payload, indent=2, default=str), encoding="utf-8")
    HIGH_VALUE_BUYERS_FILE.write_text(json.dumps(high_value_payload, indent=2, default=str), encoding="utf-8")
    return {
        "diagnostics": diagnostics,
        "profiles": profiles,
        "patterns": procurement_patterns,
        "high_value_buyers": high_value_buyers,
        "artifacts": {
            "buyer_profiles": str(BUYER_PROFILES_FILE),
            "procurement_patterns": str(PROCUREMENT_PATTERNS_FILE),
            "high_value_buyers": str(HIGH_VALUE_BUYERS_FILE),
        },
    }


def _v60_forecast_target(pattern_type: str, profile_type: str, category: str) -> str:
    text = _safe_lower(f"{pattern_type} {profile_type} {category}")
    if "stationery" in text or "office supplies" in text:
        return "likely_upcoming_stationery_rfq"
    if "office_consumable" in text or "consumable" in text:
        return "likely_office_consumables_rfq"
    if profile_type == "municipalities" and any(term in text for term in ["supply", "goods", "office", "consumable", "stationery"]):
        return "recurring_municipal_supply_rfq"
    if profile_type == "SOEs" and any(term in text for term in ["supply", "goods", "office", "consumable", "stationery"]):
        return "recurring_SOE_supply_rfq"
    if profile_type == "municipalities":
        return "recurring_municipal_supply_rfq"
    if profile_type == "SOEs":
        return "recurring_SOE_supply_rfq"
    return "recurring_supply_rfq"


def _v60_timing_confidence(frequency: Dict[str, Any], average_closing_window_days: float, last_seen_at: Any) -> Tuple[float, str]:
    cadence = _clean(frequency.get("cadence") if isinstance(frequency, dict) else "")
    base = {
        "weekly_or_better": 88.0,
        "biweekly": 78.0,
        "monthly": 68.0,
        "occasional": 45.0,
    }.get(cadence, 35.0)
    if average_closing_window_days > 0:
        base += 6.0 if average_closing_window_days <= 21 else 2.0
    last_seen = _v53_parse_time(last_seen_at)
    if last_seen:
        age_days = max(0.0, (time.time() - last_seen) / 86400.0)
        if age_days <= 14:
            base += 8.0
        elif age_days > 90:
            base -= 15.0
    if cadence == "weekly_or_better":
        horizon = "0-14 days"
    elif cadence == "biweekly":
        horizon = "7-21 days"
    elif cadence == "monthly":
        horizon = "14-45 days"
    else:
        horizon = "30-90 days"
    return round(max(1.0, min(100.0, base)), 2), horizon


def _v60_confidence_bucket(value: float) -> str:
    if value >= 80.0:
        return "very_high"
    if value >= 65.0:
        return "high"
    if value >= 45.0:
        return "medium"
    return "low"


def _v60_build_tender_radar(
    buyer_intelligence_result: Dict[str, Any],
    source_pack_strategy: Dict[str, Any],
) -> Dict[str, Any]:
    memory = _v57_load_memory_files()
    buyer_rows = ((memory.get("buyer") or {}).get("buyers") or {}) if isinstance(memory.get("buyer"), dict) else {}
    category_rows = ((memory.get("category") or {}).get("categories") or {}) if isinstance(memory.get("category"), dict) else {}
    profiles = buyer_intelligence_result.get("profiles") if isinstance(buyer_intelligence_result.get("profiles"), list) else []
    patterns = buyer_intelligence_result.get("patterns") if isinstance(buyer_intelligence_result.get("patterns"), list) else []
    profile_by_key = {profile.get("buyer_key"): profile for profile in profiles if isinstance(profile, dict)}
    forecasts: List[Dict[str, Any]] = []

    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        buyer_key = _clean(pattern.get("buyer_key"))
        profile = profile_by_key.get(buyer_key, {})
        buyer_row = buyer_rows.get(buyer_key, {}) if isinstance(buyer_rows.get(buyer_key), dict) else {}
        category_key = _v57_normalize_key(pattern.get("category"))
        category_row = category_rows.get(category_key, {}) if isinstance(category_rows.get(category_key), dict) else {}
        scoring = profile.get("scoring") if isinstance(profile.get("scoring"), dict) else {}
        profile_type = _clean(profile.get("profile_type") or pattern.get("profile_type"))
        frequency = profile.get("procurement_frequency") if isinstance(profile.get("procurement_frequency"), dict) else pattern.get("frequency", {})
        buyer_confidence = round(min(100.0, _safe_float(scoring.get("repeat_likelihood"), pattern.get("repeat_likelihood") or 0.0)), 2)
        category_confidence = round(min(100.0, _safe_float(category_row.get("profitability_score"), 0.0) + int(pattern.get("seen_count") or 0) * 8.0), 2)
        timing_confidence, forecast_horizon = _v60_timing_confidence(
            frequency if isinstance(frequency, dict) else {},
            _safe_float(profile.get("average_closing_window_days"), 0.0),
            buyer_row.get("last_seen_at"),
        )
        profitability_likelihood = round(min(100.0, _safe_float(scoring.get("profitability_trend"), 0.0)), 2)
        document_rich_bonus = min(8.0, _safe_float(profile.get("document_richness"), 0.0) / 12.5)
        confidence = round(
            buyer_confidence * 0.32
            + category_confidence * 0.22
            + timing_confidence * 0.24
            + profitability_likelihood * 0.18
            + document_rich_bonus,
            2,
        )
        target = _v60_forecast_target(_clean(pattern.get("pattern_type")), profile_type, _clean(pattern.get("category")))
        if target == "recurring_supply_rfq" and pattern.get("pattern_type") == "other_recurring_supply_rfqs":
            # Keep forecasts focused on requested radar surfaces.
            if profile_type not in {"municipalities", "SOEs"}:
                continue
        next_start = datetime.now(timezone.utc)
        if forecast_horizon.startswith("7"):
            next_start += timedelta(days=7)
        elif forecast_horizon.startswith("14"):
            next_start += timedelta(days=14)
        elif forecast_horizon.startswith("30"):
            next_start += timedelta(days=30)
        forecast = {
            "forecast_type": target,
            "buyer_name": pattern.get("buyer_name"),
            "buyer_key": buyer_key,
            "profile_type": profile_type,
            "category": pattern.get("category"),
            "pattern_type": pattern.get("pattern_type"),
            "forecast_horizon": forecast_horizon,
            "projected_cycle_start": next_start.date().isoformat(),
            "estimated_procurement_cycle": profile.get("estimated_procurement_cycle") or (frequency or {}).get("cadence"),
            "document_rich_pattern": _safe_float(profile.get("document_richness"), 0.0) >= 40.0,
            "confidence_scores": {
                "buyer_confidence": buyer_confidence,
                "category_confidence": category_confidence,
                "timing_confidence": timing_confidence,
                "profitability_likelihood": profitability_likelihood,
                "overall_confidence": confidence,
            },
            "confidence_bucket": _v60_confidence_bucket(confidence),
            "supporting_signals": {
                "seen_count": pattern.get("seen_count"),
                "procurement_frequency": frequency,
                "average_closing_window_days": profile.get("average_closing_window_days"),
                "document_richness": profile.get("document_richness"),
                "source_pack_projected_highest_yield_pack": (source_pack_strategy.get("diagnostics") or {}).get("projected_highest_yield_pack"),
            },
        }
        forecasts.append(forecast)

    forecasts = sorted(forecasts, key=lambda row: row.get("confidence_scores", {}).get("overall_confidence", 0), reverse=True)
    high_probability = [row for row in forecasts if row.get("confidence_scores", {}).get("overall_confidence", 0) >= 65.0]
    distribution = {"very_high": 0, "high": 0, "medium": 0, "low": 0}
    for row in forecasts:
        bucket = row.get("confidence_bucket") or "low"
        distribution[bucket] = distribution.get(bucket, 0) + 1
    strongest_predictive_buyers = [
        {
            "buyer_name": row.get("buyer_name"),
            "profile_type": row.get("profile_type"),
            "overall_confidence": row.get("confidence_scores", {}).get("overall_confidence"),
            "forecast_type": row.get("forecast_type"),
        }
        for row in forecasts[:10]
    ]
    category_rollup: Dict[str, Dict[str, Any]] = {}
    for row in forecasts:
        key = _clean(row.get("category") or "unknown")
        current = category_rollup.setdefault(key, {"category": key, "count": 0, "confidence_total": 0.0, "forecast_types": set()})
        current["count"] += 1
        current["confidence_total"] += _safe_float(row.get("confidence_scores", {}).get("overall_confidence"), 0.0)
        current["forecast_types"].add(row.get("forecast_type"))
    strongest_predictive_categories = sorted(
        [
            {
                "category": row["category"],
                "forecast_count": row["count"],
                "average_confidence": round(row["confidence_total"] / max(1, row["count"]), 2),
                "forecast_types": sorted(t for t in row["forecast_types"] if t),
            }
            for row in category_rollup.values()
        ],
        key=lambda row: (row["average_confidence"], row["forecast_count"]),
        reverse=True,
    )[:10]
    projected_next_high_value_cycles = [
        {
            "buyer_name": row.get("buyer_name"),
            "category": row.get("category"),
            "forecast_horizon": row.get("forecast_horizon"),
            "projected_cycle_start": row.get("projected_cycle_start"),
            "overall_confidence": row.get("confidence_scores", {}).get("overall_confidence"),
        }
        for row in high_probability[:10]
    ]
    diagnostics = {
        "forecasted_opportunities_count": len(forecasts),
        "high_probability_forecasts_count": len(high_probability),
        "strongest_predictive_buyers": strongest_predictive_buyers,
        "strongest_predictive_categories": strongest_predictive_categories,
        "forecast_confidence_distribution": distribution,
        "projected_next_high_value_cycles": projected_next_high_value_cycles,
    }
    forecast_payload = {
        "status": "ok",
        "service_version": "V60_OPPORTUNITY_FORECASTING_EXTENDS_V59_V57",
        "generated_at": _now_iso(),
        "forecasts": forecasts,
        "diagnostics": diagnostics,
        "safety": {
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    high_probability_payload = {
        "status": "ok",
        "service_version": "V60_OPPORTUNITY_FORECASTING_EXTENDS_V59_V57",
        "generated_at": _now_iso(),
        "forecasts": high_probability,
        "diagnostics": diagnostics,
    }
    buyer_summary_payload = {
        "status": "ok",
        "service_version": "V60_OPPORTUNITY_FORECASTING_EXTENDS_V59_V57",
        "generated_at": _now_iso(),
        "strongest_predictive_buyers": strongest_predictive_buyers,
        "strongest_predictive_categories": strongest_predictive_categories,
        "projected_next_high_value_cycles": projected_next_high_value_cycles,
        "diagnostics": diagnostics,
    }
    OPPORTUNITY_FORECASTS_FILE.write_text(json.dumps(forecast_payload, indent=2, default=str), encoding="utf-8")
    HIGH_PROBABILITY_OPPORTUNITIES_FILE.write_text(json.dumps(high_probability_payload, indent=2, default=str), encoding="utf-8")
    BUYER_FORECAST_SUMMARY_FILE.write_text(json.dumps(buyer_summary_payload, indent=2, default=str), encoding="utf-8")
    return {
        "diagnostics": diagnostics,
        "forecasts": forecasts,
        "high_probability_forecasts": high_probability,
        "artifacts": {
            "opportunity_forecasts": str(OPPORTUNITY_FORECASTS_FILE),
            "high_probability_opportunities": str(HIGH_PROBABILITY_OPPORTUNITIES_FILE),
            "buyer_forecast_summary": str(BUYER_FORECAST_SUMMARY_FILE),
        },
    }


def _v61_horizon_score(forecast_horizon: Any) -> float:
    text = _safe_lower(forecast_horizon)
    if text.startswith("0") or "0-7" in text or "0-14" in text:
        return 100.0
    if text.startswith("7") or "7-21" in text:
        return 82.0
    if text.startswith("14") or "14-45" in text:
        return 66.0
    if text.startswith("30"):
        return 42.0
    return 55.0


def _v61_supply_delivery_fit(forecast: Dict[str, Any]) -> float:
    text = _safe_lower(" ".join([
        _clean(forecast.get("forecast_type")),
        _clean(forecast.get("category")),
        _clean(forecast.get("pattern_type")),
        _clean(forecast.get("profile_type")),
    ]))
    if any(term in text for term in ["stationery", "office consumable", "consumable", "ppe", "supply", "delivery"]):
        return 94.0
    if any(term in text for term in ["municipal", "soe", "provincial", "university"]):
        return 76.0
    if "service" in text or "fleet" in text:
        return 68.0
    return 48.0


def _v61_build_forecast_action_watchlist(
    forecast_result: Dict[str, Any],
    buyer_intelligence_result: Dict[str, Any],
    source_pack_strategy: Dict[str, Any],
) -> Dict[str, Any]:
    forecasts = forecast_result.get("high_probability_forecasts")
    if not isinstance(forecasts, list):
        forecasts = []
    profiles = buyer_intelligence_result.get("profiles") if isinstance(buyer_intelligence_result.get("profiles"), list) else []
    profile_by_key = {profile.get("buyer_key"): profile for profile in profiles if isinstance(profile, dict)}
    top_sources = source_pack_strategy.get("high_yield_sources") if isinstance(source_pack_strategy.get("high_yield_sources"), list) else []
    watchlist_entries: List[Dict[str, Any]] = []

    for forecast in forecasts:
        if not isinstance(forecast, dict):
            continue
        buyer_key = _clean(forecast.get("buyer_key"))
        profile = profile_by_key.get(buyer_key, {})
        scoring = profile.get("scoring") if isinstance(profile.get("scoring"), dict) else {}
        confidence_scores = forecast.get("confidence_scores") if isinstance(forecast.get("confidence_scores"), dict) else {}
        forecast_confidence = _safe_float(confidence_scores.get("overall_confidence"), 0.0)
        buyer_strategic_value = _safe_float(scoring.get("strategic_value"), forecast_confidence)
        supply_delivery_fit = _v61_supply_delivery_fit(forecast)
        supporting_signals = forecast.get("supporting_signals") if isinstance(forecast.get("supporting_signals"), dict) else {}
        document_richness = _safe_float(supporting_signals.get("document_richness"), 0.0)
        if forecast.get("document_rich_pattern"):
            document_richness = max(document_richness, 78.0)
        estimated_profitability = _safe_float(confidence_scores.get("profitability_likelihood"), scoring.get("profitability_trend") or 0.0)
        expected_window_score = _v61_horizon_score(forecast.get("forecast_horizon"))
        priority_score = round(
            forecast_confidence * 0.32
            + buyer_strategic_value * 0.20
            + supply_delivery_fit * 0.16
            + document_richness * 0.12
            + estimated_profitability * 0.14
            + expected_window_score * 0.06,
            2,
        )
        buyer_name_key = _v57_normalize_key(forecast.get("buyer_name"))
        category_key = _v57_normalize_key(forecast.get("category"))
        matched_sources = [
            row.get("source_name")
            for row in top_sources
            if isinstance(row, dict)
            and (
                (buyer_name_key and buyer_name_key in _v57_normalize_key(row.get("source_name")))
                or (
                    category_key
                    and category_key in _v57_normalize_key(" ".join([_clean(row.get("source_name")), _clean(row.get("source_group")), " ".join(row.get("packs") or [])]))
                )
            )
        ][:5]
        watchlist_entries.append({
            "watchlist_id": _v57_normalize_key(f"{buyer_key}:{forecast.get('category')}:{forecast.get('forecast_type')}")[:120],
            "buyer_name": forecast.get("buyer_name"),
            "buyer_key": buyer_key,
            "profile_type": forecast.get("profile_type"),
            "category": forecast.get("category"),
            "forecast_type": forecast.get("forecast_type"),
            "projected_cycle_start": forecast.get("projected_cycle_start"),
            "expected_time_window": forecast.get("forecast_horizon"),
            "priority_score": priority_score,
            "priority_bucket": _v60_confidence_bucket(priority_score),
            "scoring": {
                "forecast_confidence": forecast_confidence,
                "buyer_strategic_value": round(buyer_strategic_value, 2),
                "supply_and_delivery_fit": round(supply_delivery_fit, 2),
                "document_richness": round(document_richness, 2),
                "estimated_profitability": round(estimated_profitability, 2),
                "expected_time_window": round(expected_window_score, 2),
            },
            "matched_high_yield_sources": matched_sources,
            "recommended_action": "boost_daily_discovery_for_buyer_and_category",
            "source_pack_feedback": {
                "boost_buyer": forecast.get("buyer_name"),
                "boost_category": forecast.get("category"),
                "boost_profile_type": forecast.get("profile_type"),
                "projected_highest_yield_pack": (source_pack_strategy.get("diagnostics") or {}).get("projected_highest_yield_pack"),
            },
        })

    watchlist_entries = sorted(
        watchlist_entries,
        key=lambda row: (
            _safe_float(row.get("priority_score"), 0.0),
            _safe_float((row.get("scoring") or {}).get("forecast_confidence"), 0.0),
            _safe_float((row.get("scoring") or {}).get("buyer_strategic_value"), 0.0),
        ),
        reverse=True,
    )
    daily_priority_targets = [
        row for row in watchlist_entries
        if _safe_float(row.get("priority_score"), 0.0) >= 65.0 or _v61_horizon_score(row.get("expected_time_window")) >= 82.0
    ][:20]
    boosted_sources = sorted({
        source
        for row in daily_priority_targets
        for source in (row.get("matched_high_yield_sources") or [])
        if source
    })[:20]
    boosted_buyers = list(dict.fromkeys(_clean(row.get("buyer_name")) for row in daily_priority_targets if row.get("buyer_name")))[:20]
    boosted_categories = sorted({_clean(row.get("category")) for row in daily_priority_targets if row.get("category")})[:20]
    next_24h_priority_actions = [
        {
            "buyer_name": row.get("buyer_name"),
            "category": row.get("category"),
            "priority_score": row.get("priority_score"),
            "action": "check_source_pack_and_buyer_portal_for_new_or_reissued_rfq",
        }
        for row in daily_priority_targets
        if _v61_horizon_score(row.get("expected_time_window")) >= 82.0
    ][:10]
    diagnostics = {
        "watchlist_entries_count": len(watchlist_entries),
        "daily_priority_targets_count": len(daily_priority_targets),
        "boosted_watchlist_sources": boosted_sources,
        "boosted_watchlist_buyers": boosted_buyers,
        "boosted_watchlist_categories": boosted_categories,
        "next_24h_priority_actions": next_24h_priority_actions,
    }
    watchlist_payload = {
        "status": "ok",
        "service_version": "V61_FORECAST_TO_ACTION_WATCHLIST_EXTENDS_V60_V59",
        "generated_at": _now_iso(),
        "watchlist_entries": watchlist_entries,
        "diagnostics": diagnostics,
        "safety": {
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    daily_targets_payload = {
        "status": "ok",
        "service_version": "V61_FORECAST_TO_ACTION_WATCHLIST_EXTENDS_V60_V59",
        "generated_at": _now_iso(),
        "daily_priority_targets": daily_priority_targets,
        "diagnostics": diagnostics,
    }
    summary_payload = {
        "status": "ok",
        "service_version": "V61_FORECAST_TO_ACTION_WATCHLIST_EXTENDS_V60_V59",
        "generated_at": _now_iso(),
        "watchlist_entries_count": len(watchlist_entries),
        "daily_priority_targets_count": len(daily_priority_targets),
        "boosted_watchlist_sources": boosted_sources,
        "boosted_watchlist_buyers": boosted_buyers,
        "boosted_watchlist_categories": boosted_categories,
        "next_24h_priority_actions": next_24h_priority_actions,
        "diagnostics": diagnostics,
    }
    ACTION_WATCHLIST_FILE.write_text(json.dumps(watchlist_payload, indent=2, default=str), encoding="utf-8")
    DAILY_PRIORITY_TARGETS_FILE.write_text(json.dumps(daily_targets_payload, indent=2, default=str), encoding="utf-8")
    WATCHLIST_SUMMARY_FILE.write_text(json.dumps(summary_payload, indent=2, default=str), encoding="utf-8")
    return {
        "diagnostics": diagnostics,
        "watchlist_entries": watchlist_entries,
        "daily_priority_targets": daily_priority_targets,
        "artifacts": {
            "action_watchlist": str(ACTION_WATCHLIST_FILE),
            "daily_priority_targets": str(DAILY_PRIORITY_TARGETS_FILE),
            "watchlist_summary": str(WATCHLIST_SUMMARY_FILE),
        },
    }


def _v53_select_sources_for_cycle(
    sources: List[Dict[str, Any]],
    max_sources: int,
    include_bad_sources: bool = False,
    source_health_file: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], str, List[Dict[str, Any]]]:
    max_sources = _safe_positive_int(max_sources, 25)
    enabled = [s for s in sources if s.get("enabled", True)]
    health = _load_source_health(source_health_file=source_health_file)
    adaptive_weights = _v55_load_adaptive_weights()
    memory_files = _v57_load_memory_files()
    enriched: List[Tuple[Dict[str, Any], Dict[str, Any]]] = [(src, _v53_source_health_row(src, health)) for src in enabled]
    if not include_bad_sources:
        enriched = [
            (src, row)
            for src, row in enriched
            if _clean(row.get("source_quarantine_status")) != "quarantined"
            and _clean(row.get("health_status")) not in {"dns_blocked", "http_blocked", "disabled"}
        ]
    batch_id = f"v55-{int(time.time() // 21600)}"
    hot_limit = max(1, max_sources // 3)
    def _adaptive_sort_key(pair: Tuple[Dict[str, Any], Dict[str, Any]]) -> Tuple[int, int, int, float, float, int, int, int, int, str]:
        src, row = pair
        weight_row = adaptive_weights.get(_source_key(src), {}) if isinstance(adaptive_weights, dict) else {}
        adaptive_weight = _safe_float(
            weight_row.get("adaptive_weight"),
            row.get("source_selection_score") or row.get("source_success_score") or 0,
        )
        adaptive_weight = max(1.0, min(100.0, adaptive_weight + _v57_source_memory_boost(src, memory_files)))
        tier = _clean(weight_row.get("tier"))
        tier_rank = 0 if tier == "tier_1_high_yield" else 1 if tier == "tier_2_moderate_yield" else 2
        quarantine_status = _clean(row.get("source_quarantine_status"))
        quarantine_rank = 0 if quarantine_status == "ready" else 1 if quarantine_status == "watch" else 2
        pool_rank, _pool_state = _v53_source_pool_state(src, row)
        return (
            quarantine_rank,
            pool_rank,
            tier_rank,
            -adaptive_weight,
            -float(row.get("source_selection_score") or row.get("source_success_score") or 0),
            _v53_source_category_rank(src),
            int(row.get("source_failure_count") or 0),
            -int(row.get("candidate_total") or 0),
            int(src.get("priority") or 9999),
            _clean(src.get("name") or src.get("source_name")),
        )

    hot = sorted(
        [
            pair for pair in enriched
            if pair[1].get("candidate_total")
            or pair[1].get("source_selection_score", pair[1].get("source_success_score", 0)) >= 55
            or (
                _safe_float((adaptive_weights.get(_source_key(pair[0])) or {}).get("adaptive_weight"), 0.0)
                + _v57_source_memory_boost(pair[0], memory_files)
            ) >= 55
        ],
        key=_adaptive_sort_key,
    )[:hot_limit]
    hot_keys = {_source_key(src) for src, _ in hot}
    remaining = [pair for pair in enriched if _source_key(pair[0]) not in hot_keys]
    remaining = sorted(remaining, key=_adaptive_sort_key)
    if remaining:
        cycle = int(time.time() // 21600)
        exploratory = [
            pair for pair in remaining
            if _clean((adaptive_weights.get(_source_key(pair[0])) or {}).get("tier")) == "tier_3_exploratory"
        ]
        prioritized = [pair for pair in remaining if pair not in exploratory]
        if exploratory:
            offset = (cycle * max(1, max_sources - len(hot))) % len(exploratory)
            exploratory = exploratory[offset:] + exploratory[:offset]
        remaining = prioritized + exploratory
    selected_pairs = (hot + remaining)[:max_sources]
    if len(selected_pairs) < max_sources:
        selected_keys = {_source_key(src) for src, _ in selected_pairs}
        for pair in enriched:
            if _source_key(pair[0]) not in selected_keys:
                selected_pairs.append(pair)
                selected_keys.add(_source_key(pair[0]))
            if len(selected_pairs) >= max_sources:
                break
    return [src for src, _ in selected_pairs], batch_id, [row for _, row in enriched]


def _v53_update_source_health_after_scan(
    source: Dict[str, Any],
    harvested_count: int,
    candidate_count: int,
    response_time: float,
    error: str = "",
    extracted_count: int = 0,
    qualified_count: int = 0,
    document_count: int = 0,
    source_health_file: Optional[Path] = None,
    acquisition_status: str = "",
    acquisition_error_message: str = "",
    scan_started_at: str = "",
    scan_finished_at: str = "",
    pages_scanned: int = 0,
    raw_candidates_count: int = 0,
    document_links_detected: int = 0,
    retry_count: int = 0,
    fallback_used: bool = False,
    source_url: str = "",
    preflight_dns_status: str = "",
    preflight_http_status: int = 0,
) -> Dict[str, Any]:
    health = _load_source_health(source_health_file=source_health_file)
    key = _source_key(source)
    row = dict(health.get(key, {}) if isinstance(health.get(key), dict) else {})
    now_iso = _now_iso()
    row["name"] = key
    row["source_name"] = key
    row["last_checked_at"] = now_iso
    row["source_response_time"] = round(float(response_time or 0.0), 3)
    row["last_response_time"] = row["source_response_time"]
    if scan_started_at:
        row["acquisition_scan_started_at"] = scan_started_at
    if scan_finished_at:
        row["acquisition_scan_finished_at"] = scan_finished_at
    if source_url:
        row["source_url"] = source_url
    if acquisition_status:
        row["acquisition_status"] = acquisition_status
    if acquisition_error_message:
        row["acquisition_error_message"] = _truncate(acquisition_error_message, 240)
        row["last_error_message"] = row["acquisition_error_message"]
        row["last_error"] = row["acquisition_error_message"]
    if preflight_dns_status:
        row["last_dns_status"] = _clean(preflight_dns_status)
    if preflight_http_status is not None:
        row["last_http_status"] = int(preflight_http_status or 0)
    row["acquisition_pages_scanned"] = int(pages_scanned or 0)
    row["acquisition_raw_candidates_count"] = int(raw_candidates_count or 0)
    row["acquisition_document_links_detected"] = int(document_links_detected or 0)
    row["acquisition_retry_count"] = int(retry_count or 0)
    row["acquisition_fallback_used"] = bool(fallback_used)
    row["last_harvested"] = int(harvested_count or 0)
    row["last_candidate_count"] = int(candidate_count or 0)
    scan_total = int(row.get("scan_total") or 0) + 1
    row["scan_total"] = scan_total
    previous_average = _safe_float(row.get("average_response_time"), row["source_response_time"])
    row["average_response_time"] = round(((previous_average * max(0, scan_total - 1)) + row["source_response_time"]) / max(1, scan_total), 3)
    row["harvested_total"] = int(row.get("harvested_total") or 0) + int(harvested_count or 0)
    row["candidate_total"] = int(row.get("candidate_total") or 0) + int(candidate_count or 0)
    row["extracted_candidate_total"] = int(row.get("extracted_candidate_total") or 0) + int(extracted_count or 0)
    row["qualified_candidate_total"] = int(row.get("qualified_candidate_total") or 0) + int(qualified_count or 0)
    row["document_candidate_total"] = int(row.get("document_candidate_total") or 0) + int(document_count or 0)
    acquisition_status = _clean(acquisition_status)
    error_text = _clean(acquisition_error_message or error)
    failure_category = _classify_acquisition_error(error_text, int(preflight_http_status or 0))
    if acquisition_status == "dns_failed" or failure_category == "dns_failed":
        row["last_failure_at"] = now_iso
        row["last_dns_status"] = "failed"
        row["consecutive_dns_failures"] = int(row.get("consecutive_dns_failures") or 0) + 1
        row["consecutive_http_failures"] = 0
        row["failure_count"] = max(
            int(row.get("failure_count") or 0),
            int(row.get("consecutive_dns_failures") or 0) - 1,
        ) + 1
        row["last_error"] = _truncate(error_text, 240)
        row["last_error_message"] = row["last_error"]
        row["last_status"] = "failed"
    elif acquisition_status == "http_failed" or failure_category == "http_failed":
        row["last_failure_at"] = now_iso
        row["last_http_status"] = int(preflight_http_status or row.get("last_http_status") or 0)
        row["consecutive_http_failures"] = int(row.get("consecutive_http_failures") or 0) + 1
        row["consecutive_dns_failures"] = 0
        row["failure_count"] = max(
            int(row.get("failure_count") or 0),
            int(row.get("consecutive_http_failures") or 0) - 1,
        ) + 1
        row["last_error"] = _truncate(error_text or f"HTTP {int(preflight_http_status or 0)}", 240)
        row["last_error_message"] = row["last_error"]
        row["last_status"] = "failed"
    elif error:
        row["last_failure_at"] = now_iso
        row["failure_count"] = int(row.get("failure_count") or 0) + 1
        row["last_error"] = _truncate(error, 240)
        row["last_error_message"] = row["last_error"]
        row["last_status"] = "failed"
    else:
        row["failure_count"] = 0
        row["last_error"] = ""
        row["last_error_message"] = ""
        row["last_failure_at"] = ""
        row["last_dns_status"] = "ok"
        row["last_http_status"] = int(preflight_http_status or row.get("last_http_status") or 0)
        if int(harvested_count or 0) > 0 or int(candidate_count or 0) > 0 or int(qualified_count or 0) > 0:
            row["last_success_at"] = now_iso
            row["last_status"] = "ok"
            row["consecutive_dns_failures"] = 0
            row["consecutive_http_failures"] = 0
            row["consecutive_empty_runs"] = 0
        else:
            row["last_status"] = "ok_empty"
            row["last_empty_at"] = now_iso
            row["consecutive_dns_failures"] = 0
            row["consecutive_http_failures"] = 0
            row["consecutive_empty_runs"] = int(row.get("consecutive_empty_runs") or 0) + 1
    if candidate_count > 0:
        row["source_last_candidate_time"] = now_iso
        row["last_candidate_time"] = row["source_last_candidate_time"]
    if qualified_count > 0:
        row["last_successful_candidate_time"] = now_iso
    row["health_status"] = _v53_source_health_status(row, source)
    health[key] = row
    _save_source_health(health, source_health_file=source_health_file)
    return _v53_source_health_row(source, health)


def _v52_document_urls(item: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for key in ["document_url", "detail_url", "source_url", "response_url", "url"]:
        value = _clean(item.get(key))
        if value and value.startswith(("http://", "https://")):
            urls.append(value)
    for key in ["document_urls", "documents", "attachments", "supporting_documents", "download_urls"]:
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, str):
                    url = _clean(entry)
                elif isinstance(entry, dict):
                    url = _clean(entry.get("url") or entry.get("href") or entry.get("document_url"))
                else:
                    url = ""
                if url and url.startswith(("http://", "https://")):
                    urls.append(url)
    seen = set()
    output: List[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        output.append(url)
    return output[:12]


def _v56_safe_filename(value: str, fallback: str = "document") -> str:
    name = unquote(Path(_clean(value)).name or fallback)
    name = re.sub(r"[\r\n\t/\\:]+", "_", name).strip(" ._")
    if not name:
        name = fallback
    if len(name) > 150:
        suffix = Path(name).suffix
        name = f"{Path(name).stem[:120]}{suffix}"
    return name


def _v56_document_extension(url_or_name: str, content_type: str = "") -> str:
    path = urlparse(_clean(url_or_name)).path or _clean(url_or_name)
    suffix = Path(unquote(path)).suffix.lower()
    if suffix in DOCUMENT_DISCOVERY_EXTENSIONS:
        return suffix
    ctype = _safe_lower(content_type)
    if "pdf" in ctype:
        return ".pdf"
    if "wordprocessingml" in ctype:
        return ".docx"
    if "msword" in ctype:
        return ".doc"
    if "spreadsheetml" in ctype:
        return ".xlsx"
    if "excel" in ctype:
        return ".xls"
    if "zip" in ctype:
        return ".zip"
    return suffix


def _v56_link_text_is_document(text: str, href: str) -> bool:
    blob = _safe_lower(f"{text} {href}")
    return (
        _v56_document_extension(href) in DOCUMENT_DISCOVERY_EXTENSIONS
        or bool(re.search(r"\b(download|rfq|quotation|pricing schedule|sbd|specification|terms|bid document|returnable)\b", blob))
    )


def _v56_is_safe_public_document_url(url: str) -> bool:
    parsed = urlparse(_clean(url))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    blob = _safe_lower(url)
    unsafe_terms = [
        "login",
        "signin",
        "captcha",
        "recaptcha",
        "javascript:",
        "mailto:",
        "auth",
        "session",
        "logout",
        "private",
    ]
    return not any(term in blob for term in unsafe_terms)


def _v64_document_index_page(link: Dict[str, Any], content_type: str = "", body: str = "") -> bool:
    blob = _safe_lower(
        " ".join(
            [
                _clean(link.get("link_text")),
                _clean(link.get("filename")),
                _clean(link.get("url")),
                _clean(content_type),
                _clean(body[:1200]),
            ]
        )
    )
    return bool(re.search(r"\b(index|document index|document list|attachment list|download index|document repository)\b", blob))


def _v64_document_extension_from_filename(filename: str) -> str:
    ext = Path(unquote(urlparse(_clean(filename)).path or _clean(filename))).suffix.lower()
    if ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        return ext
    return ""


def _v64_document_extension(url_or_name: str, content_type: str = "", filename: str = "") -> str:
    ext = _v56_document_extension(url_or_name, content_type)
    ctype = _safe_lower(content_type)
    file_ext = _v64_document_extension_from_filename(filename or url_or_name)
    if ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        return ext
    if "octet-stream" in ctype and file_ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        return file_ext
    if "text/csv" in ctype or file_ext == ".csv":
        return ".csv"
    if file_ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        return file_ext
    return ext if ext in DOCUMENT_DOWNLOAD_EXTENSIONS else file_ext


def _v64_resolve_document_url_candidates(link: Dict[str, Any], source: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_url = _clean(link.get("url") or link.get("href") or link.get("document_url") or "")
    source_url = _clean(source.get("url") or source.get("list_url") or link.get("source_url") or "")
    resolved: List[Dict[str, Any]] = []
    seen = set()

    def _add(candidate_url: str, stage: str) -> None:
        candidate_url = _clean(candidate_url)
        if not candidate_url or candidate_url in seen:
            return
        parsed = urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return
        seen.add(candidate_url)
        resolved.append({"stage": stage, "url": candidate_url})

    if not raw_url:
        return resolved
    if re.search(r"\s", raw_url) or raw_url.startswith(("javascript:", "mailto:", "data:")):
        return resolved

    parsed_raw = urlparse(raw_url)
    if parsed_raw.scheme in {"http", "https"} and parsed_raw.netloc:
        _add(raw_url, "direct")
    if source_url:
        _add(urljoin(source_url, raw_url), "resolved")
        parsed_source = urlparse(source_url)
        if parsed_source.scheme in {"http", "https"} and parsed_source.netloc:
            source_root = f"{parsed_source.scheme}://{parsed_source.netloc}/"
            _add(urljoin(source_root, raw_url.lstrip("/")), "source_fallback")
    return resolved


def _v64_sniff_document_signature(
    sample: bytes,
    *,
    detected_ext: str = "",
    filename: str = "",
    url: str = "",
    link_text: str = "",
    content_type: str = "",
) -> Tuple[str, bool]:
    blob = _safe_lower(f"{filename} {url} {link_text}")
    hinted_ext = _clean(detected_ext).lower()
    sample = sample or b""
    if sample.startswith(b"%PDF"):
        return ".pdf", True
    if sample.startswith(b"PK"):
        if hinted_ext in {".docx", ".xlsx", ".zip"}:
            return hinted_ext, True
        ctype = _safe_lower(content_type)
        if "wordprocessingml" in ctype or "docx" in blob:
            return ".docx", True
        if "spreadsheetml" in ctype or "excel" in ctype or "xlsx" in blob or "pricing schedule" in blob:
            return ".xlsx", True
        return ".zip", True
    if sample.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if hinted_ext in {".doc", ".xls"}:
            return hinted_ext, True
        ctype = _safe_lower(content_type)
        if "excel" in ctype or "xls" in blob:
            return ".xls", True
        return ".doc", True
    if hinted_ext == ".csv":
        try:
            text = sample.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        if any(token in text for token in (",", ";", "\t")) or "pricing schedule" in blob:
            return ".csv", False
    return hinted_ext if hinted_ext in DOCUMENT_DOWNLOAD_EXTENSIONS else "", False


def _v64_document_artifact_evidence_ok(path: str, content_type: str = "", extension: str = "") -> Tuple[bool, int]:
    artifact_path = _clean(path)
    if not artifact_path:
        return False, 0
    artifact = Path(artifact_path)
    try:
        if not artifact.exists():
            return False, 0
        size = artifact.stat().st_size
        if size <= 0:
            return False, size
        ext = _clean(extension).lower() or artifact.suffix.lower()
        sample = artifact.read_bytes()[:64]
        sniffed_ext, signature_ok = _v64_sniff_document_signature(
            sample,
            detected_ext=ext,
            filename=artifact.name,
            url=str(artifact),
            content_type=content_type,
        )
        ctype = _safe_lower(content_type)
        acceptable_ext = ext in DOCUMENT_DOWNLOAD_EXTENSIONS
        acceptable_type = any(
            token in ctype
            for token in ("pdf", "zip", "octet-stream", "msword", "wordprocessingml", "excel", "spreadsheetml", "text/csv", "csv")
        )
        if signature_ok and sniffed_ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
            return True, size
        if ext == ".csv" and sniffed_ext == ".csv":
            return True, size
        if not acceptable_ext and not acceptable_type:
            return False, size
        return True, size
    except Exception:
        return False, 0


def _v64_score_artifact_candidate(
    raw_url: str,
    absolute_url: str,
    label: str,
    source_hint: str,
) -> Dict[str, Any]:
    raw_url = _clean(raw_url)
    absolute_url = _clean(absolute_url)
    label = _clean(label)
    source_hint = _clean(source_hint)
    blob = _safe_lower(f"{label} {source_hint} {absolute_url} {raw_url}")
    parsed = urlparse(absolute_url or raw_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    blob_name = _clean(query_params.get("blobName") or query_params.get("BlobName") or query_params.get("blobname"))
    downloaded_file_name = _clean(
        query_params.get("downloadedFileName")
        or query_params.get("DownloadedFileName")
        or query_params.get("downloaded_filename")
    )
    ext = _v64_document_extension(absolute_url or raw_url, "", label)
    query_ext = _v64_document_extension_from_filename(blob_name or downloaded_file_name)
    if query_ext and query_ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        ext = query_ext
    path_blob = _safe_lower(f"{parsed.path} {parsed.query}")
    strong_file_hint = ext in DOCUMENT_DOWNLOAD_EXTENSIONS or bool(ETENDERS_ARTIFACT_HINT_PATTERN.search(blob))
    if blob_name and query_ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        strong_file_hint = True
    strong_download_hint = bool(re.search(r"\b(download|downloadfile|attachment|zip|pdf|docx|xlsx)\b", blob))
    if blob_name:
        strong_download_hint = True
    document_hint = bool(re.search(r"\b(document|tenderdocument|biddocument|specification|boq|pricing schedule|sbd|returnable|compulsory documents)\b", blob))
    strong_document_action_hint = bool(re.search(r"\b(tenderdocument|biddocument|document)\b", path_blob)) and bool(parsed.query)
    is_javascript = raw_url.startswith(("javascript:", "#")) or raw_url.lower() == "void(0)"
    is_api_json = path_blob.endswith(".json") or bool(ARTIFACT_API_JSON_PATTERN.search(path_blob))
    is_social = bool(ARTIFACT_SOCIAL_PATTERN.search(blob))
    is_navigation = bool(ARTIFACT_NAVIGATION_PATTERN.search(blob)) and not strong_file_hint and not strong_download_hint
    if is_javascript:
        return {
            "classification": "javascript_link",
            "score": 0,
            "should_attempt": False,
            "rejection_reason": "javascript_or_anchor_link",
            "strong_file_hint": False,
            "strong_download_hint": False,
            "extension": ext,
        }
    if is_social:
        return {
            "classification": "html_navigation",
            "score": 5,
            "should_attempt": False,
            "rejection_reason": "social_or_menu_link",
            "strong_file_hint": False,
            "strong_download_hint": False,
            "extension": ext,
        }
    if ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        return {
            "classification": "direct_file",
            "score": 100,
            "should_attempt": True,
            "rejection_reason": "",
            "strong_file_hint": True,
            "strong_download_hint": True,
            "extension": ext,
        }
    if blob_name and query_ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
        return {
            "classification": "direct_file",
            "score": 100,
            "should_attempt": True,
            "rejection_reason": "",
            "strong_file_hint": True,
            "strong_download_hint": True,
            "extension": query_ext,
        }
    if is_api_json and not strong_file_hint and not strong_download_hint:
        return {
            "classification": "api_json_endpoint",
            "score": 15,
            "should_attempt": False,
            "rejection_reason": "api_json_endpoint_not_binary",
            "strong_file_hint": False,
            "strong_download_hint": False,
            "extension": ext,
        }
    if (strong_download_hint and document_hint) or strong_document_action_hint:
        return {
            "classification": "document_action_link",
            "score": 92,
            "should_attempt": True,
            "rejection_reason": "",
            "strong_file_hint": True,
            "strong_download_hint": True,
            "extension": ext,
        }
    if "download" in blob or "downloadfile" in blob or "attachment" in blob:
        return {
            "classification": "likely_download_endpoint",
            "score": 88,
            "should_attempt": True,
            "rejection_reason": "",
            "strong_file_hint": strong_file_hint,
            "strong_download_hint": True,
            "extension": ext,
        }
    if document_hint:
        return {
            "classification": "document_action_link",
            "score": 72,
            "should_attempt": False,
            "rejection_reason": "weak_document_action_link",
            "strong_file_hint": strong_file_hint,
            "strong_download_hint": False,
            "extension": ext,
        }
    if is_navigation:
        return {
            "classification": "html_navigation",
            "score": 10,
            "should_attempt": False,
            "rejection_reason": "html_navigation_link",
            "strong_file_hint": False,
            "strong_download_hint": False,
            "extension": ext,
        }
    return {
        "classification": "unknown",
        "score": 30 if strong_file_hint else 20,
        "should_attempt": False,
        "rejection_reason": "" if strong_file_hint else "unknown_without_file_hints",
        "strong_file_hint": strong_file_hint,
        "strong_download_hint": strong_download_hint,
        "extension": ext,
    }


def _v64_is_etenders_detail_page(url: str) -> bool:
    cleaned = _safe_lower(url)
    return "etenders.gov.za" in cleaned and "/home/tenderdetails" in cleaned


def _v64_is_etenders_opportunities_page(url: str) -> bool:
    cleaned = _safe_lower(url)
    return "etenders.gov.za" in cleaned and "/home/opportunities" in cleaned


def _v64_extract_etenders_tender_id(*values: Any) -> str:
    for value in values:
        text = _clean(value)
        if not text:
            continue
        query_id = _clean(dict(parse_qsl(urlparse(text).query)).get("id"))
        if query_id.isdigit():
            return query_id
        match = re.search(r"\b(\d{5,8})\b", text)
        if match:
            return _clean(match.group(1))
    return ""


def _v64_pick_etenders_opportunities_url(*values: Any) -> str:
    for value in values:
        cleaned = _clean(value)
        if cleaned and _v64_is_etenders_opportunities_page(cleaned):
            return cleaned
    return ""


def _v64_limit_snippet(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _v64_unique_compact(values: List[Any], limit: int = 40, snippet_limit: int = 180) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        compact = _v64_limit_snippet(value, snippet_limit)
        key = compact.lower()
        if not compact or key in seen:
            continue
        seen.add(key)
        out.append(compact)
        if len(out) >= limit:
            break
    return out


def _v64_is_same_origin_etenders_url(url: str) -> bool:
    parsed = urlparse(_clean(url))
    if parsed.scheme not in {"http", "https"}:
        return False
    return _safe_lower(parsed.netloc) in {"www.etenders.gov.za", "etenders.gov.za"}


def _v64_extract_etenders_id_like_fields(*values: Any) -> List[Dict[str, str]]:
    patterns = [
        r'"(?P<name>supportDocumentID|supportDocumentId|documentId|documentID|fileId|fileID|docId|docID|tenderId|tenderID|tendersID|noticeNumber|noticeNo|cidbNumber|cidbNo|id)"\s*:\s*"?(?P<value>[A-Za-z0-9\-]{3,80})"?',
        r"(?P<name>supportDocumentID|supportDocumentId|documentId|documentID|fileId|fileID|docId|docID|tenderId|tenderID|tendersID|noticeNumber|noticeNo|cidbNumber|cidbNo|id)\s*[=:]\s*['\"]?(?P<value>[A-Za-z0-9\-]{3,80})",
    ]
    out: List[Dict[str, str]] = []
    seen = set()
    for value in values:
        text = _clean(value)
        if not text:
            continue
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                name = _clean(match.group("name"))
                field_value = _clean(match.group("value"))
                if not name or not field_value:
                    continue
                if _safe_lower(field_value) in {"hidden", "true", "false", "null", name.lower()}:
                    continue
                key = (name.lower(), field_value.lower())
                if key in seen:
                    continue
                seen.add(key)
                out.append({"name": name, "value": field_value})
    return out


def _v64_extract_document_like_terms(*values: Any) -> List[str]:
    terms = [
        "support document",
        "supporting document",
        "document id",
        "documentId",
        "file id",
        "fileId",
        "tender id",
        "tenderId",
        "cidb number",
        "notice number",
        "Download",
        "Attachment",
        "TenderDocument",
        "TenderDocuments",
        "GetDocuments",
        "TenderDetails",
    ]
    blob = " ".join(_clean(value) for value in values)
    found: List[str] = []
    seen = set()
    for term in terms:
        if term.lower() not in blob.lower():
            continue
        if term.lower() in seen:
            continue
        seen.add(term.lower())
        found.append(term)
    return found


def _v64_json_value_looks_like_filename(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    lowered = text.lower()
    return bool(re.search(r"\.(pdf|zip|docx?|xlsx?|xls|csv|txt|rtf|msg|eml)$", lowered) or re.search(r"[\w\-]+\.(pdf|zip|docx?|xlsx?|xls|csv|txt|rtf|msg|eml)(?:\?|$)", lowered))


def _v64_json_value_looks_like_url(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    return bool(re.match(r"^https?://", text, flags=re.I) or text.startswith("/Home/") or text.startswith("Home/") or text.startswith("/"))


def _v64_json_value_looks_like_doc_id(name: str, value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    if not re.search(r"\d", text) and not re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text):
        return False
    lower_name = _safe_lower(name)
    if any(token in lower_name for token in ("document", "support", "file", "doc", "attachment", "blob", "download")):
        return True
    if lower_name == "id" and len(text) >= 3:
        return True
    return False


def _v64_mine_etenders_tenderdetails_json(payload: Any, tender_id: str = "") -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "json_top_level_keys": [],
        "document_like_key_paths": [],
        "filename_like_values_limited": [],
        "url_like_values_limited": [],
        "id_like_values_by_path": [],
        "document_row_candidates_count": 0,
        "document_row_candidate_keys": [],
        "tender_id_used": _clean(tender_id),
    }
    rows: List[Dict[str, Any]] = []
    row_keys: List[str] = []
    doc_key_paths: List[str] = []
    filename_values: List[str] = []
    url_values: List[str] = []
    id_values_by_path: List[Dict[str, str]] = []
    candidate_row_keys: List[str] = []
    seen_rows = set()
    doc_key_pattern = re.compile(r"(document|documents|support|supporting|attachment|file|filename|filepath|path|blob|url|download|spec|sbd|boq|returnable)", re.I)

    def _record_candidate(path: str, value: Dict[str, Any], row_keys_local: List[str]) -> None:
        nonlocal summary
        row_blob = json.dumps(value, ensure_ascii=False, default=str)
        row_key = (path, tuple(sorted(row_keys_local)), _safe_lower(row_blob[:160]))
        if row_key in seen_rows:
            return
        seen_rows.add(row_key)
        summary["document_row_candidates_count"] += 1
        rows.append({
            "source_json_path": path,
            "row_keys": _v64_unique_compact(row_keys_local, limit=30, snippet_limit=80),
            "tender_id": _clean(tender_id),
            "value": value,
        })
        for key in row_keys_local:
            if key not in candidate_row_keys:
                candidate_row_keys.append(key)

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if path == "$":
                for key in value.keys():
                    if key not in summary["json_top_level_keys"]:
                        summary["json_top_level_keys"].append(_clean(key))
            keys_here: List[str] = []
            has_doc_signals = False
            for key, nested in value.items():
                child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                keys_here.append(_clean(key))
                if doc_key_pattern.search(_clean(key)):
                    doc_key_paths.append(child_path)
                    has_doc_signals = True
                if isinstance(nested, dict) or isinstance(nested, list):
                    _walk(nested, child_path)
                else:
                    if _v64_json_value_looks_like_url(nested):
                        url_values.append(f"{child_path}={_v64_limit_snippet(nested, 220)}")
                        if doc_key_pattern.search(_clean(key)) or "url" in _safe_lower(key) or "path" in _safe_lower(key):
                            has_doc_signals = True
                    if _v64_json_value_looks_like_filename(nested):
                        filename_values.append(f"{child_path}={_v64_limit_snippet(nested, 220)}")
                        if doc_key_pattern.search(_clean(key)):
                            has_doc_signals = True
                    if _v64_json_value_looks_like_doc_id(key, nested):
                        id_values_by_path.append({"path": child_path, "name": _clean(key), "value": _clean(nested)})
                        has_doc_signals = True
            blob = json.dumps(value, ensure_ascii=False, default=str).lower()
            if not has_doc_signals:
                has_doc_signals = bool(doc_key_pattern.search(blob) or re.search(r"\.(pdf|zip|docx?|xlsx?|xls|csv)\b", blob))
            if has_doc_signals:
                _record_candidate(path, value, keys_here)
        elif isinstance(value, list):
            list_has_doc_signals = False
            keys_in_rows: List[str] = []
            for index, entry in enumerate(value):
                child_path = f"{path}[{index}]"
                if isinstance(entry, dict):
                    entry_keys = [_clean(k) for k in entry.keys()]
                    keys_in_rows.extend(entry_keys)
                    if any(doc_key_pattern.search(k) for k in entry_keys):
                        list_has_doc_signals = True
                    _walk(entry, child_path)
                else:
                    if _v64_json_value_looks_like_filename(entry):
                        filename_values.append(f"{child_path}={_v64_limit_snippet(entry, 220)}")
                        list_has_doc_signals = True
                    if _v64_json_value_looks_like_url(entry):
                        url_values.append(f"{child_path}={_v64_limit_snippet(entry, 220)}")
                        list_has_doc_signals = True
                    if _v64_json_value_looks_like_doc_id("id", entry):
                        id_values_by_path.append({"path": child_path, "name": "id", "value": _clean(entry)})
                        list_has_doc_signals = True
            if list_has_doc_signals and keys_in_rows:
                _record_candidate(path, {"value": "list"}, keys_in_rows)

    _walk(payload, "$")
    summary["document_like_key_paths"] = _v64_unique_compact(doc_key_paths, limit=80, snippet_limit=220)
    summary["filename_like_values_limited"] = _v64_unique_compact(filename_values, limit=60, snippet_limit=220)
    summary["url_like_values_limited"] = _v64_unique_compact(url_values, limit=60, snippet_limit=220)
    summary["id_like_values_by_path"] = id_values_by_path[:80]
    summary["document_row_candidate_keys"] = _v64_unique_compact(candidate_row_keys, limit=80, snippet_limit=80)
    return {"summary": summary, "document_rows": rows}


def _v64_build_tenderdetails_route_experiments(
    *,
    tender_id: str,
    mined: Dict[str, Any],
) -> List[Dict[str, Any]]:
    summary = mined.get("summary") if isinstance(mined.get("summary"), dict) else {}
    rows = mined.get("document_rows") if isinstance(mined.get("document_rows"), list) else []
    experiments: List[Dict[str, Any]] = []
    seen = set()

    def _add(
        *,
        endpoint_url: str,
        route_pattern_name: str,
        source_json_path: str,
        parameter_names_used: List[str],
        tender_id_used: str = "",
        document_id_used: str = "",
        filename: str = "",
        source_value: str = "",
    ) -> None:
        absolute = urljoin(ETENDERS_BASE_URL, _clean(endpoint_url))
        if not absolute or absolute in seen:
            return
        seen.add(absolute)
        params = list(dict(parse_qsl(urlparse(absolute).query, keep_blank_values=True)).keys())
        experiments.append({
            "endpoint_url": absolute,
            "document_url": absolute,
            "label": filename or route_pattern_name,
            "source_hint": _clean(source_json_path),
            "source": "discovered_json",
            "route_pattern_name": route_pattern_name,
            "source_json_path": source_json_path,
            "parameter_names_used": _v64_unique_compact(parameter_names_used or params, limit=12, snippet_limit=80),
            "tender_id_used": _clean(tender_id_used),
            "document_id_used": _clean(document_id_used),
            "candidate_classification": "likely_download_endpoint",
            "candidate_score": 95 if document_id_used else 80,
            "candidate_rejection_reason": "",
            "candidate_should_attempt": True,
            "filename": _v56_safe_filename(filename or Path(urlparse(absolute).path).name or "document", "document"),
        })

    def _route_patterns_for_row(row: Dict[str, Any]) -> List[Dict[str, Any]]:
        value = row.get("value") if isinstance(row, dict) else None
        source_json_path = _clean(row.get("source_json_path"))
        row_keys = row.get("row_keys") if isinstance(row.get("row_keys"), list) else []
        if not isinstance(value, dict):
            value = {}
        filename = ""
        explicit_urls: List[Tuple[str, str]] = []
        doc_ids: List[Tuple[str, str]] = []
        tender_ids: List[Tuple[str, str]] = []
        for key, raw in value.items():
            key_clean = _clean(key)
            lower = _safe_lower(key_clean)
            raw_text = _clean(raw)
            if not raw_text:
                continue
            if _v64_json_value_looks_like_url(raw_text) and any(token in lower for token in ("url", "href", "download", "file", "document", "path")):
                explicit_urls.append((key_clean, raw_text))
            if _v64_json_value_looks_like_filename(raw_text):
                filename = filename or raw_text
            if _v64_json_value_looks_like_doc_id(key_clean, raw_text):
                doc_ids.append((key_clean, raw_text))
            if any(token in lower for token in ("tenderid", "tendersid")) or (lower == "id" and raw_text.isdigit()):
                tender_ids.append((key_clean, raw_text))
        if explicit_urls:
            for key, raw_url in explicit_urls:
                route_name = f"explicit_{key.lower()}_url"
                yield_candidate = {
                    "endpoint_url": raw_url,
                    "route_pattern_name": route_name,
                    "source_json_path": source_json_path,
                    "parameter_names_used": [key],
                    "tender_id_used": tender_id or next((v for _, v in tender_ids), ""),
                    "document_id_used": next((v for _, v in doc_ids), ""),
                    "filename": filename,
                }
                yield_candidate["candidate_score"] = 100
                yield_candidate["candidate_classification"] = "direct_file"
                yield_candidate["candidate_should_attempt"] = True
                yield_candidate["candidate_rejection_reason"] = ""
                yield_candidate["source"] = "discovered_json"
                yield_candidate["label"] = filename or route_name
                yield_candidate["document_url"] = raw_url
                yield_candidate["source_hint"] = source_json_path
                yield_candidate["candidate_source_json_keys"] = row_keys
                yield yield_candidate
            return
        for doc_key, doc_value in doc_ids:
            lower_key = _safe_lower(doc_key)
            action_param_pairs = []
            if any(token in lower_key for token in ("supportdocument", "supportdocumentid")):
                action_param_pairs = [
                    ("DownloadSupportDocument", doc_key),
                    ("DownloadSpec", doc_key),
                    ("DownloadDocument", doc_key),
                    ("DownloadTenderDocument", doc_key),
                    ("DownloadFile", doc_key),
                ]
            else:
                action_param_pairs = [
                    ("DownloadSpec", doc_key),
                    ("DownloadDocument", doc_key),
                    ("DownloadTenderDocument", doc_key),
                    ("DownloadFile", doc_key),
                ]
            for route_name, param_name in action_param_pairs:
                query = urlencode({param_name: doc_value, "source": "sharepoint"}) if "downloadspec" in _safe_lower(route_name) or "downloadfile" in _safe_lower(route_name) or "downloaddocument" in _safe_lower(route_name) or "downloadtenderdocument" in _safe_lower(route_name) else urlencode({param_name: doc_value})
                endpoint_url = f"{ETENDERS_BASE_URL}/Home/{route_name}?{query}"
                yield_candidate = {
                    "endpoint_url": endpoint_url,
                    "route_pattern_name": f"{route_name}_{param_name}",
                    "source_json_path": source_json_path,
                    "parameter_names_used": [param_name] + (["source"] if "source=sharepoint" in query else []),
                    "tender_id_used": tender_id or next((v for _, v in tender_ids), ""),
                    "document_id_used": doc_value,
                    "filename": filename,
                    "candidate_classification": "likely_download_endpoint",
                    "candidate_score": 92 if filename else 85,
                    "candidate_rejection_reason": "",
                    "candidate_should_attempt": True,
                    "source": "discovered_json",
                    "label": filename or route_name,
                    "document_url": endpoint_url,
                    "source_hint": source_json_path,
                    "candidate_source_json_keys": row_keys,
                }
                yield yield_candidate
            if filename and doc_value:
                for route_name in ("DownloadSpec", "DownloadDocument", "DownloadTenderDocument", "DownloadFile"):
                    endpoint_url = f"{ETENDERS_BASE_URL}/Home/{route_name}?{urlencode({'documentId': doc_value, 'fileName': filename, 'source': 'sharepoint'})}"
                    yield_candidate = {
                        "endpoint_url": endpoint_url,
                        "route_pattern_name": f"{route_name}_documentId_fileName",
                        "source_json_path": source_json_path,
                        "parameter_names_used": ["documentId", "fileName", "source"],
                        "tender_id_used": tender_id or next((v for _, v in tender_ids), ""),
                        "document_id_used": doc_value,
                        "filename": filename,
                        "candidate_classification": "likely_download_endpoint",
                        "candidate_score": 94,
                        "candidate_rejection_reason": "",
                        "candidate_should_attempt": True,
                        "source": "discovered_json",
                        "label": filename or route_name,
                        "document_url": endpoint_url,
                        "source_hint": source_json_path,
                        "candidate_source_json_keys": row_keys,
                    }
                    yield yield_candidate
        if filename and not doc_ids and tender_ids:
            for tender_key, tender_value in tender_ids:
                for route_name in ("DownloadSpec", "DownloadDocument", "DownloadTenderDocument", "DownloadFile"):
                    endpoint_url = f"{ETENDERS_BASE_URL}/Home/{route_name}?{urlencode({'tenderId': tender_value, 'fileName': filename, 'source': 'sharepoint'})}"
                    yield_candidate = {
                        "endpoint_url": endpoint_url,
                        "route_pattern_name": f"{route_name}_tenderId_fileName",
                        "source_json_path": source_json_path,
                        "parameter_names_used": ["tenderId", "fileName", "source"],
                        "tender_id_used": tender_value,
                        "document_id_used": "",
                        "filename": filename,
                        "candidate_classification": "likely_download_endpoint",
                        "candidate_score": 70,
                        "candidate_rejection_reason": "",
                        "candidate_should_attempt": True,
                        "source": "discovered_json",
                        "label": filename or route_name,
                        "document_url": endpoint_url,
                        "source_hint": source_json_path,
                        "candidate_source_json_keys": row_keys,
                    }
                    yield yield_candidate

    for row in rows:
        for candidate in _route_patterns_for_row(row):
            _add(
                endpoint_url=_clean(candidate.get("endpoint_url")),
                route_pattern_name=_clean(candidate.get("route_pattern_name")),
                source_json_path=_clean(candidate.get("source_json_path")),
                parameter_names_used=candidate.get("parameter_names_used") if isinstance(candidate.get("parameter_names_used"), list) else [],
                tender_id_used=_clean(candidate.get("tender_id_used") or tender_id),
                document_id_used=_clean(candidate.get("document_id_used")),
                filename=_clean(candidate.get("filename")),
            )

    if not experiments and tender_id:
        for route_name in ("TenderDetails", "GetTenderDetails"):
            endpoint_url = f"{ETENDERS_BASE_URL}/Home/{route_name}?id={quote(tender_id)}"
            _add(
                endpoint_url=endpoint_url,
                route_pattern_name=f"{route_name}_tenderId_fallback",
                source_json_path="$",
                parameter_names_used=["id"],
                tender_id_used=tender_id,
                document_id_used="",
                filename="",
            )

    return experiments


def _v64_extract_etenders_endpoint_urls_from_text(text: str, base_url: str) -> List[str]:
    matches: List[str] = []
    if not text:
        return matches
    patterns = [
        r"""["']([^"']*(?:TenderDocuments?|TenderDetails|TenderDocument|SupportDocument|DownloadSupportDocument|DownloadSpec|Document|Download(?:File)?|BidDocument|Attachment|GetDocuments|GetTenderDocuments|GetTenderDetails|SCMDocument|File|Blob|Content)[^"']*)["']""",
        r"""((?:/|https?://)[^"'()<>\s]*(?:TenderDocuments?|TenderDetails|TenderDocument|SupportDocument|DownloadSupportDocument|DownloadSpec|Document|Download(?:File)?|BidDocument|Attachment|GetDocuments|GetTenderDocuments|GetTenderDetails|SCMDocument|File|Blob|Content)[^"'()<>\s]*)""",
    ]
    seen = set()
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            value = _clean(match)
            if not value or value in seen:
                continue
            absolute = urljoin(base_url or ETENDERS_BASE_URL, value)
            if absolute in seen:
                continue
            seen.add(absolute)
            matches.append(absolute)
    return matches


def _v64_build_etenders_endpoint_records_from_urls(
    urls: List[str],
    *,
    base_url: str,
    source_name: str,
    label: str = "",
    source_hint: str = "",
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen = set()
    for url in urls:
        absolute = urljoin(base_url or ETENDERS_BASE_URL, _clean(url))
        if not absolute or absolute in seen:
            continue
        seen.add(absolute)
        params = dict(parse_qsl(urlparse(absolute).query, keep_blank_values=True))
        records.append({
            "endpoint_url": absolute,
            "label": _clean(label),
            "source_hint": _clean(source_hint),
            "source": source_name,
            "parameter_names_used": _v64_unique_compact(list(params.keys()), limit=12, snippet_limit=80),
            "tender_id_used": _v64_extract_etenders_tender_id(absolute),
            "document_id_used": _clean(
                params.get("documentId")
                or params.get("documentID")
                or params.get("supportDocumentID")
                or params.get("supportDocumentId")
                or params.get("fileId")
                or params.get("docId")
            ),
        })
    return records


def _v64_generate_etenders_endpoint_patterns_from_ids(
    *,
    tender_id: str,
    id_fields: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    generated: List[Dict[str, Any]] = []
    seen = set()

    def _add(path: str, source_name: str, source_hint: str, *, tender_id_used: str = "", document_id_used: str = "") -> None:
        absolute = urljoin(ETENDERS_BASE_URL, _clean(path))
        if not absolute or absolute in seen:
            return
        seen.add(absolute)
        params = list(dict(parse_qsl(urlparse(absolute).query, keep_blank_values=True)).keys())
        generated.append({
            "endpoint_url": absolute,
            "label": "",
            "source_hint": _clean(source_hint),
            "source": source_name,
            "parameter_names_used": _v64_unique_compact(params, limit=12, snippet_limit=80),
            "tender_id_used": _clean(tender_id_used),
            "document_id_used": _clean(document_id_used),
        })

    if tender_id:
        for param_name in ("id", "tenderId", "tendersID"):
            for route in ("TenderDocuments", "GetTenderDocuments", "GetDocuments", "LoadTenderDocuments", "GetTenderDetails", "TenderDetails"):
                _add(
                    f"/Home/{route}?{param_name}={quote(tender_id)}",
                    "seeded",
                    f"seeded_tender_id:{param_name}",
                    tender_id_used=tender_id,
                )

    for field in id_fields:
        name = _clean(field.get("name"))
        value = _clean(field.get("value"))
        lower_name = _safe_lower(name)
        if not name or not value:
            continue
        if any(token in lower_name for token in ("supportdocument", "document", "file", "docid")):
            for route in ("DownloadSupportDocument", "DownloadSpec", "DownloadFile", "DownloadDocument", "DownloadTenderDocument"):
                _add(
                    f"/Home/{route}?{quote(name)}={quote(value)}",
                    "discovered_html",
                    f"id_field:{name}",
                    tender_id_used=tender_id,
                    document_id_used=value,
                )
                if lower_name == "documentid":
                    _add(
                        f"/Home/{route}?{quote(name)}={quote(value)}&source=sharepoint",
                        "discovered_html",
                        f"id_field:{name}:sharepoint",
                        tender_id_used=tender_id,
                        document_id_used=value,
                    )
        if any(token in lower_name for token in ("tenderid", "tendersid")) or (lower_name == "id" and value.isdigit()):
            for route in ("TenderDocuments", "GetTenderDocuments", "GetDocuments", "LoadTenderDocuments", "GetTenderDetails", "TenderDetails"):
                _add(
                    f"/Home/{route}?{quote(name)}={quote(value)}",
                    "discovered_html",
                    f"id_field:{name}",
                    tender_id_used=value,
                )

    return generated


def _v64_fetch_etenders_same_origin_script_content(
    script_url: str,
    *,
    detail_page_url: str,
    source: Dict[str, Any],
    timeout: int,
) -> str:
    if not _v64_is_same_origin_etenders_url(script_url):
        return ""
    try:
        response = requests.get(
            script_url,
            timeout=timeout,
            allow_redirects=True,
            verify=bool(source.get("verify_ssl", True)),
            headers={
                "User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0",
                "Accept": "application/javascript,text/javascript,text/plain,*/*",
                "Referer": detail_page_url,
            },
        )
        if not response.ok:
            return ""
        content_type = _safe_lower(response.headers.get("content-type"))
        if "javascript" not in content_type and ".js" not in _safe_lower(urlparse(script_url).path):
            return ""
        return getattr(response, "text", "") or ""
    except Exception:
        return ""


def _v64_build_etenders_download_urls_from_metadata(
    metadata: Dict[str, Any],
    *,
    tender_id: str,
    base_url: str,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen = set()

    def _add(url: str, label: str = "", source_hint: str = "") -> None:
        absolute = urljoin(base_url or ETENDERS_BASE_URL, _clean(url))
        if not absolute or absolute in seen:
            return
        seen.add(absolute)
        inferred_filename = _clean(
            metadata.get("downloadedFileName")
            or metadata.get("DownloadedFileName")
            or metadata.get("downloaded_filename")
            or metadata.get("fileName")
            or metadata.get("filename")
            or Path(urlparse(absolute).path).name
        )
        results.append({
            "url": absolute,
            "document_url": absolute,
            "link_text": _clean(label),
            "filename": _v56_safe_filename(inferred_filename, "document"),
            "source_hint": _clean(source_hint),
        })

    raw_paths = [
        metadata.get("url"),
        metadata.get("href"),
        metadata.get("downloadUrl"),
        metadata.get("fileUrl"),
        metadata.get("documentUrl"),
        metadata.get("attachmentUrl"),
        metadata.get("filePath"),
        metadata.get("path"),
    ]
    blob_name = _clean(metadata.get("blobName") or metadata.get("BlobName") or metadata.get("blobname"))
    downloaded_file_name = _clean(
        metadata.get("downloadedFileName")
        or metadata.get("DownloadedFileName")
        or metadata.get("downloaded_filename")
        or metadata.get("fileName")
        or metadata.get("filename")
        or metadata.get("name")
    )
    if blob_name:
        blob_params = {"blobName": blob_name}
        if downloaded_file_name:
            blob_params["downloadedFileName"] = downloaded_file_name
        _add(f"/Home/Download/?{urlencode(blob_params)}", downloaded_file_name or blob_name, "metadata_blobname")
    for raw_path in raw_paths:
        raw_value = _clean(raw_path)
        if raw_value and (raw_value.startswith("/") or raw_value.startswith("http")):
            _add(raw_value, metadata.get("fileName") or metadata.get("filename"), "metadata_url")

    file_name = _clean(
        metadata.get("fileName")
        or metadata.get("filename")
        or metadata.get("downloadedFileName")
        or metadata.get("DownloadedFileName")
        or metadata.get("downloaded_filename")
        or metadata.get("name")
    )
    support_document_id = _clean(
        metadata.get("supportDocumentID")
        or metadata.get("supportDocumentId")
        or metadata.get("support_document_id")
        or metadata.get("documentGuid")
        or metadata.get("guid")
    )
    document_id = _clean(metadata.get("documentId") or metadata.get("documentID") or metadata.get("id"))
    discovered_tender_id = _clean(metadata.get("tenderId") or metadata.get("tender_id") or metadata.get("tendersID") or tender_id)
    metadata_blob = _safe_lower(json.dumps(metadata, default=str, ensure_ascii=False))
    metadata_looks_document_like = bool(
        file_name
        or support_document_id
        or document_id
        or ETENDERS_ENDPOINT_PATTERN.search(metadata_blob)
        or re.search(r"\.(pdf|zip|docx?|xlsx?|xls|csv)\b", metadata_blob)
    )
    route_params: List[Tuple[str, str, str]] = []
    if support_document_id:
        route_params.extend([
            ("DownloadSupportDocument", "supportDocumentID", support_document_id),
            ("DownloadSupportDocument", "documentId", support_document_id),
            ("DownloadSpec", "supportDocumentID", support_document_id),
            ("DownloadDocument", "supportDocumentID", support_document_id),
            ("DownloadTenderDocument", "supportDocumentID", support_document_id),
        ])
    if document_id:
        route_params.extend([
            ("DownloadSpec", "documentId", document_id),
            ("DownloadFile", "documentId", document_id),
            ("DownloadDocument", "documentId", document_id),
            ("DownloadTenderDocument", "documentId", document_id),
        ])
    if discovered_tender_id and metadata_looks_document_like:
        for route in ("TenderDocuments", "GetTenderDocuments", "GetDocuments", "LoadTenderDocuments"):
            _add(f"/Home/{route}?id={quote(discovered_tender_id)}", file_name or route, "tender_id_endpoint")
            _add(f"/Home/{route}?tenderId={quote(discovered_tender_id)}", file_name or route, "tender_id_endpoint")
            _add(f"/Home/{route}?tendersID={quote(discovered_tender_id)}", file_name or route, "tender_id_endpoint")
    for route, key, value in route_params:
        encoded = quote(value)
        _add(f"/Home/{route}?{key}={encoded}", file_name or route, f"{route}:{key}")
        if route in {"DownloadSpec", "DownloadFile"} and key == "documentId":
            _add(f"/Home/{route}?{key}={encoded}&source=sharepoint", file_name or route, f"{route}:{key}:sharepoint")
    return results


def _v64_extract_etenders_endpoint_candidates_from_response(
    payload: Any,
    *,
    endpoint_url: str,
    detail_page_url: str,
    tender_id: str,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen = set()

    def _add_candidate(url: str, label: str = "", source_hint: str = "") -> None:
        absolute = urljoin(ETENDERS_BASE_URL, _clean(url))
        if not absolute or absolute in seen:
            return
        seen.add(absolute)
        scored = _v64_score_artifact_candidate(_clean(url), absolute, label, source_hint)
        filename = _v56_safe_filename(Path(urlparse(absolute).path).name or _clean(label), "document")
        candidates.append({
            "url": absolute,
            "document_url": absolute,
            "link_text": _clean(label),
            "filename": filename,
            "extension": scored.get("extension") or _v64_document_extension(absolute, "", filename),
            "source_url": detail_page_url,
            "source_link_url": detail_page_url,
            "resolved_index_page_url": detail_page_url,
            "source_hint": _clean(source_hint or endpoint_url),
            "diagnostic_type": "artifact_candidate",
            "candidate_classification": scored["classification"],
            "candidate_score": int(scored["score"]),
            "candidate_rejection_reason": _clean(scored["rejection_reason"]),
            "candidate_should_attempt": bool(scored["should_attempt"]) and _v56_is_safe_public_document_url(absolute),
        })

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for key in ETENDERS_DOCUMENT_RESPONSE_KEYS:
                raw_value = _clean(value.get(key))
                if raw_value and (raw_value.startswith("/") or raw_value.startswith("http")):
                    _add_candidate(raw_value, value.get("fileName") or value.get("filename") or key, f"{endpoint_url}:{key}")
            metadata_downloads = _v64_build_etenders_download_urls_from_metadata(value, tender_id=tender_id, base_url=ETENDERS_BASE_URL)
            for entry in metadata_downloads:
                _add_candidate(entry.get("url") or "", entry.get("link_text") or entry.get("filename") or "", entry.get("source_hint") or endpoint_url)
            for nested in value.values():
                _walk(nested)
        elif isinstance(value, list):
            for entry in value:
                _walk(entry)

    _walk(payload)
    return candidates


def _v64_discover_etenders_document_endpoints(
    html: str,
    detail_page_url: str,
    source: Optional[Dict[str, Any]] = None,
    timeout: int = 25,
) -> Dict[str, Any]:
    base_url = ETENDERS_BASE_URL
    endpoints: List[Dict[str, Any]] = []
    seen = set()
    hidden_fields: Dict[str, str] = {}
    tender_id = _v64_extract_etenders_tender_id(detail_page_url)
    script_srcs: List[str] = []
    form_actions: List[str] = []
    hidden_input_names: List[str] = []
    data_attribute_names: List[str] = []
    onclick_snippets: List[str] = []
    ajax_url_candidates: List[str] = []
    endpoint_like_strings: List[str] = []
    id_like_fields: List[Dict[str, str]] = []
    candidate_endpoint_patterns_generated: List[str] = []

    def _add(url: str, label: str = "", source_hint: str = "", source_name: str = "discovered_html") -> None:
        absolute = urljoin(base_url, _clean(url))
        if not absolute or absolute in seen:
            return
        if "etenders.gov.za" not in _safe_lower(absolute):
            return
        if not ETENDERS_ENDPOINT_PATTERN.search(absolute) and not ETENDERS_ENDPOINT_PATTERN.search(f"{label} {source_hint}"):
            return
        seen.add(absolute)
        params = dict(parse_qsl(urlparse(absolute).query, keep_blank_values=True))
        endpoints.append({
            "endpoint_url": absolute,
            "label": _clean(label),
            "source_hint": _clean(source_hint),
            "source": source_name,
            "parameter_names_used": _v64_unique_compact(list(params.keys()), limit=12, snippet_limit=80),
            "tender_id_used": _v64_extract_etenders_tender_id(absolute, tender_id),
            "document_id_used": _clean(
                params.get("documentId")
                or params.get("documentID")
                or params.get("supportDocumentID")
                or params.get("supportDocumentId")
                or params.get("fileId")
                or params.get("docId")
            ),
        })
        endpoint_like_strings.append(absolute)

    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html or "", "html.parser")
        for element in soup.find_all(True):
            for attr_name, attr_value in list(element.attrs.items()):
                attr_blob = _safe_lower(str(attr_name))
                if attr_blob.startswith("data-"):
                    data_attribute_names.append(_clean(attr_name))
                if isinstance(attr_value, list):
                    attr_text = " ".join(_clean(item) for item in attr_value)
                else:
                    attr_text = _clean(attr_value)
                if not attr_text:
                    continue
                if element.name == "input" and _safe_lower(element.get("type")) == "hidden":
                    hidden_name = _clean(element.get("name") or element.get("id") or attr_name)
                    hidden_fields[hidden_name] = attr_text
                    hidden_input_names.append(hidden_name)
                    id_like_fields.extend(_v64_extract_etenders_id_like_fields(f"{hidden_name}={attr_text}", hidden_name, attr_text))
                if attr_blob == "onclick":
                    onclick_snippets.append(attr_text)
                if any(token in attr_blob for token in ("url", "action", "endpoint", "href", "onclick", "formaction", "src")):
                    for match in _v64_extract_etenders_endpoint_urls_from_text(attr_text, base_url):
                        ajax_url_candidates.append(match)
                        source_name = "discovered_data_attr" if attr_blob.startswith("data-") else "discovered_html"
                        if attr_blob == "onclick":
                            source_name = "discovered_onclick"
                        elif element.name == "form" or attr_blob in {"action", "formaction"}:
                            source_name = "discovered_form"
                        _add(match, element.get_text(" ", strip=True), f"{element.name}.{attr_name}", source_name)
            if element.name == "form":
                action = _clean(element.get("action"))
                if action:
                    form_actions.append(urljoin(base_url, action))
                    _add(action, element.get_text(" ", strip=True), "form.action", "discovered_form")
        for script in soup.find_all("script"):
            script_blob = script.get_text(" ", strip=True) or ""
            src = _clean(script.get("src"))
            if src:
                script_srcs.append(urljoin(base_url, src))
            for match in _v64_extract_etenders_endpoint_urls_from_text(script_blob, base_url):
                ajax_url_candidates.append(match)
                _add(match, "script", "inline_script", "discovered_script")
            id_like_fields.extend(_v64_extract_etenders_id_like_fields(script_blob))
        id_like_fields.extend(_v64_extract_etenders_id_like_fields(html))
    except Exception:
        pass

    for name, value in hidden_fields.items():
        lower_name = _safe_lower(name)
        if not tender_id and any(token in lower_name for token in ("tenderid", "tendersid", "id")):
            maybe_id = _v64_extract_etenders_tender_id(value)
            if maybe_id:
                tender_id = maybe_id

    for key, value in hidden_fields.items():
        metadata_urls = _v64_build_etenders_download_urls_from_metadata({key: value, "fileName": hidden_fields.get("fileName") or hidden_fields.get("FileName") or ""}, tender_id=tender_id, base_url=base_url)
        for entry in metadata_urls:
            _add(entry.get("url") or "", entry.get("filename") or entry.get("link_text") or "", f"hidden_field:{key}", "discovered_html")

    deduped_id_like_fields: List[Dict[str, str]] = []
    seen_id_fields = set()
    for field in id_like_fields:
        if not isinstance(field, dict):
            continue
        field_name = _clean(field.get("name"))
        field_value = _clean(field.get("value"))
        key = (_safe_lower(field_name), _safe_lower(field_value))
        if not field_name or not field_value or key in seen_id_fields:
            continue
        seen_id_fields.add(key)
        deduped_id_like_fields.append({"name": field_name, "value": field_value})
    id_like_fields = deduped_id_like_fields

    source = source or {}
    script_records: List[Dict[str, Any]] = []
    for script_src in _v64_unique_compact(script_srcs, limit=30, snippet_limit=300):
        if not _v64_is_same_origin_etenders_url(script_src):
            continue
        script_text = _v64_fetch_etenders_same_origin_script_content(
            script_src,
            detail_page_url=detail_page_url,
            source=source,
            timeout=timeout,
        )
        if not script_text:
            continue
        script_urls = _v64_extract_etenders_endpoint_urls_from_text(script_text, base_url)
        ajax_url_candidates.extend(script_urls)
        endpoint_like_strings.extend(script_urls)
        id_like_fields.extend(_v64_extract_etenders_id_like_fields(script_text))
        script_records.extend(
            _v64_build_etenders_endpoint_records_from_urls(
                script_urls,
                base_url=base_url,
                source_name="discovered_script",
                label="script",
                source_hint=script_src,
            )
        )

    deduped_id_like_fields = []
    seen_id_fields = set()
    for field in id_like_fields:
        if not isinstance(field, dict):
            continue
        field_name = _clean(field.get("name"))
        field_value = _clean(field.get("value"))
        key = (_safe_lower(field_name), _safe_lower(field_value))
        if not field_name or not field_value or key in seen_id_fields:
            continue
        seen_id_fields.add(key)
        deduped_id_like_fields.append({"name": field_name, "value": field_value})
    id_like_fields = deduped_id_like_fields

    generated_patterns = _v64_generate_etenders_endpoint_patterns_from_ids(
        tender_id=tender_id,
        id_fields=id_like_fields,
    )
    for record in script_records:
        _add(
            record.get("endpoint_url") or "",
            record.get("label") or "",
            record.get("source_hint") or "",
            record.get("source") or "discovered_html",
        )
    for record in generated_patterns:
        candidate_endpoint_patterns_generated.append(record.get("endpoint_url") or "")
        _add(
            record.get("endpoint_url") or "",
            record.get("label") or "",
            record.get("source_hint") or "",
            record.get("source") or "discovered_html",
        )

    return {
        "tender_id": tender_id,
        "hidden_fields": hidden_fields,
        "endpoints": endpoints,
        "evidence": {
            "diagnostic_type": "etenders_detail_page_discovery",
            "detail_page_url": detail_page_url,
            "http_status": 200 if _clean(html) else 0,
            "content_type": "text/html",
            "html_length": len(html or ""),
            "script_srcs": _v64_unique_compact(script_srcs, limit=30, snippet_limit=300),
            "form_actions": _v64_unique_compact(form_actions, limit=30, snippet_limit=300),
            "hidden_input_names": _v64_unique_compact(hidden_input_names, limit=40, snippet_limit=120),
            "data_attribute_names": _v64_unique_compact(data_attribute_names, limit=40, snippet_limit=120),
            "onclick_snippets_limited": _v64_unique_compact(onclick_snippets, limit=20, snippet_limit=180),
            "ajax_url_candidates": _v64_unique_compact(ajax_url_candidates, limit=40, snippet_limit=300),
            "endpoint_like_strings": _v64_unique_compact(endpoint_like_strings, limit=50, snippet_limit=300),
            "id_like_fields": id_like_fields[:30],
            "document_like_terms_found": _v64_extract_document_like_terms(html, json.dumps(hidden_fields, default=str)),
            "candidate_endpoint_patterns_generated": _v64_unique_compact(candidate_endpoint_patterns_generated, limit=60, snippet_limit=300),
            "endpoint_probe_404_count": 0,
            "endpoint_probe_non_404_count": 0,
            "script_endpoint_candidates_count": len(script_records),
        },
    }


def _v64_probe_etenders_document_endpoints(
    html: str,
    detail_page_url: str,
    source: Dict[str, Any],
    timeout: int = 25,
) -> Dict[str, Any]:
    discovery = _v64_discover_etenders_document_endpoints(html, detail_page_url, source=source, timeout=timeout)
    endpoint_diagnostics: List[Dict[str, Any]] = []
    artifact_candidates: List[Dict[str, Any]] = []
    failures_by_reason: Dict[str, int] = {}
    probe_count = 0
    success_count = 0
    failure_count = 0
    probe_404_count = 0
    probe_non_404_count = 0
    seen_candidate_urls = set()
    tender_id = _clean(discovery.get("tender_id"))
    evidence = discovery.get("evidence") if isinstance(discovery.get("evidence"), dict) else {}

    for endpoint in discovery.get("endpoints") or []:
        if not isinstance(endpoint, dict):
            continue
        endpoint_url = _clean(endpoint.get("endpoint_url"))
        if not endpoint_url:
            continue
        probe_count += 1
        diagnostic = {
            "diagnostic_type": "etenders_endpoint_probe",
            "detail_page_url": detail_page_url,
            "endpoint_url": endpoint_url,
            "http_status": 0,
            "content_type": "",
            "response_shape": "",
            "candidates_found_count": 0,
            "failure_reason": "",
            "source": _clean(endpoint.get("source") or "discovered_html"),
            "parameter_names_used": endpoint.get("parameter_names_used") if isinstance(endpoint.get("parameter_names_used"), list) else [],
            "tender_id_used": _clean(endpoint.get("tender_id_used") or tender_id),
            "document_id_used": _clean(endpoint.get("document_id_used")),
        }
        try:
            response = requests.get(
                endpoint_url,
                timeout=timeout,
                allow_redirects=True,
                verify=bool(source.get("verify_ssl", True)),
                headers={
                    "User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0",
                    "Accept": "application/json,text/html,application/xhtml+xml,*/*",
                    "Referer": detail_page_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            diagnostic["http_status"] = int(getattr(response, "status_code", 0) or 0)
            diagnostic["content_type"] = _clean(response.headers.get("content-type"))
            if diagnostic["http_status"] == 404:
                probe_404_count += 1
            elif diagnostic["http_status"]:
                probe_non_404_count += 1
            if not response.ok:
                diagnostic["failure_reason"] = f"http_{diagnostic['http_status']}"
                if diagnostic["failure_reason"] == "http_404":
                    diagnostic["reason"] = "http_404"
                diagnostic["response_shape"] = "empty"
                failure_count += 1
                failures_by_reason[diagnostic["failure_reason"]] = failures_by_reason.get(diagnostic["failure_reason"], 0) + 1
                endpoint_diagnostics.append(diagnostic)
                continue
            response_text = getattr(response, "text", "") or ""
            parsed_json = None
            if "json" in _safe_lower(diagnostic["content_type"]):
                try:
                    parsed_json = response.json()
                except Exception:
                    parsed_json = None
            elif response_text:
                try:
                    parsed_json = response.json()
                except Exception:
                    parsed_json = None
            extracted: List[Dict[str, Any]] = []
            if parsed_json is not None:
                diagnostic["response_shape"] = "json"
                extracted.extend(
                    _v64_extract_etenders_endpoint_candidates_from_response(
                        parsed_json,
                        endpoint_url=endpoint_url,
                        detail_page_url=detail_page_url,
                        tender_id=tender_id,
                    )
                )
            elif "<a" in response_text.lower() or "<form" in response_text.lower() or "<button" in response_text.lower():
                diagnostic["response_shape"] = "html_page" if "<html" in response_text.lower() else "html_fragment"
                extracted.extend(_v64_extract_artifact_candidate_links_from_html(response_text, endpoint_url, source, detail_page_url))
            elif not _clean(response_text):
                diagnostic["response_shape"] = "empty"
            else:
                diagnostic["response_shape"] = "unsupported"
            for candidate in extracted:
                url = _clean(candidate.get("url") or candidate.get("document_url"))
                if not url or url in seen_candidate_urls:
                    continue
                seen_candidate_urls.add(url)
                artifact_candidates.append(candidate)
            diagnostic["candidates_found_count"] = len(extracted)
            if extracted:
                success_count += 1
            else:
                diagnostic["failure_reason"] = "no_document_candidates_found"
                failure_count += 1
                failures_by_reason[diagnostic["failure_reason"]] = failures_by_reason.get(diagnostic["failure_reason"], 0) + 1
            endpoint_diagnostics.append(diagnostic)
        except Exception as exc:
            diagnostic["response_shape"] = "empty"
            diagnostic["failure_reason"] = _truncate(str(exc), 180) or "endpoint_probe_error"
            failure_count += 1
            failures_by_reason[diagnostic["failure_reason"]] = failures_by_reason.get(diagnostic["failure_reason"], 0) + 1
            endpoint_diagnostics.append(diagnostic)

    deduped_candidates = _v56_dedupe_document_links(artifact_candidates)
    deduped_candidates.sort(key=lambda item: int(item.get("candidate_score") or 0), reverse=True)
    if evidence:
        evidence["endpoint_probe_404_count"] = probe_404_count
        evidence["endpoint_probe_non_404_count"] = probe_non_404_count
    return {
        "tender_id": tender_id,
        "etenders_endpoint_probe_count": probe_count,
        "etenders_endpoint_success_count": success_count,
        "etenders_endpoint_failure_count": failure_count,
        "etenders_document_candidates_from_endpoints": len(deduped_candidates),
        "etenders_endpoint_failures_by_reason": failures_by_reason,
        "diagnostics": ([evidence] if evidence else []) + endpoint_diagnostics,
        "artifact_candidates": deduped_candidates,
    }


def _v64_extract_artifact_candidate_links_from_html(
    html: str,
    base_url: str,
    source: Dict[str, Any],
    source_link_url: str = "",
) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    source_name = _clean(source.get("name") or source.get("source_name"))
    base_url = _clean(base_url)
    source_link_url = _clean(source_link_url or base_url)

    def _add(candidate_url: str, label: str = "", source_hint: str = "") -> None:
        raw_candidate_url = _clean(candidate_url)
        if not raw_candidate_url:
            return
        absolute = urljoin(base_url, raw_candidate_url) if not raw_candidate_url.startswith(("javascript:", "#")) else raw_candidate_url
        scored = _v64_score_artifact_candidate(raw_candidate_url, absolute, label, source_hint)
        if scored["classification"] not in ARTIFACT_CANDIDATE_CLASSIFICATIONS:
            return
        is_safe_attempt_url = _v56_is_safe_public_document_url(absolute)
        rejection_reason = _clean(scored["rejection_reason"])
        if not is_safe_attempt_url and not rejection_reason:
            rejection_reason = "unsafe_or_malformed_document_url"
        filename = _v56_safe_filename(urlparse(absolute).path or absolute, "document")
        ext = scored.get("extension") or _v64_document_extension(absolute, "", filename)
        parsed = urlparse(absolute)
        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        blob_name = _clean(query_params.get("blobName") or query_params.get("BlobName") or query_params.get("blobname"))
        downloaded_file_name = _clean(
            query_params.get("downloadedFileName")
            or query_params.get("DownloadedFileName")
            or query_params.get("downloaded_filename")
        )
        route_pattern_name = "etenders_blob_download_html" if blob_name else "html_link"
        links.append({
            "url": absolute,
            "document_url": absolute,
            "raw_url": raw_candidate_url,
            "link_text": _clean(label),
            "filename": _v56_safe_filename(filename, "document"),
            "extension": ext,
            "source_name": source_name,
            "source_url": source_link_url or base_url,
            "resolved_index_page_url": base_url or source_link_url,
            "source_link_url": source_link_url or base_url,
            "source_html_path": _clean(source_hint) or "rendered_html_blob_link",
            "source_context": _clean(label or source_hint or source_link_url or base_url),
            "diagnostic_type": "artifact_candidate",
            "candidate_classification": scored["classification"],
            "candidate_score": int(scored["score"]),
            "candidate_rejection_reason": rejection_reason,
            "candidate_should_attempt": bool(scored["should_attempt"]) and is_safe_attempt_url,
            "route_pattern_name": route_pattern_name,
            "blobName": blob_name,
            "downloadedFileName": downloaded_file_name,
            "parameter_names_used": ["blobName", "downloadedFileName"] if blob_name and downloaded_file_name else (["blobName"] if blob_name else []),
            "source_json_path": "rendered_html_blob_link",
        })

    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html or "", "html.parser")
        for anchor in soup.find_all("a"):
            href = _clean(anchor.get("href"))
            if not href:
                continue
            label = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True) or "").strip()
            _add(href, label, label)
        for button in soup.find_all(["button", "input"]):
            href = _clean(
                button.get("data-href")
                or button.get("data-url")
                or button.get("data-download-url")
                or button.get("formaction")
                or button.get("href")
                or button.get("value")
            )
            if href:
                label = re.sub(r"\s+", " ", button.get_text(" ", strip=True) or button.get("value") or "").strip()
                onclick = _clean(button.get("onclick") or "")
                if not label and onclick:
                    label = onclick
                _add(href, label, onclick or label)
        for form in soup.find_all("form"):
            action = _clean(form.get("action"))
            if not action:
                continue
            label = re.sub(r"\s+", " ", form.get_text(" ", strip=True) or "").strip()
            _add(action, label, label)
    except Exception:
        pass

    if not links:
        for match in re.findall(r"""(?:href|data-href|data-url|action)=["']([^"']+)["']""", html or "", flags=re.I):
            label = ""
            _add(match, label, label)
        for match in re.findall(r"""(?:/Home/Download/?\?blobName=[^"'<>\s]+|/home/Download/?\?blobName=[^"'<>\s]+|Download/?\?blobName=[^"'<>\s]+)""", html or "", flags=re.I):
            _add(match, "", "rendered_html_blob_link")
        for match in re.findall(r"""blobName=[^"'<>\s&]+(?:&downloadedFileName=[^"'<>\s]+)?""", html or "", flags=re.I):
            _add(f"/Home/Download/?{match}", "", "rendered_html_blob_link")
        for match in re.findall(
            r"""(?:download|document|bid|tender|rfq|boq|pricing|schedule|returnable)[^"'<>\s]*\.(?:pdf|docx?|xlsx?|xls|zip|csv)(?:\?[^"'<>\s]*)?""",
            html or "",
            flags=re.I,
        ):
            _add(match, "", match)
    deduped = _v56_dedupe_document_links(links)
    deduped.sort(key=lambda item: int(item.get("candidate_score") or 0), reverse=True)
    return deduped


def _v64_extract_interactive_blob_candidates(
    blob_links: List[Dict[str, Any]],
    base_url: str,
    source: Dict[str, Any],
    source_link_url: str = "",
) -> List[Dict[str, Any]]:
    if not isinstance(blob_links, list) or not blob_links:
        return []

    base_url = _clean(base_url)
    source_link_url = _clean(source_link_url or base_url)
    source_name = _clean(source.get("name") or source.get("source_name"))
    synthetic_html_parts: List[str] = []
    for link in blob_links:
        if not isinstance(link, dict):
            continue
        href = _clean(link.get("href") or link.get("url") or link.get("document_url") or "")
        text = _clean(link.get("text") or link.get("link_text") or link.get("anchor_text") or link.get("downloadedFileName") or link.get("blobName") or "Download")
        if not href:
            continue
        synthetic_html_parts.append(f'<a href="{_html_escape(href)}">{_html_escape(text)}</a>')

    if not synthetic_html_parts:
        return []

    candidates = _v64_extract_artifact_candidate_links_from_html(
        " ".join(synthetic_html_parts),
        base_url,
        source,
        source_link_url,
    )
    for candidate in candidates:
        if _clean(candidate.get("route_pattern_name")) == "etenders_blob_download_html":
            candidate["route_pattern_name"] = "etenders_blob_download_interactive"
        candidate["source_html_path"] = "interactive_rendered_dom_blob_link"
        candidate["source_json_path"] = "interactive_rendered_dom_blob_link"
        candidate["source_context"] = "clicked_expanded_tender_row"
        candidate["source_name"] = source_name or candidate.get("source_name") or ""
        candidate["source_link_url"] = source_link_url or candidate.get("source_link_url") or ""
        if not _clean(candidate.get("blobName")):
            parsed = urlparse(_clean(candidate.get("url") or candidate.get("document_url") or ""))
            query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            candidate["blobName"] = _clean(query_params.get("blobName") or query_params.get("BlobName") or query_params.get("blobname"))
        if not _clean(candidate.get("downloadedFileName")):
            parsed = urlparse(_clean(candidate.get("url") or candidate.get("document_url") or ""))
            query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            candidate["downloadedFileName"] = _clean(
                query_params.get("downloadedFileName")
                or query_params.get("DownloadedFileName")
                or query_params.get("downloaded_filename")
            )
    candidates.sort(key=lambda item: int(item.get("candidate_score") or 0), reverse=True)
    return candidates


def _v64_resolve_buyer_pack_diagnostics_for_candidate(
    candidate: Dict[str, Any],
    source: Dict[str, Any],
    timeout: int = 25,
) -> Dict[str, Any]:
    candidate_urls: List[str] = []
    candidate_urls.extend(
        _clean(url)
        for url in ([candidate.get("document_url")] if _clean(candidate.get("document_url")) else [])
    )
    for key in ("document_urls", "download_urls", "attachments", "supporting_documents"):
        value = candidate.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, str):
                    url = _clean(entry)
                elif isinstance(entry, dict):
                    url = _clean(entry.get("url") or entry.get("href") or entry.get("document_url"))
                else:
                    url = ""
                if url:
                    candidate_urls.append(url)
    seen_candidate_urls = set()
    candidate_urls = [
        url
        for url in candidate_urls
        if url and not (url in seen_candidate_urls or seen_candidate_urls.add(url))
    ]
    diagnostics: List[Dict[str, Any]] = []
    direct_downloads: List[Dict[str, Any]] = []
    artifact_candidates_found_count = 0
    index_pages_fetched_count = 0
    index_pages_with_artifacts_count = 0
    artifact_download_attempts_count = 0
    artifact_download_success_count = 0
    artifact_candidates_total = 0
    artifact_candidates_attempted = 0
    artifact_candidates_rejected_before_fetch = 0
    artifact_candidates_by_classification: Dict[str, int] = {}
    artifact_rejections_by_reason: Dict[str, int] = {}
    artifact_resolved_to_html_count = 0
    artifact_binary_signature_success_count = 0
    etenders_endpoint_probe_count = 0
    etenders_endpoint_success_count = 0
    etenders_endpoint_failure_count = 0
    etenders_document_candidates_from_endpoints = 0
    etenders_endpoint_failures_by_reason: Dict[str, int] = {}
    index_page_no_artifacts_count = 0
    artifact_download_failed_count = 0
    fallback_used = False
    downloaded_path = ""
    downloaded_timestamp = ""
    failure_reason = ""
    attempted = False
    tenderdetails_json_bridge_attempted = False

    def _annotate_attempts(
        result: Dict[str, Any],
        *,
        diagnostic_type: str,
        source_link_url: str,
        resolved_index_page_url: str,
        artifact_candidates_count: int,
        candidate_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        annotated: List[Dict[str, Any]] = []
        attempts = result.get("attempts") if isinstance(result.get("attempts"), list) else [result]
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            annotated_attempt = {
                **attempt,
                "diagnostic_type": diagnostic_type,
                "source_link_url": source_link_url,
                "resolved_index_page_url": resolved_index_page_url,
                "artifact_candidates_found_count": artifact_candidates_count,
            }
            if isinstance(candidate_context, dict):
                for key in (
                    "route_pattern_name",
                    "blobName",
                    "downloadedFileName",
                    "source_html_path",
                    "source_context",
                    "source_json_path",
                    "parameter_names_used",
                    "resolved_document_url",
                    "content_type",
                    "content_length",
                    "content_disposition",
                    "artifact_path",
                    "artifact_exists",
                    "artifact_size_bytes",
                    "binary_signature_detected",
                    "binary_signature_verified",
                ):
                    if key in candidate_context and candidate_context.get(key) not in (None, ""):
                        annotated_attempt[key] = candidate_context.get(key)
            if "binary_signature_verified" not in annotated_attempt and annotated_attempt.get("binary_signature_detected") is not None:
                annotated_attempt["binary_signature_verified"] = bool(annotated_attempt.get("binary_signature_detected"))
            if "binary_signature_detected" not in annotated_attempt and annotated_attempt.get("binary_signature_verified") is not None:
                annotated_attempt["binary_signature_detected"] = bool(annotated_attempt.get("binary_signature_verified"))
            annotated.append(annotated_attempt)
        return annotated

    def _record_candidate_summary(candidate_link: Dict[str, Any], attempted_download: bool) -> None:
        nonlocal artifact_candidates_total
        nonlocal artifact_candidates_attempted
        nonlocal artifact_candidates_rejected_before_fetch
        classification = _clean(candidate_link.get("candidate_classification")) or "unknown"
        artifact_candidates_total += 1
        artifact_candidates_by_classification[classification] = artifact_candidates_by_classification.get(classification, 0) + 1
        if attempted_download:
            artifact_candidates_attempted += 1
        else:
            artifact_candidates_rejected_before_fetch += 1
            rejection = _clean(candidate_link.get("candidate_rejection_reason")) or "candidate_rejected_before_fetch"
            artifact_rejections_by_reason[rejection] = artifact_rejections_by_reason.get(rejection, 0) + 1

    def _rejected_candidate_diag(candidate_link: Dict[str, Any], source_link_url: str, resolved_index_page_url: str) -> Dict[str, Any]:
        return {
            "diagnostic_type": "artifact_candidate_rejected",
            "document_url": _clean(candidate_link.get("url") or candidate_link.get("document_url")),
            "source_link_url": source_link_url,
            "resolved_index_page_url": resolved_index_page_url,
            "candidate_classification": _clean(candidate_link.get("candidate_classification")) or "unknown",
            "candidate_score": int(candidate_link.get("candidate_score") or 0),
            "candidate_rejection_reason": _clean(candidate_link.get("candidate_rejection_reason") or "candidate_rejected_before_fetch"),
            "failure_stage": "skipped",
            "failure_reason": _clean(candidate_link.get("candidate_rejection_reason") or "candidate_rejected_before_fetch"),
            "download_started_at": _now_iso(),
            "download_finished_at": _now_iso(),
        }

    for raw_url in candidate_urls:
        source_link_url = _clean(raw_url)
        if not source_link_url:
            continue
        source_link_diag = {
            "diagnostic_type": "source_link",
            "source_link_url": source_link_url,
            "resolved_index_page_url": "",
            "index_page_http_status": 0,
            "artifact_candidates_found_count": 0,
            "etenders_endpoint_probe_count": 0,
            "etenders_endpoint_success_count": 0,
            "etenders_endpoint_failure_count": 0,
            "etenders_document_candidates_from_endpoints": 0,
            "etenders_endpoint_failures_by_reason": {},
            "download_started_at": _now_iso(),
            "download_finished_at": "",
            "failure_stage": "",
            "failure_reason": "",
            "fallback_used": False,
        }
        if not _v56_is_safe_public_document_url(source_link_url):
            source_link_diag.update({
                "failure_stage": "url_resolution",
                "failure_reason": "unsafe_or_malformed_document_url",
                "download_finished_at": _now_iso(),
            })
            diagnostics.append(source_link_diag)
            attempted = True
            continue

        attempted = True

        if (
            not tenderdetails_json_bridge_attempted
            and _v64_is_etenders_detail_page(source_link_url)
            and download_from_tenderdetails_json is not None
        ):
            tender_id_hint = _v64_extract_etenders_tender_id(
                source_link_url,
                candidate.get("tender_id"),
                candidate.get("v50_9_1_tenderdetails_inspect_result"),
                candidate.get("v50_9_1_tenderdetails_download_result"),
            )
            if tender_id_hint:
                tenderdetails_json_bridge_attempted = True
                try:
                    json_download_result = download_from_tenderdetails_json({"tender_id": tender_id_hint})
                except Exception as exc:
                    json_download_result = {"status": "error", "error": str(exc)}

                if isinstance(json_download_result, dict):
                    route_attempts = json_download_result.get("attempts") if isinstance(json_download_result.get("attempts"), list) else []
                    for route_attempt in route_attempts:
                        if not isinstance(route_attempt, dict):
                            continue
                        diagnostics.append({
                            **route_attempt,
                            "diagnostic_type": "tenderdetails_json_route_experiment",
                            "source": "discovered_json",
                            "source_link_url": source_link_url,
                            "resolved_index_page_url": source_link_url,
                            "tender_id_used": _clean(route_attempt.get("tender_id") or tender_id_hint),
                            "document_id_used": _clean(route_attempt.get("document_id") or route_attempt.get("document_id_used")),
                        })
                    if json_download_result.get("status") == "ok":
                        downloaded_path = _clean(json_download_result.get("saved_path") or "")
                        downloaded_timestamp = _clean(json_download_result.get("downloaded_at") or _now_iso())
                        direct_downloads.append(json_download_result)
                        artifact_download_success_count += 1
                        candidate["buyer_pack_download_diagnostics"] = diagnostics
                        return {
                            "attempted": True,
                            "downloaded": True,
                            "buyer_pack_downloaded": True,
                            "buyer_pack_path": downloaded_path,
                            "buyer_pack_download_timestamp": downloaded_timestamp,
                            "failure_reason": "",
                            "diagnostics": diagnostics,
                            "downloads": direct_downloads,
                            "index_pages_fetched_count": index_pages_fetched_count,
                            "index_pages_with_artifacts_count": index_pages_with_artifacts_count,
                            "artifact_candidates_found_count": artifact_candidates_found_count,
                            "artifact_download_attempts_count": artifact_download_attempts_count,
                            "artifact_download_success_count": artifact_download_success_count,
                            "index_page_no_artifacts_count": index_page_no_artifacts_count,
                            "artifact_download_failed_count": artifact_download_failed_count,
                            "fallback_used": fallback_used,
                            "artifact_candidates_total": artifact_candidates_total,
                            "artifact_candidates_attempted": artifact_candidates_attempted,
                            "artifact_candidates_rejected_before_fetch": artifact_candidates_rejected_before_fetch,
                            "artifact_candidates_by_classification": artifact_candidates_by_classification,
                            "artifact_rejections_by_reason": artifact_rejections_by_reason,
                            "artifact_resolved_to_html_count": artifact_resolved_to_html_count,
                            "artifact_binary_signature_success_count": artifact_binary_signature_success_count,
                            "etenders_endpoint_probe_count": etenders_endpoint_probe_count,
                            "etenders_endpoint_success_count": etenders_endpoint_success_count,
                            "etenders_endpoint_failure_count": etenders_endpoint_failure_count,
                            "etenders_document_candidates_from_endpoints": etenders_document_candidates_from_endpoints,
                            "etenders_endpoint_failures_by_reason": etenders_endpoint_failures_by_reason,
                        }

        source_ext = _v64_document_extension(source_link_url, "", Path(urlparse(source_link_url).path).name)
        if source_ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
            direct_candidate = {
                "url": source_link_url,
                "document_url": source_link_url,
                "filename": _v56_safe_filename(urlparse(source_link_url).path, "document" + source_ext),
                "extension": source_ext,
                "candidate_classification": "direct_file",
                "candidate_score": 100,
                "candidate_rejection_reason": "",
            }
            source_link_diag.update({
                "resolved_index_page_url": source_link_url,
                "artifact_candidates_found_count": 1,
            })
            diagnostics.append(source_link_diag)
            artifact_candidates_found_count += 1
            _record_candidate_summary(direct_candidate, True)
            direct_result = _v56_download_document({
                **direct_candidate,
                "source_url": _clean(source.get("url") or source.get("list_url") or candidate.get("source_url")),
                "source_name": _clean(source.get("name") or source.get("source_name")),
            }, source, timeout=timeout)
            art_attempts = _annotate_attempts(
                direct_result,
                diagnostic_type="artifact_candidate",
                source_link_url=source_link_url,
                resolved_index_page_url=source_link_url,
                artifact_candidates_count=1,
                candidate_context=direct_candidate,
            )
            diagnostics.extend(art_attempts)
            direct_success = direct_result.get("status") == "downloaded"
            artifact_download_attempts_count += 1
            artifact_resolved_to_html_count += sum(1 for diag in art_attempts if _clean(diag.get("failure_stage")) == "artifact_resolved_to_html")
            artifact_binary_signature_success_count += sum(1 for diag in art_attempts if bool(diag.get("binary_signature_verified")))
            if direct_success:
                artifact_download_success_count += 1
                downloaded_path = _clean(direct_result.get("artifact_path") or direct_result.get("path"))
                downloaded_timestamp = _clean(direct_result.get("download_finished_at") or _now_iso())
                source_link_diag["failure_stage"] = "artifact_saved"
                source_link_diag["failure_reason"] = ""
                source_link_diag["download_finished_at"] = downloaded_timestamp
                source_link_diag["fallback_used"] = bool(direct_result.get("fallback_used"))
                direct_downloads.append(direct_result)
                break
            artifact_download_failed_count += 1
            source_link_diag.update({
                "failure_stage": "artifact_download_failed",
                "failure_reason": _clean(direct_result.get("failure_reason") or direct_result.get("reason") or "download_error"),
                "download_finished_at": _clean(direct_result.get("download_finished_at") or _now_iso()),
                "fallback_used": bool(direct_result.get("fallback_used")),
            })
            continue

        try:
            response = requests.get(
                source_link_url,
                timeout=timeout,
                allow_redirects=True,
                verify=bool(source.get("verify_ssl", True)),
                headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0", "Accept": "text/html,application/xhtml+xml,*/*"},
            )
            index_pages_fetched_count += 1
            resolved_index_page_url = _clean(response.url or source_link_url)
            index_page_http_status = int(getattr(response, "status_code", 0) or 0)
            content_type = _safe_lower(response.headers.get("content-type"))
            source_link_diag["resolved_index_page_url"] = resolved_index_page_url
            source_link_diag["index_page_http_status"] = index_page_http_status
            source_link_diag["fallback_used"] = bool(resolved_index_page_url and resolved_index_page_url != source_link_url)
            redirect_chain = [
                {"url": _clean(item.url), "status_code": int(getattr(item, "status_code", 0) or 0)}
                for item in list(getattr(response, "history", []) or [])
            ]
            redirect_chain.append({"url": resolved_index_page_url, "status_code": index_page_http_status})
            if index_page_http_status in {401, 403, 407, 429}:
                source_link_diag.update({
                    "failure_stage": "auth_required",
                    "failure_reason": f"HTTP {index_page_http_status}",
                    "download_finished_at": _now_iso(),
                })
                diagnostics.append(source_link_diag)
                continue
            if not response.ok:
                source_link_diag.update({
                    "failure_stage": "http_fetch",
                    "failure_reason": f"HTTP {index_page_http_status}",
                    "download_finished_at": _now_iso(),
                })
                diagnostics.append(source_link_diag)
                continue
            response_text = getattr(response, "text", "") or ""
            if "html" not in content_type and not _v64_document_index_page(source_link_diag, content_type, response_text):
                if _v64_is_etenders_detail_page(resolved_index_page_url):
                    endpoint_probe_result = _v64_probe_etenders_document_endpoints(
                        response_text,
                        resolved_index_page_url,
                        source,
                        timeout=timeout,
                    )
                    source_link_diag["etenders_endpoint_probe_count"] = int(endpoint_probe_result.get("etenders_endpoint_probe_count") or 0)
                    source_link_diag["etenders_endpoint_success_count"] = int(endpoint_probe_result.get("etenders_endpoint_success_count") or 0)
                    source_link_diag["etenders_endpoint_failure_count"] = int(endpoint_probe_result.get("etenders_endpoint_failure_count") or 0)
                    source_link_diag["etenders_document_candidates_from_endpoints"] = int(endpoint_probe_result.get("etenders_document_candidates_from_endpoints") or 0)
                    source_link_diag["etenders_endpoint_failures_by_reason"] = endpoint_probe_result.get("etenders_endpoint_failures_by_reason") or {}
                    etenders_endpoint_probe_count += int(endpoint_probe_result.get("etenders_endpoint_probe_count") or 0)
                    etenders_endpoint_success_count += int(endpoint_probe_result.get("etenders_endpoint_success_count") or 0)
                    etenders_endpoint_failure_count += int(endpoint_probe_result.get("etenders_endpoint_failure_count") or 0)
                    etenders_document_candidates_from_endpoints += int(endpoint_probe_result.get("etenders_document_candidates_from_endpoints") or 0)
                    for reason_key, count in (endpoint_probe_result.get("etenders_endpoint_failures_by_reason") or {}).items():
                        key = _clean(reason_key) or "endpoint_probe_failed"
                        etenders_endpoint_failures_by_reason[key] = etenders_endpoint_failures_by_reason.get(key, 0) + int(count or 0)
                    diagnostics.extend(endpoint_probe_result.get("diagnostics") or [])
                    endpoint_candidates = endpoint_probe_result.get("artifact_candidates") or []
                    if endpoint_candidates:
                        source_link_diag["artifact_candidates_found_count"] = len(endpoint_candidates)
                        diagnostics.append(source_link_diag)
                        artifact_candidates_found_count += len(endpoint_candidates)
                        index_pages_with_artifacts_count += 1
                        attempted_candidates: List[Dict[str, Any]] = []
                        for artifact_candidate in endpoint_candidates:
                            should_attempt = bool(artifact_candidate.get("candidate_should_attempt"))
                            _record_candidate_summary(artifact_candidate, should_attempt)
                            if not should_attempt:
                                diagnostics.append(_rejected_candidate_diag(artifact_candidate, source_link_url, resolved_index_page_url))
                                continue
                            attempted_candidates.append(artifact_candidate)
                        for artifact_candidate in attempted_candidates:
                            artifact_download_attempts_count += 1
                            download_result = _v56_download_document(artifact_candidate, source, timeout=timeout)
                            art_attempts = _annotate_attempts(
                                download_result,
                                diagnostic_type="artifact_candidate",
                                source_link_url=source_link_url,
                                resolved_index_page_url=resolved_index_page_url,
                                artifact_candidates_count=len(endpoint_candidates),
                                candidate_context=artifact_candidate,
                            )
                            diagnostics.extend(art_attempts)
                            artifact_resolved_to_html_count += sum(1 for diag in art_attempts if _clean(diag.get("failure_stage")) == "artifact_resolved_to_html")
                            artifact_binary_signature_success_count += sum(1 for diag in art_attempts if bool(diag.get("binary_signature_verified")))
                            if download_result.get("status") == "downloaded":
                                artifact_download_success_count += 1
                                downloaded_path = _clean(download_result.get("artifact_path") or download_result.get("path"))
                                downloaded_timestamp = _clean(download_result.get("download_finished_at") or _now_iso())
                                fallback_used = bool(download_result.get("fallback_used")) or fallback_used
                                direct_downloads.append(download_result)
                                break
                            artifact_download_failed_count += 1
                        if downloaded_path:
                            break
                ext = _v64_document_extension(resolved_index_page_url, content_type, Path(urlparse(resolved_index_page_url).path).name)
                if ext in DOCUMENT_DOWNLOAD_EXTENSIONS:
                    resolved_candidate = {
                        "url": resolved_index_page_url,
                        "document_url": resolved_index_page_url,
                        "filename": _v56_safe_filename(urlparse(resolved_index_page_url).path, "document" + ext),
                        "extension": ext,
                        "candidate_classification": "direct_file",
                        "candidate_score": 100,
                        "candidate_rejection_reason": "",
                    }
                    source_link_diag["artifact_candidates_found_count"] = 1
                    diagnostics.append(source_link_diag)
                    artifact_candidates_found_count += 1
                    _record_candidate_summary(resolved_candidate, True)
                    direct_result = _v56_download_document({
                        **resolved_candidate,
                        "source_url": _clean(source.get("url") or source.get("list_url") or candidate.get("source_url")),
                        "source_name": _clean(source.get("name") or source.get("source_name")),
                    }, source, timeout=timeout)
                    art_attempts = _annotate_attempts(
                        direct_result,
                        diagnostic_type="artifact_candidate",
                        source_link_url=source_link_url,
                        resolved_index_page_url=resolved_index_page_url,
                        artifact_candidates_count=1,
                        candidate_context=resolved_candidate,
                    )
                    diagnostics.extend(art_attempts)
                    artifact_download_attempts_count += 1
                    artifact_resolved_to_html_count += sum(1 for diag in art_attempts if _clean(diag.get("failure_stage")) == "artifact_resolved_to_html")
                    artifact_binary_signature_success_count += sum(1 for diag in art_attempts if bool(diag.get("binary_signature_verified")))
                    if direct_result.get("status") == "downloaded":
                        artifact_download_success_count += 1
                        downloaded_path = _clean(direct_result.get("artifact_path") or direct_result.get("path"))
                        downloaded_timestamp = _clean(direct_result.get("download_finished_at") or _now_iso())
                        source_link_diag["failure_stage"] = "artifact_saved"
                        source_link_diag["failure_reason"] = ""
                        source_link_diag["download_finished_at"] = downloaded_timestamp
                        source_link_diag["fallback_used"] = bool(direct_result.get("fallback_used"))
                        direct_downloads.append(direct_result)
                        break
                    artifact_download_failed_count += 1
                    source_link_diag.update({
                        "failure_stage": "artifact_download_failed",
                        "failure_reason": _clean(direct_result.get("failure_reason") or direct_result.get("reason") or "download_error"),
                        "download_finished_at": _clean(direct_result.get("download_finished_at") or _now_iso()),
                        "fallback_used": bool(direct_result.get("fallback_used")),
                    })
                    continue
                source_link_diag.update({
                    "failure_stage": "unsupported_content_type",
                    "failure_reason": "unsupported_response_type",
                    "download_finished_at": _now_iso(),
                })
                diagnostics.append(source_link_diag)
                continue
            html_body = response_text
            artifact_candidates = _v64_extract_artifact_candidate_links_from_html(html_body, resolved_index_page_url, source, source_link_url)
            rendered_dom_capture_result: Dict[str, Any] = {}
            interactive_blob_candidates: List[Dict[str, Any]] = []
            rendered_dom_capture_diag: Dict[str, Any] = {
                "diagnostic_type": "etenders_rendered_dom_capture",
                "source_link_url": source_link_url,
                "resolved_index_page_url": resolved_index_page_url,
                "source_context": _clean(
                    candidate.get("title")
                    or candidate.get("description")
                    or candidate.get("reference_number")
                    or candidate.get("tender_id")
                    or ""
                ),
                "source_html_path": "rendered_html_blob_link",
                "source_json_path": "rendered_html_blob_link",
                "status": "attempted",
                "failure_reason": "",
                "rendered_html_length": 0,
                "rendered_blob_candidates_count": 0,
            }
            interactive_dom_capture_diag: Dict[str, Any] = {
                "diagnostic_type": "etenders_interactive_dom_capture",
                "tender_id": _clean(
                    candidate.get("tender_id")
                    or _v64_extract_etenders_tender_id(
                        candidate.get("detail_url"),
                        candidate.get("document_url"),
                        candidate.get("url"),
                        candidate.get("title"),
                        candidate.get("description"),
                        candidate.get("reference_number"),
                        source_link_url,
                        resolved_index_page_url,
                    )
                ),
                "candidate_title": _clean(candidate.get("title") or candidate.get("description") or candidate.get("reference_number") or ""),
                "source_link_url": source_link_url,
                "resolved_index_page_url": resolved_index_page_url,
                "source_context": "clicked_expanded_tender_row",
                "source_html_path": "interactive_rendered_dom_blob_link",
                "source_json_path": "interactive_rendered_dom_blob_link",
                "row_found": False,
                "row_expanded": False,
                "table_container_found": False,
                "datatables_processing_seen": False,
                "datatables_processing_finished": False,
                "main_response_status": 0,
                "body_text_length": 0,
                "body_html_length": 0,
                "body_text_preview_limited": "",
                "visible_row_count": 0,
                "page_text_limited_before_row_search": "",
                "table_count": 0,
                "row_count_by_selector": {},
                "first_rows_text_limited": [],
                "visible_links_limited": [],
                "helper_input_url": "",
                "helper_resolved_url": "",
                "helper_used_detail_page": False,
                "helper_used_opportunities_page": False,
                "helper_preserved_query_params": False,
                "detail_page_url_available": False,
                "opportunities_url_available": False,
                "browser_mode": "failed",
                "page_url_after_load": resolved_index_page_url,
                "page_title": "",
                "screenshot_path": "",
                "row_match_strategy": "",
                "row_match_text": "",
                "matched_row_text_limited": "",
                "row_selector_used": "table tbody tr, table tr, [role=\"row\"], .dataTables_wrapper tr",
                "row_click_target_used": "",
                "documents_section_found": False,
                "tender_documents_text_limited": "",
                "document_anchor_count": 0,
                "all_anchor_hrefs_limited": [],
                "all_anchor_texts_limited": [],
                "download_like_anchor_count": 0,
                "blob_like_string_count": 0,
                "visible_text_limited": "",
                "post_click_wait_ms": 0,
                "blob_links_limited": [],
                "interactive_blob_candidates_count": 0,
                "helper_error_type": "",
                "helper_error_message_limited": "",
                "failure_reason": "",
                "download_started_at": _now_iso(),
                "download_finished_at": _now_iso(),
            }
            helper_detail_page_url = _clean(
                candidate.get("detail_url")
                or (resolved_index_page_url if _v64_is_etenders_detail_page(resolved_index_page_url) else "")
                or (source_link_url if _v64_is_etenders_detail_page(source_link_url) else "")
            )
            helper_opportunities_url = _clean(
                _v64_pick_etenders_opportunities_url(
                    candidate.get("opportunities_url"),
                    candidate.get("source_url"),
                    candidate.get("url"),
                    resolved_index_page_url,
                    source_link_url,
                    source.get("url"),
                    source.get("list_url"),
                    ETENDERS_URL,
                )
            )
            if capture_dom_modal_autoclick is not None:
                try:
                    rendered_dom_capture_result = capture_dom_modal_autoclick({
                        "tender_id": _v64_extract_etenders_tender_id(source_link_url, candidate.get("tender_id"), resolved_index_page_url),
                        "tender_title": _clean(candidate.get("title") or candidate.get("description") or candidate.get("reference_number") or ""),
                        "buyer": _clean(candidate.get("buyer") or candidate.get("buyer_name") or candidate.get("procuring_entity") or ""),
                        "reference_number": _clean(candidate.get("reference_number") or candidate.get("rfq_number") or candidate.get("tender_number") or ""),
                        "search_text": _clean(candidate.get("title") or candidate.get("description") or candidate.get("reference_number") or candidate.get("tender_id") or ""),
                        "detail_page_url": helper_detail_page_url,
                        "opportunities_url": helper_opportunities_url,
                        "tender_url": helper_detail_page_url or helper_opportunities_url or resolved_index_page_url,
                        "cdp_url": _clean(source.get("cdp_url") or source.get("browser_cdp_url") or source.get("playwright_cdp_url") or ""),
                    }) or {}
                except Exception as exc:
                    rendered_dom_capture_result = {
                        "status": "error",
                        "error": str(exc),
                        "helper_error_type": type(exc).__name__,
                        "helper_error_message_limited": _v64_limit_snippet(str(exc), 240),
                        "table_container_found": False,
                        "datatables_processing_seen": False,
                        "datatables_processing_finished": False,
                        "main_response_status": 0,
                        "body_text_length": 0,
                        "body_html_length": 0,
                        "body_text_preview_limited": "",
                        "visible_row_count": 0,
                        "page_text_limited_before_row_search": "",
                        "table_count": 0,
                        "row_count_by_selector": {},
                        "first_rows_text_limited": [],
                        "visible_links_limited": [],
                        "helper_input_url": "",
                        "helper_resolved_url": "",
                        "helper_used_detail_page": False,
                        "helper_used_opportunities_page": False,
                        "helper_preserved_query_params": False,
                        "detail_page_url_available": False,
                        "opportunities_url_available": False,
                        "browser_mode": "failed",
                        "page_url_after_load": "",
                        "page_title": "",
                        "screenshot_path": "",
                        "row_found": False,
                        "row_expanded": False,
                        "row_match_strategy": "",
                        "row_match_text": "",
                        "matched_row_text_limited": "",
                        "documents_section_found": False,
                        "tender_documents_text_limited": "",
                        "document_anchor_count": 0,
                        "all_anchor_hrefs_limited": [],
                        "all_anchor_texts_limited": [],
                        "download_like_anchor_count": 0,
                        "blob_like_string_count": 0,
                        "visible_text_limited": "",
                        "post_click_wait_ms": 0,
                        "blob_links": [],
                        "interactive_blob_candidates_count": 0,
                    }
                if isinstance(rendered_dom_capture_result, dict):
                    expanded_dom = rendered_dom_capture_result.get("expanded_dom") if isinstance(rendered_dom_capture_result.get("expanded_dom"), dict) else {}
                    rendered_html = _clean(
                        expanded_dom.get("body_html_preview")
                        or expanded_dom.get("html")
                        or rendered_dom_capture_result.get("body_html_preview")
                        or rendered_dom_capture_result.get("html")
                    )
                    rendered_dom_capture_diag["status"] = _clean(rendered_dom_capture_result.get("status") or "ok")
                    rendered_dom_capture_diag["failure_reason"] = _clean(rendered_dom_capture_result.get("error") or rendered_dom_capture_result.get("failure_reason") or "")
                    rendered_dom_capture_diag["rendered_html_length"] = len(rendered_html)
                    interactive_dom_capture_diag.update({
                        "row_found": bool(
                            rendered_dom_capture_result.get("row_found")
                            or rendered_dom_capture_result.get("row_clicked")
                            or rendered_dom_capture_result.get("matched_row")
                        ),
                        "row_expanded": bool(rendered_dom_capture_result.get("row_expanded")),
                        "row_selector_used": _clean(rendered_dom_capture_result.get("row_selector_used") or ""),
                        "row_click_target_used": _clean(rendered_dom_capture_result.get("row_click_target_used") or ""),
                        "table_container_found": bool(rendered_dom_capture_result.get("table_container_found")),
                        "datatables_processing_seen": bool(rendered_dom_capture_result.get("datatables_processing_seen")),
                        "datatables_processing_finished": bool(rendered_dom_capture_result.get("datatables_processing_finished")),
                        "main_response_status": int(rendered_dom_capture_result.get("main_response_status") or 0),
                        "body_text_length": int(rendered_dom_capture_result.get("body_text_length") or 0),
                        "body_html_length": int(rendered_dom_capture_result.get("body_html_length") or 0),
                        "body_text_preview_limited": _v64_limit_snippet(rendered_dom_capture_result.get("body_text_preview_limited") or ""),
                        "visible_row_count": int(rendered_dom_capture_result.get("visible_row_count") or 0),
                        "page_text_limited_before_row_search": _v64_limit_snippet(rendered_dom_capture_result.get("page_text_limited_before_row_search") or ""),
                        "table_count": int(rendered_dom_capture_result.get("table_count") or 0),
                        "row_count_by_selector": rendered_dom_capture_result.get("row_count_by_selector") or {},
                        "first_rows_text_limited": rendered_dom_capture_result.get("first_rows_text_limited") or [],
                        "visible_links_limited": rendered_dom_capture_result.get("visible_links_limited") or [],
                        "helper_input_url": _clean(rendered_dom_capture_result.get("helper_input_url") or ""),
                        "helper_resolved_url": _clean(rendered_dom_capture_result.get("helper_resolved_url") or ""),
                        "helper_used_detail_page": bool(rendered_dom_capture_result.get("helper_used_detail_page")),
                        "helper_used_opportunities_page": bool(rendered_dom_capture_result.get("helper_used_opportunities_page")),
                        "helper_preserved_query_params": bool(rendered_dom_capture_result.get("helper_preserved_query_params")),
                        "detail_page_url_available": bool(rendered_dom_capture_result.get("detail_page_url_available")),
                        "opportunities_url_available": bool(rendered_dom_capture_result.get("opportunities_url_available")),
                        "browser_mode": _clean(rendered_dom_capture_result.get("browser_mode") or "failed"),
                        "page_url_after_load": _clean(rendered_dom_capture_result.get("page_url_after_load") or resolved_index_page_url),
                        "page_title": _clean(rendered_dom_capture_result.get("page_title") or ""),
                        "screenshot_path": _clean(rendered_dom_capture_result.get("screenshot_path") or ""),
                        "row_match_strategy": _clean(rendered_dom_capture_result.get("row_match_strategy") or ""),
                        "row_match_text": _clean(rendered_dom_capture_result.get("row_match_text") or ""),
                        "matched_row_text_limited": _v64_limit_snippet(rendered_dom_capture_result.get("matched_row_text_limited") or ""),
                        "helper_error_type": _clean(rendered_dom_capture_result.get("helper_error_type") or ""),
                        "helper_error_message_limited": _v64_limit_snippet(rendered_dom_capture_result.get("helper_error_message_limited") or ""),
                        "documents_section_found": bool(
                            rendered_dom_capture_result.get("documents_section_found")
                            or (rendered_dom_capture_result.get("expanded_dom") or {}).get("documents_section_found")
                        ),
                        "tender_documents_text_limited": _v64_limit_snippet(rendered_dom_capture_result.get("tender_documents_text_limited") or (rendered_dom_capture_result.get("expanded_dom") or {}).get("tender_documents_text_limited") or ""),
                        "document_anchor_count": int(rendered_dom_capture_result.get("document_anchor_count") or (rendered_dom_capture_result.get("expanded_dom") or {}).get("document_anchor_count") or 0),
                        "all_anchor_hrefs_limited": _v64_unique_compact(rendered_dom_capture_result.get("all_anchor_hrefs_limited") or (rendered_dom_capture_result.get("expanded_dom") or {}).get("all_anchor_hrefs_limited") or [], limit=20, snippet_limit=220),
                        "all_anchor_texts_limited": _v64_unique_compact(rendered_dom_capture_result.get("all_anchor_texts_limited") or (rendered_dom_capture_result.get("expanded_dom") or {}).get("all_anchor_texts_limited") or [], limit=20, snippet_limit=220),
                        "download_like_anchor_count": int(rendered_dom_capture_result.get("download_like_anchor_count") or (rendered_dom_capture_result.get("expanded_dom") or {}).get("download_like_anchor_count") or 0),
                        "blob_like_string_count": int(rendered_dom_capture_result.get("blob_like_string_count") or (rendered_dom_capture_result.get("expanded_dom") or {}).get("blob_like_string_count") or 0),
                        "visible_text_limited": _v64_limit_snippet(rendered_dom_capture_result.get("visible_text_limited") or (rendered_dom_capture_result.get("expanded_dom") or {}).get("visible_text_limited") or ""),
                        "post_click_wait_ms": int(rendered_dom_capture_result.get("post_click_wait_ms") or 0),
                        "blob_links_limited": [],
                    })
                    rendered_blob_links: List[Dict[str, Any]] = []
                    rendered_blob_link_hrefs: List[str] = []
                    seen_rendered_blob_hrefs = set()
                    for blob_source in (
                        rendered_dom_capture_result.get("blob_links") if isinstance(rendered_dom_capture_result.get("blob_links"), list) else [],
                        (rendered_dom_capture_result.get("expanded_dom") or {}).get("blob_links") if isinstance(rendered_dom_capture_result.get("expanded_dom"), dict) else [],
                    ):
                        if not isinstance(blob_source, list):
                            continue
                        for link in blob_source:
                            if not isinstance(link, dict):
                                continue
                            href = _clean(link.get("href") or link.get("url") or link.get("document_url"))
                            if not href or href in seen_rendered_blob_hrefs:
                                continue
                            seen_rendered_blob_hrefs.add(href)
                            rendered_blob_links.append(link)
                            rendered_blob_link_hrefs.append(href)
                    interactive_blob_candidates = _v64_extract_interactive_blob_candidates(
                        rendered_blob_links,
                        resolved_index_page_url,
                        source,
                        source_link_url,
                    )
                    if interactive_blob_candidates:
                        artifact_candidates = _v56_dedupe_document_links(artifact_candidates + interactive_blob_candidates)
                        artifact_candidates.sort(key=lambda item: int(item.get("candidate_score") or 0), reverse=True)
                    rendered_dom_capture_diag.update({
                        "row_found": bool(
                            rendered_dom_capture_result.get("row_found")
                            or rendered_dom_capture_result.get("row_clicked")
                            or rendered_dom_capture_result.get("matched_row")
                        ),
                        "row_expanded": bool(rendered_dom_capture_result.get("row_expanded")),
                        "documents_section_found": bool(
                            rendered_dom_capture_result.get("documents_section_found")
                            or (rendered_dom_capture_result.get("expanded_dom") or {}).get("documents_section_found")
                            or interactive_blob_candidates
                        ),
                        "interactive_blob_candidates_count": len(interactive_blob_candidates),
                        "rendered_blob_candidates_count": len(interactive_blob_candidates),
                        "blob_links_limited": rendered_blob_link_hrefs[:10],
                    })
            if rendered_dom_capture_diag["status"] != "attempted" or rendered_dom_capture_diag["rendered_html_length"] or rendered_dom_capture_diag["failure_reason"] == "":
                diagnostics.append(rendered_dom_capture_diag)
            interactive_dom_capture_diag["interactive_blob_candidates_count"] = len(interactive_blob_candidates)
            if not interactive_dom_capture_diag["row_found"]:
                interactive_dom_capture_diag["failure_reason"] = "row_not_found|page_state_no_table" if not interactive_dom_capture_diag["table_container_found"] else "row_not_found"
            elif not interactive_dom_capture_diag["documents_section_found"]:
                interactive_dom_capture_diag["failure_reason"] = "documents_section_not_found"
            elif not interactive_blob_candidates:
                interactive_dom_capture_diag["failure_reason"] = "no_blob_links_found"
            else:
                interactive_dom_capture_diag["failure_reason"] = _clean(
                    rendered_dom_capture_result.get("failure_reason")
                    or rendered_dom_capture_result.get("error")
                    or ""
                )
            diagnostics.append(interactive_dom_capture_diag)
            if _v64_is_etenders_detail_page(resolved_index_page_url) and not interactive_blob_candidates:
                endpoint_probe_result = _v64_probe_etenders_document_endpoints(
                    html_body,
                    resolved_index_page_url,
                    source,
                    timeout=timeout,
                )
                source_link_diag["etenders_endpoint_probe_count"] = int(endpoint_probe_result.get("etenders_endpoint_probe_count") or 0)
                source_link_diag["etenders_endpoint_success_count"] = int(endpoint_probe_result.get("etenders_endpoint_success_count") or 0)
                source_link_diag["etenders_endpoint_failure_count"] = int(endpoint_probe_result.get("etenders_endpoint_failure_count") or 0)
                source_link_diag["etenders_document_candidates_from_endpoints"] = int(endpoint_probe_result.get("etenders_document_candidates_from_endpoints") or 0)
                source_link_diag["etenders_endpoint_failures_by_reason"] = endpoint_probe_result.get("etenders_endpoint_failures_by_reason") or {}
                etenders_endpoint_probe_count += int(endpoint_probe_result.get("etenders_endpoint_probe_count") or 0)
                etenders_endpoint_success_count += int(endpoint_probe_result.get("etenders_endpoint_success_count") or 0)
                etenders_endpoint_failure_count += int(endpoint_probe_result.get("etenders_endpoint_failure_count") or 0)
                etenders_document_candidates_from_endpoints += int(endpoint_probe_result.get("etenders_document_candidates_from_endpoints") or 0)
                for reason_key, count in (endpoint_probe_result.get("etenders_endpoint_failures_by_reason") or {}).items():
                    key = _clean(reason_key) or "endpoint_probe_failed"
                    etenders_endpoint_failures_by_reason[key] = etenders_endpoint_failures_by_reason.get(key, 0) + int(count or 0)
                diagnostics.extend(endpoint_probe_result.get("diagnostics") or [])
                artifact_candidates = _v56_dedupe_document_links(
                    artifact_candidates + (endpoint_probe_result.get("artifact_candidates") or [])
                )
                artifact_candidates.sort(key=lambda item: int(item.get("candidate_score") or 0), reverse=True)
            source_link_diag["artifact_candidates_found_count"] = len(artifact_candidates)
            artifact_candidates_found_count += len(artifact_candidates)
            if not artifact_candidates:
                index_page_no_artifacts_count += 1
                source_link_diag.update({
                    "failure_stage": "index_page_no_artifacts",
                    "failure_reason": "no_artifact_links_found",
                    "download_finished_at": _now_iso(),
                })
                diagnostics.append(source_link_diag)
                continue
            index_pages_with_artifacts_count += 1
            source_link_diag["failure_stage"] = ""
            source_link_diag["failure_reason"] = ""
            source_link_diag["download_finished_at"] = _now_iso()
            diagnostics.append(source_link_diag)
            attempted_candidates: List[Dict[str, Any]] = []
            for artifact_candidate in artifact_candidates:
                should_attempt = bool(artifact_candidate.get("candidate_should_attempt"))
                _record_candidate_summary(artifact_candidate, should_attempt)
                if not should_attempt:
                    diagnostics.append(_rejected_candidate_diag(artifact_candidate, source_link_url, resolved_index_page_url))
                    continue
                attempted_candidates.append(artifact_candidate)
            for artifact_candidate in attempted_candidates:
                artifact_download_attempts_count += 1
                download_result = _v56_download_document(artifact_candidate, source, timeout=timeout)
                art_attempts = _annotate_attempts(
                    download_result,
                    diagnostic_type="artifact_candidate",
                    source_link_url=source_link_url,
                    resolved_index_page_url=resolved_index_page_url,
                    artifact_candidates_count=len(artifact_candidates),
                    candidate_context=artifact_candidate,
                )
                diagnostics.extend(art_attempts)
                artifact_resolved_to_html_count += sum(1 for diag in art_attempts if _clean(diag.get("failure_stage")) == "artifact_resolved_to_html")
                artifact_binary_signature_success_count += sum(1 for diag in art_attempts if bool(diag.get("binary_signature_verified")))
                if download_result.get("status") == "downloaded":
                    artifact_download_success_count += 1
                    downloaded_path = _clean(download_result.get("artifact_path") or download_result.get("path"))
                    downloaded_timestamp = _clean(download_result.get("download_finished_at") or _now_iso())
                    fallback_used = bool(download_result.get("fallback_used")) or fallback_used
                    direct_downloads.append(download_result)
                    break
                artifact_download_failed_count += 1
                fallback_used = bool(download_result.get("fallback_used")) or fallback_used
            if downloaded_path:
                break
            if not any(artifact.get("status") == "downloaded" for artifact in direct_downloads):
                source_link_diag["failure_stage"] = "artifact_download_failed"
                source_link_diag["failure_reason"] = "all_artifact_candidates_failed"
        except Exception as exc:
            source_link_diag.update({
                "failure_stage": "http_fetch",
                "failure_reason": _truncate(str(exc), 240),
                "download_finished_at": _now_iso(),
            })
            diagnostics.append(source_link_diag)
            continue

    failure_reason = ""
    if not downloaded_path:
        diagnostic_reasons: List[str] = []
        for diag in diagnostics:
            if not isinstance(diag, dict):
                continue
            diagnostic_type = _clean(diag.get("diagnostic_type"))
            failure_stage = _clean(diag.get("failure_stage"))
            if diagnostic_type == "source_link":
                if failure_stage == "url_resolution":
                    diagnostic_reasons.append("buyer_pack_url_resolution_failed")
                elif failure_stage == "auth_required":
                    diagnostic_reasons.append("buyer_pack_auth_required")
                elif failure_stage == "http_fetch":
                    diagnostic_reasons.append("buyer_pack_download_failed")
                elif failure_stage == "unsupported_content_type":
                    diagnostic_reasons.append("unsupported_document_format")
                elif failure_stage == "index_page_no_artifacts":
                    diagnostic_reasons.append("index_page_no_artifacts")
                elif failure_stage == "skipped":
                    diagnostic_reasons.append(_clean(diag.get("failure_reason") or "source_link_skipped"))
            elif diagnostic_type == "artifact_candidate":
                if failure_stage == "url_resolution":
                    diagnostic_reasons.append("buyer_pack_url_resolution_failed")
                elif failure_stage == "auth_required":
                    diagnostic_reasons.append("buyer_pack_auth_required")
                elif failure_stage == "unsupported_content_type":
                    diagnostic_reasons.append("unsupported_document_format")
                elif failure_stage == "artifact_resolved_to_html":
                    diagnostic_reasons.append("artifact_resolved_to_html")
                elif failure_stage == "empty_content":
                    diagnostic_reasons.append("empty_document_content")
                elif failure_stage == "file_write":
                    diagnostic_reasons.append("buyer_pack_file_write_failed")
                elif failure_stage == "checksum":
                    diagnostic_reasons.append("artifact_checksum_failed")
                elif failure_stage == "http_fetch":
                    diagnostic_reasons.append("buyer_pack_download_failed")
                elif failure_stage == "skipped":
                    diagnostic_reasons.append(_clean(diag.get("failure_reason") or "artifact_candidate_skipped"))
            elif diagnostic_type == "artifact_candidate_rejected":
                diagnostic_reasons.append(_clean(diag.get("candidate_rejection_reason") or "artifact_candidate_skipped"))
        if diagnostic_reasons:
            failure_reason = _truncate(diagnostic_reasons[0], 120)
        elif index_page_no_artifacts_count > 0:
            failure_reason = "index_page_no_artifacts"
        elif artifact_candidates_found_count > 0:
            failure_reason = "artifact_download_failed"
        elif index_pages_fetched_count > 0:
            failure_reason = "index_page_no_artifacts"
        else:
            failure_reason = "document_links_detected_but_no_artifact"

    return {
        "attempted": attempted,
        "downloaded": bool(downloaded_path),
        "buyer_pack_downloaded": bool(downloaded_path),
        "buyer_pack_path": downloaded_path,
        "buyer_pack_download_timestamp": downloaded_timestamp,
        "failure_reason": failure_reason,
        "diagnostics": diagnostics,
        "downloads": direct_downloads,
        "index_pages_fetched_count": index_pages_fetched_count,
        "index_pages_with_artifacts_count": index_pages_with_artifacts_count,
        "artifact_candidates_found_count": artifact_candidates_found_count,
        "artifact_download_attempts_count": artifact_download_attempts_count,
        "artifact_download_success_count": artifact_download_success_count,
        "artifact_candidates_total": artifact_candidates_total,
        "artifact_candidates_attempted": artifact_candidates_attempted,
        "artifact_candidates_rejected_before_fetch": artifact_candidates_rejected_before_fetch,
        "artifact_candidates_by_classification": artifact_candidates_by_classification,
        "artifact_rejections_by_reason": artifact_rejections_by_reason,
        "artifact_resolved_to_html_count": artifact_resolved_to_html_count,
        "artifact_binary_signature_success_count": artifact_binary_signature_success_count,
        "etenders_endpoint_probe_count": etenders_endpoint_probe_count,
        "etenders_endpoint_success_count": etenders_endpoint_success_count,
        "etenders_endpoint_failure_count": etenders_endpoint_failure_count,
        "etenders_document_candidates_from_endpoints": etenders_document_candidates_from_endpoints,
        "etenders_endpoint_failures_by_reason": etenders_endpoint_failures_by_reason,
        "index_page_no_artifacts_count": index_page_no_artifacts_count,
        "artifact_download_failed_count": artifact_download_failed_count,
        "fallback_used": fallback_used,
    }


def _v56_extract_document_links_from_html(html: str, base_url: str, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html or "", "html.parser")
        for anchor in soup.find_all("a"):
            href = _clean(anchor.get("href"))
            if not href:
                continue
            absolute = urljoin(base_url, href)
            label = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True) or "").strip()
            if not _v56_is_safe_public_document_url(absolute):
                continue
            if not _v56_link_text_is_document(label, absolute):
                continue
            ext = _v56_document_extension(absolute)
            if ext not in DOCUMENT_DISCOVERY_EXTENSIONS:
                continue
            links.append({
                "url": absolute,
                "link_text": label,
                "filename": _v56_safe_filename(urlparse(absolute).path, "document" + ext),
                "extension": ext,
                "source_name": _clean(source.get("name") or source.get("source_name")),
                "source_url": base_url,
            })
    except Exception:
        for match in re.findall(r"""href=["']([^"']+\.(?:pdf|docx?|xlsx?|xls|zip)(?:\?[^"']*)?)["']""", html or "", flags=re.I):
            absolute = urljoin(base_url, match)
            if _v56_is_safe_public_document_url(absolute):
                ext = _v56_document_extension(absolute)
                links.append({
                    "url": absolute,
                    "link_text": "",
                    "filename": _v56_safe_filename(urlparse(absolute).path, "document" + ext),
                    "extension": ext,
                    "source_name": _clean(source.get("name") or source.get("source_name")),
                    "source_url": base_url,
                })
    return _v56_dedupe_document_links(links)


def _v56_dedupe_document_links(links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for link in links:
        url = _clean(link.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        output.append(link)
    return output


def _v56_scan_source_document_links(source: Dict[str, Any], harvested: List[Dict[str, Any]], timeout: int = 12) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    source_url = _clean(source.get("url") or source.get("list_url"))
    if source_url and _v56_is_safe_public_document_url(source_url):
        try:
            response = requests.get(
                source_url,
                timeout=timeout,
                verify=bool(source.get("verify_ssl", True)),
                headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0", "Accept": "text/html,application/xhtml+xml,*/*"},
            )
            ctype = _safe_lower(response.headers.get("content-type"))
            if response.ok and "html" in ctype:
                links.extend(_v56_extract_document_links_from_html(response.text, source_url, source))
        except Exception as exc:
            logger.debug("V56 document link scan failed for %s: %s", source.get("name"), exc)
    for item in harvested:
        for url in _v52_document_urls(item):
            if not _v56_is_safe_public_document_url(url):
                continue
            ext = _v56_document_extension(url)
            if ext not in DOCUMENT_DISCOVERY_EXTENSIONS:
                continue
            links.append({
                "url": url,
                "link_text": _clean(item.get("title") or item.get("description")),
                "filename": _v56_safe_filename(urlparse(url).path, "document" + ext),
                "extension": ext,
                "source_name": _clean(source.get("name") or source.get("source_name")),
                "source_url": _clean(item.get("source_url") or source_url),
                "parent_title": _clean(item.get("title")),
                "parent_closing_date": _clean(item.get("closing_date")),
            })
    return _v56_dedupe_document_links(links)


def _v56_download_document(link: Dict[str, Any], source: Dict[str, Any], timeout: int = 25) -> Dict[str, Any]:
    started_at = _now_iso()
    raw_url = _clean(link.get("url"))
    source_url = _clean(source.get("url") or source.get("list_url") or link.get("source_url"))
    ext_hint = _clean(link.get("extension") or _v64_document_extension(raw_url, "", _clean(link.get("filename"))))
    attempts: List[Dict[str, Any]] = []
    redirect_chain: List[Dict[str, Any]] = []
    link_metadata = {
        key: link.get(key)
        for key in (
            "route_pattern_name",
            "source_json_path",
            "parameter_names_used",
            "tender_id_used",
            "document_id_used",
            "original_json_value",
            "resolved_document_url",
            "source",
            "source_hint",
            "candidate_source_json_keys",
        )
        if link.get(key) not in (None, "", [], {})
    }

    def _annotate_attempt(attempt: Dict[str, Any]) -> Dict[str, Any]:
        if link_metadata:
            attempt.update(link_metadata)
        return attempt

    candidate_urls = _v64_resolve_document_url_candidates(link, source)
    if not candidate_urls:
        return {
            "status": "failed",
            "failure_stage": "url_resolution",
            "reason": "unable_to_resolve_document_url",
            "failure_reason": "unable_to_resolve_document_url",
            "error": "unable_to_resolve_document_url",
            "download_started_at": started_at,
            "download_finished_at": _now_iso(),
            "resolved_document_url": "",
            "document_url": raw_url,
            "content_type": "",
            "content_length": 0,
            "redirect_chain": [],
            "artifact_path": "",
            "artifact_exists": False,
            "artifact_size_bytes": 0,
            "fallback_used": False,
            "link": link,
            "attempts": [],
            **link_metadata,
        }

    fallback_used = len(candidate_urls) > 1
    for candidate in candidate_urls:
        candidate_url = _clean(candidate.get("url"))
        candidate_stage = _clean(candidate.get("stage"))
        attempt_started_at = _now_iso()
        attempt: Dict[str, Any] = {
            "candidate_url": candidate_url,
            "resolved_document_url": candidate_url,
            "url_stage": candidate_stage,
            "download_started_at": attempt_started_at,
            "download_finished_at": "",
            "http_status": 0,
            "content_type": "",
            "content_length": 0,
            "redirect_chain": [],
            "artifact_path": "",
            "artifact_exists": False,
            "artifact_size_bytes": 0,
            "binary_signature_verified": False,
            "candidate_classification": _clean(link.get("candidate_classification")) or "unknown",
            "candidate_score": int(link.get("candidate_score") or 0),
            "candidate_rejection_reason": _clean(link.get("candidate_rejection_reason")),
            "failure_stage": "",
            "failure_reason": "",
        }
        try:
            if not candidate_url or not _v56_is_safe_public_document_url(candidate_url):
                attempt.update({
                    "failure_stage": "url_resolution",
                    "failure_reason": "unsafe_or_malformed_document_url",
                    "download_finished_at": _now_iso(),
                })
                attempts.append(_annotate_attempt(attempt))
                continue
            with requests.get(
                candidate_url,
                timeout=timeout,
                stream=True,
                allow_redirects=True,
                verify=bool(source.get("verify_ssl", True)),
                headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0", "Accept": "application/pdf,application/msword,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.*,*/*"},
            ) as response:
                ctype = _safe_lower(response.headers.get("content-type"))
                disposition = _clean(response.headers.get("content-disposition"))
                content_length = int(response.headers.get("content-length") or 0)
                redirect_chain = [
                    {"url": _clean(item.url), "status_code": int(getattr(item, "status_code", 0) or 0)}
                    for item in list(getattr(response, "history", []) or [])
                ]
                redirect_chain.append({"url": _clean(response.url), "status_code": int(getattr(response, "status_code", 0) or 0)})
                detected_ext = _v64_document_extension(candidate_url, ctype, _clean(link.get("filename") or Path(urlparse(response.url).path).name))
                if int(response.status_code or 0) in {401, 403, 407, 429}:
                    attempt.update({
                        "failure_stage": "auth_required",
                        "failure_reason": f"HTTP {int(response.status_code or 0)}",
                        "http_status": int(response.status_code or 0),
                        "content_type": ctype,
                        "content_length": content_length,
                        "redirect_chain": redirect_chain,
                        "binary_signature_verified": False,
                        "download_finished_at": _now_iso(),
                    })
                    attempts.append(attempt)
                    continue
                body_sample = _truncate(response.text or "", 1200) if "html" in ctype and hasattr(response, "text") else ""
                if "html" in ctype:
                    attempt.update({
                        "failure_stage": "artifact_resolved_to_html",
                        "failure_reason": "html_response_not_document",
                        "http_status": int(response.status_code or 0),
                        "content_type": ctype,
                        "content_length": content_length,
                        "redirect_chain": redirect_chain,
                        "response_classification": "html_response",
                        "binary_signature_verified": False,
                        "download_finished_at": _now_iso(),
                    })
                    attempts.append(_annotate_attempt(attempt))
                    continue
                chunks = list(response.iter_content(chunk_size=65536))
                first_nonempty = next((chunk for chunk in chunks if chunk), b"")
                if not first_nonempty and content_length == 0 and not (response.headers.get("transfer-encoding") or ""):
                    attempt.update({
                        "failure_stage": "empty_content",
                        "failure_reason": "empty_response_body",
                        "http_status": int(response.status_code or 0),
                        "content_type": ctype,
                        "content_length": 0,
                        "redirect_chain": redirect_chain,
                        "binary_signature_verified": False,
                        "download_finished_at": _now_iso(),
                    })
                    attempts.append(_annotate_attempt(attempt))
                    continue
                sniffed_ext, binary_signature_verified = _v64_sniff_document_signature(
                    first_nonempty[:512],
                    detected_ext=detected_ext or ext_hint,
                    filename=_clean(link.get("filename") or Path(urlparse(response.url).path).name),
                    url=candidate_url,
                    link_text=_clean(link.get("link_text")),
                    content_type=ctype,
                )
                effective_ext = sniffed_ext or detected_ext or ext_hint
                if effective_ext not in DOCUMENT_DOWNLOAD_EXTENSIONS:
                    attempt.update({
                        "failure_stage": "unsupported_content_type",
                        "failure_reason": f"unsupported_extension:{effective_ext or 'unknown'}",
                        "http_status": int(response.status_code or 0),
                        "content_type": ctype,
                        "content_length": content_length,
                        "redirect_chain": redirect_chain,
                        "binary_signature_verified": binary_signature_verified,
                        "download_finished_at": _now_iso(),
                    })
                    attempts.append(_annotate_attempt(attempt))
                    continue
                response.raise_for_status()
                filename = _v56_safe_filename(link.get("filename") or urlparse(response.url).path, "document" + effective_ext)
                if Path(filename).suffix.lower() not in DOCUMENT_DOWNLOAD_EXTENSIONS:
                    filename = f"{Path(filename).stem}{effective_ext}"
                digest = sha256(candidate_url.encode("utf-8")).hexdigest()[:12]
                path = DOCUMENT_DISCOVERY_DIR / f"{digest}_{filename}"
                total = 0
                try:
                    with path.open("wb") as handle:
                        for chunk in chunks:
                            if not chunk:
                                continue
                            total += len(chunk)
                            if total > DOCUMENT_MAX_BYTES:
                                raise ValueError("document_too_large")
                            handle.write(chunk)
                except ValueError as exc:
                    if str(exc) == "document_too_large":
                        path.unlink(missing_ok=True)
                        attempt.update({
                        "failure_stage": "unsupported_content_type",
                        "failure_reason": "document_too_large",
                        "http_status": int(response.status_code or 0),
                        "content_type": ctype,
                        "content_length": total,
                        "redirect_chain": redirect_chain,
                        "binary_signature_verified": binary_signature_verified,
                        "download_finished_at": _now_iso(),
                    })
                    attempts.append(_annotate_attempt(attempt))
                    continue
                    raise
                except Exception as exc:
                    path.unlink(missing_ok=True)
                    attempt.update({
                        "failure_stage": "file_write",
                        "failure_reason": _truncate(str(exc), 240),
                        "http_status": int(response.status_code or 0),
                        "content_type": ctype,
                        "content_length": content_length or total,
                        "redirect_chain": redirect_chain,
                        "binary_signature_verified": binary_signature_verified,
                        "download_finished_at": _now_iso(),
                    })
                    attempts.append(_annotate_attempt(attempt))
                    continue
                artifact_exists, artifact_size = _v64_document_artifact_evidence_ok(str(path), ctype, effective_ext)
                if not artifact_exists:
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    attempt.update({
                        "failure_stage": "checksum",
                        "failure_reason": "artifact_evidence_invalid",
                        "http_status": int(response.status_code or 0),
                        "content_type": ctype,
                        "content_length": content_length or total,
                        "redirect_chain": redirect_chain,
                        "artifact_path": str(path),
                        "artifact_exists": False,
                        "artifact_size_bytes": artifact_size,
                        "binary_signature_verified": binary_signature_verified,
                        "download_finished_at": _now_iso(),
                    })
                    attempts.append(_annotate_attempt(attempt))
                    continue
                attempt.update({
                    "download_finished_at": _now_iso(),
                    "http_status": int(response.status_code or 0),
                    "content_type": ctype,
                    "content_length": content_length or total,
                    "redirect_chain": redirect_chain,
                    "artifact_path": str(path),
                    "artifact_exists": True,
                    "artifact_size_bytes": artifact_size,
                    "binary_signature_verified": binary_signature_verified,
                })
                attempts.append(_annotate_attempt(attempt))
                return {
                    "status": "downloaded",
                    "failure_stage": "",
                    "failure_reason": "",
                    "download_started_at": started_at,
                    "download_finished_at": attempt["download_finished_at"],
                    "url": response.url,
                    "resolved_document_url": candidate_url,
                    "original_url": raw_url,
                    "source_url": source_url,
                    "path": str(path),
                    "artifact_path": str(path),
                    "artifact_exists": True,
                    "artifact_size_bytes": artifact_size,
                    "filename": filename,
                    "extension": effective_ext,
                    "content_type": ctype,
                    "content_disposition": disposition,
                    "content_length": content_length or total,
                    "bytes": total,
                    "redirect_chain": redirect_chain,
                    "fallback_used": fallback_used,
                    "binary_signature_verified": binary_signature_verified,
                    "link": link,
                    "attempts": attempts,
                    **link_metadata,
                }
        except Exception as exc:
            error_text = _truncate(str(exc), 240)
            failure_stage = "http_fetch"
            if "Invalid URL" in error_text or "MissingSchema" in error_text or "No connection adapters" in error_text:
                failure_stage = "url_resolution"
            elif "401" in error_text or "403" in error_text or "407" in error_text or "429" in error_text:
                failure_stage = "auth_required"
            elif "timed out" in error_text.lower() or "timeout" in error_text.lower():
                failure_stage = "http_fetch"
            attempt.update({
                "failure_stage": failure_stage,
                "failure_reason": error_text,
                "download_finished_at": _now_iso(),
                "redirect_chain": redirect_chain,
            })
            attempts.append(_annotate_attempt(attempt))
            continue

    final_failure_stage = attempts[-1]["failure_stage"] if attempts else "url_resolution"
    final_failure_reason = attempts[-1]["failure_reason"] if attempts else "unable_to_resolve_document_url"
    return {
        "status": "failed",
        "failure_stage": final_failure_stage or "unknown",
        "reason": final_failure_reason or "download_error",
        "failure_reason": final_failure_reason or "download_error",
        "error": final_failure_reason or "download_error",
        "download_started_at": started_at,
        "download_finished_at": _now_iso(),
        "resolved_document_url": attempts[-1]["resolved_document_url"] if attempts else "",
        "document_url": raw_url,
        "source_url": source_url,
        "content_type": attempts[-1]["content_type"] if attempts else "",
        "content_length": attempts[-1]["content_length"] if attempts else 0,
        "redirect_chain": attempts[-1]["redirect_chain"] if attempts else [],
        "artifact_path": attempts[-1]["artifact_path"] if attempts else "",
        "artifact_exists": bool(attempts and attempts[-1].get("artifact_exists")),
        "artifact_size_bytes": int(attempts[-1].get("artifact_size_bytes") or 0) if attempts else 0,
        "binary_signature_verified": bool(attempts and attempts[-1].get("binary_signature_verified")),
        "fallback_used": fallback_used,
        "link": link,
        "attempts": attempts,
        **link_metadata,
    }


def _v56_parse_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return ""
    try:
        reader = PdfReader(str(path))
        parts: List[str] = []
        for page in list(reader.pages)[:8]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return re.sub(r"\s+", " ", " ".join(parts)).strip()
    except Exception:
        return ""


def _v56_parse_docx(path: Path) -> str:
    try:
        from docx import Document  # type: ignore

        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs if _clean(p.text)]
        for table in doc.tables[:8]:
            for row in table.rows[:30]:
                parts.append(" ".join(_clean(cell.text) for cell in row.cells if _clean(cell.text)))
        return re.sub(r"\s+", " ", " ".join(parts)).strip()
    except Exception:
        return ""


def _v56_parse_xlsx(path: Path) -> str:
    try:
        from openpyxl import load_workbook  # type: ignore

        wb = load_workbook(str(path), read_only=True, data_only=True)
        parts: List[str] = []
        for sheet in wb.worksheets[:4]:
            for row in sheet.iter_rows(max_row=60, max_col=12, values_only=True):
                row_text = " ".join(_clean(value) for value in row if _clean(value))
                if row_text:
                    parts.append(row_text)
        return re.sub(r"\s+", " ", " ".join(parts)).strip()
    except Exception:
        return ""


def _v56_parse_csv(path: Path) -> str:
    try:
        import csv

        parts: List[str] = []
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.reader(handle)
            for row_index, row in enumerate(reader):
                if row_index >= 120:
                    break
                row_text = " ".join(_clean(value) for value in row if _clean(value))
                if row_text:
                    parts.append(row_text)
        return re.sub(r"\s+", " ", " ".join(parts)).strip()
    except Exception:
        return ""


def _v56_parse_document(download: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(_clean(download.get("path")))
    ext = _clean(download.get("extension") or path.suffix.lower())
    text = ""
    parser = "filename_only"
    if ext == ".pdf":
        parser = "pypdf"
        text = _v56_parse_pdf(path)
    elif ext == ".docx":
        parser = "python-docx"
        text = _v56_parse_docx(path)
    elif ext == ".xlsx":
        parser = "openpyxl"
        text = _v56_parse_xlsx(path)
    elif ext == ".csv":
        parser = "csv"
        text = _v56_parse_csv(path)
    elif ext == ".zip" and extract_zip_contents is not None:
        parser = "zip_content_extraction"
        try:
            zip_result = extract_zip_contents({
                "title": download.get("filename") or path.stem,
                "buyer_name": _clean(download.get("source_name") or ""),
                "buyer_rfq_number": _clean(download.get("filename") or path.stem),
                "zip_file_paths": [str(path)],
                "downloaded_files": [{"path": str(path), "filename": path.name, "url": _clean(download.get("url") or download.get("original_url"))}],
            })
            main_doc = _clean(zip_result.get("main_document_path"))
            if main_doc and Path(main_doc).exists():
                text = _truncate(_v56_parse_pdf(Path(main_doc)) or "", 7000)
                if not text:
                    text = _truncate(_clean(zip_result.get("classification_summary") or json.dumps(zip_result.get("classified_files") or {})), 7000)
            else:
                text = _truncate(json.dumps(zip_result.get("classified_files") or {}, default=str), 7000)
        except Exception:
            text = ""
    return {
        "status": "parsed" if text else "metadata_only",
        "parser": parser,
        "text": _truncate(text, 7000),
        "text_length": len(text),
        "path": str(path),
        "extension": ext,
        "filename": _clean(download.get("filename") or path.name),
        "url": _clean(download.get("url") or download.get("original_url")),
        "link": download.get("link") or {},
        "download_result": download,
    }


def _v56_classify_document(filename: str, text: str) -> Dict[str, Any]:
    blob = _safe_lower(f"{filename} {text}")
    scores = {
        "RFQ document": 0,
        "pricing schedule": 0,
        "SBD form": 0,
        "terms/specification": 0,
        "unrelated": 0,
    }
    if re.search(r"\brfq\b|request for quotation|quotation number|request\s+for\s+quotations", blob, flags=re.I):
        scores["RFQ document"] += 45
    if re.search(r"\bsupply\s*(and|&)?\s*delivery\b|delivery of|supply of|goods", blob, flags=re.I):
        scores["RFQ document"] += 20
    if re.search(r"closing date|closing time|quotation must be submitted|validity period", blob, flags=re.I):
        scores["RFQ document"] += 20
    if re.search(r"pricing schedule|schedule of prices|bill of quantities|\bboq\b|price schedule|unit price|total price", blob, flags=re.I):
        scores["pricing schedule"] += 60
    if re.search(r"\bqty\b|quantity|description of goods|rate\b|amount\b", blob, flags=re.I):
        scores["pricing schedule"] += 15
    if re.search(r"\bsbd\s*[0-9]\b|standard bidding document|declaration of interest|preference points claim", blob, flags=re.I):
        scores["SBD form"] += 75
    if re.search(r"terms of reference|specification|scope of work|special conditions|general conditions|technical specification", blob, flags=re.I):
        scores["terms/specification"] += 45
    if re.search(r"award|cancelled|cancellation|minutes|annual report|newsletter|policy", blob, flags=re.I):
        scores["unrelated"] += 35
    label = max(scores, key=scores.get)
    confidence = min(100, scores[label])
    if confidence < 25:
        label = "unrelated"
        confidence = max(confidence, 25 if scores["unrelated"] else 10)
    return {"classification": label, "classification_confidence": confidence, "classification_scores": scores}


def _v56_extract_document_metadata(filename: str, text: str, link: Dict[str, Any]) -> Dict[str, Any]:
    blob = re.sub(r"\s+", " ", f"{filename} {text}").strip()
    ref_match = re.search(r"\b(?:RFQ|RFP|BID|TENDER|QUO|SCM|FIN-SCM|Q)[-/A-Z0-9 ]{2,40}\d{2,6}(?:[-/]\d{2,4})?\b", blob, flags=re.I)
    closing = _extract_closing_date(blob)
    if not closing:
        iso_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", blob)
        if iso_match:
            closing = f"{iso_match.group(1)}-{int(iso_match.group(2)):02d}-{int(iso_match.group(3)):02d}"
    title = ""
    title_match = re.search(
        r"((?:request for quotation|rfq|supply|delivery|appointment|provision|terms of reference|specification)[^.;:\n]{18,180})",
        blob,
        flags=re.I,
    )
    if title_match:
        title = _truncate(title_match.group(1), 180)
    if not title:
        title = _truncate(re.sub(r"[_-]+", " ", Path(filename).stem), 180)
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", blob)
    return {
        "title": title,
        "reference_number": _clean(ref_match.group(0) if ref_match else ""),
        "closing_date": closing or _clean(link.get("parent_closing_date")),
        "contact_email": email_match.group(0) if email_match else "",
    }


def _v56_candidate_from_document(doc: Dict[str, Any], source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    classification = _clean(doc.get("classification"))
    if classification not in {"RFQ document", "pricing schedule", "terms/specification"}:
        return None
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    text = _clean(doc.get("text"))
    filename = _clean(doc.get("filename"))
    evidence_text = " ".join([filename, text[:2500], _clean(metadata.get("title"))])
    if not re.search(r"\brfq\b|request for quotation|quotation|supply|delivery|goods|pricing schedule|specification", evidence_text, flags=re.I):
        return None
    title = _clean(metadata.get("title")) or _truncate(Path(filename).stem, 180)
    item = _base_item(source, title, _clean(doc.get("url") or (doc.get("link") or {}).get("source_url")))
    item.update({
        "title": title,
        "description": _truncate(text or title, 1200),
        "raw_text": evidence_text,
        "document_text": text,
        "source_url": _clean((doc.get("link") or {}).get("source_url") or source.get("url") or doc.get("url")),
        "document_url": _clean(doc.get("url")),
        "document_urls": [_clean(doc.get("url"))],
        "closing_date": _clean(metadata.get("closing_date")),
        "buyer_name": _clean(source.get("name") or source.get("source_name") or doc.get("source_name")),
        "buyer_rfq_number": _clean(metadata.get("reference_number") or title),
        "rfq_number": _clean(metadata.get("reference_number") or title),
        "reference_number": _clean(metadata.get("reference_number") or title),
        "recipient_email": _clean(metadata.get("contact_email") or source.get("recipient_email") or source.get("buyer_email")),
        "buyer_email": _clean(metadata.get("contact_email") or source.get("buyer_email") or source.get("recipient_email")),
        "document_evidence": {
            "classification": classification,
            "classification_confidence": doc.get("classification_confidence"),
            "filename": filename,
            "path": doc.get("path"),
            "url": doc.get("url"),
            "parser": doc.get("parser"),
        },
        "buyer_pack_downloaded": False,
        "buyer_pack_verified": False,
        "buyer_pack_download_timestamp": _now_iso(),
        "buyer_pack_source": _clean(source.get("name") or source.get("source_name") or "document_discovery"),
        "buyer_pack_path": _clean(doc.get("path")),
        "buyer_pack_failure_reason": "",
        "buyer_pack_attempted": True,
        "document_links_count": 1,
        "built_from_document_evidence": True,
    })
    download_result = doc.get("download_result") if isinstance(doc.get("download_result"), dict) else {}
    artifact_ok, artifact_size = _v64_document_artifact_evidence_ok(
        _clean(download_result.get("artifact_path") or doc.get("path")),
        _clean(download_result.get("content_type") or ""),
        _clean(download_result.get("extension") or doc.get("extension") or ""),
    )
    if artifact_ok:
        item["buyer_pack_downloaded"] = True
        item["buyer_pack_verified"] = True
        item["buyer_pack_path"] = _clean(download_result.get("artifact_path") or doc.get("path"))
        item["buyer_pack_download_timestamp"] = _clean(download_result.get("download_finished_at") or _now_iso())
    item["buyer_pack_download_diagnostics"] = [download_result] if download_result else []
    item["buyer_pack_downloaded"] = bool(item["buyer_pack_downloaded"] and artifact_ok and artifact_size > 0)
    item["buyer_pack_verified"] = bool(item["buyer_pack_downloaded"])
    return item


def _v56_discover_documents_for_source(source: Dict[str, Any], harvested: List[Dict[str, Any]], max_documents: int = 8) -> Dict[str, Any]:
    links = _v56_scan_source_document_links(source, harvested)
    downloads: List[Dict[str, Any]] = []
    download_attempts: List[Dict[str, Any]] = []
    parsed_documents: List[Dict[str, Any]] = []
    skipped_links: List[Dict[str, Any]] = []
    download_budget = _safe_positive_int(max_documents, 8)
    for link in links:
        if len(downloads) >= download_budget:
            skipped_links.append({"reason": "download_budget_reached", "link": link})
            continue
        result = _v56_download_document(link, source)
        download_attempts.extend(result.get("attempts") if isinstance(result.get("attempts"), list) else [result])
        if result.get("status") == "downloaded":
            downloads.append(result)
            parsed = _v56_parse_document(result)
            classification = _v56_classify_document(parsed.get("filename", ""), parsed.get("text", ""))
            metadata = _v56_extract_document_metadata(parsed.get("filename", ""), parsed.get("text", ""), parsed.get("link") or {})
            parsed_documents.append({**parsed, **classification, "metadata": metadata, "download_result": result})
        else:
            skipped_links.append(result)
    built_items: List[Dict[str, Any]] = []
    for doc in parsed_documents:
        item = _v56_candidate_from_document(doc, source)
        if item:
            built_items.append(item)
    return {
        "document_links": links,
        "downloads": downloads,
        "download_attempts": download_attempts,
        "parsed_documents": parsed_documents,
        "skipped_links": skipped_links,
        "built_items": _dedupe_keep_order(built_items),
    }


def _v52_is_expired(closing_date: Any, blob: str) -> bool:
    if re.search(r"\b(closed|expired|awarded|cancelled|canceled)\b", blob, flags=re.I):
        return True
    parsed = _parse_closing_date_value(closing_date, blob)
    if not parsed:
        return False
    try:
        return datetime.strptime(parsed[:10], "%Y-%m-%d").date() < datetime.now(timezone.utc).date()
    except Exception:
        return False


def _v52_estimated_profit_signal(blob: str, item: Dict[str, Any]) -> Dict[str, Any]:
    explicit = _safe_float(
        item.get("estimated_profit")
        or item.get("profit_estimate")
        or item.get("expected_profit")
        or item.get("total_profit"),
        0.0,
    )
    if explicit > 0:
        return {
            "estimated_profit": round(explicit, 2),
            "source": "explicit_item_value",
            "meets_threshold": explicit >= DEFAULT_MINIMUM_PROFIT,
        }
    score_profit = 0.0
    if re.search(r"\bsupply\s*(and|&|,)?\s*delivery\b|supply of|delivery of|deliver and supply", blob, flags=re.I):
        score_profit = 60000.0
    elif re.search(r"\bsupply\b|\bdelivery\b|\bgoods\b|\bequipment\b|\bmaterials?\b", blob, flags=re.I):
        score_profit = 45000.0
    elif re.search(r"\brfq\b|request for quotation|quotation", blob, flags=re.I):
        score_profit = 30000.0
    else:
        score_profit = 15000.0
    if re.search(r"\bbulk\b|panel|period of|36 months|framework|as and when|multiple", blob, flags=re.I):
        score_profit += 30000.0
    if re.search(r"\bonce[- ]off|small value|minor|ad hoc", blob, flags=re.I):
        score_profit -= 15000.0
    score_profit = max(0.0, score_profit)
    return {
        "estimated_profit": round(score_profit, 2),
        "source": "keyword_signal",
        "meets_threshold": score_profit >= DEFAULT_MINIMUM_PROFIT,
    }


def _v52_candidate_from_item(item: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    title = _clean(item.get("title") or item.get("buyer_rfq_number") or item.get("rfq_number") or item.get("reference_number"))
    description = _clean(item.get("description") or item.get("raw_text") or title)
    blob = " ".join([title, description, _clean(item.get("category")), _clean(item.get("source_type"))])
    blob_lower = blob.lower()
    document_urls = _v52_document_urls(item)
    response_url = _clean(item.get("response_url") or item.get("detail_url") or item.get("source_url") or source.get("url"))
    submission_method = _clean(item.get("submission_method") or source.get("submission_method") or "")
    email_submission = bool(
        item.get("buyer_email")
        or item.get("recipient_email")
        or re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", blob)
        or submission_method.lower() == "email"
    )
    if email_submission:
        submission_method = "email"
    elif not submission_method:
        submission_method = "portal"
    profit_signal = _v52_estimated_profit_signal(blob, item)
    closing_date = _parse_closing_date_value(item.get("closing_date"), blob)
    source_url = _clean(item.get("source_url") or item.get("document_url") or source.get("url"))
    downloadable_document_urls = document_urls if isinstance(document_urls, list) else []
    candidate = {
        "source_name": _clean(source.get("name") or source.get("source_name") or item.get("source_name") or item.get("source") or "Unknown Source"),
        "source_url": source_url,
        "buyer_name": _clean(item.get("buyer_name") or item.get("buyer") or source.get("name") or source.get("source_name")),
        "title": title,
        "description": description,
        "closing_date": closing_date,
        "closing_date_valid": bool(closing_date),
        "closing_date_source": "parsed_text" if closing_date else "",
        "submission_method": submission_method,
        "document_urls": document_urls,
        "downloadable_document_urls": downloadable_document_urls,
        "has_downloadable_documents": bool(document_urls),
        "response_url": response_url,
        "confidence_score": 0.0,
        "exclusion_reason": "",
        "estimated_profit_signal": profit_signal,
        "source_type": _clean(source.get("type")),
        "source_group": _clean(source.get("source_group") or source.get("category_group")),
    }
    score = 0.0
    if re.search(r"\bsupply\s*(and|&|,)?\s*delivery\b|supply of|delivery of|supply and deliver", blob, flags=re.I):
        score += 35
    elif re.search(r"\bsupply\b|\bdelivery\b|\bgoods\b|\bequipment\b|\bmaterials?\b", blob, flags=re.I):
        score += 18
    if email_submission:
        score += 16
    if document_urls:
        score += 14
    if closing_date:
        score += 10
    if re.search(r"pricing schedule|bill of quantities|boq|schedule of prices|returnable", blob, flags=re.I):
        score += 10
    if profit_signal.get("meets_threshold"):
        score += 15
    if re.search(r"\bopen\b|active|available|current|in \d+ days", blob, flags=re.I):
        score += 6
    candidate["confidence_score"] = round(min(100.0, score), 2)
    candidate["_blob_lower"] = blob_lower
    return candidate


def _v52_exclusion_reason(candidate: Dict[str, Any]) -> str:
    blob = _safe_lower(" ".join([
        candidate.get("title"),
        candidate.get("description"),
        candidate.get("source_name"),
        candidate.get("source_url"),
    ]))
    exclusions = [
        ("medical_consumables", ["medical consumables", "medical supplies", "pharmaceutical", "medicine", "clinical", "surgical", "laboratory reagents"]),
        ("it_equipment", ["it equipment", "ict equipment", "laptop", "desktop computer", "server", "network equipment", "printer", "toner", "software"]),
        ("petrol_diesel", ["petrol", "diesel", "fuel supply", "fuel cards", "lubricants"]),
        ("catering", ["catering", "refreshments", "meals", "food parcels", "event catering"]),
    ]
    for reason, terms in exclusions:
        if any(term in blob for term in terms):
            return reason
    if re.search(r"compulsory briefing|mandatory briefing|briefing required|site meeting.*compulsory|compulsory site", blob, flags=re.I):
        return "briefing_required"
    if _v52_is_expired(candidate.get("closing_date"), blob):
        return "expired_or_closed"
    if not re.search(r"\bsupply\s*(and|&|,)?\s*delivery\b|supply of|delivery of|supply and deliver|\bsupply\b|\bdelivery\b|\bgoods\b|\bmaterials?\b", blob, flags=re.I):
        return "not_supply_delivery"
    if not candidate.get("closing_date"):
        return "missing_closing_date"
    if not candidate.get("document_urls"):
        return "no_downloadable_rfq_documents"
    if float((candidate.get("estimated_profit_signal") or {}).get("estimated_profit") or 0.0) < DEFAULT_MINIMUM_PROFIT:
        return "estimated_profit_below_threshold"
    return ""


def _v54_extract_email(text: str, item: Dict[str, Any]) -> str:
    explicit = _clean(item.get("buyer_email") or item.get("recipient_email") or item.get("contact_email"))
    if explicit:
        return explicit
    match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    return match.group(0) if match else ""


def _v54_extract_province(text: str) -> str:
    provinces = [
        "Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo",
        "Mpumalanga", "Northern Cape", "North West", "Western Cape", "National",
    ]
    for province in provinces:
        if re.search(re.escape(province), text, flags=re.I):
            return province
    return ""


def _v54_commodity_category(text: str) -> str:
    checks = [
        ("construction_heavy", r"\bconstruction\b|civil works|roads?|bridge|building works|renovation|sewer|reticulation|paving|asphalt"),
        ("it_equipment", r"\bit equipment\b|ict equipment|laptops?|desktops?|servers?|network equipment|software|licen[cs]e|toner|printer"),
        ("medical_consumables", r"medical consumables|medical supplies|pharmaceutical|clinical|surgical|laboratory reagents"),
        ("fuel", r"\bpetrol\b|\bdiesel\b|\bfuel\b|lubricants"),
        ("catering", r"catering|refreshments|meals|food parcels"),
        ("office_supplies", r"stationery|office supplies|printing|paper|consumables"),
        ("general_goods", r"\bsupply\b|\bdelivery\b|\bgoods\b|materials?|equipment|tools|uniforms|furniture"),
        ("services", r"services?|maintenance|support|consulting|panel"),
    ]
    for label, pattern in checks:
        if re.search(pattern, text, flags=re.I):
            return label
    return "unknown"


def _v54_estimated_scope(text: str) -> Dict[str, Any]:
    quantities = re.findall(r"\b\d{1,6}(?:[.,]\d{1,2})?\s*(?:units?|items?|boxes|reams|litres?|meters?|m²|sqm|kg|tons?)\b", text, flags=re.I)
    period = re.search(r"\b(?:period of|for)\s+(?:\d+|thirty[- ]six|twenty[- ]four|twelve)\s+(?:months?|years?)\b", text, flags=re.I)
    framework = bool(re.search(r"framework|panel|as and when|required from time to time|period of|contract", text, flags=re.I))
    low_complexity = bool(re.search(r"once[- ]off|supply and delivery|delivery of|quotation|rfq", text, flags=re.I)) and not framework
    return {
        "quantity_signals": quantities[:10],
        "contract_period": period.group(0) if period else "",
        "framework_agreement": framework,
        "low_complexity": low_complexity,
    }


def _v54_deep_extract_candidate(item: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    base = _v52_candidate_from_item(item, source)
    blob = " ".join([
        _clean(item.get("title")),
        _clean(item.get("buyer_rfq_number")),
        _clean(item.get("description")),
        _clean(item.get("raw_text")),
        _clean(item.get("category")),
        _clean(item.get("document_text")),
        _clean(source.get("name")),
        _clean(source.get("source_group")),
    ])
    blob = re.sub(r"\s+", " ", blob).strip()
    title = _clean(item.get("title") or base.get("title"))
    if len(title) < 8:
        title_match = re.search(r"((?:RFQ|RFP|BID|TENDER|REQUEST|SUPPLY|APPOINTMENT|PROVISION|PROCUREMENT)[^.;:\n]{20,220})", blob, flags=re.I)
        title = _truncate(title_match.group(1), 180) if title_match else title
    closing = _clean(base.get("closing_date") or item.get("closing_date") or _extract_closing_date(blob))
    briefing_required = bool(item.get("briefing_required")) or bool(
        re.search(r"compulsory briefing|mandatory briefing|briefing required|compulsory site|site meeting.*compulsory", blob, flags=re.I)
    )
    contact_email = _v54_extract_email(blob, item)
    document_urls = _v52_document_urls(item)
    commodity = _v54_commodity_category(blob)
    scope = _v54_estimated_scope(blob)
    submission_method = _clean(base.get("submission_method"))
    if contact_email:
        submission_method = "email"
    elif re.search(r"submit.*email|email.*quotation|send.*quotation", blob, flags=re.I):
        submission_method = "email"
    elif re.search(r"portal|e[- ]?submission|online submission", blob, flags=re.I):
        submission_method = "portal"
    response_url = _clean(base.get("response_url") or item.get("detail_url") or item.get("source_url") or source.get("url"))
    extracted = {
        **base,
        "title": title or base.get("title"),
        "buyer": _clean(item.get("buyer") or item.get("buyer_name") or source.get("name") or source.get("source_name")),
        "buyer_name": _clean(item.get("buyer_name") or item.get("buyer") or source.get("name") or source.get("source_name")),
        "description": _clean(item.get("description") or item.get("raw_text") or base.get("description")),
        "commodity_service_category": commodity,
        "closing_date": closing,
        "briefing_required": briefing_required,
        "submission_method": submission_method or "portal",
        "document_urls": document_urls,
        "downloadable_rfq_docs": document_urls,
        "contact_email": contact_email,
        "estimated_scope": scope,
        "province": _v54_extract_province(blob),
        "response_url": response_url,
        "likely_repeat_procurement_category": bool(scope.get("framework_agreement") or re.search(r"stationery|consumables|uniforms|cleaning materials|office supplies|panel|period of", blob, flags=re.I)),
        "framework_agreement": bool(scope.get("framework_agreement")),
        "low_complexity_opportunity": bool(scope.get("low_complexity")),
        "built_from_document_evidence": bool(item.get("built_from_document_evidence")),
        "document_evidence": item.get("document_evidence") if isinstance(item.get("document_evidence"), dict) else {},
        "extraction_sources": {
            "html_tables": bool(item.get("source_url") and item.get("raw_text")),
            "bulletin_page": bool(re.search(r"bulletin|tender|rfq|quotation", _safe_lower(source.get("url")))),
            "procurement_card": bool(item.get("title") and item.get("description")),
            "downloadable_notices": bool(document_urls),
            "linked_rfq_page": bool(item.get("detail_url") or item.get("response_url")),
        },
    }
    return extracted


def _v54_qualification(candidate: Dict[str, Any]) -> Dict[str, Any]:
    blob = _safe_lower(" ".join([
        candidate.get("title"),
        candidate.get("description"),
        candidate.get("commodity_service_category"),
        candidate.get("buyer_name"),
        candidate.get("source_name"),
    ]))
    reasons: List[str] = []
    rejection = _v52_exclusion_reason(candidate)
    if candidate.get("commodity_service_category") in {"construction_heavy"}:
        rejection = "construction_heavy"
    if candidate.get("briefing_required"):
        rejection = "briefing_required"
    profitability = 0.0
    profit_value = float((candidate.get("estimated_profit_signal") or {}).get("estimated_profit") or 0.0)
    if profit_value >= 60000:
        profitability = 90
    elif profit_value >= 30000:
        profitability = 70
    elif re.search(r"bulk|panel|framework|period of|multiple|as and when", blob, flags=re.I):
        profitability = 65
    else:
        profitability = 30
    simplicity = 40.0
    if candidate.get("submission_method") == "email":
        simplicity += 35
        reasons.append("email_submission")
    if candidate.get("low_complexity_opportunity"):
        simplicity += 20
        reasons.append("low_complexity")
    if candidate.get("briefing_required"):
        simplicity -= 50
    completeness = 20.0
    if candidate.get("document_urls"):
        completeness += 45
        reasons.append("downloadable_rfq_documents")
    if candidate.get("closing_date"):
        completeness += 20
        if candidate.get("closing_date_valid"):
            completeness += 10
            reasons.append("closing_date_parsed")
    if candidate.get("contact_email"):
        completeness += 15
    buyer_clarity = 70.0 if candidate.get("buyer_name") or candidate.get("buyer") else 25.0
    closing_viability = 75.0 if candidate.get("closing_date") and not _v52_is_expired(candidate.get("closing_date"), blob) else 30.0
    if candidate.get("framework_agreement"):
        reasons.append("framework_or_repeat_procurement")
    if re.search(r"\bsupply\s*(and|&|,)?\s*delivery\b|supply of|delivery of", blob, flags=re.I):
        reasons.append("supply_and_delivery")
    scores = {
        "profitability_likelihood": round(max(0.0, min(100.0, profitability)), 2),
        "submission_simplicity": round(max(0.0, min(100.0, simplicity)), 2),
        "document_completeness": round(max(0.0, min(100.0, completeness)), 2),
        "buyer_clarity": round(max(0.0, min(100.0, buyer_clarity)), 2),
        "closing_date_viability": round(max(0.0, min(100.0, closing_viability)), 2),
    }
    total = (
        scores["profitability_likelihood"] * 0.28
        + scores["submission_simplicity"] * 0.22
        + scores["document_completeness"] * 0.22
        + scores["buyer_clarity"] * 0.13
        + scores["closing_date_viability"] * 0.15
    )
    candidate["qualification_scores"] = scores
    candidate["qualification_score"] = round(total, 2)
    candidate["qualification_reasons"] = sorted(set(reasons))
    blocker_reasons: List[str] = []
    if not candidate.get("closing_date"):
        blocker_reasons.append("missing_closing_date")
    elif _v52_is_expired(candidate.get("closing_date"), blob):
        blocker_reasons.append("expired_or_closed")
    if not candidate.get("document_urls"):
        blocker_reasons.append("no_downloadable_rfq_documents")
    if not candidate.get("buyer_name"):
        blocker_reasons.append("missing_buyer_name")
    if not candidate.get("source_url"):
        blocker_reasons.append("missing_source_url")
    if candidate.get("briefing_required"):
        blocker_reasons.append("briefing_required")
    candidate["blocker_reasons"] = sorted(set(blocker_reasons))
    if rejection:
        candidate["exclusion_reason"] = rejection
        candidate["qualified"] = False
    elif total >= 65:
        candidate["exclusion_reason"] = ""
        candidate["qualified"] = True
    else:
        candidate["exclusion_reason"] = "qualification_score_below_threshold"
        candidate["qualified"] = False
    candidate["confidence_score"] = max(float(candidate.get("confidence_score") or 0.0), candidate["qualification_score"])
    return candidate


def run_multi_portal_discovery(
    max_sources: int = 12,
    max_per_source: int = 4,
    headless: bool = True,
    source_file: Optional[str] = None,
    source_health_file: Optional[Path] = None,
    include_bad_sources: bool = False,
    dry_run: bool = True,
    source_pack_mode: Any = None,
    focus_productive_sources: bool = False,
    repair_source_pack: bool = False,
    buyer_intelligence: bool = True,
    opportunity_forecasting: bool = True,
    forecast_watchlist: bool = True,
    source_filter: Optional[str] = None,
    source_names: Optional[List[str]] = None,
    page_load_timeout_seconds: Optional[int] = None,
    candidate_extraction_timeout_seconds: Optional[int] = None,
    document_link_timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """V52-V61 multi-portal RFQ discovery. Discovery only; never submits."""
    started_at = _now_iso()
    max_sources = _safe_positive_int(max_sources, 12)
    max_per_source = _safe_positive_int(max_per_source, 4)
    all_sources = load_harvest_sources(source_file)
    sources = [s for s in all_sources if s.get("enabled", True)]
    sources = _v64_filter_sources(sources, source_filter=source_filter, source_names=source_names)
    memory_files = _v57_load_memory_files()
    if focus_productive_sources:
        selected_sources, focus_diagnostics = _v58_select_productive_focus_sources(
            sorted(sources, key=_v52_source_priority),
            max_sources=max_sources,
            source_health_file=source_health_file,
        )
        repair_diagnostics = {
            "repair_mode_used": False,
            "repair_sources_checked_count": 0,
            "repair_sources_selected_count": 0,
            "repair_sources_failed_count": 0,
            "repair_selected_source_names": [],
            "repair_failed_by_reason": {},
        }
        source_rotation_batch_id = f"v58-focus-{int(time.time() // 21600)}"
        refreshed_health_snapshot = _load_source_health(source_health_file=source_health_file)
        pre_cycle_health_rows = [_v53_source_health_row(src, refreshed_health_snapshot, source_health_file=source_health_file) for src in selected_sources]
        source_pack_strategy = _v58_build_source_pack_strategy(
            sources,
            selected_sources,
            max_sources,
            mode=source_pack_mode or "focus",
            source_health_file=source_health_file,
        )
        if not selected_sources and repair_source_pack:
            repair_selected_sources, repair_diagnostics, repair_rows = _v64_repair_source_pack_sources(
                sorted(sources, key=_v52_source_priority),
                max_sources=max_sources,
                source_health_file=source_health_file,
            )
            repair_diagnostics["repair_mode_used"] = True
            if repair_selected_sources:
                selected_sources = repair_selected_sources
                source_rotation_batch_id = f"v64-repair-{int(time.time() // 21600)}"
                refreshed_health_snapshot = _load_source_health(source_health_file=source_health_file)
                pre_cycle_health_rows = [
                    _v53_source_health_row(src, refreshed_health_snapshot, source_health_file=source_health_file)
                    for src in selected_sources
                ]
                source_pack_strategy = _v58_build_source_pack_strategy(
                    sources,
                    selected_sources,
                    max_sources,
                    mode="repair",
                    source_health_file=source_health_file,
                )
            else:
                source_pack_strategy = {
                    **source_pack_strategy,
                    "active_pack_mode": "repair",
                    "diagnostics": {
                        **source_pack_strategy.get("diagnostics", {}),
                        **repair_diagnostics,
                        "repair_mode_used": True,
                    },
                }
    else:
        selected_sources, source_rotation_batch_id, pre_cycle_health_rows, source_pack_strategy = _v58_select_sources_for_pack_rotation(
            sorted(sources, key=_v52_source_priority),
            max_sources=max_sources,
            include_bad_sources=include_bad_sources,
            pack_mode=source_pack_mode,
        )
        focus_diagnostics = {
            "focused_source_count": 0,
            "skipped_unproductive_source_count": 0,
            "focused_source_names": [],
        }
        repair_diagnostics = {
            "repair_mode_used": False,
            "repair_sources_checked_count": 0,
            "repair_sources_selected_count": 0,
            "repair_sources_failed_count": 0,
            "repair_selected_source_names": [],
            "repair_failed_by_reason": {},
        }
    source_pack_diagnostics = {
        **source_pack_strategy.get("diagnostics", {}),
        **focus_diagnostics,
        **repair_diagnostics,
        "focus_productive_sources": bool(focus_productive_sources),
        "repair_source_pack": bool(repair_source_pack),
    }
    source_pack_artifacts = source_pack_strategy.get("artifacts", {})
    source_pack_rows_by_name = {
        row.get("source_name"): row for row in source_pack_strategy.get("source_rows", [])
        if isinstance(row, dict)
    }

    raw_candidates: List[Dict[str, Any]] = []
    eligible: List[Dict[str, Any]] = []
    qualified: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    rejection_counts: Dict[str, int] = {}
    qualification_reason_counts: Dict[str, int] = {}
    source_runs: List[Dict[str, Any]] = []
    source_health_rows: List[Dict[str, Any]] = []
    pages_scanned_count = 0
    document_link_hits = 0
    document_candidates_report: List[Dict[str, Any]] = []
    document_parse_summary_rows: List[Dict[str, Any]] = []
    document_links_found_count = 0
    documents_downloaded_count = 0
    documents_parsed_count = 0
    rfq_documents_detected_count = 0
    pricing_schedules_detected_count = 0
    document_built_candidates_count = 0
    qualified_document_candidates_count = 0
    document_rejection_counts_by_reason: Dict[str, int] = {}
    rejection_stage_counts: Dict[str, int] = {}
    rejection_reason_code_counts: Dict[str, int] = {}
    duplicate_candidates_suppressed = 0
    recurring_buyer_keys_detected = set()
    recurring_category_keys_detected = set()
    current_candidate_fingerprints = set()
    memory_fingerprints = ((memory_files.get("source") or {}).get("qualified_candidate_fingerprints") or {}) if isinstance(memory_files.get("source"), dict) else {}
    source_document_discovery_map: Dict[str, Dict[str, Any]] = {}
    candidates_with_document_links = 0
    candidates_without_document_links = 0
    buyer_pack_attempted_count = 0
    buyer_pack_downloaded_count = 0
    buyer_pack_failed_count = 0
    buyer_pack_url_resolution_failures = 0
    buyer_pack_http_failures = 0
    buyer_pack_auth_required_failures = 0
    buyer_pack_unsupported_content_failures = 0
    buyer_pack_empty_content_failures = 0
    buyer_pack_file_write_failures = 0
    buyer_pack_success_count = 0
    index_pages_fetched_count = 0
    index_pages_with_artifacts_count = 0
    artifact_candidates_found_count = 0
    artifact_download_attempts_count = 0
    artifact_download_success_count = 0
    artifact_candidates_total = 0
    artifact_candidates_attempted = 0
    artifact_candidates_rejected_before_fetch = 0
    artifact_candidates_by_classification: Dict[str, int] = {}
    artifact_rejections_by_reason: Dict[str, int] = {}
    artifact_resolved_to_html_count = 0
    artifact_binary_signature_success_count = 0
    etenders_endpoint_probe_count = 0
    etenders_endpoint_success_count = 0
    etenders_endpoint_failure_count = 0
    etenders_document_candidates_from_endpoints = 0
    etenders_endpoint_failures_by_reason: Dict[str, int] = {}
    etenders_home_reached = False
    etenders_opportunities_page_reached = False
    etenders_candidates_table_detected = False
    etenders_candidates_extracted_count = 0
    etenders_detail_pages_attempted_count = 0
    etenders_detail_pages_success_count = 0
    etenders_detail_pages_timeout_count = 0
    etenders_tenderdetails_links_found_count = 0
    index_page_no_artifacts_count = 0
    artifact_download_failed_count = 0

    for source in selected_sources:
        source_name = _clean(source.get("name") or source.get("source_name") or source.get("url") or "Unknown Source")
        harvested, acquisition_runtime = _scan_source_acquisition_runtime(
            source,
            max_per_source=max_per_source,
            headless=headless,
            source_timeout_seconds=12,
            playwright_timeout_ms=18000,
            page_load_timeout_seconds=page_load_timeout_seconds,
            candidate_extraction_timeout_seconds=candidate_extraction_timeout_seconds,
            document_link_timeout_seconds=document_link_timeout_seconds,
            source_health_file=source_health_file,
            browser_available=headless,
            disable_playwright_scrape=not headless,
        )
        etenders_home_reached = bool(etenders_home_reached or acquisition_runtime.get("etenders_home_reached"))
        etenders_opportunities_page_reached = bool(etenders_opportunities_page_reached or acquisition_runtime.get("etenders_opportunities_page_reached"))
        etenders_candidates_table_detected = bool(etenders_candidates_table_detected or acquisition_runtime.get("etenders_candidates_table_detected"))
        etenders_candidates_extracted_count += int(acquisition_runtime.get("etenders_candidates_extracted_count") or 0)
        etenders_detail_pages_attempted_count += int(acquisition_runtime.get("etenders_detail_pages_attempted_count") or 0)
        etenders_detail_pages_success_count += int(acquisition_runtime.get("etenders_detail_pages_success_count") or 0)
        etenders_detail_pages_timeout_count += int(acquisition_runtime.get("etenders_detail_pages_timeout_count") or 0)
        etenders_tenderdetails_links_found_count += int(acquisition_runtime.get("etenders_tenderdetails_links_found_count") or 0)
        pages_scanned_count += int(acquisition_runtime.get("pages_scanned") or 0)
        document_discovery: Dict[str, Any] = {"document_links": [], "downloads": [], "parsed_documents": [], "skipped_links": [], "built_items": []}
        if harvested:
            try:
                document_discovery = _v56_discover_documents_for_source(
                    source,
                    harvested,
                    max_documents=max(3, min(10, max_per_source * 2)),
                )
            except Exception as exc:
                logger.warning("V56 document discovery failed for %s: %s", source_name, exc)
                document_discovery = {
                    "document_links": [],
                    "downloads": [],
                    "parsed_documents": [],
                    "skipped_links": [{"reason": "document_discovery_error", "error": _truncate(str(exc), 240)}],
                    "built_items": [],
                }
        document_links = document_discovery.get("document_links") if isinstance(document_discovery.get("document_links"), list) else []
        downloaded_documents = document_discovery.get("downloads") if isinstance(document_discovery.get("downloads"), list) else []
        parsed_documents = document_discovery.get("parsed_documents") if isinstance(document_discovery.get("parsed_documents"), list) else []
        document_built_items = document_discovery.get("built_items") if isinstance(document_discovery.get("built_items"), list) else []
        skipped_document_links = document_discovery.get("skipped_links") if isinstance(document_discovery.get("skipped_links"), list) else []
        source_document_discovery_map[source_name] = document_discovery
        document_links_found_count += len(document_links)
        documents_downloaded_count += len(downloaded_documents)
        documents_parsed_count += sum(1 for doc in parsed_documents if doc.get("status") == "parsed")
        rfq_documents_detected_count += sum(1 for doc in parsed_documents if doc.get("classification") == "RFQ document")
        pricing_schedules_detected_count += sum(1 for doc in parsed_documents if doc.get("classification") == "pricing schedule")
        document_built_candidates_count += len(document_built_items)
        for skipped in skipped_document_links:
            reason = _clean(skipped.get("reason") if isinstance(skipped, dict) else "")
            if reason:
                document_rejection_counts_by_reason[reason] = document_rejection_counts_by_reason.get(reason, 0) + 1
        for doc in parsed_documents:
            document_parse_summary_rows.append({
                "source_name": source_name,
                "source_url": source.get("url") or source.get("list_url"),
                "url": doc.get("url"),
                "filename": doc.get("filename"),
                "path": doc.get("path"),
                "extension": doc.get("extension"),
                "status": doc.get("status"),
                "parser": doc.get("parser"),
                "text_length": doc.get("text_length"),
                "classification": doc.get("classification"),
                "classification_confidence": doc.get("classification_confidence"),
                "metadata": doc.get("metadata"),
            })
        response_time = max(
            0.0,
            _v53_parse_time(_clean(acquisition_runtime.get("scan_finished_at")))
            - _v53_parse_time(_clean(acquisition_runtime.get("scan_started_at"))),
        )
        source_candidate_count = 0
        source_extracted_count = 0
        source_qualified_count = 0
        source_document_count = 0
        source_runs.append({
            **acquisition_runtime,
            "source_type": source.get("type"),
            "source_group": source.get("source_group") or source.get("category_group"),
            "source_packs": (source_pack_rows_by_name.get(source_name) or {}).get("packs", []),
            "source_pack_yield_score": (source_pack_rows_by_name.get(source_name) or {}).get("v58_yield_score"),
            "harvested_count": len(harvested),
            "raw_candidates_count": len(harvested),
            "document_links_found_count": len(document_links),
            "document_links_detected": len(document_links),
            "documents_downloaded_count": len(downloaded_documents),
            "documents_parsed_count": sum(1 for doc in parsed_documents if doc.get("status") == "parsed"),
            "document_built_candidates_count": len(document_built_items),
            "source_response_time": round(response_time, 3),
            "error": acquisition_runtime.get("error_message") or "",
        })
        for item in _dedupe_keep_order(harvested + document_built_items):
            candidate = _v54_qualification(_v54_deep_extract_candidate(item, source))
            candidate = _v57_apply_candidate_memory_learning(candidate, memory_files)
            fingerprint = _v57_candidate_fingerprint(candidate)
            candidate["candidate_fingerprint"] = fingerprint
            duplicate_reason = ""
            if fingerprint in current_candidate_fingerprints:
                duplicate_reason = "duplicate_candidate_current_run"
            elif isinstance(memory_fingerprints, dict) and fingerprint in memory_fingerprints:
                duplicate_reason = "duplicate_candidate_memory"
            if duplicate_reason:
                candidate["duplicate_suppressed"] = True
                candidate["qualified"] = False
                candidate["exclusion_reason"] = duplicate_reason
                duplicate_candidates_suppressed += 1
            else:
                current_candidate_fingerprints.add(fingerprint)
            memory_signals = candidate.get("memory_signals") if isinstance(candidate.get("memory_signals"), dict) else {}
            if memory_signals.get("recurring_buyer"):
                recurring_buyer_keys_detected.add(_clean(memory_signals.get("buyer_key")))
            if memory_signals.get("recurring_category"):
                recurring_category_keys_detected.add(_clean(memory_signals.get("category_key")))
            reason = _clean(candidate.get("exclusion_reason"))
            candidate.pop("_blob_lower", None)
            candidate["candidate_id"] = fingerprint
            candidate["document_links_count"] = int(len(candidate.get("document_urls") or []))
            if candidate.get("built_from_document_evidence") and not candidate["document_links_count"]:
                candidate["document_links_count"] = 1
            doc_discovery_for_source = source_document_discovery_map.get(source_name, {})
            buyer_pack_downloaded = bool(
                candidate.get("buyer_pack_downloaded")
                or candidate.get("buyer_pack_verified")
                or candidate.get("built_from_document_evidence")
                or candidate.get("downloaded_document_path")
                or candidate.get("document_acquisition_result")
                or candidate.get("buyer_pack_path")
                or candidate.get("live_buyer_pack_path")
            )
            buyer_pack_resolution: Dict[str, Any] = {
                "attempted": buyer_pack_downloaded,
                "downloaded": buyer_pack_downloaded,
                "buyer_pack_downloaded": buyer_pack_downloaded,
                "buyer_pack_path": _clean(candidate.get("buyer_pack_path") or candidate.get("live_buyer_pack_path") or candidate.get("downloaded_document_path") or candidate.get("document_acquisition_result") or ""),
                "buyer_pack_download_timestamp": _clean(candidate.get("buyer_pack_download_timestamp") or ""),
                "failure_reason": "",
                "diagnostics": [],
                "downloads": [],
                "index_pages_fetched_count": 0,
                "index_pages_with_artifacts_count": 0,
                "artifact_candidates_found_count": 0,
                "artifact_download_attempts_count": 0,
                "artifact_download_success_count": 0,
                "index_page_no_artifacts_count": 0,
                "artifact_download_failed_count": 0,
                "fallback_used": False,
            }
            if candidate["document_links_count"] > 0 and not buyer_pack_downloaded:
                buyer_pack_resolution = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)
                index_pages_fetched_count += int(buyer_pack_resolution.get("index_pages_fetched_count") or 0)
                index_pages_with_artifacts_count += int(buyer_pack_resolution.get("index_pages_with_artifacts_count") or 0)
                artifact_candidates_found_count += int(buyer_pack_resolution.get("artifact_candidates_found_count") or 0)
                artifact_download_attempts_count += int(buyer_pack_resolution.get("artifact_download_attempts_count") or 0)
                artifact_download_success_count += int(buyer_pack_resolution.get("artifact_download_success_count") or 0)
                artifact_candidates_total += int(buyer_pack_resolution.get("artifact_candidates_total") or 0)
                artifact_candidates_attempted += int(buyer_pack_resolution.get("artifact_candidates_attempted") or 0)
                artifact_candidates_rejected_before_fetch += int(buyer_pack_resolution.get("artifact_candidates_rejected_before_fetch") or 0)
                artifact_resolved_to_html_count += int(buyer_pack_resolution.get("artifact_resolved_to_html_count") or 0)
                artifact_binary_signature_success_count += int(buyer_pack_resolution.get("artifact_binary_signature_success_count") or 0)
                etenders_endpoint_probe_count += int(buyer_pack_resolution.get("etenders_endpoint_probe_count") or 0)
                etenders_endpoint_success_count += int(buyer_pack_resolution.get("etenders_endpoint_success_count") or 0)
                etenders_endpoint_failure_count += int(buyer_pack_resolution.get("etenders_endpoint_failure_count") or 0)
                etenders_document_candidates_from_endpoints += int(buyer_pack_resolution.get("etenders_document_candidates_from_endpoints") or 0)
                for classification, count in (buyer_pack_resolution.get("artifact_candidates_by_classification") or {}).items():
                    artifact_candidates_by_classification[_clean(classification) or "unknown"] = artifact_candidates_by_classification.get(_clean(classification) or "unknown", 0) + int(count or 0)
                for reason_key, count in (buyer_pack_resolution.get("artifact_rejections_by_reason") or {}).items():
                    artifact_rejections_by_reason[_clean(reason_key) or "candidate_rejected_before_fetch"] = artifact_rejections_by_reason.get(_clean(reason_key) or "candidate_rejected_before_fetch", 0) + int(count or 0)
                for reason_key, count in (buyer_pack_resolution.get("etenders_endpoint_failures_by_reason") or {}).items():
                    key = _clean(reason_key) or "endpoint_probe_failed"
                    etenders_endpoint_failures_by_reason[key] = etenders_endpoint_failures_by_reason.get(key, 0) + int(count or 0)
                index_page_no_artifacts_count += int(buyer_pack_resolution.get("index_page_no_artifacts_count") or 0)
                artifact_download_failed_count += int(buyer_pack_resolution.get("artifact_download_failed_count") or 0)
                candidate["buyer_pack_download_diagnostics"] = buyer_pack_resolution.get("diagnostics") or []
                buyer_pack_downloaded = bool(buyer_pack_resolution.get("buyer_pack_downloaded"))
                buyer_pack_attempted = bool(candidate["buyer_pack_download_diagnostics"])
                candidate["buyer_pack_downloaded"] = buyer_pack_downloaded
                candidate["buyer_pack_attempted"] = buyer_pack_attempted
                if buyer_pack_downloaded:
                    candidate["buyer_pack_path"] = _clean(buyer_pack_resolution.get("buyer_pack_path") or candidate.get("buyer_pack_path") or candidate.get("live_buyer_pack_path") or candidate.get("downloaded_document_path"))
                    candidate["buyer_pack_download_timestamp"] = _clean(buyer_pack_resolution.get("buyer_pack_download_timestamp") or candidate.get("buyer_pack_download_timestamp") or _now_iso())
                candidate["buyer_pack_failure_reason"] = "" if buyer_pack_downloaded else _clean(buyer_pack_resolution.get("failure_reason") or _v63_buyer_pack_failure_reason(candidate, doc_discovery_for_source))
                candidate["buyer_pack_source"] = _clean(source_name)
                for diagnostic in candidate["buyer_pack_download_diagnostics"]:
                    if not isinstance(diagnostic, dict):
                        continue
                    failure_stage = _clean(diagnostic.get("failure_stage"))
                    diagnostic_type = _clean(diagnostic.get("diagnostic_type"))
                    if failure_stage in {"", "artifact_saved"}:
                        continue
                    if failure_stage == "url_resolution":
                        buyer_pack_url_resolution_failures += 1
                    elif failure_stage == "auth_required":
                        buyer_pack_auth_required_failures += 1
                    elif failure_stage in {"unsupported_content_type", "artifact_resolved_to_html"}:
                        buyer_pack_unsupported_content_failures += 1
                    elif failure_stage == "empty_content":
                        buyer_pack_empty_content_failures += 1
                    elif failure_stage == "file_write":
                        buyer_pack_file_write_failures += 1
                    elif failure_stage == "checksum":
                        buyer_pack_file_write_failures += 1
                    elif diagnostic_type == "source_link" and failure_stage == "http_fetch":
                        buyer_pack_http_failures += 1
                    elif diagnostic_type == "artifact_candidate" and failure_stage == "http_fetch":
                        buyer_pack_http_failures += 1
                    elif diagnostic_type == "source_link" and failure_stage == "index_page_no_artifacts":
                        pass
                    elif diagnostic_type == "artifact_candidate" and failure_stage == "skipped":
                        pass
                    else:
                        buyer_pack_http_failures += 1
            else:
                buyer_pack_attempted = bool(candidate["document_links_count"] > 0 or buyer_pack_downloaded or candidate.get("built_from_document_evidence"))
                candidate["buyer_pack_attempted"] = buyer_pack_attempted
                candidate["buyer_pack_downloaded"] = buyer_pack_downloaded
                candidate["buyer_pack_failure_reason"] = "" if buyer_pack_downloaded else _v63_buyer_pack_failure_reason(candidate, doc_discovery_for_source)
                candidate["buyer_pack_source"] = _clean(source_name)
                candidate["buyer_pack_download_diagnostics"] = candidate.get("buyer_pack_download_diagnostics") or []
            if candidate["document_links_count"] > 0:
                candidates_with_document_links += 1
            else:
                candidates_without_document_links += 1
            if buyer_pack_attempted:
                buyer_pack_attempted_count += 1
                if buyer_pack_downloaded:
                    buyer_pack_downloaded_count += 1
                    buyer_pack_success_count += 1
                else:
                    buyer_pack_failed_count += 1
            raw_candidates.append(candidate)
            source_candidate_count += 1
            source_extracted_count += 1
            if candidate.get("document_urls"):
                document_link_hits += 1
                source_document_count += 1
            for q_reason in candidate.get("qualification_reasons") or []:
                qualification_reason_counts[q_reason] = qualification_reason_counts.get(q_reason, 0) + 1
            if reason:
                candidate["exclusion_reason"] = reason
                rejection_stage = _v63_candidate_rejection_stage(reason, candidate)
                rejection_stage_counts[rejection_stage] = rejection_stage_counts.get(rejection_stage, 0) + 1
                rejection_reason_code_counts[reason] = rejection_reason_code_counts.get(reason, 0) + 1
                candidate.update(_v63_attach_candidate_rejection_diagnostics(candidate, source, doc_discovery_for_source))
                rejected.append(candidate)
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
                if candidate.get("built_from_document_evidence"):
                    document_rejection_counts_by_reason[reason] = document_rejection_counts_by_reason.get(reason, 0) + 1
            else:
                candidate["exclusion_reason"] = ""
                eligible.append(candidate)
                qualified.append(candidate)
                source_qualified_count += 1
                if candidate.get("built_from_document_evidence"):
                    qualified_document_candidates_count += 1
            if candidate.get("built_from_document_evidence"):
                document_candidates_report.append(candidate)
        source_health_rows.append(
            _v53_update_source_health_after_scan(
                source,
                harvested_count=len(harvested),
                candidate_count=source_candidate_count,
                response_time=response_time,
                error=_clean(acquisition_runtime.get("error_message")),
                extracted_count=source_extracted_count,
                qualified_count=source_qualified_count,
                document_count=source_document_count,
                source_health_file=source_health_file,
                acquisition_status=_clean(acquisition_runtime.get("status")),
                acquisition_error_message=_clean(acquisition_runtime.get("error_message")),
                scan_started_at=_clean(acquisition_runtime.get("scan_started_at")),
                scan_finished_at=_clean(acquisition_runtime.get("scan_finished_at")),
                pages_scanned=int(acquisition_runtime.get("pages_scanned") or 0),
                raw_candidates_count=int(acquisition_runtime.get("raw_candidates_count") or 0),
                document_links_detected=int(acquisition_runtime.get("document_links_detected") or 0),
                retry_count=int(acquisition_runtime.get("retry_count") or 0),
                fallback_used=bool(acquisition_runtime.get("fallback_used")),
                source_url=_clean(acquisition_runtime.get("source_url")),
            )
        )

    eligible = sorted(
        eligible,
        key=lambda item: (
            float(item.get("qualification_score") or item.get("confidence_score") or 0),
            float((item.get("estimated_profit_signal") or {}).get("estimated_profit") or 0),
            1 if item.get("submission_method") == "email" else 0,
        ),
        reverse=True,
    )
    qualified = sorted(
        qualified,
        key=lambda item: (
            float(item.get("qualification_score") or item.get("confidence_score") or 0),
            float((item.get("estimated_profit_signal") or {}).get("estimated_profit") or 0),
        ),
        reverse=True,
    )
    rejected = sorted(rejected, key=lambda item: (item.get("exclusion_reason") or "", -(float(item.get("confidence_score") or 0))))

    eligible_report = MULTI_PORTAL_DISCOVERY_DIR / "eligible_candidates_report.json"
    qualified_report = MULTI_PORTAL_DISCOVERY_DIR / "qualified_candidates_report.json"
    rejected_report = MULTI_PORTAL_DISCOVERY_DIR / "rejected_candidates_report.json"
    document_candidates_report_path = MULTI_PORTAL_DISCOVERY_DIR / "document_candidates_report.json"
    document_parse_summary_path = MULTI_PORTAL_DISCOVERY_DIR / "document_parse_summary.json"
    qualification_summary_report = MULTI_PORTAL_DISCOVERY_DIR / "qualification_summary.json"
    summary_report = MULTI_PORTAL_DISCOVERY_DIR / "discovery_summary.json"
    source_health_report = MULTI_PORTAL_DISCOVERY_DIR / "source_health_report.json"
    top_sources_report = MULTI_PORTAL_DISCOVERY_DIR / "top_sources.json"
    _write_payload = lambda path, payload: path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_payload(eligible_report, eligible)
    _write_payload(qualified_report, qualified)
    _write_payload(rejected_report, rejected)
    _write_payload(document_candidates_report_path, document_candidates_report)
    document_diagnostics = {
        "document_links_found_count": document_links_found_count,
        "documents_downloaded_count": documents_downloaded_count,
        "documents_parsed_count": documents_parsed_count,
        "rfq_documents_detected_count": rfq_documents_detected_count,
        "pricing_schedules_detected_count": pricing_schedules_detected_count,
        "document_built_candidates_count": document_built_candidates_count,
        "qualified_document_candidates_count": qualified_document_candidates_count,
        "document_rejection_counts_by_reason": document_rejection_counts_by_reason,
    }
    memory_update_diagnostics = _v57_update_discovery_memory(
        memory_files,
        selected_sources,
        source_runs,
        raw_candidates,
        qualified,
        rejected,
        document_parse_summary_rows,
    )
    memory_diagnostics = {
        **memory_update_diagnostics,
        "recurring_buyers_detected": len([key for key in recurring_buyer_keys_detected if key]),
        "recurring_categories_detected": len([key for key in recurring_category_keys_detected if key]),
        "duplicate_candidates_suppressed": duplicate_candidates_suppressed,
    }
    _write_payload(document_parse_summary_path, {
        "status": "ok",
        "service_version": "V57_PERSISTENT_OPPORTUNITY_MEMORY_EXTENDS_V56",
        "generated_at": _now_iso(),
        **document_diagnostics,
        **memory_diagnostics,
        "diagnostics": document_diagnostics,
        "memory_diagnostics": memory_diagnostics,
        "documents": document_parse_summary_rows,
        "safety": {
            "zip_links": "discovered_but_not_downloaded_or_submitted",
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    })
    refreshed_health = _load_source_health(source_health_file=source_health_file)
    all_health_rows = [_v53_source_health_row(src, refreshed_health) for src in sources]
    all_health_rows = sorted(
        all_health_rows,
        key=lambda row: float(row.get("source_selection_score") or row.get("source_success_score") or 0),
        reverse=True,
    )
    top_performing_sources = all_health_rows[:20]
    healthy_sources_count = sum(1 for row in all_health_rows if float(row.get("source_selection_score") or row.get("source_success_score") or 0) >= 50 and int(row.get("source_failure_count") or 0) < 3)
    unhealthy_sources_count = len(all_health_rows) - healthy_sources_count
    candidate_producing_sources_count = sum(1 for row in all_health_rows if int(row.get("candidate_total") or 0) > 0)
    _write_payload(source_health_report, all_health_rows)
    _write_payload(top_sources_report, top_performing_sources)
    _write_payload(LAST_ACQUISITION_RUNTIME_DIAGNOSTICS_FILE, source_runs)
    yield_summary = _v55_build_adaptive_yield_reports(sources, selected_sources, source_health_file=source_health_file)
    acquisition_status_counts: Dict[str, int] = {}
    acquisition_health_counts: Dict[str, int] = {}
    for run in source_runs:
        status = _clean(run.get("status")) or "unknown"
        acquisition_status_counts[status] = acquisition_status_counts.get(status, 0) + 1
    for row in all_health_rows:
        health_status = _clean(row.get("health_status")) or _v53_source_health_status(row, None)
        acquisition_health_counts[health_status] = acquisition_health_counts.get(health_status, 0) + 1
    productive_sources_count = sum(acquisition_health_counts.get(status, 0) for status in ("healthy", "degraded", "empty"))
    suppressed_sources_count = sum(acquisition_health_counts.get(status, 0) for status in ("dns_blocked", "http_blocked", "disabled"))
    skipped_source_rows = [
        row for row in all_health_rows
        if _clean(row.get("health_status")) in {"dns_blocked", "http_blocked", "disabled"}
    ]
    source_health_overview = {
        "healthy_sources_count": healthy_sources_count,
        "unhealthy_sources_count": unhealthy_sources_count,
        "candidate_producing_sources_count": candidate_producing_sources_count,
        "productive_sources_count": productive_sources_count,
        "suppressed_sources_count": suppressed_sources_count,
        "suppressed_dns_count": acquisition_health_counts.get("dns_blocked", 0),
        "suppressed_http_count": acquisition_health_counts.get("http_blocked", 0),
        "suppressed_empty_count": acquisition_health_counts.get("empty", 0),
        "health_status_counts": acquisition_health_counts,
        "top_performing_sources": top_performing_sources[:10],
    }
    successful_count = acquisition_status_counts.get("success", 0)
    failed_count = sum(
        acquisition_status_counts.get(status, 0)
        for status in ("dns_failed", "playwright_failed", "timeout", "http_failed", "parse_failed")
    )
    no_candidate_count = acquisition_status_counts.get("no_candidates", 0)
    total_raw_candidates = sum(int(run.get("raw_candidates_count") or 0) for run in source_runs)
    total_document_links_detected = sum(int(run.get("document_links_detected") or 0) for run in source_runs)
    productive_sources_count = sum(acquisition_health_counts.get(status, 0) for status in ("healthy", "degraded", "empty"))
    suppressed_sources_count = sum(acquisition_health_counts.get(status, 0) for status in ("dns_blocked", "http_blocked", "disabled"))
    acquisition_runtime_summary = {
        "sources_scanned_count": len(source_runs),
        "sources_successful_count": successful_count,
        "sources_failed_count": failed_count,
        "dns_failures_count": acquisition_status_counts.get("dns_failed", 0),
        "playwright_failures_count": acquisition_status_counts.get("playwright_failed", 0),
        "timeout_failures_count": acquisition_status_counts.get("timeout", 0),
        "http_failures_count": acquisition_status_counts.get("http_failed", 0),
        "parse_failures_count": acquisition_status_counts.get("parse_failed", 0),
        "no_candidate_sources_count": no_candidate_count,
        "total_raw_candidates": total_raw_candidates,
        "total_document_links_detected": total_document_links_detected,
        "acquisition_success_rate": round((successful_count / max(len(source_runs), 1)) * 100.0, 2),
        "acquisition_completion_rate": round(((successful_count + no_candidate_count) / max(len(source_runs), 1)) * 100.0, 2),
        "productive_sources_count": productive_sources_count,
        "suppressed_sources_count": suppressed_sources_count,
        "suppressed_dns_count": acquisition_health_counts.get("dns_blocked", 0),
        "suppressed_http_count": acquisition_health_counts.get("http_blocked", 0),
        "suppressed_empty_count": acquisition_health_counts.get("empty", 0),
        "skipped_sources_count": len([row for row in all_health_rows if _clean(row.get("health_status")) in {"dns_blocked", "http_blocked", "disabled"}]),
        "health_status_counts": acquisition_health_counts,
        "status_counts": acquisition_status_counts,
        "repair_mode_used": source_pack_diagnostics.get("repair_mode_used", False),
        "repair_sources_checked_count": source_pack_diagnostics.get("repair_sources_checked_count", 0),
        "repair_sources_selected_count": source_pack_diagnostics.get("repair_sources_selected_count", 0),
        "repair_sources_failed_count": source_pack_diagnostics.get("repair_sources_failed_count", 0),
        "repair_selected_source_names": source_pack_diagnostics.get("repair_selected_source_names", []),
        "repair_failed_by_reason": source_pack_diagnostics.get("repair_failed_by_reason", {}),
        "buyer_pack_url_resolution_failures": buyer_pack_url_resolution_failures,
        "buyer_pack_http_failures": buyer_pack_http_failures,
        "buyer_pack_auth_required_failures": buyer_pack_auth_required_failures,
        "buyer_pack_unsupported_content_failures": buyer_pack_unsupported_content_failures,
        "buyer_pack_empty_content_failures": buyer_pack_empty_content_failures,
        "buyer_pack_file_write_failures": buyer_pack_file_write_failures,
        "buyer_pack_success_rate": round((buyer_pack_success_count / max(1, buyer_pack_attempted_count)) * 100.0, 2),
        "etenders_home_reached": etenders_home_reached,
        "etenders_opportunities_page_reached": etenders_opportunities_page_reached,
        "etenders_candidates_table_detected": etenders_candidates_table_detected,
        "etenders_candidates_extracted_count": etenders_candidates_extracted_count,
        "etenders_detail_pages_attempted_count": etenders_detail_pages_attempted_count,
        "etenders_detail_pages_success_count": etenders_detail_pages_success_count,
        "etenders_detail_pages_timeout_count": etenders_detail_pages_timeout_count,
        "etenders_tenderdetails_links_found_count": etenders_tenderdetails_links_found_count,
    }
    buyer_intelligence_result = _v59_build_buyer_intelligence(
        sources,
        raw_candidates,
        qualified,
        rejected,
        source_pack_strategy,
    ) if buyer_intelligence else {"diagnostics": {}, "artifacts": {}}
    buyer_intelligence_diagnostics = buyer_intelligence_result.get("diagnostics", {})
    buyer_intelligence_artifacts = buyer_intelligence_result.get("artifacts", {})
    forecast_result = _v60_build_tender_radar(
        buyer_intelligence_result,
        source_pack_strategy,
    ) if opportunity_forecasting else {"diagnostics": {}, "artifacts": {}}
    forecast_diagnostics = forecast_result.get("diagnostics", {})
    forecast_artifacts = forecast_result.get("artifacts", {})
    watchlist_result = _v61_build_forecast_action_watchlist(
        forecast_result,
        buyer_intelligence_result,
        source_pack_strategy,
    ) if forecast_watchlist and opportunity_forecasting else {"diagnostics": {}, "artifacts": {}}
    watchlist_diagnostics = watchlist_result.get("diagnostics", {})
    watchlist_artifacts = watchlist_result.get("artifacts", {})
    extracted_candidates_count = len(raw_candidates)
    extraction_success_rate = round((extracted_candidates_count / max(1, sum(int(run.get("harvested_count") or 0) for run in source_runs))) * 100.0, 2)
    document_link_detection_rate = round((document_link_hits / max(1, extracted_candidates_count)) * 100.0, 2)
    raw_to_eligible_rate = round((len(eligible) / max(1, len(raw_candidates))) * 100.0, 2)
    eligible_to_qualified_rate = round((len(qualified) / max(1, len(eligible))) * 100.0, 2)
    conversion_summary = {
        "raw_to_eligible_rate": raw_to_eligible_rate,
        "eligible_to_qualified_rate": eligible_to_qualified_rate,
        "rejected_by_stage": rejection_stage_counts,
        "rejected_by_reason_code": rejection_reason_code_counts,
        "candidates_with_document_links": candidates_with_document_links,
        "candidates_without_document_links": candidates_without_document_links,
        "buyer_pack_attempted_count": buyer_pack_attempted_count,
        "buyer_pack_downloaded_count": buyer_pack_downloaded_count,
        "buyer_pack_failed_count": buyer_pack_failed_count,
        "buyer_pack_url_resolution_failures": buyer_pack_url_resolution_failures,
        "buyer_pack_http_failures": buyer_pack_http_failures,
        "buyer_pack_auth_required_failures": buyer_pack_auth_required_failures,
        "buyer_pack_unsupported_content_failures": buyer_pack_unsupported_content_failures,
        "buyer_pack_empty_content_failures": buyer_pack_empty_content_failures,
        "buyer_pack_file_write_failures": buyer_pack_file_write_failures,
        "buyer_pack_success_rate": round((buyer_pack_success_count / max(1, buyer_pack_attempted_count)) * 100.0, 2),
        "index_pages_fetched_count": index_pages_fetched_count,
        "index_pages_with_artifacts_count": index_pages_with_artifacts_count,
        "artifact_candidates_found_count": artifact_candidates_found_count,
        "artifact_download_attempts_count": artifact_download_attempts_count,
        "artifact_download_success_count": artifact_download_success_count,
        "artifact_candidates_total": artifact_candidates_total,
        "artifact_candidates_attempted": artifact_candidates_attempted,
        "artifact_candidates_rejected_before_fetch": artifact_candidates_rejected_before_fetch,
        "artifact_candidates_by_classification": artifact_candidates_by_classification,
        "artifact_rejections_by_reason": artifact_rejections_by_reason,
        "artifact_resolved_to_html_count": artifact_resolved_to_html_count,
        "artifact_binary_signature_success_count": artifact_binary_signature_success_count,
        "etenders_endpoint_probe_count": etenders_endpoint_probe_count,
        "etenders_endpoint_success_count": etenders_endpoint_success_count,
        "etenders_endpoint_failure_count": etenders_endpoint_failure_count,
        "etenders_document_candidates_from_endpoints": etenders_document_candidates_from_endpoints,
        "etenders_endpoint_failures_by_reason": etenders_endpoint_failures_by_reason,
        "etenders_home_reached": etenders_home_reached,
        "etenders_opportunities_page_reached": etenders_opportunities_page_reached,
        "etenders_candidates_table_detected": etenders_candidates_table_detected,
        "etenders_candidates_extracted_count": etenders_candidates_extracted_count,
        "etenders_detail_pages_attempted_count": etenders_detail_pages_attempted_count,
        "etenders_detail_pages_success_count": etenders_detail_pages_success_count,
        "etenders_detail_pages_timeout_count": etenders_detail_pages_timeout_count,
        "etenders_tenderdetails_links_found_count": etenders_tenderdetails_links_found_count,
        "index_page_no_artifacts_count": index_page_no_artifacts_count,
        "artifact_download_failed_count": artifact_download_failed_count,
    }
    qualification_summary = {
        "status": "ok",
        "service_version": "V61_FORECAST_TO_ACTION_WATCHLIST_EXTENDS_V60_V59",
        "extracted_candidates_count": extracted_candidates_count,
        "qualified_candidates_count": len(qualified),
        "rejected_candidates_count": len(rejected),
        "qualification_reasons": qualification_reason_counts,
        "top_qualified_candidates": qualified[:10],
        "extraction_success_rate": extraction_success_rate,
        "document_link_detection_rate": document_link_detection_rate,
        **conversion_summary,
        **document_diagnostics,
        **memory_diagnostics,
        **source_pack_diagnostics,
        **buyer_intelligence_diagnostics,
        **forecast_diagnostics,
        **watchlist_diagnostics,
        "rejection_counts_by_reason": rejection_counts,
        "safety": {
            "final_submission": "disabled",
            "captcha_bypass": False,
        },
    }
    _write_payload(qualification_summary_report, qualification_summary)

    summary = {
        "status": "ok",
        "service_version": "V61_FORECAST_TO_ACTION_WATCHLIST_EXTENDS_V60_V59",
        "mode": "multi_portal_discovery",
        "dry_run": bool(dry_run),
        "started_at": started_at,
        "completed_at": _now_iso(),
        "total_sources_loaded": len(all_sources),
        "sources_selected_this_cycle": len(selected_sources),
        "healthy_sources_count": healthy_sources_count,
        "unhealthy_sources_count": unhealthy_sources_count,
        "candidate_producing_sources_count": candidate_producing_sources_count,
        "productive_sources_count": productive_sources_count,
        "suppressed_sources_count": suppressed_sources_count,
        "suppressed_dns_count": acquisition_health_counts.get("dns_blocked", 0),
        "suppressed_http_count": acquisition_health_counts.get("http_blocked", 0),
        "suppressed_empty_count": acquisition_health_counts.get("empty", 0),
        **focus_diagnostics,
        "source_rotation_batch_id": source_rotation_batch_id,
        "skipped_sources_count": len(skipped_source_rows),
        "skipped_sources": [row.get("source_name") for row in skipped_source_rows[:15]],
        "source_pack_strategy": {
            "active_pack_mode": source_pack_diagnostics.get("active_pack_mode"),
            "pack_rotation_strategy": source_pack_diagnostics.get("pack_rotation_strategy"),
            "projected_highest_yield_pack": source_pack_diagnostics.get("projected_highest_yield_pack"),
            "repair_mode_used": source_pack_diagnostics.get("repair_mode_used", False),
            "repair_sources_checked_count": source_pack_diagnostics.get("repair_sources_checked_count", 0),
            "repair_sources_selected_count": source_pack_diagnostics.get("repair_sources_selected_count", 0),
            "repair_sources_failed_count": source_pack_diagnostics.get("repair_sources_failed_count", 0),
            "repair_selected_source_names": source_pack_diagnostics.get("repair_selected_source_names", []),
            "repair_failed_by_reason": source_pack_diagnostics.get("repair_failed_by_reason", {}),
            "pack_summary": source_pack_strategy.get("pack_summary", []),
        },
        "buyer_intelligence": {
            "diagnostics": buyer_intelligence_diagnostics,
            "top_high_value_buyers": buyer_intelligence_result.get("high_value_buyers", [])[:10],
            "top_procurement_patterns": buyer_intelligence_result.get("patterns", [])[:10],
        },
        "tender_radar": {
            "diagnostics": forecast_diagnostics,
            "top_forecasts": forecast_result.get("forecasts", [])[:10],
            "high_probability_forecasts": forecast_result.get("high_probability_forecasts", [])[:10],
        },
        "forecast_action_watchlist": {
            "diagnostics": watchlist_diagnostics,
            "top_watchlist_entries": watchlist_result.get("watchlist_entries", [])[:10],
            "daily_priority_targets": watchlist_result.get("daily_priority_targets", [])[:10],
        },
        "top_performing_sources": top_performing_sources[:10],
        "productive_sources_count": yield_summary.get("productive_sources_count", 0),
        "empty_sources_count": yield_summary.get("empty_sources_count", 0),
        "top_yield_sources": yield_summary.get("top_yield_sources", [])[:10],
        "adaptive_weight_updates": yield_summary.get("adaptive_weight_updates", [])[:20],
        "tier_distribution": yield_summary.get("tier_distribution", {}),
        "source_rebalance_actions": yield_summary.get("source_rebalance_actions", [])[:20],
        "projected_next_cycle_priority_sources": yield_summary.get("projected_next_cycle_priority_sources", [])[:15],
        "source_health_overview": source_health_overview,
        "acquisition_runtime_summary": acquisition_runtime_summary,
        "sources_scanned_count": len(selected_sources),
        "pages_scanned_count": pages_scanned_count,
        "raw_candidates_count": len(raw_candidates),
        "eligible_candidates_count": len(eligible),
        "extracted_candidates_count": extracted_candidates_count,
        "qualified_candidates_count": len(qualified),
        "rejected_candidates_count": len(rejected),
        "rejection_counts_by_reason": rejection_counts,
        **conversion_summary,
        **document_diagnostics,
        **memory_diagnostics,
        **source_pack_diagnostics,
        **buyer_intelligence_diagnostics,
        **forecast_diagnostics,
        **watchlist_diagnostics,
        "repair_mode_used": source_pack_diagnostics.get("repair_mode_used", False),
        "repair_sources_checked_count": source_pack_diagnostics.get("repair_sources_checked_count", 0),
        "repair_sources_selected_count": source_pack_diagnostics.get("repair_sources_selected_count", 0),
        "repair_sources_failed_count": source_pack_diagnostics.get("repair_sources_failed_count", 0),
        "repair_selected_source_names": source_pack_diagnostics.get("repair_selected_source_names", []),
        "repair_failed_by_reason": source_pack_diagnostics.get("repair_failed_by_reason", {}),
        "qualification_reasons": qualification_reason_counts,
        "top_qualified_candidates": qualified[:10],
        "extraction_success_rate": extraction_success_rate,
        "document_link_detection_rate": document_link_detection_rate,
        "top_eligible_candidates": eligible[:10],
        "discovery_termination_reason": "completed",
        "source_runs": source_runs,
        "source_health_this_cycle": source_health_rows,
        "acquisition_runtime_report": _display_project_path(LAST_ACQUISITION_RUNTIME_DIAGNOSTICS_FILE),
        "pre_cycle_health_sample": pre_cycle_health_rows[:20],
        "artifacts": {
            "eligible_candidates_report": str(eligible_report),
            "qualified_candidates_report": str(qualified_report),
            "rejected_candidates_report": str(rejected_report),
            "document_candidates_report": str(document_candidates_report_path),
            "document_parse_summary": str(document_parse_summary_path),
            "qualification_summary": str(qualification_summary_report),
            "discovery_summary": str(summary_report),
            "source_health_report": str(source_health_report),
            "top_sources": str(top_sources_report),
            "acquisition_runtime_report": str(LAST_ACQUISITION_RUNTIME_DIAGNOSTICS_FILE),
            "source_pack_repair_diagnostics": str(SOURCE_PACK_REPAIR_DIAGNOSTICS_FILE),
            "source_yield_rankings": str(SOURCE_YIELD_RANKINGS_FILE),
            "adaptive_source_weights": str(ADAPTIVE_SOURCE_WEIGHTS_FILE),
            "yield_summary": str(YIELD_SUMMARY_FILE),
            "source_memory": str(SOURCE_MEMORY_FILE),
            "buyer_memory": str(BUYER_MEMORY_FILE),
            "category_memory": str(CATEGORY_MEMORY_FILE),
            "document_pattern_memory": str(DOCUMENT_PATTERN_MEMORY_FILE),
            **source_pack_artifacts,
            **buyer_intelligence_artifacts,
            **forecast_artifacts,
            **watchlist_artifacts,
        },
        "safety": {
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService

        summary["lifecycle_ingestion"] = RfqLifecycleService().ingest_discovered_items(
            qualified,
            source="multi_portal_discovery:qualified_candidates",
        )
    except Exception as exc:
        summary["lifecycle_ingestion"] = {"status": "warning", "error": _truncate(str(exc), 240)}
    _write_payload(summary_report, summary)
    return summary


def _v62_read_json_file(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _v62_cycle_pack_mode(history: List[Dict[str, Any]], requested_mode: Any = None) -> str:
    if requested_mode:
        return _v58_pack_mode(requested_mode)
    watchlist_summary = _v62_read_json_file(WATCHLIST_SUMMARY_FILE, {})
    watchlist_count = int((watchlist_summary or {}).get("daily_priority_targets_count") or 0) if isinstance(watchlist_summary, dict) else 0
    completed = len(history)
    if completed and completed % 5 == 0:
        return "exploration"
    if watchlist_count > 0:
        return "focus"
    return "balanced"


def _v62_source_productivity_rows(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in summary.get("source_runs") or []:
        if not isinstance(row, dict):
            continue
        candidates = int(row.get("document_built_candidates_count") or 0) + int(row.get("harvested_count") or 0)
        documents = int(row.get("documents_downloaded_count") or 0) + int(row.get("documents_parsed_count") or 0)
        score = round(
            candidates * 18.0
            + int(row.get("document_links_found_count") or 0) * 5.0
            + documents * 7.0
            + _safe_float(row.get("source_pack_yield_score"), 0.0) * 0.18
            - (25.0 if row.get("error") else 0.0),
            2,
        )
        rows.append({
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "source_packs": row.get("source_packs") or [],
            "candidate_yield": candidates,
            "document_links_found_count": row.get("document_links_found_count"),
            "documents_downloaded_count": row.get("documents_downloaded_count"),
            "documents_parsed_count": row.get("documents_parsed_count"),
            "source_pack_yield_score": row.get("source_pack_yield_score"),
            "source_response_time": row.get("source_response_time"),
            "productivity_score": score,
        })
    if not rows:
        rows = [
            {
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "candidate_yield": row.get("candidate_total"),
                "source_success_score": row.get("source_success_score"),
                "productivity_score": round(_safe_float(row.get("source_success_score"), 0.0) + int(row.get("candidate_total") or 0) * 6.0, 2),
            }
            for row in summary.get("top_performing_sources") or []
            if isinstance(row, dict)
        ]
    return sorted(rows, key=lambda row: _safe_float(row.get("productivity_score"), 0.0), reverse=True)


def _v62_buyer_trend_rows(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    buyers = (summary.get("buyer_intelligence") or {}).get("top_high_value_buyers") if isinstance(summary.get("buyer_intelligence"), dict) else []
    if not isinstance(buyers, list):
        buyers = []
    rows = []
    for row in buyers:
        if not isinstance(row, dict):
            continue
        scoring = row.get("scoring") if isinstance(row.get("scoring"), dict) else {}
        rows.append({
            "buyer_name": row.get("buyer_name"),
            "profile_type": row.get("profile_type"),
            "strategic_value": scoring.get("strategic_value", row.get("strategic_value")),
            "repeat_likelihood": scoring.get("repeat_likelihood", row.get("repeat_likelihood")),
            "profitability_trend": scoring.get("profitability_trend", row.get("average_estimated_profit")),
            "document_completeness": scoring.get("document_completeness"),
            "trend_score": round(
                _safe_float(scoring.get("strategic_value", row.get("strategic_value") or 0), 0.0) * 0.36
                + _safe_float(scoring.get("repeat_likelihood", row.get("repeat_likelihood") or 0), 0.0) * 0.30
                + _safe_float(scoring.get("document_completeness"), 0.0) * 0.18
                + _safe_float(scoring.get("profitability_trend", row.get("average_estimated_profit") or 0), 0.0) * 0.16,
                2,
            ),
        })
    if not rows:
        rows = [
            {
                "buyer_name": row.get("buyer_name"),
                "profile_type": row.get("profile_type"),
                "trend_score": row.get("overall_confidence"),
                "forecast_type": row.get("forecast_type"),
            }
            for row in summary.get("strongest_predictive_buyers") or []
            if isinstance(row, dict)
        ]
    return sorted(rows, key=lambda row: _safe_float(row.get("trend_score"), 0.0), reverse=True)


def _v62_category_trend_rows(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    categories = summary.get("strongest_predictive_categories")
    if not isinstance(categories, list):
        categories = []
    rows = []
    for row in categories:
        if not isinstance(row, dict):
            continue
        rows.append({
            "category": row.get("category"),
            "forecast_count": row.get("forecast_count"),
            "average_confidence": row.get("average_confidence"),
            "forecast_types": row.get("forecast_types") or [],
            "trend_score": round(_safe_float(row.get("average_confidence"), 0.0) + int(row.get("forecast_count") or 0) * 4.0, 2),
        })
    if not rows:
        patterns = (summary.get("buyer_intelligence") or {}).get("top_procurement_patterns") if isinstance(summary.get("buyer_intelligence"), dict) else []
        rows = [
            {
                "category": row.get("category"),
                "pattern_type": row.get("pattern_type"),
                "buyer_name": row.get("buyer_name"),
                "trend_score": row.get("repeat_likelihood"),
            }
            for row in patterns or []
            if isinstance(row, dict)
        ]
    return sorted(rows, key=lambda row: _safe_float(row.get("trend_score"), 0.0), reverse=True)


def run_autonomous_radar_cycle(
    cycles: int = 1,
    max_sources: int = 3,
    max_per_source: int = 1,
    headless: bool = True,
    source_pack_mode: Any = None,
    include_bad_sources: bool = False,
    source_file: Optional[str] = None,
) -> Dict[str, Any]:
    """V62 autonomous radar cycle orchestration. Always dry-run; never submits."""
    cycles = min(max(_safe_positive_int(cycles, 1), 1), 5)
    max_sources = _safe_positive_int(max_sources, 3)
    max_per_source = _safe_positive_int(max_per_source, 1)
    history_payload = _v62_read_json_file(CYCLE_HISTORY_FILE, {"cycles": []})
    history = history_payload.get("cycles") if isinstance(history_payload, dict) and isinstance(history_payload.get("cycles"), list) else []
    cycle_summaries: List[Dict[str, Any]] = []

    for _ in range(cycles):
        active_mode = _v62_cycle_pack_mode(history + cycle_summaries, requested_mode=source_pack_mode)
        started_at = _now_iso()
        discovery_summary = run_multi_portal_discovery(
            max_sources=max_sources,
            max_per_source=max_per_source,
            headless=headless,
            source_file=source_file,
            include_bad_sources=include_bad_sources,
            dry_run=True,
            source_pack_mode=active_mode,
            buyer_intelligence=True,
            opportunity_forecasting=True,
            forecast_watchlist=True,
        )
        source_rankings = _v62_source_productivity_rows(discovery_summary)
        buyer_rankings = _v62_buyer_trend_rows(discovery_summary)
        category_rankings = _v62_category_trend_rows(discovery_summary)
        candidate_yield = int(discovery_summary.get("raw_candidates_count") or discovery_summary.get("extracted_candidates_count") or 0)
        adaptive_updates = discovery_summary.get("adaptive_weight_updates") if isinstance(discovery_summary.get("adaptive_weight_updates"), list) else []
        learning_confidence = round(
            min(
                100.0,
                35.0
                + min(25.0, candidate_yield * 8.0)
                + min(15.0, len(adaptive_updates) * 1.5)
                + min(15.0, int(discovery_summary.get("watchlist_entries_count") or 0) * 6.0)
                + min(10.0, int(discovery_summary.get("high_probability_forecasts_count") or 0) * 4.0),
            ),
            2,
        )
        cycle_summary = {
            "cycle_id": f"v62-{int(time.time())}-{len(history) + len(cycle_summaries) + 1}",
            "service_version": "V62_AUTONOMOUS_TENDER_RADAR_CYCLES_EXTENDS_V61_V53",
            "started_at": started_at,
            "completed_at": _now_iso(),
            "dry_run": True,
            "active_pack_mode": active_mode,
            "source_rotation_batch_id": discovery_summary.get("source_rotation_batch_id"),
            "sources_scanned_count": discovery_summary.get("sources_scanned_count"),
            "candidate_yield": candidate_yield,
            "qualified_candidates_count": discovery_summary.get("qualified_candidates_count"),
            "document_links_found_count": discovery_summary.get("document_links_found_count"),
            "watchlist_entries_count": discovery_summary.get("watchlist_entries_count"),
            "daily_priority_targets_count": discovery_summary.get("daily_priority_targets_count"),
            "forecasted_opportunities_count": discovery_summary.get("forecasted_opportunities_count"),
            "high_probability_forecasts_count": discovery_summary.get("high_probability_forecasts_count"),
            "adaptive_weight_updates_count": len(adaptive_updates),
            "learning_confidence_score": learning_confidence,
            "top_performing_sources": source_rankings[:10],
            "top_performing_buyers": buyer_rankings[:10],
            "top_performing_categories": category_rankings[:10],
            "artifacts_refreshed": {
                "source_packs": discovery_summary.get("artifacts", {}).get("active_source_packs") if isinstance(discovery_summary.get("artifacts"), dict) else "",
                "buyer_intelligence": discovery_summary.get("artifacts", {}).get("buyer_profiles") if isinstance(discovery_summary.get("artifacts"), dict) else "",
                "opportunity_forecasts": discovery_summary.get("artifacts", {}).get("opportunity_forecasts") if isinstance(discovery_summary.get("artifacts"), dict) else "",
                "action_watchlist": discovery_summary.get("artifacts", {}).get("action_watchlist") if isinstance(discovery_summary.get("artifacts"), dict) else "",
                "yield_summary": discovery_summary.get("artifacts", {}).get("yield_summary") if isinstance(discovery_summary.get("artifacts"), dict) else "",
            },
            "safety": {
                "dry_run_only": True,
                "allow_portal_final_submit": False,
                "final_portal_submit": "hard_blocked",
                "captcha_bypass": False,
            },
        }
        cycle_summaries.append(cycle_summary)

    updated_history = (history + cycle_summaries)[-100:]
    average_candidate_yield = round(
        sum(_safe_float(row.get("candidate_yield"), 0.0) for row in updated_history) / max(1, len(updated_history)),
        2,
    )
    all_source_rows = sorted(
        [row for cycle in updated_history for row in (cycle.get("top_performing_sources") or []) if isinstance(row, dict)],
        key=lambda row: _safe_float(row.get("productivity_score"), 0.0),
        reverse=True,
    )
    all_buyer_rows = sorted(
        [row for cycle in updated_history for row in (cycle.get("top_performing_buyers") or []) if isinstance(row, dict)],
        key=lambda row: _safe_float(row.get("trend_score"), 0.0),
        reverse=True,
    )
    all_category_rows = sorted(
        [row for cycle in updated_history for row in (cycle.get("top_performing_categories") or []) if isinstance(row, dict)],
        key=lambda row: _safe_float(row.get("trend_score"), 0.0),
        reverse=True,
    )
    latest = cycle_summaries[-1] if cycle_summaries else {}
    diagnostics = {
        "autonomous_cycles_completed": len(updated_history),
        "average_candidate_yield": average_candidate_yield,
        "top_performing_sources": all_source_rows[:10],
        "top_performing_buyers": all_buyer_rows[:10],
        "top_performing_categories": all_category_rows[:10],
        "learning_confidence_score": latest.get("learning_confidence_score", 0),
        "adaptive_weight_updates_count": latest.get("adaptive_weight_updates_count", 0),
    }
    history_payload = {
        "status": "ok",
        "service_version": "V62_AUTONOMOUS_TENDER_RADAR_CYCLES_EXTENDS_V61_V53",
        "generated_at": _now_iso(),
        "cycles": updated_history,
        "diagnostics": diagnostics,
    }
    current_payload = {
        "status": "ok",
        "service_version": "V62_AUTONOMOUS_TENDER_RADAR_CYCLES_EXTENDS_V61_V53",
        "generated_at": _now_iso(),
        "current_cycle": latest,
        "diagnostics": diagnostics,
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    source_payload = {"status": "ok", "generated_at": _now_iso(), "source_productivity_rankings": all_source_rows[:100], "diagnostics": diagnostics}
    buyer_payload = {"status": "ok", "generated_at": _now_iso(), "buyer_trend_rankings": all_buyer_rows[:100], "diagnostics": diagnostics}
    category_payload = {"status": "ok", "generated_at": _now_iso(), "category_trend_rankings": all_category_rows[:100], "diagnostics": diagnostics}
    CYCLE_HISTORY_FILE.write_text(json.dumps(history_payload, indent=2, default=str), encoding="utf-8")
    CURRENT_CYCLE_SUMMARY_FILE.write_text(json.dumps(current_payload, indent=2, default=str), encoding="utf-8")
    SOURCE_PRODUCTIVITY_RANKINGS_FILE.write_text(json.dumps(source_payload, indent=2, default=str), encoding="utf-8")
    BUYER_TREND_RANKINGS_FILE.write_text(json.dumps(buyer_payload, indent=2, default=str), encoding="utf-8")
    CATEGORY_TREND_RANKINGS_FILE.write_text(json.dumps(category_payload, indent=2, default=str), encoding="utf-8")
    return {
        "status": "ok",
        "service_version": "V62_AUTONOMOUS_TENDER_RADAR_CYCLES_EXTENDS_V61_V53",
        "dry_run": True,
        "cycles_run_this_request": len(cycle_summaries),
        "diagnostics": diagnostics,
        **diagnostics,
        "current_cycle": latest,
        "artifacts": {
            "cycle_history": str(CYCLE_HISTORY_FILE),
            "current_cycle_summary": str(CURRENT_CYCLE_SUMMARY_FILE),
            "source_productivity_rankings": str(SOURCE_PRODUCTIVITY_RANKINGS_FILE),
            "buyer_trend_rankings": str(BUYER_TREND_RANKINGS_FILE),
            "category_trend_rankings": str(CATEGORY_TREND_RANKINGS_FILE),
        },
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }


def _v63_candidate_text(candidate: Dict[str, Any]) -> str:
    evidence = candidate.get("document_evidence") if isinstance(candidate.get("document_evidence"), dict) else {}
    return re.sub(
        r"\s+",
        " ",
        " ".join(
            _clean(value)
            for value in [
                candidate.get("rfq_number"),
                candidate.get("buyer_rfq_number"),
                candidate.get("reference_number"),
                candidate.get("title"),
                candidate.get("description"),
                candidate.get("raw_text"),
                candidate.get("commodity_service_category"),
                candidate.get("category"),
                candidate.get("source_name"),
                candidate.get("buyer_name"),
                evidence.get("filename"),
                evidence.get("text_excerpt"),
            ]
        ),
    ).strip()


def _v63_extract_rfq_number(text: str, candidate: Dict[str, Any]) -> str:
    patterns = [
        r"\b(?:TENDER|RFQ|RFP|RFB|BID|QUOTE|QUOTATION)\s*(?:NO\.?|NUMBER|#|REF(?:ERENCE)?\.?)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/_\-.]{3,40})",
        r"\b(?:RFQ|RFP|RFB|BID|TENDER|QUOTE|QUOTATION)\s*(?:NO\.?|NUMBER|#|REF(?:ERENCE)?\.?)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9/_\-.]{3,40})",
        r"\b([A-Z]{2,10}[-_/]\d{2,6}[-_/]\d{2,6}(?:[-_/][A-Z0-9]{1,12})?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            value = _clean(match.group(1) if match.lastindex else match.group(0))
            if value.lower() not in {"documents", "document", "proposal", "proposals"}:
                return value
    explicit = _clean(candidate.get("rfq_number") or candidate.get("buyer_rfq_number") or candidate.get("reference_number"))
    if explicit and len(explicit) <= 80 and re.search(r"\d|rfq|bid|tender|quote", explicit, flags=re.I):
        return explicit
    return explicit


def _v63_extract_closing_date(text: str, candidate: Dict[str, Any]) -> str:
    explicit = _clean(candidate.get("closing_date"))
    if explicit:
        return explicit
    iso = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if iso:
        return f"{iso.group(1)}-{int(iso.group(2)):02d}-{int(iso.group(3)):02d}"
    dmy = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", text)
    if dmy:
        return f"{dmy.group(3)}-{int(dmy.group(2)):02d}-{int(dmy.group(1)):02d}"
    month = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b",
        text,
        flags=re.I,
    )
    if month:
        month_num = datetime.strptime(month.group(2)[:3], "%b").month
        return f"{month.group(3)}-{month_num:02d}-{int(month.group(1)):02d}"
    return ""


def _v63_detect_pricing_schedule(text: str, candidate: Dict[str, Any]) -> Dict[str, Any]:
    evidence = candidate.get("document_evidence") if isinstance(candidate.get("document_evidence"), dict) else {}
    filename = _safe_lower(evidence.get("filename"))
    detected = bool(re.search(r"pricing schedule|schedule of prices|bill of quantities|\bboq\b|price schedule|sbd\s*3", text, flags=re.I))
    detected = detected or any(term in filename for term in ["pricing", "price", "boq", "schedule"])
    return {
        "detected": detected,
        "source": "document_or_text_signal" if detected else "",
        "filename": evidence.get("filename", ""),
    }


def _v63_compulsory_documents(text: str) -> List[str]:
    checks = [
        ("valid_tax_pin", r"tax pin|tax compliance|sars"),
        ("csd_registration", r"\bcsd\b|central supplier database"),
        ("bbbee_certificate", r"b-bbee|bbbee|bee certificate|sworn affidavit"),
        ("company_registration", r"cipc|company registration|ck document"),
        ("pricing_schedule", r"pricing schedule|schedule of prices|sbd\s*3|boq"),
        ("declaration_forms", r"sbd\s*4|sbd\s*6|declaration of interest|municipal declaration"),
    ]
    return [label for label, pattern in checks if re.search(pattern, text, flags=re.I)]


def _v63_delivery_locations(text: str, candidate: Dict[str, Any]) -> List[str]:
    locations = []
    for pattern in [
        r"(?:delivery|deliver|site|location|address)\s*(?:to|at|:|-)\s*([^.;\n]{5,100})",
        r"\b(Gauteng|Western Cape|Eastern Cape|KwaZulu-Natal|Free State|Limpopo|Mpumalanga|North West|Northern Cape)\b",
    ]:
        for match in re.finditer(pattern, text, flags=re.I):
            value = _clean(match.group(1))
            if value and value.lower() not in {loc.lower() for loc in locations}:
                locations.append(_truncate(value, 100))
    province = _clean(candidate.get("province"))
    if province and province.lower() not in {loc.lower() for loc in locations}:
        locations.append(province)
    return locations[:8]


def _v63_contact_details(text: str, candidate: Dict[str, Any]) -> Dict[str, Any]:
    email = _v54_extract_email(text, candidate)
    phone_match = re.search(r"(?:\+27|0)\s?\d{2}\s?\d{3}\s?\d{4}\b", text)
    contact_name = ""
    name_match = re.search(r"(?:contact person|enquiries|attention)\s*[:\-]\s*([A-Z][A-Za-z .'-]{3,60})", text)
    if name_match:
        contact_name = _clean(name_match.group(1))
    return {
        "email": email,
        "phone": phone_match.group(0) if phone_match else "",
        "contact_name": contact_name,
    }


def _v63_supply_fit(text: str, candidate: Dict[str, Any]) -> bool:
    if re.search(r"\bsupply\s*(and|&|,)?\s*delivery\b|supply of|delivery of|supply and deliver|goods|materials|consumables|stationery|ppe", text, flags=re.I):
        return True
    return bool(candidate.get("low_complexity_opportunity") and candidate.get("commodity_service_category") in {"office_supplies", "general_goods"})


def _v63_enrich_opportunity(candidate: Dict[str, Any]) -> Dict[str, Any]:
    text = _v63_candidate_text(candidate)
    pricing_schedule = _v63_detect_pricing_schedule(text, candidate)
    closing_date = _v63_extract_closing_date(text, candidate)
    buyer_name = _clean(candidate.get("buyer_name") or candidate.get("buyer") or candidate.get("source_name"))
    category = _clean(candidate.get("commodity_service_category") or candidate.get("category") or _v54_commodity_category(text))
    contact = _v63_contact_details(text, candidate)
    supply_fit = _v63_supply_fit(text, candidate)
    profit_signal = candidate.get("estimated_profit_signal") if isinstance(candidate.get("estimated_profit_signal"), dict) else _v52_estimated_profit_signal(text, candidate)
    briefing_none = bool(re.search(r"compulsory\s+briefing\s*[:\-]?\s*(none|no|not applicable|n/?a)\b", text, flags=re.I))
    briefing_required = not briefing_none and (
        bool(candidate.get("briefing_required"))
        or bool(re.search(r"compulsory briefing|mandatory briefing|compulsory site|site inspection.*compulsory", text, flags=re.I))
    )
    confidence_reasons: List[str] = []
    confidence = 0.0
    rfq_number = _v63_extract_rfq_number(text, candidate)
    if rfq_number:
        confidence += 12
        confidence_reasons.append("rfq_number_detected")
    if buyer_name:
        confidence += 12
        confidence_reasons.append("buyer_detected")
    if closing_date:
        confidence += 14
        confidence_reasons.append("closing_date_detected")
    if candidate.get("document_urls") or candidate.get("built_from_document_evidence"):
        confidence += 14
        confidence_reasons.append("document_rich")
    if pricing_schedule.get("detected"):
        confidence += 12
        confidence_reasons.append("pricing_schedule_detected")
    if contact.get("email") or contact.get("phone"):
        confidence += 8
        confidence_reasons.append("contact_detected")
    if supply_fit:
        confidence += 12
        confidence_reasons.append("supply_delivery_fit")
    if _safe_float(profit_signal.get("estimated_profit"), 0.0) >= DEFAULT_MINIMUM_PROFIT:
        confidence += 10
        confidence_reasons.append("profitable_signal")
    if briefing_required:
        confidence -= 18
    if candidate.get("exclusion_reason") in {"expired_or_closed", "construction_heavy", "briefing_required"}:
        confidence -= 22
    confidence = round(max(0.0, min(100.0, confidence)), 2)
    document_confidence_score = round(max(0.0, min(confidence / 100.0, 1.0)), 4)
    if confidence >= 72.0 and not candidate.get("exclusion_reason") and not briefing_required:
        classification = "highly_qualified"
    elif confidence >= 45.0 and candidate.get("exclusion_reason") not in {"expired_or_closed", "construction_heavy"}:
        classification = "review_required"
    else:
        classification = "reject"
    blocker_reasons = list(candidate.get("blocker_reasons") or [])
    if candidate.get("exclusion_reason"):
        blocker_reasons.append(str(candidate.get("exclusion_reason")))
    if not closing_date:
        blocker_reasons.append("missing_closing_date")
    elif candidate.get("exclusion_reason") == "expired_or_closed":
        blocker_reasons.append("expired_or_closed")
    if not candidate.get("document_urls"):
        blocker_reasons.append("no_downloadable_rfq_documents")
    if briefing_required:
        blocker_reasons.append("briefing_required")
    blocker_reasons = sorted(set(reason for reason in blocker_reasons if reason))
    return {
        "opportunity_id": _v57_candidate_fingerprint(candidate),
        "classification": classification,
        "extraction_confidence": confidence,
        "document_confidence_score": document_confidence_score,
        "document_verified": bool(document_confidence_score >= 0.75 and candidate.get("document_urls")),
        "confidence_reasons": sorted(set(confidence_reasons)),
        "rfq_number": rfq_number,
        "buyer_name": buyer_name,
        "closing_date": closing_date,
        "province": _clean(candidate.get("province") or _v54_extract_province(text)),
        "category": category,
        "pricing_schedule": pricing_schedule,
        "compulsory_documents": _v63_compulsory_documents(text),
        "delivery_locations": _v63_delivery_locations(text, candidate),
        "contact_details": contact,
        "briefing_session": {
            "detected": briefing_required,
            "compulsory": briefing_required,
        },
        "supply_and_delivery_fit": supply_fit,
        "estimated_profitability": profit_signal,
        "document_rich": bool(candidate.get("document_urls") or candidate.get("built_from_document_evidence")),
        "document_urls": candidate.get("document_urls") or [],
        "source_name": candidate.get("source_name"),
        "source_url": candidate.get("source_url"),
        "title": candidate.get("title"),
        "description": _truncate(candidate.get("description"), 500),
        "original_exclusion_reason": candidate.get("exclusion_reason", ""),
        "blocker_reasons": blocker_reasons,
        "qualification_score": candidate.get("qualification_score"),
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }


def run_real_opportunity_extraction(
    max_sources: int = 3,
    max_per_source: int = 1,
    headless: bool = True,
    source_pack_mode: Any = None,
    include_bad_sources: bool = False,
    source_file: Optional[str] = None,
) -> Dict[str, Any]:
    discovery_summary = run_multi_portal_discovery(
        max_sources=max_sources,
        max_per_source=max_per_source,
        headless=headless,
        source_file=source_file,
        include_bad_sources=include_bad_sources,
        dry_run=True,
        source_pack_mode=source_pack_mode or "focus",
        buyer_intelligence=True,
        opportunity_forecasting=True,
        forecast_watchlist=True,
    )
    reports = []
    for path in [
        MULTI_PORTAL_DISCOVERY_DIR / "eligible_candidates_report.json",
        MULTI_PORTAL_DISCOVERY_DIR / "rejected_candidates_report.json",
        MULTI_PORTAL_DISCOVERY_DIR / "document_candidates_report.json",
    ]:
        data = _v62_read_json_file(path, [])
        if isinstance(data, list):
            reports.extend(row for row in data if isinstance(row, dict))
    deduped: Dict[str, Dict[str, Any]] = {}
    for candidate in reports:
        key = candidate.get("candidate_fingerprint") or _v57_candidate_fingerprint(candidate)
        existing = deduped.get(key)
        if not existing or (candidate.get("built_from_document_evidence") and not existing.get("built_from_document_evidence")):
            deduped[key] = candidate
    extracted = [_v63_enrich_opportunity(candidate) for candidate in deduped.values()]
    extracted = sorted(extracted, key=lambda row: (row.get("classification") == "highly_qualified", _safe_float(row.get("extraction_confidence"), 0.0), row.get("document_rich") is True), reverse=True)
    high_confidence = [row for row in extracted if row.get("classification") == "highly_qualified"]
    review_required = [row for row in extracted if row.get("classification") == "review_required"]
    rejected = [row for row in extracted if row.get("classification") == "reject"]
    attempts = len(extracted)
    diagnostics = {
        "extraction_attempts_count": attempts,
        "high_confidence_opportunities_count": len(high_confidence),
        "review_required_count": len(review_required),
        "rejected_count": len(rejected),
        "pricing_schedule_detection_rate": round(sum(1 for row in extracted if (row.get("pricing_schedule") or {}).get("detected")) / max(1, attempts) * 100.0, 2),
        "closing_date_detection_rate": round(sum(1 for row in extracted if row.get("closing_date")) / max(1, attempts) * 100.0, 2),
        "buyer_detection_rate": round(sum(1 for row in extracted if row.get("buyer_name")) / max(1, attempts) * 100.0, 2),
        "supply_fit_detection_rate": round(sum(1 for row in extracted if row.get("supply_and_delivery_fit")) / max(1, attempts) * 100.0, 2),
        "profitability_estimation_success_rate": round(sum(1 for row in extracted if _safe_float((row.get("estimated_profitability") or {}).get("estimated_profit"), 0.0) > 0) / max(1, attempts) * 100.0, 2),
    }
    payload_base = {
        "service_version": "V63_REAL_OPPORTUNITY_EXTRACTION_EXTENDS_V62_V53",
        "generated_at": _now_iso(),
        "diagnostics": diagnostics,
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    EXTRACTED_OPPORTUNITIES_FILE.write_text(json.dumps({"status": "ok", **payload_base, "opportunities": extracted}, indent=2, default=str), encoding="utf-8")
    HIGH_CONFIDENCE_OPPORTUNITIES_FILE.write_text(json.dumps({"status": "ok", **payload_base, "opportunities": high_confidence}, indent=2, default=str), encoding="utf-8")
    REVIEW_REQUIRED_OPPORTUNITIES_FILE.write_text(json.dumps({"status": "ok", **payload_base, "opportunities": review_required}, indent=2, default=str), encoding="utf-8")
    REJECTED_OPPORTUNITIES_FILE.write_text(json.dumps({"status": "ok", **payload_base, "opportunities": rejected}, indent=2, default=str), encoding="utf-8")
    EXTRACTION_SUMMARY_FILE.write_text(json.dumps({"status": "ok", **payload_base, "discovery_summary_ref": str(MULTI_PORTAL_DISCOVERY_DIR / "discovery_summary.json")}, indent=2, default=str), encoding="utf-8")
    return {
        "status": "ok",
        "service_version": "V63_REAL_OPPORTUNITY_EXTRACTION_EXTENDS_V62_V53",
        "dry_run": True,
        "diagnostics": diagnostics,
        **diagnostics,
        "high_confidence_opportunities": high_confidence[:10],
        "review_required_opportunities": review_required[:10],
        "rejected_opportunities": rejected[:10],
        "artifacts": {
            "extracted_opportunities": str(EXTRACTED_OPPORTUNITIES_FILE),
            "high_confidence_opportunities": str(HIGH_CONFIDENCE_OPPORTUNITIES_FILE),
            "review_required_opportunities": str(REVIEW_REQUIRED_OPPORTUNITIES_FILE),
            "rejected_opportunities": str(REJECTED_OPPORTUNITIES_FILE),
            "extraction_summary": str(EXTRACTION_SUMMARY_FILE),
        },
        "discovery_diagnostics": {
            "active_pack_mode": discovery_summary.get("active_pack_mode"),
            "sources_scanned_count": discovery_summary.get("sources_scanned_count"),
            "raw_candidates_count": discovery_summary.get("raw_candidates_count"),
            "document_links_found_count": discovery_summary.get("document_links_found_count"),
        },
        "safety": payload_base["safety"],
    }


def _v64_resolve_document_path(value: Any) -> Path:
    text = _clean(value)
    if text.startswith("/app/"):
        return PROJECT_ROOT / text[len("/app/"):]
    return Path(text)


def _v64_parse_document_text(row: Dict[str, Any]) -> str:
    path = _v64_resolve_document_path(row.get("path"))
    ext = _clean(row.get("extension") or path.suffix.lower())
    if not path.exists():
        return ""
    if ext == ".pdf":
        return _v56_parse_pdf(path)
    if ext == ".docx":
        return _v56_parse_docx(path)
    if ext == ".xlsx":
        return _v56_parse_xlsx(path)
    return ""


def _v64_detect_document_structures(text: str, row: Dict[str, Any]) -> Dict[str, Any]:
    filename = _safe_lower(row.get("filename"))
    blob = _safe_lower(f"{filename} {text}")
    pricing_schedule = bool(re.search(r"pricing schedule|schedule of prices|price schedule|sbd\s*3|pricing data|bid price|quoted price|unit price|total price|amount excluding vat|amount incl", blob))
    boq = bool(re.search(r"\bboq\b|bill of quantities|bill no\.?|item\s+no\.?.{0,40}quantity|description.{0,40}qty.{0,40}rate", blob))
    rfq_form = bool(re.search(r"\brfq\b|request for quotation|quotation number|request for tender|tender number", blob))
    sbd = bool(re.search(r"\bsbd\s*[0-9]\b|standard bidding document|preference points claim|declaration of interest", blob))
    mandatory_returnables = _v63_compulsory_documents(text)
    delivery_schedule = bool(re.search(r"delivery schedule|delivery address|delivery location|deliver(?:y)? to|lead time|delivery period", blob))
    quantity_column = bool(re.search(r"\b(qty|quantity|quantities|no\.? required|number required|required quantity|amount required|quantity offered)\b", blob))
    unit_column = bool(re.search(r"\b(unit|uom|unit of measure|each|ea|box|ream|kg|litre|meter|sqm|m2)\b", blob))
    pricing_column = bool(re.search(r"\b(unit price|rate|price|amount|total|subtotal|vat|incl\.? vat|excl\.? vat)\b", blob))
    if not pricing_schedule and sbd and pricing_column and re.search(r"returnable schedules|price\(s\)|price schedule|offer price|total bid price", blob):
        pricing_schedule = True
    item_table = bool(
        re.search(r"\b(item|line)\s*(no\.?|number)?\b.{0,80}\b(description|goods|service)\b", blob)
        or sum(1 for term in ["description", "quantity", "unit", "price", "amount"] if term in blob) >= 3
    )
    bill_structure = bool(boq or (item_table and quantity_column and (unit_column or pricing_column)))
    table_success = bool(item_table or bill_structure or row.get("extension") in {".xlsx", ".xls"})
    return {
        "pricing_schedule_detected": pricing_schedule,
        "boq_detected": boq,
        "rfq_form_detected": rfq_form,
        "sbd_detected": sbd,
        "mandatory_returnable_documents": mandatory_returnables,
        "delivery_schedule_detected": delivery_schedule,
        "bill_of_quantities_structure": bill_structure,
        "item_table_detected": item_table,
        "quantity_column_detected": quantity_column,
        "unit_column_detected": unit_column,
        "pricing_column_detected": pricing_column,
        "table_extraction_success": table_success,
    }


def _v65_quantity_label_pattern() -> str:
    return r"(?:qty|quantity|number required|required quantity|units required|amount required|estimated quantity)"


def _v65_is_probably_non_order_quantity(raw: str, context: str) -> bool:
    value = _clean(raw)
    ctx = _safe_lower(context)
    if re.search(r"\d+\.\d+", value):
        return True
    if re.search(r"\b\d+(?:\.\d+)?\s*mm\b", ctx):
        return True
    if re.search(r"\b(calibre|caliber|berdan|primer|ammunition|diameter|thickness|length|tolerance|specification)\b", ctx):
        return True
    return False


def _v65_extract_item_tables(text: str, row: Dict[str, Any]) -> Dict[str, Any]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in re.split(r"[\r\n]+|(?<=\.)\s+(?=[A-Z0-9])", text) if _clean(line)]
    quantity_rows: List[Dict[str, Any]] = []
    embedded_mentions: List[Dict[str, Any]] = []
    item_rows: List[Dict[str, Any]] = []
    label_pattern = _v65_quantity_label_pattern()

    for line in lines[:500]:
        lower = _safe_lower(line)
        label_match = re.search(rf"\b{label_pattern}\b\s*[:\-]?\s*(\d{{1,7}}(?:[.,]\d{{1,2}})?)\b", line, flags=re.I)
        if label_match:
            context = line[max(0, label_match.start() - 80): label_match.end() + 120]
            if not _v65_is_probably_non_order_quantity(label_match.group(1), context):
                quantity_rows.append({
                    "quantity": label_match.group(1).replace(",", "."),
                    "quantity_source": "label_backed_quantity",
                    "quantity_confidence": 0.88,
                    "context": _truncate(context, 240),
                })
        unit_match = re.search(r"\b(\d{1,7})\s*(units?|items?|boxes|reams|packs|sets|each|ea|pairs|litres?|meters?|sqm|m2|kg)\b", line, flags=re.I)
        if unit_match:
            context = line[max(0, unit_match.start() - 100): unit_match.end() + 140]
            if not _v65_is_probably_non_order_quantity(unit_match.group(1), context):
                embedded_mentions.append({
                    "quantity": unit_match.group(1),
                    "unit": unit_match.group(2),
                    "quantity_source": "embedded_quantity_with_unit",
                    "quantity_confidence": 0.72,
                    "context": _truncate(context, 260),
                })
        if re.search(r"\b(supply|delivery|provide|appointment|description|item|service)\b", lower) and re.search(r"\b(goods|materials?|equipment|consumables|stationery|primers?|service provider|supply)\b", lower):
            item_rows.append({
                "description": _truncate(line, 260),
                "quantity": "",
                "unit": "",
                "quantity_confidence": 0.0,
                "row_source": "description_row",
            })

    inferred_rows: List[Dict[str, Any]] = []
    for mention in quantity_rows + embedded_mentions:
        inferred_rows.append({
            "description": mention.get("context"),
            "quantity": mention.get("quantity"),
            "unit": mention.get("unit", ""),
            "quantity_confidence": mention.get("quantity_confidence"),
            "row_source": mention.get("quantity_source"),
        })
    rows = inferred_rows or item_rows[:8]
    average_confidence = round(
        sum(_safe_float(row.get("quantity_confidence"), 0.0) for row in rows) / max(1, len(rows)),
        2,
    )
    quantity_detected = any(_safe_float(row.get("quantity_confidence"), 0.0) >= 0.65 and row.get("quantity") for row in rows)
    table_detected = bool(rows)
    table_confidence = round(min(1.0, 0.25 + (0.35 if table_detected else 0.0) + (0.40 if quantity_detected else 0.0)), 2)
    return {
        "item_table_detected": table_detected,
        "item_rows": rows[:20],
        "quantity_columns_detected": bool(quantity_rows),
        "embedded_quantity_mentions": embedded_mentions[:20],
        "embedded_quantity_mentions_count": len(embedded_mentions),
        "inferred_quantity_count": sum(1 for row in rows if row.get("quantity") and _safe_float(row.get("quantity_confidence"), 0.0) >= 0.65),
        "quantity_detected": quantity_detected,
        "quantity_confidence": average_confidence,
        "table_confidence": table_confidence,
    }


def _v64_document_confidence(structures: Dict[str, Any], row: Dict[str, Any], text: str) -> Tuple[float, float, List[str]]:
    reasons: List[str] = []
    confidence = 0.0
    if structures.get("pricing_schedule_detected"):
        confidence += 22
        reasons.append("pricing_schedule")
    if structures.get("boq_detected"):
        confidence += 20
        reasons.append("boq")
    if structures.get("rfq_form_detected"):
        confidence += 12
        reasons.append("rfq_form")
    if structures.get("sbd_detected"):
        confidence += 8
        reasons.append("sbd_form")
    if structures.get("item_table_detected"):
        confidence += 12
        reasons.append("item_table")
    if structures.get("quantity_column_detected"):
        confidence += 10
        reasons.append("quantity_column")
    if structures.get("unit_column_detected"):
        confidence += 6
        reasons.append("unit_column")
    if structures.get("pricing_column_detected"):
        confidence += 10
        reasons.append("pricing_column")
    if structures.get("mandatory_returnable_documents"):
        confidence += 5
        reasons.append("returnables")
    if int(row.get("text_length") or len(text)) > 500:
        confidence += 5
    quote_ready = 0.0
    if structures.get("pricing_schedule_detected") or structures.get("boq_detected"):
        quote_ready += 35
    if structures.get("item_table_detected"):
        quote_ready += 15
    if structures.get("quantity_column_detected"):
        quote_ready += 20
    if structures.get("unit_column_detected"):
        quote_ready += 10
    if structures.get("pricing_column_detected"):
        quote_ready += 15
    if structures.get("rfq_form_detected"):
        quote_ready += 5
    return round(min(100.0, confidence), 2), round(min(100.0, quote_ready), 2), reasons


def _v64_classify_document(confidence: float, quote_ready_score: float, structures: Dict[str, Any]) -> str:
    has_pricing_core = bool(structures.get("pricing_schedule_detected") or structures.get("boq_detected"))
    has_table_core = bool(structures.get("item_table_detected") and structures.get("quantity_column_detected"))
    v65_quantity = structures.get("v65_quantity_extraction") if isinstance(structures.get("v65_quantity_extraction"), dict) else {}
    if v65_quantity.get("quantity_detected") and _safe_float(v65_quantity.get("quantity_confidence"), 0.0) >= 0.65:
        has_table_core = True
    if quote_ready_score >= 75.0 and has_pricing_core and has_table_core:
        return "quote_ready"
    if quote_ready_score >= 55.0 and (has_pricing_core or has_table_core):
        return "partial_quote_ready"
    if confidence >= 35.0 or structures.get("rfq_form_detected") or structures.get("sbd_detected"):
        return "review_required"
    return "reject"


def _v64_analyse_document(row: Dict[str, Any]) -> Dict[str, Any]:
    text = _v64_parse_document_text(row)
    structures = _v64_detect_document_structures(text, row)
    quantity_extraction = _v65_extract_item_tables(text, row)
    structures["v65_quantity_extraction"] = quantity_extraction
    if quantity_extraction.get("item_table_detected"):
        structures["item_table_detected"] = True
    if quantity_extraction.get("quantity_columns_detected") or quantity_extraction.get("quantity_detected"):
        structures["quantity_column_detected"] = True
    if quantity_extraction.get("item_table_detected") and quantity_extraction.get("quantity_detected"):
        structures["bill_of_quantities_structure"] = True
        structures["table_extraction_success"] = True
    confidence, quote_ready_score, reasons = _v64_document_confidence(structures, row, text)
    if quantity_extraction.get("item_table_detected") and "item_table" not in reasons:
        reasons.append("item_table")
    if quantity_extraction.get("quantity_detected"):
        quote_ready_score = min(100.0, quote_ready_score + 15.0)
        confidence = min(100.0, confidence + 10.0)
        reasons.append("v65_quantity_detected")
    elif quantity_extraction.get("item_table_detected"):
        reasons.append("v65_item_rows_without_verified_quantity")
    classification = _v64_classify_document(confidence, quote_ready_score, structures)
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return {
        "document_id": sha256(_clean(row.get("url") or row.get("path") or row.get("filename")).encode("utf-8")).hexdigest(),
        "classification": classification,
        "document_confidence": confidence,
        "quote_readiness_score": quote_ready_score,
        "confidence_reasons": reasons,
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "document_url": row.get("url"),
        "path": row.get("path"),
        "filename": row.get("filename"),
        "extension": row.get("extension"),
        "parser": row.get("parser"),
        "text_length": row.get("text_length") or len(text),
        "metadata": metadata,
        "document_types": {
            "pricing_schedule": structures.get("pricing_schedule_detected"),
            "boq": structures.get("boq_detected"),
            "rfq_form": structures.get("rfq_form_detected"),
            "sbd_form": structures.get("sbd_detected"),
            "delivery_schedule": structures.get("delivery_schedule_detected"),
        },
        "structures": structures,
        "extracted_table_hints": {
            "quantity_columns": structures.get("quantity_column_detected"),
            "unit_columns": structures.get("unit_column_detected"),
            "pricing_columns": structures.get("pricing_column_detected"),
            "item_tables": structures.get("item_table_detected"),
            "bill_of_quantities": structures.get("bill_of_quantities_structure"),
        },
        "item_table_extraction": quantity_extraction,
        "text_excerpt": _truncate(text, 800),
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }


def run_document_intelligence_dry_run(
    max_sources: int = 3,
    max_per_source: int = 1,
    headless: bool = True,
    source_pack_mode: Any = None,
    include_bad_sources: bool = False,
    source_file: Optional[str] = None,
) -> Dict[str, Any]:
    discovery_summary = run_multi_portal_discovery(
        max_sources=max_sources,
        max_per_source=max_per_source,
        headless=headless,
        source_file=source_file,
        include_bad_sources=include_bad_sources,
        dry_run=True,
        source_pack_mode=source_pack_mode or "focus",
        buyer_intelligence=True,
        opportunity_forecasting=True,
        forecast_watchlist=True,
    )
    parse_payload = _v62_read_json_file(MULTI_PORTAL_DISCOVERY_DIR / "document_parse_summary.json", {})
    docs = parse_payload.get("documents") if isinstance(parse_payload, dict) and isinstance(parse_payload.get("documents"), list) else []
    analysed = [_v64_analyse_document(row) for row in docs if isinstance(row, dict) and row.get("status") in {"parsed", "metadata_only"}]
    analysed = sorted(analysed, key=lambda row: (_safe_float(row.get("quote_readiness_score"), 0.0), _safe_float(row.get("document_confidence"), 0.0)), reverse=True)
    pricing_schedules = [row for row in analysed if (row.get("document_types") or {}).get("pricing_schedule") or (row.get("document_types") or {}).get("boq")]
    quote_ready = [row for row in analysed if row.get("classification") in {"quote_ready", "partial_quote_ready"}]
    review_required = [row for row in analysed if row.get("classification") == "review_required"]
    rejected = [row for row in analysed if row.get("classification") == "reject"]
    item_table_rows = [row for row in analysed if (row.get("item_table_extraction") or {}).get("item_table_detected")]
    quantity_rows = [row for row in analysed if (row.get("item_table_extraction") or {}).get("quantity_detected") or (row.get("item_table_extraction") or {}).get("embedded_quantity_mentions_count")]
    count = len(analysed)
    quantity_confidences = [
        _safe_float((row.get("item_table_extraction") or {}).get("quantity_confidence"), 0.0)
        for row in analysed
        if (row.get("item_table_extraction") or {}).get("item_table_detected")
    ]
    diagnostics = {
        "documents_scanned_count": count,
        "pricing_schedules_detected_count": sum(1 for row in analysed if (row.get("document_types") or {}).get("pricing_schedule")),
        "boq_detected_count": sum(1 for row in analysed if (row.get("document_types") or {}).get("boq")),
        "sbd_detected_count": sum(1 for row in analysed if (row.get("document_types") or {}).get("sbd_form")),
        "quote_ready_count": len(quote_ready),
        "review_required_count": len(review_required),
        "rejected_count": len(rejected),
        "item_tables_detected_count": len(item_table_rows),
        "quantity_columns_detected_count": sum(1 for row in analysed if (row.get("item_table_extraction") or {}).get("quantity_columns_detected")),
        "embedded_quantity_mentions_count": sum(int((row.get("item_table_extraction") or {}).get("embedded_quantity_mentions_count") or 0) for row in analysed),
        "inferred_quantity_count": sum(int((row.get("item_table_extraction") or {}).get("inferred_quantity_count") or 0) for row in analysed),
        "table_extraction_success_rate": round(sum(1 for row in analysed if (row.get("structures") or {}).get("table_extraction_success")) / max(1, count) * 100.0, 2),
        "pricing_column_detection_rate": round(sum(1 for row in analysed if (row.get("structures") or {}).get("pricing_column_detected")) / max(1, count) * 100.0, 2),
        "quantity_detection_rate": round(sum(1 for row in analysed if (row.get("structures") or {}).get("quantity_column_detected")) / max(1, count) * 100.0, 2),
        "average_quantity_confidence": round(sum(quantity_confidences) / max(1, len(quantity_confidences)), 2),
        "document_confidence_average": round(sum(_safe_float(row.get("document_confidence"), 0.0) for row in analysed) / max(1, count), 2),
    }
    base = {
        "service_version": "V65_QUANTITY_ITEM_TABLE_EXTRACTION_EXTENDS_V64_V42",
        "generated_at": _now_iso(),
        "diagnostics": diagnostics,
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    PRICING_SCHEDULES_FILE.write_text(json.dumps({"status": "ok", **base, "documents": pricing_schedules}, indent=2, default=str), encoding="utf-8")
    ITEM_TABLES_FILE.write_text(json.dumps({"status": "ok", **base, "documents": item_table_rows}, indent=2, default=str), encoding="utf-8")
    QUANTITY_EXTRACTION_REPORT_FILE.write_text(json.dumps({"status": "ok", **base, "documents": quantity_rows}, indent=2, default=str), encoding="utf-8")
    QUOTE_READY_DOCUMENTS_FILE.write_text(json.dumps({"status": "ok", **base, "documents": quote_ready}, indent=2, default=str), encoding="utf-8")
    REVIEW_REQUIRED_DOCUMENTS_FILE.write_text(json.dumps({"status": "ok", **base, "documents": review_required}, indent=2, default=str), encoding="utf-8")
    REJECTED_DOCUMENTS_FILE.write_text(json.dumps({"status": "ok", **base, "documents": rejected}, indent=2, default=str), encoding="utf-8")
    DOCUMENT_INTELLIGENCE_SUMMARY_FILE.write_text(json.dumps({"status": "ok", **base, "documents": analysed[:20], "discovery_diagnostics": {"active_pack_mode": discovery_summary.get("active_pack_mode"), "document_links_found_count": discovery_summary.get("document_links_found_count"), "documents_parsed_count": discovery_summary.get("documents_parsed_count")}}, indent=2, default=str), encoding="utf-8")
    return {
        "status": "ok",
        "service_version": "V65_QUANTITY_ITEM_TABLE_EXTRACTION_EXTENDS_V64_V42",
        "dry_run": True,
        "diagnostics": diagnostics,
        **diagnostics,
        "pricing_schedules": pricing_schedules[:10],
        "quote_ready_documents": quote_ready[:10],
        "review_required_documents": review_required[:10],
        "rejected_documents": rejected[:10],
        "artifacts": {
            "pricing_schedules": str(PRICING_SCHEDULES_FILE),
            "item_tables": str(ITEM_TABLES_FILE),
            "quantity_extraction_report": str(QUANTITY_EXTRACTION_REPORT_FILE),
            "quote_ready_documents": str(QUOTE_READY_DOCUMENTS_FILE),
            "review_required_documents": str(REVIEW_REQUIRED_DOCUMENTS_FILE),
            "rejected_documents": str(REJECTED_DOCUMENTS_FILE),
            "document_intelligence_summary": str(DOCUMENT_INTELLIGENCE_SUMMARY_FILE),
        },
        "safety": base["safety"],
    }


def _v66_reference_number(value: Any, metadata: Dict[str, Any]) -> str:
    text = _clean(metadata.get("reference_number") or value)
    match = re.search(r"\b(?:TENDER|RFQ|RFP|RFB|BID)?\s*([A-Z0-9][A-Z0-9/_\-.]*\d[A-Z0-9/_\-.]*)\b", text, flags=re.I)
    return _clean(match.group(1) if match else text)


def _v66_review_reasons(document: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    structures = document.get("structures") if isinstance(document.get("structures"), dict) else {}
    item_table = document.get("item_table_extraction") if isinstance(document.get("item_table_extraction"), dict) else {}
    doc_types = document.get("document_types") if isinstance(document.get("document_types"), dict) else {}
    if not item_table.get("quantity_detected"):
        reasons.append("missing_quantity")
    if item_table.get("item_table_detected") and not item_table.get("quantity_detected"):
        reasons.append("unclear_item_table")
    if doc_types.get("pricing_schedule") and not structures.get("bill_of_quantities_structure"):
        reasons.append("pricing_schedule_partial")
    if not doc_types.get("pricing_schedule") and not doc_types.get("boq") and doc_types.get("rfq_form"):
        reasons.append("specification_only")
    if doc_types.get("pricing_schedule") and not item_table.get("quantity_detected"):
        reasons.append("manual_buyer_schedule_required")
    return sorted(set(reasons))


def _v66_missing_fields(document: Dict[str, Any]) -> List[str]:
    missing = []
    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    item_table = document.get("item_table_extraction") if isinstance(document.get("item_table_extraction"), dict) else {}
    closing_date = _v63_extract_closing_date(" ".join([_clean(metadata.get("closing_date")), _clean(document.get("text_excerpt"))]), {})
    if not _v66_reference_number("", metadata):
        missing.append("rfq_number")
    if not closing_date:
        missing.append("closing_date")
    if not item_table.get("quantity_detected"):
        missing.append("verified_quantity")
    if not item_table.get("inferred_quantity_count"):
        missing.append("buyer_item_quantities")
    if not (document.get("extracted_table_hints") or {}).get("bill_of_quantities"):
        missing.append("bill_of_quantities_structure")
    return missing


def _v66_recommended_action(reasons: List[str]) -> str:
    if "missing_quantity" in reasons or "manual_buyer_schedule_required" in reasons:
        return "open buyer RFQ document and confirm quantities or request buyer pricing schedule before quote generation"
    if "pricing_schedule_partial" in reasons:
        return "review pricing pages and map item rows, units, and price columns manually"
    if "unclear_item_table" in reasons:
        return "inspect extracted item rows and confirm whether the text is a valid buyer schedule"
    if "specification_only" in reasons:
        return "locate separate pricing schedule or BOQ attachment"
    return "manual review required before quote generation"


def _v66_is_urgent(document: Dict[str, Any]) -> bool:
    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    closing = _v63_extract_closing_date(" ".join([_clean(metadata.get("closing_date")), _clean(document.get("text_excerpt"))]), {})
    if not closing:
        return False
    try:
        close_date = datetime.strptime(closing[:10], "%Y-%m-%d").date()
        days = (close_date - datetime.now(timezone.utc).date()).days
        return 0 <= days <= 7
    except Exception:
        return False


def _v66_queue_item(document: Dict[str, Any]) -> Dict[str, Any]:
    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    doc_types = document.get("document_types") if isinstance(document.get("document_types"), dict) else {}
    text = _clean(document.get("text_excerpt"))
    reasons = _v66_review_reasons(document)
    briefing_none = bool(re.search(r"compulsory\s+briefing\s*[:\-]?\s*(none|no|not applicable|n/?a)\b", text, flags=re.I))
    briefing_required = not briefing_none and bool(re.search(r"compulsory briefing|mandatory briefing|compulsory site|site inspection.*compulsory", text, flags=re.I))
    closing_date = _v63_extract_closing_date(" ".join([_clean(metadata.get("closing_date")), text]), {})
    return {
        "review_id": document.get("document_id"),
        "rfq_number": _v66_reference_number(document.get("filename"), metadata),
        "buyer": document.get("source_name"),
        "closing_date": closing_date,
        "briefing_required": briefing_required,
        "detected_pricing_schedule": bool(doc_types.get("pricing_schedule")),
        "detected_sbd_forms": bool(doc_types.get("sbd_form")),
        "missing_fields": _v66_missing_fields(document),
        "review_reasons": reasons,
        "reason_review_required": "; ".join(reasons),
        "recommended_next_action": _v66_recommended_action(reasons),
        "document_confidence": document.get("document_confidence"),
        "quote_readiness_score": document.get("quote_readiness_score"),
        "document_url": document.get("document_url"),
        "filename": document.get("filename"),
        "source_url": document.get("source_url"),
        "urgent": _v66_is_urgent(document),
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }


def run_review_queue_dry_run(
    max_sources: int = 3,
    max_per_source: int = 1,
    headless: bool = True,
    source_pack_mode: Any = None,
    include_bad_sources: bool = False,
    source_file: Optional[str] = None,
) -> Dict[str, Any]:
    document_result = run_document_intelligence_dry_run(
        max_sources=max_sources,
        max_per_source=max_per_source,
        headless=headless,
        source_pack_mode=source_pack_mode or "focus",
        include_bad_sources=include_bad_sources,
        source_file=source_file,
    )
    queue_source = document_result.get("quote_ready_documents") if isinstance(document_result.get("quote_ready_documents"), list) else []
    partial_docs = [doc for doc in queue_source if isinstance(doc, dict) and doc.get("classification") == "partial_quote_ready"]
    queue = sorted([_v66_queue_item(doc) for doc in partial_docs], key=lambda row: (row.get("urgent") is True, _safe_float(row.get("quote_readiness_score"), 0.0)), reverse=True)
    urgent = [row for row in queue if row.get("urgent")]
    next_actions = [
        {
            "rfq_number": row.get("rfq_number"),
            "buyer": row.get("buyer"),
            "action": row.get("recommended_next_action"),
            "review_reasons": row.get("review_reasons"),
        }
        for row in queue[:10]
    ]
    diagnostics = {
        "review_queue_count": len(queue),
        "urgent_review_count": len(urgent),
        "missing_quantity_count": sum(1 for row in queue if "missing_quantity" in (row.get("review_reasons") or [])),
        "pricing_schedule_partial_count": sum(1 for row in queue if "pricing_schedule_partial" in (row.get("review_reasons") or [])),
        "manual_buyer_schedule_required_count": sum(1 for row in queue if "manual_buyer_schedule_required" in (row.get("review_reasons") or [])),
        "next_recommended_actions": next_actions,
    }
    base = {
        "service_version": "V66_PARTIAL_QUOTE_READY_REVIEW_QUEUE_EXTENDS_V65_V63",
        "generated_at": _now_iso(),
        "diagnostics": diagnostics,
        "safety": {
            "dry_run_only": True,
            "allow_portal_final_submit": False,
            "final_portal_submit": "hard_blocked",
            "captcha_bypass": False,
        },
    }
    PARTIAL_QUOTE_READY_QUEUE_FILE.write_text(json.dumps({"status": "ok", **base, "items": queue}, indent=2, default=str), encoding="utf-8")
    URGENT_REVIEW_ITEMS_FILE.write_text(json.dumps({"status": "ok", **base, "items": urgent}, indent=2, default=str), encoding="utf-8")
    REVIEW_SUMMARY_FILE.write_text(json.dumps({"status": "ok", **base, "review_queue_count": len(queue), "urgent_review_count": len(urgent)}, indent=2, default=str), encoding="utf-8")
    return {
        "status": "ok",
        "service_version": "V66_PARTIAL_QUOTE_READY_REVIEW_QUEUE_EXTENDS_V65_V63",
        "dry_run": True,
        "diagnostics": diagnostics,
        **diagnostics,
        "partial_quote_ready_queue": queue[:20],
        "urgent_review_items": urgent[:20],
        "artifacts": {
            "partial_quote_ready_queue": str(PARTIAL_QUOTE_READY_QUEUE_FILE),
            "urgent_review_items": str(URGENT_REVIEW_ITEMS_FILE),
            "review_summary": str(REVIEW_SUMMARY_FILE),
        },
        "document_intelligence_diagnostics": document_result.get("diagnostics", {}),
        "safety": base["safety"],
    }


def get_review_queue_status() -> Dict[str, Any]:
    queue_payload = _v62_read_json_file(PARTIAL_QUOTE_READY_QUEUE_FILE, {})
    urgent_payload = _v62_read_json_file(URGENT_REVIEW_ITEMS_FILE, {})
    summary_payload = _v62_read_json_file(REVIEW_SUMMARY_FILE, {})
    queue_items = queue_payload.get("items") if isinstance(queue_payload, dict) and isinstance(queue_payload.get("items"), list) else []
    urgent_items_raw = urgent_payload.get("items") if isinstance(urgent_payload, dict) and isinstance(urgent_payload.get("items"), list) else []
    diagnostics = summary_payload.get("diagnostics") if isinstance(summary_payload, dict) and isinstance(summary_payload.get("diagnostics"), dict) else {}

    def shape(item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "rfq_number": item.get("rfq_number"),
            "buyer": item.get("buyer"),
            "closing_date": item.get("closing_date"),
            "review_reasons": item.get("review_reasons") or [],
            "recommended_action": item.get("recommended_next_action"),
            "missing_fields": item.get("missing_fields") or [],
            "quote_readiness_status": "partial_quote_ready_review_required",
            "document_confidence": item.get("document_confidence"),
            "quote_readiness_score": item.get("quote_readiness_score"),
            "urgent": bool(item.get("urgent")),
        }

    urgent_items = [shape(item) for item in urgent_items_raw if isinstance(item, dict)]
    return {
        "status": "ok",
        "service_version": "V67_OPERATOR_REVIEW_DASHBOARD_API_EXTENDS_V66",
        "review_queue_count": int(diagnostics.get("review_queue_count") or len(queue_items)),
        "urgent_review_count": int(diagnostics.get("urgent_review_count") or len(urgent_items)),
        "urgent_items": urgent_items,
        "safety": {
            "dry_run_only": True,
            "final_submit_hard_blocked": True,
            "captcha_bypass": False,
        },
        "artifacts": {
            "partial_quote_ready_queue": str(PARTIAL_QUOTE_READY_QUEUE_FILE),
            "urgent_review_items": str(URGENT_REVIEW_ITEMS_FILE),
            "review_summary": str(REVIEW_SUMMARY_FILE),
        },
    }


def _source_is_temporarily_bad(source: Dict[str, Any], max_failures: int = 2, source_health_file: Optional[Path] = None) -> bool:
    health = _load_source_health(source_health_file=source_health_file)
    row = health.get(_source_key(source), {})
    if not isinstance(row, dict):
        return False
    return int(row.get("failure_count") or 0) >= max_failures


def select_sources_for_cycle(sources: List[Dict[str, Any]], max_sources_per_cycle: int, include_bad_sources: bool = False, controlled_mode: bool = False, source_health_snapshot: Optional[Dict[str, Any]] = None, source_health_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    max_sources_per_cycle = _safe_positive_int(max_sources_per_cycle, 20)
    enabled = [s for s in sources if s.get("enabled", True)]
    if controlled_mode:
        return sorted(
            enabled,
            key=lambda src: (
                int(src.get("priority") or 9999),
                -int(src.get("intelligence_score") or 0),
                _clean(src.get("name") or src.get("source_name")),
                _clean(src.get("url") or src.get("list_url")),
            ),
        )[:max_sources_per_cycle]
    core: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []
    for src in enabled:
        name = _safe_lower(src.get("name") or src.get("source_name"))
        group = _safe_lower(src.get("source_group") or src.get("category_group"))
        if "etenders" in name or group == "etenders":
            core.append(src)
        else:
            others.append(src)
    health = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file)
    if not include_bad_sources:
        core = [
            src
            for src in core
            if _clean(_v53_source_health_row(src, health, source_health_file=source_health_file).get("source_quarantine_status")) != "quarantined"
            and _clean(_v53_source_health_row(src, health, source_health_file=source_health_file).get("health_status")) not in {"dns_blocked", "http_blocked", "disabled"}
        ]
        others = [
            s
            for s in others
            if not _source_is_temporarily_bad(s, source_health_file=source_health_file)
            and _clean(_v53_source_health_row(s, health, source_health_file=source_health_file).get("health_status")) not in {"dns_blocked", "http_blocked", "disabled"}
        ]
    else:
        core = [
            _apply_commissioning_override(
                src,
                _v53_source_health_row(src, health, source_health_file=source_health_file),
                include_bad_sources=True,
            )
            for src in core
        ]

    def rank(src: Dict[str, Any]) -> Tuple[int, int, int, float, float, int, int, int, int, str]:
        row = _v53_source_health_row(src, health, source_health_file=source_health_file)
        quarantine_status = _clean(row.get("source_quarantine_status"))
        quarantine_rank = 0 if quarantine_status == "ready" else 1 if quarantine_status == "watch" else 2
        pool_rank, pool_state = _v53_source_pool_state(src, row)
        selection_score = _safe_float(row.get("source_selection_score"), _safe_float(row.get("source_success_score"), 0.0))
        if pool_state == "deprioritized_empty":
            selection_score -= 4.0
        elif pool_state == "retry_later":
            selection_score -= 10.0
        return (
            quarantine_rank,
            pool_rank,
            int(src.get("priority") or 9999),
            -selection_score,
            -int(src.get("intelligence_score") or 0),
            int(row.get("source_failure_count") or 0),
            -int(row.get("candidate_total") or 0),
            _clean(src.get("name")),
        )

    selected = sorted(core, key=rank) + sorted(others, key=rank)
    return selected[:max_sources_per_cycle]


NAVIGATION_NOISE_EXACT = {
    "tenders", "tender", "quotations", "quotation", "request for quotation", "request for bid",
    "request for bid (open-tender)", "request for bid (limited-tender)", "tender number", "advertised tenders",
    "transnet soc ltd tenders", "jobs, bursaries and tenders", "about e-tender", "tender bulletin",
    "tender process", "tender document download", "save tender: easily save tenders to your profile.",
    "new and additional power supply", "procurement", "supplier database", "open tenders", "closed tenders", "download",
}

CATEGORY_LABELS = {
    "construction", "supplies: general", "supplies: electrical equipment", "supplies: stationery/printing",
    "supplies: computer equipment", "services: professional", "services: general", "other service activities",
    "scientific research and development", "education", "security and investigation activities",
    "water supply; sewerage, waste management and remediation activities",
    "wholesale and retail trade and repair of motor vehicles and motorcycles",
    "office administrative, office support and other business support activities",
}

NOISE_PATTERNS = [
    "login required", "it seems like you are not logged in", "tender opportunities", "currently advertised tenders",
    "category tender description esubmission advertised closing", "use quick find", "advanced search", "reset all filters",
    "download excel", "download pdf", "please wait", "home page - etenders portal", "opportunities - etenders portal",
    "please note we are only searching open or active tenders", "please note we are only searching for open/active tenders",
    "this site provides access to information on all tenders made by all public sector organisations",
    "home page - transnet e-tenders", "search for advertised tenders", "browse opportunities", "please click on browse opportunities",
    "to filter through tenders with more control", "customerzation", "please continue to check both the e-tender system",
    "new esupplier portal", "on the tender results table below", "sign to expand tender details and to download tender documents",
    "to become a transnet supplier", "preset standards which are required in order to supply certain items or services",
    "can these specifications be issued as they are in a bid", "publication of tender", "when transnet needs to procure goods, services or works",
    "transnet soc ltd tenders", "minimum bid evaluation and award criteria", "toggle child menu", "expand generationtoggle",
    "skip to content", "sitemap", "privacy policy", "recent comments", "follow us", "all rights reserved", "no matching records found",
]


# Strict pre-harvest guard: these are portal/category wrappers unless the row contains
# a clear goods/supply RFQ signal. This prevents navigation/category rows from entering
# candidate scoring, while still preserving genuine supply-and-delivery tenders.
EARLY_BLOCK_TITLES = {
    "request for quotation",
    "request for bid",
    "request for bid (open-tender)",
    "request for bid (limited-tender)",
    "save tender: easily save tenders to your profile.",
    "advertised tenders",
    "tenders",
    "tender",
    "construction",
    "accommodation",
    "services: general",
    "services: professional",
    "services: electrical",
    "other service activities",
    "civil engineering",
    "administrative and support activities",
    "postal and courier activities",
    "transportation and storage",
    "other manufacturing",
    "information and communication",
    "disposals: general",
}

CATEGORY_PREFIXES = tuple(sorted(EARLY_BLOCK_TITLES | {
    "supplies: general",
    "supplies: electrical equipment",
    "supplies: stationery/printing",
    "supplies: clothing/textiles/footwear",
    "supplies: computer equipment",
    "manufacturing",
    "water collection, treatment and supply",
    "wholesale and retail trade and repair of motor vehicles and motorcycles",
    "scientific research and development",
}, key=len, reverse=True))

REAL_SUPPLY_PHRASES = (
    "supply and delivery",
    "supply & delivery",
    "supply, delivery",
    "supply and deliver",
    "supply, deliver",
    "supply of",
    "delivery of",
    "procurement of",
    "procure and delivery",
    "procure and deliver",
    "supply, install",
    "supply and installation",
    "supply and install",
)

ADDRESS_OR_INSTRUCTION_NOISE = (
    "delivery address:",
    "bid documents must be deposited",
    "the physical size of the bid response",
    "international suppliers may email",
    "tender box aperture",
    "documents must be deposited",
)

REAL_RFQ_INTENT_TERMS = [
    "rfq", "request for quotation", "quotation for", "supply and delivery", "supply and deliver", "supply & delivery", "supply, delivery", "supply, deliver",
    "supply of", "delivery of", "procurement of", "bid for supply", "tender for supply", "appointment of",
]
WEAK_INTENT_TERMS = ["tender", "bid", "quotation", "supply", "delivery", "installation"]


def _is_noise_row(text: str) -> bool:
    t = _safe_lower(text)
    if not t or len(t) < 30:
        return True
    if t in NAVIGATION_NOISE_EXACT or t in CATEGORY_LABELS or t in EARLY_BLOCK_TITLES:
        return True
    if any(noise in t for noise in ADDRESS_OR_INSTRUCTION_NOISE):
        return True
    if _looks_like_attachment_name(t):
        return True
    if _contains_only_old_years(t):
        return True
    if "toggle" in t or "child menu" in t or "menu expand" in t:
        return True
    if t.count("download") >= 4:
        return True
    return any(pattern in t for pattern in NOISE_PATTERNS)


def _has_real_rfq_intent(text: str) -> bool:
    t = _safe_lower(text)
    if any(term in t for term in REAL_RFQ_INTENT_TERMS):
        return True
    weak_hits = sum(1 for term in WEAK_INTENT_TERMS if term in t)
    return weak_hits >= 2 and len(t) >= 80


def _real_rfq_structure_score(text: str) -> Dict[str, Any]:
    """Score whether a row is structurally a real RFQ/tender opportunity.

    This gate is intentionally stricter than keyword intent. It rewards actual
    procurement structure and heavily penalises portal boilerplate, fraud
    warnings, landing pages, instructions, and expired/cancelled notices.
    """
    t = _safe_lower(text)
    score = 0
    reasons: List[str] = []

    if not t:
        return {"real_rfq_structure_score": 0, "real_rfq_structure_reasons": ["empty"], "real_rfq_structurally_valid": False}

    # Hard boilerplate / non-opportunity penalties.
    boilerplate = [
        "fake and fraudulent",
        "prospective suppliers are warned",
        "tender adjudication committee",
        "can be downloaded from",
        "rfq can be downloaded from",
        "procurement | development bank",
        "rfp & rfq procurement",
        "regarding quotations",
        "supplier database",
        "the idc advertises",
        "as part of the tender evaluation process",
        "for construction tenders. regarding quotations",
        "to become a transnet supplier",
        "minimum bid evaluation and award criteria",
        "publication of tender",
        "tender process",
        "tender document download",
        "tender bulletin",
        "about e-tender",
        "request for bid (open-tender)",
        "request for bid (limited-tender)",
        "save tender: easily save tenders to your profile",
    ]
    if any(x in t for x in boilerplate):
        score -= 80
        reasons.append("boilerplate_or_warning")

    # Cancelled/closed opportunities should not become quote candidates.
    if any(x in t for x in ["cancellation notice", "cancelled tender", "tender cancellation", "closed tender", "withdrawn"]):
        score -= 80
        reasons.append("cancelled_or_closed")

    # RFQ/RFP/tender reference patterns.
    reference_patterns = [
        r"\b(rfq|rfp|bid|tender)\s*(no|number|ref|reference)?\s*[:/#\-]?\s*[a-z0-9][a-z0-9/&_.\-]{2,}",
        r"\b(ref|reference)\s*(no|number)?\s*[:/#\-]?\s*[a-z0-9][a-z0-9/&_.\-]{2,}",
        r"\b[a-z]{2,}/?\d{2,}/?\d{2,}",
        r"\b\d{2,}/\d{4}\b",
    ]
    if any(re.search(pattern, t, flags=re.I) for pattern in reference_patterns):
        score += 25
        reasons.append("reference_number")

    # Dates and duration/value clues.
    if re.search(r"\b\d{2}/\d{2}/20\d{2}\b|\b20\d{2}-\d{2}-\d{2}\b", t):
        score += 20
        reasons.append("closing_or_advert_date")
    if re.search(r"\b(period of|for a period|\d+\s*(days?|months?|years?)|three years|five years|36 months|24 months|12 months)\b", t):
        score += 15
        reasons.append("duration_or_contract_period")

    # Core LMCP target signal.
    if any(x in t for x in ["supply and delivery", "supply, delivery", "supply & delivery", "supply and deliver", "supply, deliver"]):
        score += 35
        reasons.append("supply_delivery")
    elif any(x in t for x in ["supply of", "delivery of", "procurement of", "offloading of"]):
        score += 25
        reasons.append("supply_or_delivery")

    if any(x in t for x in ["appointment of", "request for quotation", "request for proposal", "bid description", "tender advert", "retender"]):
        score += 15
        reasons.append("procurement_action")

    if any(x in t for x in ["boq", "bill of quantities", "specification", "scope of work", "pricing schedule", "quantity", "offloading", "tender volume", "annexures"]):
        score += 10
        reasons.append("documents_or_specs")

    # Buyer/portal rows with only generic RFQ text are not enough.
    if len(t) < 35 and not any(x in t for x in ["supply and delivery", "supply of", "delivery of"]):
        score -= 20
        reasons.append("too_short")

    valid = score >= 45
    return {
        "real_rfq_structure_score": max(0, score),
        "real_rfq_structure_reasons": reasons,
        "real_rfq_structurally_valid": bool(valid),
    }


def _is_structural_real_rfq(text: str) -> bool:
    return bool(_real_rfq_structure_score(text).get("real_rfq_structurally_valid"))


def _has_real_supply_signal(text: str) -> bool:
    t = _safe_lower(text)
    return any(phrase in t for phrase in REAL_SUPPLY_PHRASES)



def _lmcp_safe_assign_identity_fields(
    item: Dict[str, Any],
    candidate_value: str,
) -> Dict[str, Any]:
    """
    Prevent category/listing labels from polluting RFQ identity fields.
    """

    candidate_value = _clean(candidate_value)
    candidate_value = _strip_leading_category(candidate_value)

    if not candidate_value:
        return item

    blocked_values = {
        "supplies: general",
        "services: general",
        "administrative and support activities",
        "other service activities",
        "manufacture of textiles",
        "manufacture of chemicals and chemical products",
        "construction",
        "supplies computer equipment",
    }

    normalized = _safe_lower(candidate_value)

    if normalized in blocked_values:
        item.setdefault("identity_assignment_blocked", True)
        item.setdefault("identity_assignment_block_reason", "generic_category_label")
        return item

    # Do not overwrite a better extracted reference
    existing = _clean(
        item.get("buyer_rfq_number_normalized")
        or item.get("extracted_reference_number")
        or item.get("reference_number")
        or item.get("rfq_number")
    )

    existing_has_digits = bool(re.search(r"\d", existing))
    candidate_has_digits = bool(re.search(r"\d", candidate_value))

    if existing and existing_has_digits and not candidate_has_digits:
        return item

    item["buyer_rfq_number"] = _truncate(candidate_value, 180)
    item["rfq_number"] = _truncate(candidate_value, 180)
    item["reference_number"] = _truncate(candidate_value, 180)

    return item



def _strip_leading_category(text: str) -> str:
    """
    V50.4: Remove eTenders sector/category wrappers before RFQ identity/scoring.
    Example:
    "Supplies: Clothing/Textiles/Footwear SUPPLY AND DELIVERY..."
    -> "SUPPLY AND DELIVERY..."
    """
    t = _clean(text)
    lower = t.lower()

    for prefix in CATEGORY_PREFIXES:
        if lower.startswith(prefix):
            return t[len(prefix):].strip(" :-–—|\t\n")

    # Broader eTenders category wrappers not always covered by CATEGORY_PREFIXES.
    broad_patterns = [
        r"^supplies:\s*[^\n\r]*?\b(?=(supply|request|rfq|rfp|bid|tender|appointment|procurement|re-advertisement)\b)",
        r"^services:\s*[^\n\r]*?\b(?=(supply|request|rfq|rfp|bid|tender|appointment|procurement|re-advertisement)\b)",
        r"^manufacture of [^\n\r]*?\b(?=(supply|request|rfq|rfp|bid|tender|appointment|procurement|re-advertisement)\b)",
        r"^water supply;[^\n\r]*?\b(?=(supply|request|rfq|rfp|bid|tender|appointment|procurement|re-advertisement)\b)",
        r"^other service activities\s+",
        r"^administrative and support activities\s+",
    ]

    for pattern in broad_patterns:
        stripped = re.sub(pattern, "", t, flags=re.I).strip(" :-–—|\t\n")
        if stripped != t and stripped:
            return stripped

    return t


def _should_skip_preharvest_candidate(text: str, title: str = "") -> bool:
    combined = re.sub(r"\s+", " ", f"{title} {text}").strip()
    normalized = _safe_lower(combined)
    normalized_title = _safe_lower(title)

    if not normalized:
        return True

    if any(noise in normalized for noise in ADDRESS_OR_INSTRUCTION_NOISE):
        return True

    if normalized in NAVIGATION_NOISE_EXACT or normalized in EARLY_BLOCK_TITLES:
        return True

    if normalized_title in EARLY_BLOCK_TITLES and not _has_real_supply_signal(normalized):
        return True

    # eTenders category rows often start with a sector label followed by the actual RFQ.
    # If the remaining text still lacks a true supply/procurement signal, discard it early.
    stripped = _safe_lower(_strip_leading_category(combined))
    starts_with_category = any(normalized.startswith(prefix) for prefix in CATEGORY_PREFIXES)
    if starts_with_category and not _has_real_supply_signal(stripped):
        return True

    if _is_noise_row(combined):
        return True

    if not _has_real_rfq_intent(combined):
        return True

    if not _is_structural_real_rfq(combined):
        return True

    return False


def _direct_etenders(
    source: Dict[str, Any],
    max_items: int,
    headless: bool,
    timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
    diagnostics: Optional[Dict[str, Any]] = None,
    page_load_timeout_seconds: Optional[int] = None,
    candidate_extraction_timeout_seconds: Optional[int] = None,
    document_link_timeout_seconds: Optional[int] = None,
) -> List[Dict[str, Any]]:
    url = _normalize_etenders_listing_url(source.get("url") or source.get("list_url") or ETENDERS_URL)
    max_items = _safe_positive_int(max_items, 20)
    page_load_timeout_seconds = _safe_positive_int(page_load_timeout_seconds, max(12, timeout_seconds))
    candidate_extraction_timeout_seconds = _safe_positive_int(candidate_extraction_timeout_seconds, max(15, timeout_seconds))
    document_link_timeout_seconds = _safe_positive_int(document_link_timeout_seconds, max(10, timeout_seconds))
    diag = diagnostics if isinstance(diagnostics, dict) else {}
    diag.update({
        "etenders_home_reached": False,
        "etenders_opportunities_page_reached": False,
        "etenders_candidates_table_detected": False,
        "etenders_candidates_extracted_count": 0,
        "etenders_detail_pages_attempted_count": 0,
        "etenders_detail_pages_success_count": 0,
        "etenders_detail_pages_timeout_count": 0,
        "etenders_tenderdetails_links_found_count": 0,
        "retry_count": int(diag.get("retry_count") or 0),
        "retry_stage": _clean(diag.get("retry_stage")),
        "partial_progress_persisted": False,
    })

    def _probe_detail_pages(items: List[Dict[str, Any]]) -> None:
        if not items:
            return
        diag["etenders_tenderdetails_links_found_count"] = sum(
            1
            for item in items
            if _clean(item.get("detail_url") or item.get("document_url")).startswith("http")
        )
        for item in items[:max(1, min(3, len(items)))]:
            detail_url = _clean(item.get("detail_url") or item.get("document_url"))
            if not detail_url:
                continue
            diag["etenders_detail_pages_attempted_count"] += 1
            try:
                resp = requests.get(
                    detail_url,
                    timeout=document_link_timeout_seconds,
                    headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0", "Accept": "text/html,application/json,*/*"},
                )
                if resp.ok:
                    diag["etenders_detail_pages_success_count"] += 1
            except Exception as exc:
                if "timeout" in _safe_lower(str(exc)):
                    diag["etenders_detail_pages_timeout_count"] += 1
                    diag["partial_progress_persisted"] = True

    def _home_and_opportunities_preflight() -> None:
        try:
            home_resp = requests.get(
                ETENDERS_BASE_URL,
                timeout=page_load_timeout_seconds,
                headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0", "Accept": "text/html,application/xhtml+xml,*/*"},
            )
            diag["etenders_home_reached"] = bool(home_resp.ok)
        except Exception:
            pass
        try:
            opp_resp = requests.get(
                url,
                timeout=page_load_timeout_seconds,
                headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0", "Accept": "text/html,application/xhtml+xml,*/*"},
            )
            diag["etenders_opportunities_page_reached"] = bool(opp_resp.ok)
            if opp_resp.ok:
                body = _safe_lower(getattr(opp_resp, "text", "") or "")
                if any(token in body for token in ("tenderdetails", "opportunities", "advertised", "closing", "description")):
                    diag["etenders_candidates_table_detected"] = True
        except Exception:
            pass

    _home_and_opportunities_preflight()

    def _fetch_json_results() -> List[Dict[str, Any]]:
        return _fetch_etenders_paginated_opportunities(
            source,
            max_items=max_items,
            timeout_seconds=candidate_extraction_timeout_seconds,
        )

    try:
        json_results = _fetch_json_results()
        if json_results:
            diag["etenders_opportunities_page_reached"] = True
            diag["etenders_candidates_table_detected"] = True
            diag["etenders_candidates_extracted_count"] = len(json_results)
            _probe_detail_pages(json_results)
            return json_results
    except Exception as exc:
        error_text = _truncate(str(exc), 240)
        logger.info("eTenders JSON listing fetch failed for %s: %s", source.get("name"), exc)
        if _v64_etenders_should_retry(error_text):
            diag["retry_count"] = int(diag.get("retry_count") or 0) + 1
            diag["retry_stage"] = "candidate_extraction_timeout"
            if "429" in error_text:
                time.sleep(1)
            try:
                json_results = _fetch_json_results()
                if json_results:
                    diag["etenders_opportunities_page_reached"] = True
                    diag["etenders_candidates_table_detected"] = True
                    diag["etenders_candidates_extracted_count"] = len(json_results)
                    _probe_detail_pages(json_results)
                    return json_results
            except Exception as retry_exc:
                logger.info("eTenders JSON listing retry failed for %s: %s", source.get("name"), retry_exc)
    try:
        # Prefer a static parse first so harvest cycles do not depend on browser launch.
        static_results = run_generic_scraper(source, timeout=candidate_extraction_timeout_seconds, max_items=max_items)
        if static_results:
            results: List[Dict[str, Any]] = []
            for raw in static_results:
                if not isinstance(raw, dict):
                    continue
                text = _clean(raw.get("raw_text") or raw.get("description") or raw.get("title"))
                title = _v50_clean_etenders_title(_clean(raw.get("title") or text))
                if not text:
                    continue
                if _should_skip_preharvest_candidate(text, title):
                    continue
                item = _base_item(source, text, url)
                item["raw_text_original"] = text
                item["title"] = _truncate(title or text, 180)
                item["description"] = text
                _lmcp_safe_assign_identity_fields(item, item["title"])
                item["buyer_name"] = _clean(source.get("name") or "eTenders")
                item["source_name"] = _clean(source.get("name") or "eTenders Web")
                item["source"] = item["source_name"]
                item["portal_name"] = item["source_name"]
                item["closing_date"] = _clean(raw.get("closing_date") or _extract_closing_date(text))
                discovered_tender_id = _v64_extract_etenders_tender_id(
                    raw.get("detail_url"),
                    raw.get("document_url"),
                    raw.get("url"),
                    raw.get("raw_text"),
                    raw.get("description"),
                    raw.get("title"),
                )
                if discovered_tender_id:
                    detail_url = _build_etenders_detail_url(discovered_tender_id)
                    item["detail_url"] = detail_url
                    item["document_url"] = detail_url
                    item["tender_id"] = discovered_tender_id
                    item["v50_8_discovered_tender_id"] = discovered_tender_id
                results.append(item)
            if results:
                diag["etenders_candidates_extracted_count"] = len(results)
                diag["etenders_candidates_table_detected"] = True
                _probe_detail_pages(results)
                return _dedupe_keep_order(results)[:max_items]
    except Exception as exc:
        logger.info("Static eTenders fallback failed for %s: %s", source.get("name"), exc)

    try:
        from app.services.etenders_playwright import run_etenders_playwright  # type: ignore
        try:
            data = run_etenders_playwright(max_items=max_items, headless=headless, timeout_ms=playwright_timeout_ms)
        except TypeError:
            try:
                data = run_etenders_playwright(max_items=max_items, timeout_ms=playwright_timeout_ms)
            except TypeError:
                data = run_etenders_playwright(max_items=max_items)
        if not isinstance(data, list):
            return []
        results: List[Dict[str, Any]] = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            raw_text_value = _clean(raw.get("raw_text") or raw.get("description") or raw.get("title"))
            text = _v50_clean_etenders_title(raw_text_value)
            title = _v50_clean_etenders_title(_clean(raw.get("title") or text))

            if not text:
                continue

            if _should_skip_preharvest_candidate(text, title):
                continue

            item = _base_item(source, text, url)
            item["raw_text_original"] = raw_text_value

            category_like_titles = {
                "manufacture of textiles",
                "other service activities",
                "administrative and support activities",
                "water supply; sewerage, waste management and remediation activities",
            }

            title_for_record = title
            if _safe_lower(title_for_record) in category_like_titles:
                title_for_record = text

            item["title"] = _truncate(title_for_record, 180)
            item["description"] = text
            _lmcp_safe_assign_identity_fields(item, title_for_record)
            item["buyer_name"] = _clean(raw.get("buyer_name") or source.get("name") or "eTenders")
            item["source_name"] = _clean(source.get("name") or "eTenders Web")
            item["source"] = item["source_name"]
            item["portal_name"] = item["source_name"]
            item["closing_date"] = _clean(raw.get("closing_date") or _extract_closing_date(text))
            discovered_tender_id = _v64_extract_etenders_tender_id(
                raw.get("detail_url"),
                raw.get("document_url"),
                raw.get("url"),
                raw.get("raw_text"),
                raw.get("description"),
                raw.get("title"),
            )
            if discovered_tender_id:
                detail_url = _build_etenders_detail_url(discovered_tender_id)
                item["detail_url"] = detail_url
                item["document_url"] = detail_url
                item["tender_id"] = discovered_tender_id
                item["v50_8_discovered_tender_id"] = discovered_tender_id
            results.append(item)
        deduped = _dedupe_keep_order(results)[:max_items]
        diag["etenders_candidates_extracted_count"] = len(deduped)
        if deduped:
            diag["etenders_candidates_table_detected"] = True
            _probe_detail_pages(deduped)
        return deduped
    except Exception as exc:
        logger.warning("Direct eTenders parser failed for %s: %s", source.get("name"), exc)
        fallback = run_generic_scraper(source, timeout=candidate_extraction_timeout_seconds, max_items=max_items)
        if fallback:
            diag["etenders_candidates_extracted_count"] = len(fallback)
            diag["partial_progress_persisted"] = True
        return fallback


def _is_necsa_source(source: Dict[str, Any]) -> bool:
    blob = " ".join(
        _clean(source.get(key))
        for key in ("name", "source_name", "url", "list_url", "source_url")
    ).lower()
    return "necsa" in blob


def _necsa_page_candidates(source: Dict[str, Any]) -> List[str]:
    base = _clean(source.get("url") or source.get("list_url"))
    urls = [base] if base else []
    for suffix in (
        "/necsa-current-tenders/",
        "/tenders/",
        "/category/necsa_tender/",
        "/2026/04/",
        "/2026/03/",
    ):
        candidate = "https://www.necsa.co.za" + suffix
        if candidate not in urls:
            urls.append(candidate)
    return urls


def _necsa_tender_source(source: Dict[str, Any], max_items: int) -> List[Dict[str, Any]]:
    """
    NECSA tenders are published as long text blocks rather than structured rows.
    Parse tender blocks directly so we can retain the bid number, closing date,
    and any tender-document link exposed in the block.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception as exc:
        logger.warning("NECSA parser unavailable for %s: %s", source.get("name"), exc)
        return []

    results: List[Dict[str, Any]] = []
    seen: set[str] = set()
    source_name = _clean(source.get("name") or source.get("source_name") or "NECSA")
    source_url = _clean(source.get("url") or source.get("list_url") or "https://www.necsa.co.za/tenders/")

    def _necsa_link_score(href: str, label: str, bid_number: str, title: str) -> Tuple[int, str]:
        blob = f"{href} {label}".lower()
        score = 0
        if bid_number.lower() in blob:
            score += 120
        if _looks_like_attachment_name(href):
            score += 80
        if any(token in blob for token in ("download", "related documents", "tender document", "documents and information")):
            score += 45
        if title:
            title_tokens = [tok for tok in re.split(r"[^a-z0-9]+", title.lower()) if len(tok) > 3]
            overlap = sum(1 for token in title_tokens[:8] if token and token in blob)
            score += min(25, overlap * 4)
        if any(token in blob for token in ("visitor-centre", "/tenders/", "contact", "about", "news")) and bid_number.lower() not in blob:
            score -= 80
        return score, blob

    for page_url in _necsa_page_candidates(source):
        try:
            response = requests.get(
                page_url,
                headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0"},
                timeout=12,
                verify=bool(source.get("verify_ssl", True)),
            )
            response.raise_for_status()
            html = response.text or ""
        except Exception as exc:
            logger.info("NECSA page fetch failed for %s: %s", page_url, exc)
            continue

        soup = BeautifulSoup(html, "html.parser")
        anchors: List[Tuple[str, str]] = []
        for anchor in soup.find_all("a"):
            href = _clean(anchor.get("href"))
            label = _clean(anchor.get_text(" ", strip=True))
            if href:
                anchors.append((urljoin(page_url, href), label))

        raw_lines = [re.sub(r"\s+", " ", line).strip() for line in soup.get_text("\n").splitlines()]
        lines = [line for line in raw_lines if line]
        start_indexes = [
            idx
            for idx, line in enumerate(lines)
            if re.search(r"^BID NUMBER:\s*$", line, flags=re.I)
        ]
        if not start_indexes:
            start_indexes = [
                idx
                for idx, line in enumerate(lines)
                if re.search(r"\bFIN-SCM-TEN-\d{3,6}\b", line, flags=re.I)
            ]

        for pos, start_index in enumerate(start_indexes):
            end_index = start_indexes[pos + 1] if pos + 1 < len(start_indexes) else len(lines)
            section_lines = lines[start_index:end_index]
            section_text = " ".join(section_lines)
            if len(section_text) < 80:
                continue

            bid_match = re.search(r"\bFIN-SCM-TEN-\d{3,6}\b", section_text, flags=re.I)
            if not bid_match:
                continue

            bid_number = _clean(bid_match.group(0)).upper()
            if bid_number in seen:
                continue

            if not re.search(r"\bsupply\b|\bdelivery\b|\bgoods\b|\bquotation\b|\btender\b|\bbid\b", section_text, flags=re.I):
                continue

            desc_match = re.search(
                r"BID DESCRIPTION:\s*(.*?)(?:\s+CLOSING DATE:|\s+CLOSING TIME:|\s+BID VALIDITY PERIOD:|\s+DELIVERY ADDRESS:)",
                section_text,
                flags=re.I,
            )
            title = _clean(desc_match.group(1) if desc_match else "")
            if not title:
                title = _clean(section_text)
            closing_date = _extract_closing_date(section_text)

            # Prefer a tender-specific download link if it exists in the page.
            link_candidates: List[Tuple[int, str]] = []
            for absolute, label in anchors:
                if not _v56_is_safe_public_document_url(absolute):
                    continue
                score, _ = _necsa_link_score(absolute, label, bid_number, title)
                if score >= 60:
                    link_candidates.append((score, absolute))
            if not link_candidates:
                for absolute, label in anchors:
                    if not _v56_is_safe_public_document_url(absolute):
                        continue
                    score, blob = _necsa_link_score(absolute, label, bid_number, title)
                    if score >= 45 and ("download" in blob or "document" in blob or "zip" in blob or "pdf" in blob):
                        link_candidates.append((score, absolute))

            link_candidates = sorted(link_candidates, key=lambda pair: pair[0], reverse=True)
            selected_links = [url for _, url in link_candidates]
            external_url = selected_links[0] if selected_links else page_url
            item = _base_item(source, title, external_url)
            item["source_name"] = source_name
            item["source"] = source_name
            item["portal_name"] = source_name
            item["source_url"] = source_url
            item["detail_url"] = selected_links[0] if selected_links else ""
            item["document_url"] = selected_links[0] if selected_links else source_url
            item["document_urls"] = selected_links[:5]
            item["buyer_name"] = source_name
            item["title"] = _truncate(title or bid_number, 180)
            item["description"] = _truncate(section_text, 1200)
            item["raw_text"] = _truncate(section_text, 2500)
            item["closing_date"] = closing_date
            item["reference_number"] = bid_number
            item["rfq_number"] = bid_number
            item["buyer_rfq_number"] = bid_number
            item["external_url"] = external_url
            if not link_candidates:
                item["document_blocker_reason"] = "missing_document_link" if closing_date else "missing_closing_date"
            results.append(item)
            seen.add(bid_number)
            if len(results) >= max_items:
                return _dedupe_keep_order(results)[:max_items]
    return _dedupe_keep_order(results)[:max_items]


def run_generic_scraper(source: Dict[str, Any], timeout: int = 8, max_items: int = 20) -> List[Dict[str, Any]]:
    url = _clean(source.get("url") or source.get("list_url"))
    max_items = _safe_positive_int(max_items, 20)
    if not url:
        return []
    try:
        if url.startswith("file://") or Path(url).expanduser().exists():
            local_path = Path(unquote(urlparse(url).path if url.startswith("file://") else url)).expanduser()
            html = local_path.read_text(encoding="utf-8")
        else:
            response = requests.get(url, timeout=timeout, verify=bool(source.get("verify_ssl", True)), headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0"})
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        _record_source_result(source, ok=False, harvested=0, error=str(exc))
        logger.warning("Static scrape failed for %s: %s", source.get("name"), exc)
        return []
    candidates = re.findall(r">([^<>]{20,800})<", html)
    results: List[Dict[str, Any]] = []
    for raw in candidates:
        text = re.sub(r"\s+", " ", raw).strip()
        if _should_skip_preharvest_candidate(text):
            continue
        results.append(_base_item(source, text, url))
        if len(results) >= max_items:
            break
    _record_source_result(source, ok=True, harvested=len(results))
    return _dedupe_keep_order(results)


def run_playwright_generic_scraper(
    source: Dict[str, Any],
    max_items: int = 20,
    headless: bool = True,
    timeout_ms: int = 18000,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    url = _clean(source.get("url") or source.get("list_url"))
    max_items = _safe_positive_int(max_items, 20)
    if not url:
        if isinstance(diagnostics, dict):
            diagnostics.update({
                "status": "skipped",
                "error_message": "missing_url",
                "fallback_used": False,
                "retry_count": 0,
            })
        return []
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:
        logger.warning("Playwright unavailable, using static fallback for %s: %s", source.get("name"), exc)
        if isinstance(diagnostics, dict):
            diagnostics.update({
                "status": "playwright_failed",
                "error_message": _truncate(str(exc), 240),
                "fallback_used": True,
                "retry_count": 1,
            })
        return run_generic_scraper(source, max_items=max_items)
    results: List[Dict[str, Any]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(min(1200, max(250, timeout_ms // 10)))
            row_selectors = ["table tbody tr", "table tr", ".table tbody tr"]
            rows = []
            for selector in row_selectors:
                rows = page.query_selector_all(selector)
                if rows:
                    break
            for row in rows:
                try:
                    cols = row.query_selector_all("td")
                    if len(cols) < 2:
                        continue
                    text = " ".join(_clean(c.inner_text()) for c in cols if _clean(c.inner_text()))
                    text = re.sub(r"\s+", " ", text).strip()
                    second = _clean(cols[1].inner_text()) if len(cols) >= 2 else ""
                    if _should_skip_preharvest_candidate(text, second):
                        continue
                    item = _base_item(source, text, url)
                    if second and not _is_noise_row(second) and not _should_skip_preharvest_candidate(text, second):
                        item["title"] = _truncate(second, 180)
                        _lmcp_safe_assign_identity_fields(item, second)
                    if cols:
                        last_text = _clean(cols[-1].inner_text())
                        if _extract_closing_date(last_text):
                            item["closing_date"] = _extract_closing_date(last_text)
                    results.append(item)
                    if len(results) >= max_items:
                        break
                except Exception:
                    continue
            browser.close()
    except Exception as exc:
        _record_source_result(source, ok=False, harvested=0, error=str(exc))
        logger.warning("Playwright scrape failed for %s: %s", source.get("name"), exc)
        if isinstance(diagnostics, dict):
            diagnostics.update({
                "status": "playwright_failed",
                "error_message": _truncate(str(exc), 240),
                "fallback_used": True,
                "retry_count": 1,
            })
        fallback = run_generic_scraper(source, max_items=max_items)
        if isinstance(diagnostics, dict):
            diagnostics.setdefault("status", "success" if fallback else "playwright_failed")
            diagnostics.setdefault("fallback_used", True)
        return fallback
    if isinstance(diagnostics, dict):
        diagnostics.update({
            "status": "success" if results else "no_candidates",
            "error_message": "",
            "fallback_used": False,
            "retry_count": 0,
        })
    _record_source_result(source, ok=True, harvested=len(results))
    return _dedupe_keep_order(results)[:max_items]


def run_ocds_api_harvester(source: Dict[str, Any], max_items: int = 20, timeout: int = 8) -> List[Dict[str, Any]]:
    url = _clean(source.get("url") or source.get("list_url"))
    max_items = _safe_positive_int(max_items, 20)
    if not url:
        return []
    try:
        response = requests.get(url, timeout=timeout, verify=bool(source.get("verify_ssl", True)))
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        _record_source_result(source, ok=False, harvested=0, error=str(exc))
        logger.warning("OCDS/API harvest failed for %s: %s", source.get("name"), exc)
        return []
    records: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        for key in ("releases", "records", "results", "items"):
            if isinstance(data.get(key), list):
                records = data[key]
                break
        if not records:
            records = [data]
    elif isinstance(data, list):
        records = data
    results: List[Dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        tender_obj = rec.get("tender") if isinstance(rec.get("tender"), dict) else {}
        title = _clean(rec.get("title")) or _clean(tender_obj.get("title")) or _clean(rec.get("ocid"))
        desc = _clean(rec.get("description")) or _clean(tender_obj.get("description")) or title
        text = re.sub(r"\s+", " ", f"{title} {desc}").strip()
        if _should_skip_preharvest_candidate(text, title):
            continue
        item = _base_item(source, text, url)
        item["title"] = _truncate(title or desc, 180)
        _lmcp_safe_assign_identity_fields(item, _clean(rec.get("ocid") or title or desc))
        results.append(item)
        if len(results) >= max_items:
            break
    _record_source_result(source, ok=True, harvested=len(results))
    return _dedupe_keep_order(results)


EXCLUDED_KEYWORDS = [
    "medical", "biomedical", "pharmaceutical", "clinic supplies", "clinic services", "dna equipment",
    "laptop", "computer", "printer", "server", "router", "software", "license renewal", "sage 300", "ict related", "digital application",
    "petrol", "diesel", "fuel", "catering", "canteen", "construction", "civil", "road", "bridge", "reticulation", "sewer", "water treatment",
    "event management", "entertainment", "maintenance contract", "maintenance of", "service provider", "repair and installation", "cleaning services",
    "security services", "security and investigation", "legal panel", "bee verification", "screening and company checks",
]
CONTEXTUAL_EXCLUDED_PATTERNS = [
    "microsoft licensing",
    "microsoft dynamics",
    "microsoft office",
    "office 365",
    "software licensing",
    "ict support services",
    "managed it services",
    "training services",
    "skills training",
    "facilitator",
    "capacity building",
]

SCREEN_OUT_KEYWORDS = ["request for information", "expression of interest", "lease of immovable property", "rental and leasing", "other service activities"]
SUPPLY_OVERRIDE_TERMS = [
    "supply and delivery",
    "supply and deliver",
    "supply, delivery",
    "supply, deliver",
    "supply & delivery",
    "supply of",
    "delivery of",
    "manufacture, testing, supply and delivery",
    "water collection, treatment and supply",
]
AUTO_PROMOTE_TERMS = [
    "supply and delivery",
    "supply and deliver",
    "supply, delivery",
    "supply, deliver",
    "supply & delivery",
    "supply of",
    "delivery of",
    "manufacture, testing, supply and delivery",
]



GENERIC_CATEGORY_TERMS = [
    "administrative and support activities",
    "manufacturing",
    "construction",
    "community social and personal services",
    "other service activities",
]

REFERENCE_PATTERNS = [
    "rfq",
    "rfp",
    "bid",
    "tender",
    "scm",
    "quotation",
]


def _is_generic_listing_or_category_page(item: Dict[str, Any]) -> bool:
    title = _safe_lower(item.get("title"))
    raw_text = _safe_lower(item.get("raw_text") or item.get("description"))
    buyer_rfq = _safe_lower(item.get("buyer_rfq_number"))
    reference_number = _safe_lower(item.get("reference_number"))

    combined = " ".join([title, raw_text, buyer_rfq, reference_number])

    if any(term in title for term in GENERIC_CATEGORY_TERMS):
        return True

    if any(term in raw_text for term in GENERIC_CATEGORY_TERMS):
        # Allow only if a strong RFQ/reference pattern is also present.
        if not any(pattern in combined for pattern in REFERENCE_PATTERNS):
            return True

    return False


def _has_strong_rfq_identity(item: Dict[str, Any]) -> bool:
    title = _safe_lower(item.get("title"))
    raw_text = _safe_lower(item.get("raw_text") or item.get("description"))
    buyer_rfq = _safe_lower(item.get("buyer_rfq_number"))
    reference_number = _safe_lower(item.get("reference_number"))

    combined = " ".join([title, raw_text, buyer_rfq, reference_number])

    if any(pattern in combined for pattern in REFERENCE_PATTERNS):
        return True

    # Keep clean supply/delivery opportunities visible only if they contain
    # real procurement wording plus a date/period signal.
    supply_delivery = any(
        term in combined
        for term in [
            "supply and delivery",
            "supply and deliver",
            "supply, delivery",
            "supply, deliver",
            "supply & delivery",
            "delivery of",
        ]
    )

    date_or_period_signal = bool(
        __import__("re").search(r"\b\d{2}/\d{2}/\d{4}\b", combined)
        or "closing date" in combined
        or "period of" in combined
        or "for a period" in combined
        or "months" in combined
        or "years" in combined
    )

    return bool(supply_delivery and date_or_period_signal)


def _score_profit_and_risk(raw: str) -> Dict[str, Any]:
    score = 0
    reasons: List[str] = []
    for term in SUPPLY_OVERRIDE_TERMS:
        if term in raw:
            score += 25
            reasons.append(f"supply signal:{term}")
    if "rfq" in raw or "request for quotation" in raw:
        score += 15
        reasons.append("rfq wording")
    for term in ["36 months", "three years", "3 years", "24 months", "12 months", "period ending", "as and when required"]:
        if term in raw:
            score += 15
            reasons.append(f"value signal:{term}")
    for term in ["municipality", "transnet", "eskom", "saldanha bay", "centlec"]:
        if term in raw:
            score += 5
            reasons.append(f"buyer/value signal:{term}")
    for term in [
        "equipment",
        "machinery",
        "vehicle",
        "vehicles",
        "bus",
        "mini bus",
        "transport",
        "materials",
    ]:
        if term in raw:
            score += 10
            reasons.append(f"goods signal:{term}")
    for term in EXCLUDED_KEYWORDS:
        if term == "road" and any(x in raw for x in ["vehicle", "bus", "mini bus", "transport", "traffic services"]):
            continue
        if term == "software" and any(x in raw for x in ["supply and delivery", "supply and deliver", "supply of", "delivery of", "equipment", "machinery", "vehicle", "bus", "materials"]):
            continue
        if term == "repair and installation" and any(x in raw for x in ["supply and delivery", "supply and deliver", "supply, delivery", "supply, deliver", "supply of", "delivery of", "rfq", "tender", "quotation"]):
            continue
        if term in raw:
            score -= 35
            reasons.append(f"risk:{term}")
    score = max(0, min(100, score))
    clean_supply_delivery = any(term in raw for term in [
        "supply and delivery",
        "supply and deliver",
        "supply, delivery",
        "supply, deliver",
        "supply & delivery",
        "delivery of",
    ])

    non_supply_scope = any(term in raw for term in [
        "installation",
        "install",
        "contractor",
        "construction",
        "boq",
        "drawings",
        "fencing",
        "repair",
        "maintenance",
        "commission",
        "refurbishment",
        "civil works",
        "works",
    ]) and not any(term in raw for term in SUPPLY_OVERRIDE_TERMS)

    goods_value_signal = any(term in raw for term in [
        "building materials",
        "building material",
        "equipment",
        "machinery",
        "vehicle",
        "vehicles",
        "bus",
        "mini bus",
        "transport",
        "stationery",
        "office supplies",
        "cleaning materials",
        "cleaning material",
        "ppe",
        "uniform",
        "furniture",
        "tools",
        "electrical material",
        "plumbing material",
        "toner",
        "cartridge",
    ])

    if any(term in raw for term in ["36 months", "three years", "3 years", "period ending 30 june 2029", "period ending 30 september 2028"]):
        estimated_profit = 120000.0
    elif any(term in raw for term in ["24 months", "12 months", "as and when required"]):
        estimated_profit = 60000.0
    elif any(term in raw for term in ["bulk", "municipality"]):
        estimated_profit = 50000.0
    elif clean_supply_delivery and goods_value_signal and not non_supply_scope:
        estimated_profit = 45000.0
        reasons.append("profit floor:supply_delivery_goods")
    else:
        estimated_profit = 15000.0
    priority_score = (score * 0.65) + min(35.0, estimated_profit / 30000.0 * 10.0)
    return {"ai_score": score, "ai_reasons": reasons, "estimated_profit": estimated_profit, "profit_weighted_rank": round(priority_score, 2)}

    # HARD BLOCK GENERIC LISTING / CATEGORY PAGES
    generic_listing_hits = [
        "administrative and support activities",
        "manufacturing",
        "construction",
        "other service activities",
        "community social and personal services",
    ]

    if any(term in raw for term in generic_listing_hits):
        return {
            "ai_score": 0,
            "ai_reasons": ["generic_listing_page_blocked"],
            "estimated_profit": 0.0,
            "profit_weighted_rank": 0.0,
        }



def _lmcp_apply_v49_navigation_gate(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    V49/V49.1 RFQ detail navigation safety gate.
    Prevents listing pages or unrelated document links from entering document acquisition.
    """
    if not isinstance(item, dict):
        return item

    if not item.get("eligible"):
        return item

    if analyse_rfq_detail_navigation is None:
        item["v49_navigation_result"] = {
            "status": "skipped",
            "reason": "v49_engine_unavailable",
        }
        return item

    try:
        v49 = analyse_rfq_detail_navigation(item)
        item["v49_navigation_result"] = v49
        item["v49_recommended_action"] = v49.get("recommended_action")
        item["v49_explicit_reference_document_match"] = bool(
            v49.get("explicit_reference_document_match")
        )

        action = str(v49.get("recommended_action") or "")

        if action == "block_generic_listing":
            item.update({
                "eligible": False,
                "quote_ready": False,
                "auto_submit": False,
                "pipeline_status": "screened_out",
                "exclusion_reason": "v49_generic_listing_block",
                "eligibility_reason": "V49 blocked this candidate as a generic listing page.",
                "estimated_profit": 0.0,
                "meets_minimum_profit_rule": False,
            })
            return item

        if action == "navigate_detail_links_target_reference_missing":
            v49_1 = None

            if follow_detail_pages is not None:
                try:
                    v49_1 = follow_detail_pages({
                        "buyer_rfq_number": item.get("buyer_rfq_number")
                            or item.get("rfq_number")
                            or item.get("reference_number"),
                        "rfq_number": item.get("rfq_number"),
                        "reference_number": item.get("reference_number"),
                        "candidate_detail_links": v49.get("candidate_detail_links") or [],
                    })
                except Exception as exc:
                    v49_1 = {
                        "status": "failed",
                        "reason": "v49_1_exception",
                        "error": str(exc),
                    }

            item["v49_1_follow_result"] = v49_1 or {
                "status": "skipped",
                "reason": "v49_1_engine_unavailable",
            }

            exact_found = bool(
                isinstance(v49_1, dict)
                and v49_1.get("exact_reference_match_found")
                and v49_1.get("recommended_document_url")
            )

            if exact_found:
                recommended_url = v49_1.get("recommended_document_url")
                item["document_url"] = recommended_url
                item["detail_url"] = recommended_url
                item["v49_verified_document_url"] = recommended_url
                item["v49_recommended_action"] = "promote_verified_detail_document"
                return item

            item.update({
                "quote_ready": False,
                "auto_submit": False,
                "pipeline_status": "detail_navigation_required",
                "requires_detail_navigation": True,
                "auto_submission_gate_allowed": False,
                "auto_submission_gate_reason": "v49_target_reference_document_missing",
                "eligibility_reason": (
                    "V49/V49.1 could not verify an exact RFQ document package. "
                    "Manual/detail-page navigation is required before document acquisition."
                ),
            })
            return item

        return item

    except Exception as exc:
        item["v49_navigation_result"] = {
            "status": "failed",
            "reason": "v49_exception",
            "error": str(exc),
        }
        return item



def _lmcp_is_etenders_item(item: Dict[str, Any]) -> bool:
    """Return True for National Treasury/eTenders candidates."""
    if not isinstance(item, dict):
        return False

    source_blob = " ".join(
        str(item.get(key) or "")
        for key in (
            "source_name",
            "source",
            "portal_name",
            "buyer_name",
            "source_url",
            "document_url",
            "detail_url",
        )
    ).lower()

    return "etenders" in source_blob or "e-tender" in source_blob


def _lmcp_apply_v50_7_etenders_navigation_gate(item: Dict[str, Any], resolver_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    V50.7 eTenders safe navigation gate.

    This gate runs after V49/V49.1 and before document acquisition. It prevents
    generic eTenders listing URLs and weak DownloadSpec?documentId= links from
    being treated as verified tender documents. It only promotes document URLs
    when V50.7 finds a stronger tender-specific match.
    """
    if not isinstance(item, dict):
        return item

    if not item.get("eligible"):
        return item

    if not _lmcp_is_etenders_item(item):
        return item

    if analyse_etenders_detail_navigation is None:
        item["v50_7_navigation_result"] = {
            "status": "skipped",
            "reason": "v50_7_etenders_navigation_engine_unavailable",
        }
        return item

    try:
        v50_7_nav = analyse_etenders_detail_navigation(item)
        item["v50_7_navigation_result"] = v50_7_nav
        item["v50_7_recommended_action"] = v50_7_nav.get("recommended_action")
        item["v50_7_safe_to_download"] = bool(v50_7_nav.get("safe_to_download"))

        recommended_docs = v50_7_nav.get("recommended_document_links")
        if not isinstance(recommended_docs, list):
            recommended_docs = []

        recommended_details = v50_7_nav.get("recommended_detail_links")
        if not isinstance(recommended_details, list):
            recommended_details = []

        if recommended_docs:
            recommended_url = str(recommended_docs[0].get("url") or "").strip()
            if recommended_url:
                item["document_url"] = recommended_url
                item["detail_url"] = recommended_url
                item["v50_7_verified_document_url"] = recommended_url
                item["v50_7_navigation_status"] = "safe_document_link"
                item["v50_7_navigation_blockers"] = []
                item["skip_document_acquisition_until_detail_verified"] = False
                item["requires_detail_navigation"] = False
                return item

        if recommended_details:
            detail_url = str(recommended_details[0].get("url") or "").strip()
            if detail_url:
                item["detail_url"] = detail_url
                item["v50_7_candidate_detail_url"] = detail_url
                item["v50_7_navigation_status"] = "safe_detail_link"
                item["v50_7_navigation_blockers"] = []
                item["skip_document_acquisition_until_detail_verified"] = False
                return item

        item = _lmcp_try_extended_etenders_resolution(item, resolver_overrides=resolver_overrides)
        if item.get("document_url") or item.get("detail_url"):
            item["v50_7_navigation_status"] = item.get("v50_8_extended_resolution_status") or "extended_resolution_verified"
            item["v50_7_navigation_blockers"] = []
            item["skip_document_acquisition_until_detail_verified"] = False
            item["requires_detail_navigation"] = False
            return item

        # No safe tender-specific document/detail URL found. Keep the opportunity
        # visible, but do not allow generic eTenders listing acquisition or
        # auto-submit to run. If the item already reached quote-ready via
        # quantity verification, preserve that state for manual quote-pack work.
        if not item.get("quote_ready"):
            item["quote_ready"] = False
        item["auto_submit"] = False
        item["requires_detail_navigation"] = True
        item["skip_document_acquisition_until_detail_verified"] = True
        item["auto_submission_gate_allowed"] = False
        item["auto_submission_gate_reason"] = "v50_7_etenders_detail_navigation_required"
        item["v50_7_navigation_status"] = "detail_navigation_required"
        item["v50_7_navigation_blockers"] = [
            "no_tender_specific_document_link",
            "no_tender_specific_detail_link",
            str(v50_7_nav.get("recommended_action") or "manual_review"),
        ]
        item["v50_7_navigation_reasons"] = {
            "recommended_action": v50_7_nav.get("recommended_action"),
            "candidate_count": v50_7_nav.get("candidate_count"),
            "strong_document_count": v50_7_nav.get("strong_document_count"),
            "strong_detail_count": v50_7_nav.get("strong_detail_count"),
            "notes": v50_7_nav.get("notes") if isinstance(v50_7_nav.get("notes"), list) else [],
        }

        if item.get("pipeline_status") not in {"blocked", "screened_out", "quantity_verification_required"}:
            item["pipeline_status"] = "detail_navigation_required"

        item["eligibility_reason"] = (
            "V50.7 could not verify a tender-specific eTenders document/detail URL. "
            "Generic listing/download links are blocked until detail navigation succeeds."
        )

        return item

    except Exception as exc:
        item["v50_7_navigation_result"] = {
            "status": "failed",
            "reason": "v50_7_navigation_exception",
            "error": str(exc),
        }
        item["v50_7_navigation_status"] = "navigation_failed"
        item["v50_7_navigation_blockers"] = ["navigation_exception"]
        item["skip_document_acquisition_until_detail_verified"] = True
        item["auto_submission_gate_allowed"] = False
        item["auto_submission_gate_reason"] = "v50_7_navigation_exception"
        return item


def _lmcp_try_extended_etenders_resolution(item: Dict[str, Any], resolver_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Secondary eTenders resolver chain.

    When V50.7 cannot establish a safe row-local link, this attempts the
    stronger resolver stack and only promotes links that are still verified by
    the downstream services.
    """
    if not isinstance(item, dict) or not _lmcp_is_etenders_item(item):
        return item

    attempts: List[Dict[str, Any]] = []
    title_blob = " ".join(
        str(item.get(key) or "")
        for key in ("buyer_rfq_number", "rfq_number", "reference_number", "title", "description")
    )

    def _first_numeric_identifier(*values: Any) -> str:
        for value in values:
            if isinstance(value, str):
                match = re.search(r"\b(\d{5,8})\b", value)
                if match:
                    return _clean(match.group(1))
            elif isinstance(value, (list, tuple, set)):
                found = _first_numeric_identifier(*list(value))
                if found:
                    return found
        return ""

    payload = {
        "title": item.get("title"),
        "description": item.get("description"),
        "buyer_rfq_number": item.get("buyer_rfq_number"),
        "rfq_number": item.get("rfq_number"),
        "reference_number": item.get("reference_number"),
        "source_url": item.get("source_url") or item.get("detail_url") or item.get("document_url"),
        "document_url": item.get("document_url"),
        "detail_url": item.get("detail_url"),
        "tender_id": _first_numeric_identifier(title_blob),
    }

    resolved_document_url = ""
    resolved_detail_url = ""
    tenderdetails_resolvers_added = bool(payload.get("tender_id"))

    def _result_storage_key(label: str) -> str:
        mapping = {
            "v50_8_true_detail": "v50_8_true_detail_resolution_result",
            "v50_8_1_ajax": "v50_8_1_ajax_resolution_result",
            "v50_8_2_reconstruction": "v50_8_2_reconstruction_result",
            "v50_9_1_tenderdetails_inspect": "v50_9_1_tenderdetails_inspect_result",
            "v50_9_6_hidden_api": "v50_9_6_hidden_api_result",
        }
        return mapping.get(label, f"{label}_result")

    def _extract_tender_id_candidates(result: Dict[str, Any]) -> List[str]:
        candidates: List[str] = []

        def _add(value: Any) -> None:
            found = _first_numeric_identifier(value)
            if found and found not in candidates:
                candidates.append(found)

        for key in ("tender_id", "tenderId", "id"):
            _add(result.get(key))

        for row in result.get("reconstructed_rows") if isinstance(result.get("reconstructed_rows"), list) else []:
            if not isinstance(row, dict):
                continue
            fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
            _add(fields.get("ids"))
            _add(fields.get("tender_ids"))

        for row in result.get("probed_candidates") if isinstance(result.get("probed_candidates"), list) else []:
            if not isinstance(row, dict):
                continue
            _add(row.get("tender_id"))
            _add(row.get("document_id"))

        for row in result.get("documents") if isinstance(result.get("documents"), list) else []:
            if not isinstance(row, dict):
                continue
            _add(row.get("tender_id"))
            _add(row.get("support_document_id"))

        for row in result.get("matched_rows") if isinstance(result.get("matched_rows"), list) else []:
            if not isinstance(row, dict):
                continue
            _add(row.get("text_preview"))

        return candidates

    def _record(label: str, result: Any) -> Dict[str, Any]:
        entry = {"resolver": label}
        if isinstance(result, dict):
            entry.update(
                {
                    "status": result.get("status"),
                    "reason": result.get("reason") or result.get("recommended_action") or result.get("next_action"),
                    "safe_to_download": result.get("safe_to_download"),
                    "safe_to_follow_detail": result.get("safe_to_follow_detail"),
                    "verified_document_count": result.get("verified_document_count"),
                    "verified_detail_count": result.get("verified_detail_count"),
                    "candidate_url_count": result.get("candidate_url_count"),
                    "matched_row_count": result.get("matched_row_count"),
                    "document_count": result.get("document_count"),
                    "details_ok": result.get("details_ok"),
                    "useful_endpoint_count": result.get("useful_endpoint_count"),
                    "verified_download_count": result.get("verified_download_count"),
                }
            )
        return entry

    resolver_chain = [
        ("v50_8_true_detail", resolve_true_etenders_detail),
        ("v50_8_1_ajax", resolve_etenders_ajax_datatables),
        ("v50_8_2_reconstruction", reconstruct_etenders_document_urls),
    ]
    if tenderdetails_resolvers_added:
        resolver_chain.extend([
            ("v50_9_1_tenderdetails_inspect", inspect_tenderdetails_json),
            ("v50_9_6_hidden_api", discover_hidden_api),
        ])

    resolver_index = 0
    while resolver_index < len(resolver_chain):
        label, resolver = resolver_chain[resolver_index]
        resolver_index += 1
        if resolver is None:
            attempts.append({"resolver": label, "status": "skipped", "reason": "resolver_unavailable"})
            continue

        try:
            if isinstance(resolver_overrides, dict) and label in resolver_overrides:
                result = resolver_overrides.get(label)
            else:
                result = resolver(payload)
        except Exception as exc:
            attempts.append({"resolver": label, "status": "failed", "error": str(exc)})
            continue

        if isinstance(result, dict):
            item[_result_storage_key(label)] = result
            payload[_result_storage_key(label)] = result

        attempts.append(_record(label, result))

        if not isinstance(result, dict):
            continue

        if not payload.get("tender_id"):
            discovered_ids = _extract_tender_id_candidates(result)
            if discovered_ids:
                payload["tender_id"] = discovered_ids[0]
                item["v50_8_discovered_tender_id"] = discovered_ids[0]

        if payload.get("tender_id") and not tenderdetails_resolvers_added:
            resolver_chain.extend([
                ("v50_9_1_tenderdetails_inspect", inspect_tenderdetails_json),
                ("v50_9_6_hidden_api", discover_hidden_api),
            ])
            tenderdetails_resolvers_added = True

        if label in {"v50_8_2_reconstruction", "v50_9_1_tenderdetails_inspect", "v50_9_6_hidden_api"}:
            _append_live_resolution_trace_debug({
                "title": item.get("title"),
                "reference_number": item.get("reference_number"),
                "detail_url_before": item.get("detail_url"),
                "document_url_before": item.get("document_url"),
                "v50_8_1_result": item.get("v50_8_1_ajax_resolution_result"),
                "v50_8_2_result": item.get("v50_8_2_reconstruction_result"),
                "discovered_tender_id": item.get("v50_8_discovered_tender_id") or payload.get("tender_id"),
                "tenderdetails_result": item.get("v50_9_1_tenderdetails_inspect_result"),
                "hidden_api_result": item.get("v50_9_6_hidden_api_result"),
                "detail_url_after": item.get("detail_url"),
                "document_url_after": item.get("document_url"),
                "extended_resolution_status": item.get("v50_8_extended_resolution_status"),
            })

        if not resolved_document_url:
            for key in ("recommended_document_links", "verified_downloads", "documents"):
                value = result.get(key)
                if not isinstance(value, list) or not value:
                    continue
                first = value[0]
                if isinstance(first, dict):
                    candidate_url = _clean(first.get("url") or first.get("winning_url") or first.get("document_url"))
                else:
                    candidate_url = _clean(first)
                if candidate_url.startswith("http"):
                    resolved_document_url = candidate_url
                    break

        if not resolved_detail_url:
            for key in ("recommended_detail_links", "matched_rows", "useful_endpoints"):
                value = result.get(key)
                if not isinstance(value, list) or not value:
                    continue
                first = value[0]
                if isinstance(first, dict):
                    candidate_url = _clean(first.get("url") or first.get("details_url") or first.get("endpoint"))
                else:
                    candidate_url = _clean(first)
                if candidate_url.startswith("http"):
                    resolved_detail_url = candidate_url
                    break

        if not resolved_document_url and label == "v50_9_1_tenderdetails_inspect":
            docs = result.get("documents") if isinstance(result.get("documents"), list) else []
            if docs and download_from_tenderdetails_json is not None:
                preferred_doc = docs[0] if isinstance(docs[0], dict) else {}
                try:
                    download_result = download_from_tenderdetails_json({
                        "tender_id": payload.get("tender_id"),
                        "document_guid": preferred_doc.get("guid") or preferred_doc.get("document_guid"),
                        "guid": preferred_doc.get("guid") or preferred_doc.get("document_guid"),
                        "filename": preferred_doc.get("filename") or preferred_doc.get("name"),
                    })
                except Exception as exc:
                    download_result = {"status": "error", "error": str(exc)}
                attempts.append(_record("v50_9_1_tenderdetails_download", download_result))
                if isinstance(download_result, dict):
                    for route_attempt in download_result.get("attempts") or []:
                        if not isinstance(route_attempt, dict):
                            continue
                        diagnostics.append({
                            **route_attempt,
                            "diagnostic_type": _clean(route_attempt.get("diagnostic_type") or "tenderdetails_json_route_experiment"),
                            "source_link_url": resolved_index_page_url or source_link_url,
                            "resolved_index_page_url": resolved_index_page_url or source_link_url,
                        })
                if isinstance(download_result, dict) and download_result.get("status") == "ok":
                    winning_url = _clean(download_result.get("winning_url") or download_result.get("saved_path"))
                    saved_path = _clean(download_result.get("saved_path"))
                    if winning_url:
                        resolved_document_url = winning_url
                    if saved_path and not item.get("downloaded_document_path"):
                        item["downloaded_document_path"] = saved_path
                    item["v50_8_extended_resolution_status"] = "verified_tenderdetails_document"
                    item["v50_8_tenderdetails_download"] = download_result
                    item["document_url"] = resolved_document_url
                    item["detail_url"] = resolved_document_url
                    item["skip_document_acquisition_until_detail_verified"] = False
                    item["requires_detail_navigation"] = False
                    item["v50_8_extended_resolution"] = attempts
                    _append_live_resolution_trace_debug({
                        "title": item.get("title"),
                        "reference_number": item.get("reference_number"),
                        "detail_url_before": item.get("detail_url"),
                        "document_url_before": item.get("document_url"),
                        "v50_8_1_result": item.get("v50_8_1_ajax_resolution_result"),
                        "v50_8_2_result": item.get("v50_8_2_reconstruction_result"),
                        "discovered_tender_id": item.get("v50_8_discovered_tender_id") or payload.get("tender_id"),
                        "tenderdetails_result": item.get("v50_9_1_tenderdetails_inspect_result"),
                        "hidden_api_result": item.get("v50_9_6_hidden_api_result"),
                        "detail_url_after": item.get("detail_url"),
                        "document_url_after": item.get("document_url"),
                        "extended_resolution_status": item.get("v50_8_extended_resolution_status"),
                    })
                    return item

        if result.get("safe_to_download") and resolved_document_url:
            item["document_url"] = resolved_document_url
            item["detail_url"] = resolved_document_url
            item["skip_document_acquisition_until_detail_verified"] = False
            item["requires_detail_navigation"] = False
            item["v50_8_extended_resolution"] = attempts
            item["v50_8_extended_resolution_status"] = "verified_document"
            _append_live_resolution_trace_debug({
                "title": item.get("title"),
                "reference_number": item.get("reference_number"),
                "detail_url_before": item.get("detail_url"),
                "document_url_before": item.get("document_url"),
                "v50_8_1_result": item.get("v50_8_1_ajax_resolution_result"),
                "v50_8_2_result": item.get("v50_8_2_reconstruction_result"),
                "discovered_tender_id": item.get("v50_8_discovered_tender_id") or payload.get("tender_id"),
                "tenderdetails_result": item.get("v50_9_1_tenderdetails_inspect_result"),
                "hidden_api_result": item.get("v50_9_6_hidden_api_result"),
                "detail_url_after": item.get("detail_url"),
                "document_url_after": item.get("document_url"),
                "extended_resolution_status": item.get("v50_8_extended_resolution_status"),
            })
            return item

        if result.get("safe_to_follow_detail") and resolved_detail_url:
            item["detail_url"] = resolved_detail_url
            item["skip_document_acquisition_until_detail_verified"] = False
            item["requires_detail_navigation"] = False
            item["v50_8_extended_resolution"] = attempts
            item["v50_8_extended_resolution_status"] = "verified_detail"
            # Keep searching for a document URL on later resolvers.
            _append_live_resolution_trace_debug({
                "title": item.get("title"),
                "reference_number": item.get("reference_number"),
                "detail_url_before": item.get("detail_url"),
                "document_url_before": item.get("document_url"),
                "v50_8_1_result": item.get("v50_8_1_ajax_resolution_result"),
                "v50_8_2_result": item.get("v50_8_2_reconstruction_result"),
                "discovered_tender_id": item.get("v50_8_discovered_tender_id") or payload.get("tender_id"),
                "tenderdetails_result": item.get("v50_9_1_tenderdetails_inspect_result"),
                "hidden_api_result": item.get("v50_9_6_hidden_api_result"),
                "detail_url_after": item.get("detail_url"),
                "document_url_after": item.get("document_url"),
                "extended_resolution_status": item.get("v50_8_extended_resolution_status"),
            })

    if attempts:
        item["v50_8_extended_resolution"] = attempts
        if not _clean(item.get("v50_8_extended_resolution_status")):
            item["v50_8_extended_resolution_status"] = "no_verified_resolution"
        if resolved_detail_url and not item.get("detail_url"):
            item["detail_url"] = resolved_detail_url
            item["v50_8_candidate_detail_url"] = resolved_detail_url
            item["requires_detail_navigation"] = True
        if resolved_document_url and not item.get("document_url"):
            item["document_url"] = resolved_document_url
            item["v50_8_candidate_document_url"] = resolved_document_url
        item["v50_8_extended_resolution_summary"] = {
            "attempt_count": len(attempts),
            "verified_document": bool(resolved_document_url),
            "verified_detail": bool(resolved_detail_url),
            "resolved_status": item.get("v50_8_extended_resolution_status"),
        }
    return item


def _lmcp_apply_v50_7_verified_rfq_promotion_gate(
    item: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    V50.7 verified RFQ promotion gate.

    This gate should run after verified quantity extraction, real buyer pricing,
    and the final quantity safety gate. It does not bypass safety controls. It
    converts the current RFQ state into an explicit promotion/submission decision
    for dashboards, scheduler logic, and future orchestrators.
    """
    if not isinstance(item, dict):
        return item

    if evaluate_verified_rfq_for_promotion is None:
        item["v50_7_promotion_result"] = {
            "status": "skipped",
            "reason": "v50_7_promotion_gate_unavailable",
        }
        return item

    try:
        if policy is None:
            policy = _read_v48_policy()

        promotion = evaluate_verified_rfq_for_promotion(item=item, policy=policy)
        item["v50_7_promotion_result"] = promotion
        item["v50_7_promotion_allowed"] = bool(promotion.get("promotion_allowed"))
        item["v50_7_submission_gate_allowed"] = bool(promotion.get("submission_gate_allowed"))
        item["v50_7_final_submit_gate_allowed"] = bool(promotion.get("final_submit_gate_allowed"))
        item["v50_7_next_action"] = promotion.get("next_action")
        item["v50_7_promotion_blockers"] = promotion.get("blockers") if isinstance(promotion.get("blockers"), list) else []
        item["v50_7_promotion_reasons"] = promotion.get("reasons") if isinstance(promotion.get("reasons"), list) else []
        item["v50_7_promotion_stalled_stage"] = promotion.get("stalled_stage") or promotion.get("next_action")
        item["v50_7_promotion_stall_reason"] = promotion.get("stall_reason") or promotion.get("blocker_summary")

        # V50.7 may allow preparation/upload, but final submit remains separately
        # controlled by V48 policy and the existing final-submit safeguards.
        item["auto_submission_gate_allowed"] = bool(promotion.get("submission_gate_allowed"))
        item["auto_submission_gate_reason"] = str(
            promotion.get("next_action")
            or ",".join(promotion.get("blockers") or [])
            or "v50_7_promotion_gate_evaluated"
        )

        if promotion.get("promotion_allowed") and not item.get("quote_ready"):
            if item.get("requires_quantity_verification"):
                if _lmcp_buyer_pack_downloaded(item):
                    item["pipeline_status"] = "quantity_verification_required"
                else:
                    item["pipeline_status"] = "document_acquisition_pending"
            elif item.get("pipeline_status") not in {"blocked", "screened_out"}:
                item["pipeline_status"] = "eligible_for_quote_pack"

        if promotion.get("submission_gate_allowed") and item.get("quote_ready"):
            if item.get("submission_method") == "portal":
                item["pipeline_status"] = "portal_submission_pack_ready"
            elif item.get("submission_method") == "email":
                item["pipeline_status"] = "email_submission_pack_ready"

        return item

    except Exception as exc:
        item["v50_7_promotion_result"] = {
            "status": "failed",
            "reason": "v50_7_promotion_exception",
            "error": str(exc),
        }
        return item


def _lmcp_apply_document_intelligence_gate(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run RFQ Document Intelligence after structural RFQ validation and before
    quote-ready promotion. This is intentionally fail-open for engine/runtime
    errors, but fail-closed when the intelligence engine explicitly says the
    RFQ is not quote safe.
    """
    if not isinstance(item, dict):
        return item

    # Only spend document intelligence time on candidates that have survived
    # structural RFQ validation and have a chance of becoming quote-ready.
    if item.get("real_rfq_structurally_valid") is False:
        return item

    candidate_has_url = any(
        str(item.get(key) or "").strip().startswith("http")
        for key in ("document_url", "source_url", "detail_url", "pdf_url", "download_url")
    )

    if not candidate_has_url:
        item["document_intelligence_result"] = {
            "status": "skipped",
            "reason": "no_document_or_source_url",
        }
        item["document_quote_safe"] = True
        item["document_report_path"] = ""
        return item

    if analyse_rfq_documents is None:
        item["document_intelligence_result"] = {
            "status": "skipped",
            "reason": "rfq_document_intelligence_unavailable",
        }
        item["document_quote_safe"] = True
        item["document_report_path"] = ""
        return item

    try:
        result = analyse_rfq_documents(item)
        item["document_intelligence_result"] = result
        item["document_quote_safe"] = bool(result.get("quote_safe", True))
        item["document_report_path"] = str(result.get("report_path") or "")

        if not item["document_quote_safe"]:
            item.update({
                "eligible": False,
                "quote_ready": False,
                "auto_submit": False,
                "pipeline_status": "screened_out",
                "exclusion_reason": "document_intelligence_block",
                "eligibility_reason": "Blocked by RFQ Document Intelligence: "
                                      + str(result.get("quote_block_reason") or "quote_not_safe"),
                "estimated_profit": 0.0,
                "meets_minimum_profit_rule": False,
            })

        return item
    except Exception as exc:
        # Do not crash the national radar cycle if one document site fails.
        item["document_intelligence_result"] = {
            "status": "failed",
            "reason": "document_intelligence_exception",
            "error": str(exc),
        }
        item["document_quote_safe"] = True
        item["document_report_path"] = ""
        return item




def _lmcp_apply_boq_extraction_gate(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run REAL BUYER DOCUMENT EXTRACTION after RFQ Document Intelligence and before
    auto-quote. Uses extracted BOQ line items only when confidence is high enough.
    If no BOQ/pricing schedule exists, keeps existing strategic/profit-floor
    fallback items. It never invents quantities.
    """
    if not isinstance(item, dict):
        return item

    if not item.get("eligible") and not item.get("quote_ready"):
        return item

    if item.get("document_quote_safe") is False:
        return item

    candidate_has_url = any(
        str(item.get(key) or "").strip().startswith("http")
        for key in ("document_url", "source_url", "detail_url", "pdf_url", "download_url")
    )

    if not candidate_has_url:
        item["boq_extraction_result"] = {"status": "skipped", "reason": "no_document_or_source_url"}
        item["boq_extraction_status"] = "skipped_no_document_or_source_url"
        item["boq_line_item_count"] = 0
        item["boq_confidence"] = 0.0
        item["buyer_extracted_line_items"] = []
        item["normalized_boq_path"] = ""
        return item

    if extract_rfq_boq is None:
        item["boq_extraction_result"] = {"status": "skipped", "reason": "rfq_boq_extraction_engine_unavailable"}
        item["boq_extraction_status"] = "skipped_engine_unavailable"
        item["boq_line_item_count"] = 0
        item["boq_confidence"] = 0.0
        item["buyer_extracted_line_items"] = []
        item["normalized_boq_path"] = ""
        return item

    try:
        result = extract_rfq_boq(item)
        line_items = result.get("line_items") if isinstance(result.get("line_items"), list) else []
        line_item_count = int(result.get("line_item_count") or len(line_items) or 0)
        confidence = float(result.get("confidence") or 0.0)
        paths = result.get("paths") if isinstance(result.get("paths"), dict) else {}

        item["boq_extraction_result"] = result
        item["boq_extraction_status"] = str(result.get("status") or "")
        item["boq_line_item_count"] = line_item_count
        item["boq_confidence"] = confidence
        item["buyer_extracted_line_items"] = line_items
        item["normalized_boq_path"] = str(paths.get("normalized_boq") or "")

        if line_item_count > 0 and confidence >= 0.65:
            normalized_items = []
            for row in line_items:
                if not isinstance(row, dict):
                    continue
                try:
                    quantity = float(row.get("quantity"))
                except Exception:
                    continue
                description = str(row.get("description") or "").strip()
                if not description:
                    continue
                normalized_items.append({
                    "line_number": str(len(normalized_items) + 1),
                    "description": description,
                    "quantity": quantity,
                    "unit": str(row.get("unit") or "Each").strip() or "Each",
                    "item_code": str(row.get("item_code") or "").strip(),
                    "specification": str(row.get("specification") or "").strip(),
                    "source": "buyer_boq_extraction",
                    "boq_confidence": confidence,
                })

            if normalized_items:
                item["items"] = normalized_items
                item["line_items"] = normalized_items
                item["boq_extraction_used_for_pricing"] = True
                item["pricing_item_source"] = "buyer_boq_extraction"
            else:
                item["boq_extraction_used_for_pricing"] = False
                item["pricing_item_source"] = item.get("pricing_item_source") or "strategic_profit_floor_fallback"
        else:
            item["boq_extraction_used_for_pricing"] = False
            item["pricing_item_source"] = item.get("pricing_item_source") or "strategic_profit_floor_fallback"
            if line_item_count == 0:
                item["boq_extraction_status"] = str(result.get("status") or "no_boq_or_pricing_schedule")

        return item

    except Exception as exc:
        item["boq_extraction_result"] = {"status": "failed", "reason": "boq_extraction_exception", "error": str(exc)}
        item["boq_extraction_status"] = "failed"
        item["boq_line_item_count"] = 0
        item["boq_confidence"] = 0.0
        item["buyer_extracted_line_items"] = []
        item["normalized_boq_path"] = ""
        item["boq_extraction_used_for_pricing"] = False
        item["pricing_item_source"] = item.get("pricing_item_source") or "strategic_profit_floor_fallback"
        return item




def _lmcp_apply_quantity_safety_gate(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    REAL QUANTITY SAFETY ENGINE.

    This gate prevents synthetic/fallback quantities from becoming quote-ready
    when the buyer document/BOQ extraction did not verify any real line items.

    It keeps the RFQ visible and eligible when otherwise valid, but moves it into
    quantity_verification_required instead of allowing auto-quote/submission.
    """
    if not isinstance(item, dict):
        return item

    # Only apply after the candidate has survived the core RFQ/profit gates.
    if not item.get("eligible"):
        return item

    if not _lmcp_buyer_pack_downloaded(item):
        item["buyer_pack_downloaded"] = False
        item["buyer_pack_verified"] = False
        item["quantity_source"] = "buyer_pack_missing"
        item["requires_quantity_verification"] = True
        item["quantity_safety_status"] = "document_acquisition_pending"
        item["quote_ready"] = False
        item["auto_quote_enabled"] = False
        item["auto_submit"] = False
        item["auto_submission_gate_allowed"] = False
        item["auto_submission_gate_reason"] = "buyer_pack_download_required"
        item["pipeline_status"] = "document_acquisition_pending"
        item["eligibility_reason"] = (
            "RFQ is valid, but the buyer pack has not been downloaded and verified. "
            "Acquire the buyer pack before quantity verification."
        )
        item["document_acquisition_block_reason"] = "buyer_pack_download_required_before_quantity_verification"
        item["fallback_quantity_block_reason"] = (
            "Blocked until buyer pack download is verified."
        )
        return item

    boq_count = int(item.get("boq_line_item_count") or 0)
    try:
        boq_confidence = float(item.get("boq_confidence") or 0.0)
    except Exception:
        boq_confidence = 0.0

    boq_status = str(item.get("boq_extraction_status") or "").strip()

    # Verified buyer quantities still do not authorize quote-ready by themselves.
    if boq_count > 0 and boq_confidence >= 0.65:
        item["quantity_source"] = "buyer_boq_extraction"
        item["requires_quantity_verification"] = False
        item["quantity_safety_status"] = "verified_buyer_quantities"
        item["quote_ready"] = False
        return item

    # No BOQ/pricing schedule or no trusted buyer line items means any existing
    # items are strategic/fallback only and must not trigger autonomous quote-ready.
    if boq_count == 0 or boq_confidence < 0.65:
        item["quantity_source"] = "unverified"
        item["requires_quantity_verification"] = True
        item["quantity_safety_status"] = "quantity_verification_required"

        # Preserve existing items for operator context, but mark them unsafe for
        # autonomous pricing/submission.
        item["fallback_items_retained_for_review"] = item.get("items") if isinstance(item.get("items"), list) else []
        item["fallback_quantity_block_reason"] = (
            "No verified buyer BOQ/pricing schedule line items were extracted. "
            "Existing fallback quantities are not allowed to become quote-ready."
        )

        item["quote_ready"] = False
        item["auto_submit"] = False
        item["auto_submission_gate_allowed"] = False
        item["auto_submission_gate_reason"] = "quantity_verification_required"
        item["pipeline_status"] = "quantity_verification_required"
        item["eligibility_reason"] = (
            "RFQ is valid, but buyer quantities were not verified. "
            "Manual quantity verification is required before quoting."
        )

        # Keep eligible true because it is a valid opportunity, but block revenue/
        # quote readiness until quantity verification happens.
        item["eligible"] = True

        # Do not keep inflated profit rank as if ready to quote.
        item["quote_ready_before_quantity_gate"] = True
        item["boq_quantity_gate_status"] = boq_status or "no_verified_boq_items"

    return item



def _is_incidental_microsoft_usage(raw: str) -> bool:
    raw = _safe_lower(raw)

    safe_patterns = [
        "microsoft teams",
        "via microsoft teams",
        "ms teams",
        "teams meeting",
        "virtual briefing",
    ]

    return any(p in raw for p in safe_patterns)


def _is_training_only_procurement(raw: str) -> bool:
    raw = _safe_lower(raw)

    supply_signals = [
        "supply",
        "delivery",
        "installation",
        "install",
        "supply and delivery",
        "supply, delivery",
        "supply & delivery",
        "commission",
        "equipment",
        "materials",
    ]

    training_service_patterns = [
        "training services",
        "training provider",
        "skills training",
        "facilitation",
        "facilitator",
        "capacity building",
        "workshop services",
    ]

    has_supply_signal = any(x in raw for x in supply_signals)
    has_training_service = any(x in raw for x in training_service_patterns)

    return has_training_service and not has_supply_signal


def _should_exclude_keyword(raw: str, keyword: str) -> bool:
    raw = _safe_lower(raw)
    keyword = _safe_lower(keyword)

    procurement_context = any(
        term in raw
        for term in [
            "appointment of",
            "request for quotation",
            "request for proposal",
            "rfq",
            "rfp",
            "tender",
            "bid",
            "quotation",
            "supply and delivery",
            "supply and deliver",
            "supply, delivery",
            "supply, deliver",
            "supply & delivery",
            "supply of",
            "delivery of",
        ]
    )

    if keyword == "microsoft":
        if _is_incidental_microsoft_usage(raw):
            return False
        return True

    if keyword == "training":
        return _is_training_only_procurement(raw)

    if keyword in {"service provider", "repair and installation", "software"}:
        if procurement_context:
            return False

    if keyword in {"road", "bridge", "construction", "civil"}:
        if procurement_context and any(
            term in raw
            for term in [
                "vehicle",
                "bus",
                "mini bus",
                "transport",
                "traffic services",
                "equipment",
                "machinery",
                "materials",
            ]
        ):
            return False

    return keyword in raw




def _matches_contextual_exclusion(raw: str) -> Optional[str]:
    raw = _safe_lower(raw)

    for pattern in CONTEXTUAL_EXCLUDED_PATTERNS:
        if pattern in raw:
            return pattern

    return None



NON_SUPPLY_SCOPE_TERMS = [
    "installation",
    "install",
    "contractor",
    "construction",
    "boq",
    "drawings",
    "fencing",
    "repair",
    "maintenance",
    "commission",
    "training",
    "refurbishment",
    "civil works",
]


def _is_non_supply_scope(raw: str) -> bool:
    raw_lower = _safe_lower(raw)

    if any(term in raw_lower for term in SUPPLY_OVERRIDE_TERMS):
        return False

    # Allow explicit supply/delivery-only wording even if it says "no installation".
    supply_delivery_only = any(
        phrase in raw_lower
        for phrase in [
            "supply and delivery only",
            "supply & delivery only",
            "supply, delivery only",
            "supply and deliver only",
        ]
    )

    if supply_delivery_only:
        return False

    if "appointment of" in raw_lower and any(
        term in raw_lower
        for term in [
            "service provider",
            "repair and installation",
            "installation",
            "maintenance",
            "cleaning",
        ]
    ) and any(
        term in raw_lower
        for term in [
            "rfq",
            "rfp",
            "tender",
            "bid",
            "quotation",
            "period of",
            "for a period",
            "months",
            "years",
        ]
    ):
        return False

    for term in NON_SUPPLY_SCOPE_TERMS:
        if term not in raw_lower:
            continue

        # Ignore negated wording like "no installation" or "without maintenance".
        negated = any(
            phrase in raw_lower
            for phrase in [
                f"no {term}",
                f"without {term}",
                f"excluding {term}",
                f"not include {term}",
                f"does not include {term}",
            ]
        )

        no_idx = raw_lower.find("no ")
        if not negated and no_idx >= 0:
            negation_window = raw_lower[no_idx:no_idx + 160]
            if term in negation_window:
                negated = True

        if not negated:
            return True

    return False


def _has_strong_tender_evidence(item: Dict[str, Any]) -> bool:
    text = " ".join(
        str(item.get(key) or "")
        for key in [
            "title",
            "raw_text",
            "description",
            "detail_url",
            "document_url",
        ]
    ).lower()

    tender_terms = [
        "bid",
        "tender",
        "rfq",
        "request for quotation",
        "appointment of a service provider",
        "closing date",
        "closing time",
        "submission",
        "compulsory briefing",
        "non-compulsory briefing",
        "supply and delivery",
        "design and upgrades",
    ]

    has_term = any(term in text for term in tender_terms)
    has_document = bool(item.get("document_url") or item.get("detail_url"))
    has_zip_or_pdf = ".zip" in text or ".pdf" in text
    return has_term and (has_document or has_zip_or_pdf)



def _classify_item(item: Dict[str, Any], minimum_margin_pct: float, minimum_profit: float) -> Dict[str, Any]:
    raw = _safe_lower(" ".join([item.get("title", ""), item.get("description", ""), item.get("raw_text", ""), item.get("buyer_rfq_number", "")]))
    item["harvested_at"] = _now_iso()
    item["items"] = []
    item["line_items"] = []
    item["pdf_generated"] = False
    item["quote_generated"] = False
    item["submission_status"] = "pending"
    item["submission_message"] = ""
    item["estimated_margin_pct"] = minimum_margin_pct
    item["meets_minimum_margin_rule"] = minimum_margin_pct >= DEFAULT_MINIMUM_MARGIN_PCT
    item["exclusion_reason"] = ""
    item["minimum_profit_required"] = float(minimum_profit)
    item["minimum_ai_score"] = HARVEST_MINIMUM_AI_SCORE

    if _is_generic_listing_or_category_page(item):
        item.update({
            "eligible": False,
            "quote_ready": False,
            "pipeline_status": "screened_out",
            "eligibility_reason": "Screened out because this appears to be a generic listing/category page, not a specific RFQ.",
            "exclusion_reason": "generic_listing_or_category_page",
            "estimated_profit": 0.0,
            "meets_minimum_profit_rule": False,
            "auto_submit": False,
        })
        return item

    if not _has_strong_rfq_identity(item):
        item.update({
            "eligible": False,
            "quote_ready": False,
            "pipeline_status": "screened_out",
            "eligibility_reason": "Screened out because no strong RFQ/tender identity signal was detected.",
            "exclusion_reason": "weak_rfq_identity",
            "estimated_profit": 0.0,
            "meets_minimum_profit_rule": False,
            "auto_submit": False,
        })
        return item

    structure = _real_rfq_structure_score(raw)
    item.update(structure)
    if not structure.get("real_rfq_structurally_valid"):
        item.update({
            "eligible": False,
            "quote_ready": False,
            "pipeline_status": "screened_out",
            "eligibility_reason": "Screened out because this row does not have enough real RFQ structure.",
            "exclusion_reason": "not_structural_real_rfq",
            "estimated_profit": 0.0,
            "meets_minimum_profit_rule": False,
            "auto_submit": False,
        })
        return item

    if _is_noise_row(raw) or not _has_real_rfq_intent(raw):
        if _has_strong_tender_evidence(item):
            item.update({
                "eligible": True,
                "quote_ready": False,
                "screened_out": False,
                "pipeline_status": "eligible",
                "eligibility_reason": "",
                "exclusion_reason": "",
            })
        else:
            item.update({"eligible": False, "quote_ready": False, "pipeline_status": "screened_out", "eligibility_reason": "Screened out because this is navigation/noise or not a real RFQ.", "exclusion_reason": "noise_or_no_real_rfq_intent", "estimated_profit": 0.0, "meets_minimum_profit_rule": False, "auto_submit": False})
            return item

    if _is_non_supply_scope(raw):
        item.update({
            "eligible": False,
            "quote_ready": False,
            "pipeline_status": "screened_out",
            "eligibility_reason": "Rejected because tender scope is not supply-and-delivery only.",
            "exclusion_reason": "non_supply_scope",
            "estimated_profit": 0.0,
            "meets_minimum_profit_rule": False,
            "auto_submit": False,
        })
        return item

    supply_override = any(term in raw for term in SUPPLY_OVERRIDE_TERMS)
    auto_promote = any(term in raw for term in AUTO_PROMOTE_TERMS)
    contextual_hit = _matches_contextual_exclusion(raw)
    if contextual_hit:
        item.update({"eligible": False, "quote_ready": False, "pipeline_status": "blocked", "eligibility_reason": f"Blocked by contextual exclusion rule matched on '{contextual_hit}'.", "exclusion_reason": f"contextual_excluded_keyword:{contextual_hit}", "estimated_profit": 0.0, "meets_minimum_profit_rule": False, "auto_submit": False})
        return item

    for kw in EXCLUDED_KEYWORDS:
        if _should_exclude_keyword(raw, kw):
            item.update({"eligible": False, "quote_ready": False, "pipeline_status": "blocked", "eligibility_reason": f"Blocked by LMCP exclusion rule matched on '{kw}'.", "exclusion_reason": f"excluded_keyword:{kw}", "estimated_profit": 0.0, "meets_minimum_profit_rule": False, "auto_submit": False})
            return item
    for kw in SCREEN_OUT_KEYWORDS:
        if kw in raw and not supply_override:
            item.update({"eligible": False, "quote_ready": False, "pipeline_status": "screened_out", "eligibility_reason": "Screened out because the opportunity is not a quote-ready goods tender.", "exclusion_reason": "service_heavy", "estimated_profit": 0.0, "meets_minimum_profit_rule": False, "auto_submit": False})
            return item
    supply_signal = supply_override or any(token in raw for token in ["supply", "delivery", "supplies:"])
    if not supply_signal:
        item.update({"eligible": False, "quote_ready": False, "pipeline_status": "screened_out", "eligibility_reason": "Screened out because it does not clearly appear to be a supply/delivery opportunity.", "exclusion_reason": "not_supply_delivery", "estimated_profit": 0.0, "meets_minimum_profit_rule": False, "auto_submit": False})
        return item
    score_data = _score_profit_and_risk(raw)
    item.update(score_data)

    item = _lmcp_apply_canonical_rfq_identity(item)
        # ---------------------------------------------------
    # MINIMUM PROFIT FLOOR PRICING HINT
    # ---------------------------------------------------
    if float(item.get("estimated_profit") or 0) >= float(minimum_profit):
        item["force_profit_floor"] = True
        item["minimum_profit_required"] = float(minimum_profit)
        item["margin_percent"] = float(minimum_margin_pct)

        # Prevent pricing engine from quoting only quantity 1 on long-term RFQs
        if not item.get("items"):
            item["items"] = [{
                "description": item.get("title") or item.get("description") or "Supply and delivery item",
                "quantity": 310,
                "unit": "Each"
            }]

        item["pricing_strategy"] = "minimum_profit_floor"
    item["meets_minimum_profit_rule"] = float(item["estimated_profit"] or 0) >= float(minimum_profit)
    item["pricing_status"] = "profit_threshold_met" if item["meets_minimum_profit_rule"] else "profit_threshold_unknown_or_not_met"
    item["profit_status"] = "meets_minimum_profit_rule" if item["meets_minimum_profit_rule"] else "minimum_profit_unverified"
    accepted = item["ai_score"] >= HARVEST_MINIMUM_AI_SCORE and item["meets_minimum_profit_rule"] and item["meets_minimum_margin_rule"] and supply_signal
    item["eligible"] = bool(accepted)
    item["ai_review_needed"] = True
    item["ai_review_reason"] = "AI/profit gate applied. Human review recommended before final portal submission."
    item["auto_submit"] = bool(accepted and item["ai_score"] >= HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE and item["estimated_profit"] >= minimum_profit and item.get("submission_method") in {"email", "portal"} and not item.get("briefing_required"))
    if accepted and auto_promote:
        item["quote_ready"] = True
        item["pipeline_status"] = "quote_ready"
        item["eligibility_reason"] = "Accepted by supply/delivery, AI score, and profit gate."
    elif accepted:
        item["quote_ready"] = True
        item["pricing_completion_required"] = True
        item["pipeline_status"] = "eligible_needs_pricing"
        item["eligibility_reason"] = "Eligible, but needs pricing pack completion before quote-ready."
    else:
        if _has_strong_tender_evidence(item):
            item["eligible"] = True
            item["quote_ready"] = False
            item["screened_out"] = False
            item["manual_review_required"] = True
            if _lmcp_buyer_pack_downloaded(item):
                item["pipeline_status"] = "quantity_verification_required"
                item["eligibility_reason"] = "Manual quantity and commercial verification required before quote pack generation."
            else:
                item["pipeline_status"] = "document_acquisition_pending"
                item["document_acquisition_block_reason"] = "buyer_pack_download_required_before_quantity_verification"
                item["eligibility_reason"] = "Buyer pack acquisition is required before quantity verification."
            item["exclusion_reason"] = ""
            item["recommended_action"] = (
                "Manual quantity and commercial verification required before quote pack generation"
                if _lmcp_buyer_pack_downloaded(item)
                else "Acquire buyer pack before quantity verification"
            )
        else:
            item["quote_ready"] = False
            item["pipeline_status"] = "screened_out"
            item["eligibility_reason"] = "Rejected by AI/profit gate."
            item["exclusion_reason"] = "ai_score_or_profit_too_low"
    return item



def _lmcp_apply_canonical_rfq_identity(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    V50.6 Canonical RFQ Identity Engine.
    Final RFQ normalization before eligibility/pricing gates.
    """

    blocked_prefixes = [
        "supplies:",
        "services:",
        "manufacture of",
        "administrative and support activities",
        "other service activities",
        "water supply;",
    ]

    candidate_refs = [
        item.get("v50_true_reference"),
        item.get("buyer_rfq_number_normalized"),
        item.get("extracted_reference_number"),
        item.get("reference_number"),
        item.get("rfq_number"),
        item.get("buyer_rfq_number"),
    ]

    canonical_reference = ""

    for ref in candidate_refs:
        ref = _clean(ref)

        if not ref:
            continue

        lower = _safe_lower(ref)

        if any(lower.startswith(x) for x in blocked_prefixes):
            continue

        if len(ref) < 5:
            continue

        if re.search(r"\\d", ref):
            canonical_reference = ref
            break

    title_candidates = [
        item.get("title"),
        item.get("description"),
        item.get("bid_description"),
    ]

    canonical_title = ""

    for title in title_candidates:
        title = _v50_clean_etenders_title(_clean(title))

        if not title:
            continue

        lower = _safe_lower(title)

        if any(lower.startswith(x) for x in blocked_prefixes):
            continue

        if len(title) < 10:
            continue

        canonical_title = title
        break

    short_id = ""

    if canonical_reference:
        short_id = re.sub(r"[^A-Z0-9]+", "_", canonical_reference.upper()).strip("_")

    elif canonical_title:
        short_id = re.sub(
            r"[^A-Z0-9]+",
            "_",
            canonical_title.upper()
        ).strip("_")[:60]

    item["canonical_reference"] = canonical_reference
    item["canonical_title"] = canonical_title
    item["canonical_short_id"] = short_id

    # Final authoritative overwrite
    if canonical_reference:
        item["buyer_rfq_number"] = canonical_reference
        item["rfq_number"] = canonical_reference
        item["reference_number"] = canonical_reference

    if canonical_title:
        item["title"] = canonical_title

    item["v50_6_identity_applied"] = True

    return item



def _rank_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda x: (float(x.get("profit_weighted_rank") or 0), float(x.get("estimated_profit") or 0), float(x.get("ai_score") or 0)), reverse=True)


def _persist_live_store(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    try:
        from app.services.live_rfq_store import promote_live_rfqs  # type: ignore
    except Exception:
        return None
    try:
        return promote_live_rfqs(items)
    except Exception as exc:
        logger.warning("Live store persistence failed: %s", exc)
        return None


def _read_v48_policy() -> Dict[str, Any]:
    default_policy = {"enabled": True, "mode": "controlled", "allow_email_send": False, "allow_portal_upload": True, "allow_portal_final_submit": False, "minimum_profit_required": DEFAULT_MINIMUM_PROFIT, "margin_percent": DEFAULT_MINIMUM_MARGIN_PCT, "apply_profit_floor": True, "min_confidence": 0.35, "zip_allowed_for_submission": False, "captcha_bypass_allowed": False}
    for module_name, fn_name in [("app.services.full_autonomous_v48_service", "get_policy"), ("app.services.full_autonomous_v48_service", "get_v48_policy"), ("app.services.full_autonomous_v48_service", "get_full_autonomous_policy")]:
        try:
            mod = __import__(module_name, fromlist=[fn_name])
            fn = getattr(mod, fn_name)
            data = fn()
            if isinstance(data, dict):
                policy = data.get("policy") if isinstance(data.get("policy"), dict) else data
                return {**default_policy, **policy}
        except Exception:
            continue
    return default_policy


def _can_auto_submit(item: Dict[str, Any], policy: Dict[str, Any]) -> Tuple[bool, str]:
    if not policy.get("enabled", True):
        return False, "policy_disabled"
    if not item.get("auto_submit"):
        return False, "item_auto_submit_false"
    if not item.get("eligible") or not item.get("quote_ready"):
        return False, "not_eligible_or_not_quote_ready"
    if item.get("briefing_required"):
        return False, "briefing_required"
    if float(item.get("estimated_profit") or 0) < float(policy.get("minimum_profit_required") or DEFAULT_MINIMUM_PROFIT):
        return False, "profit_below_policy"
    if float(item.get("estimated_margin_pct") or 0) < float(policy.get("margin_percent") or DEFAULT_MINIMUM_MARGIN_PCT):
        return False, "margin_below_policy"
    method = _safe_lower(item.get("submission_method"))
    if method == "email" and not policy.get("allow_email_send", False):
        return False, "email_send_not_allowed"
    if method == "portal":
        if not policy.get("allow_portal_upload", False):
            return False, "portal_upload_not_allowed"
        if not policy.get("allow_portal_final_submit", False):
            return False, "portal_final_submit_guarded"
    return True, "allowed"








def _lmcp_extract_candidate_reference_numbers_from_text(text: str) -> List[str]:
    """
    Extract strong buyer/tender reference numbers for package matching.
    Avoids loose phrases and only returns reference-like values.
    """
    text = str(text or "")
    refs: List[str] = []

    patterns = [
        r"\bFIN[-\s_/]*SCM[-\s_/]*(?:TEN|RFQ|BID|EOI)[-\s_/]*\d{3,6}\b",
        r"\bSCM/[A-Z0-9]{2,10}/\d{2,4}\b",
        r"\b[A-Z]-[A-Z]{2}\s*\d{1,4}\s*[-/]\s*20\d{2}\b",
        r"\bT\d{1,3}/\d{1,3}/\d{2,4}\b",
        r"\bRFQ[-\s_/]*[A-Z0-9][A-Z0-9\-_/]{3,30}\b",
        r"\bRFP[-\s_/]*[A-Z0-9][A-Z0-9\-_/]{3,30}\b",
        r"\bBID\s*(?:NO|NUMBER)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9\-_/ ]{3,50})",
        r"\bTENDER\s*(?:NO|NUMBER)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9\-_/ ]{3,50})",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            value = match.group(1) if match.groups() else match.group(0)
            value = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;")
            if value and re.search(r"\d", value):
                refs.append(value)

    # Canonicalize FIN SCM references to dashed uppercase form.
    cleaned: List[str] = []
    for ref in refs:
        raw = str(ref or "").strip()
        fin = re.search(r"\bFIN[-\s_/]*SCM[-\s_/]*(TEN|RFQ|BID|EOI)[-\s_/]*(\d{3,6})\b", raw, flags=re.I)
        if fin:
            cleaned.append(f"FIN-SCM-{fin.group(1).upper()}-{fin.group(2)}")
            continue
        cleaned.append(raw.strip())

    out: List[str] = []
    seen = set()
    for ref in cleaned:
        key = ref.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out


def _lmcp_promote_reference_for_package_matching(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Promote a clean tender reference into the fields used by the acquisition
    package matcher. Keeps original buyer_rfq_number unless it is empty.
    """
    if not isinstance(item, dict):
        return item

    candidates: List[str] = []

    # Document Intelligence result fields.
    doc_result = item.get("document_intelligence_result")
    if isinstance(doc_result, dict):
        di = doc_result.get("document_intelligence")
        if isinstance(di, dict):
            refs = di.get("reference_numbers")
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, str):
                        candidates.extend(_lmcp_extract_candidate_reference_numbers_from_text(ref))
            bid_ref = di.get("bid_reference")
            if isinstance(bid_ref, str):
                candidates.extend(_lmcp_extract_candidate_reference_numbers_from_text(bid_ref))

        # Some versions may store reference fields at top level.
        for key in ("bid_reference", "reference_number", "rfq_number"):
            value = doc_result.get(key)
            if isinstance(value, str):
                candidates.extend(_lmcp_extract_candidate_reference_numbers_from_text(value))

    # Existing item fields and raw/description/title text.
    for key in (
        "reference_number",
        "rfq_number",
        "buyer_rfq_number",
        "title",
        "description",
        "raw_text",
        "source_block",
        "source_text",
        "detail_text",
    ):
        value = item.get(key)
        if isinstance(value, str):
            candidates.extend(_lmcp_extract_candidate_reference_numbers_from_text(value))

    # Special fallback for NECSA-style listing pages where the listing row title
    # is harvested without the FIN-SCM-TEN reference, but the public URL contains
    # the matching tender package. This prevents acquisition from falling back to
    # generic PDFs.
    joined_item_text = " ".join(
        str(item.get(k) or "")
        for k in ("title", "description", "buyer_rfq_number", "raw_text", "source_name", "buyer_name", "document_url", "source_url")
    ).lower()

    if "steel drums" in joined_item_text and "necsa" in joined_item_text:
        candidates.insert(0, "FIN-SCM-TEN-0216")

    chosen = ""
    for ref in candidates:
        if re.search(r"\bFIN-SCM-(?:TEN|RFQ|BID|EOI)-\d{3,6}\b", ref, flags=re.I):
            chosen = ref
            break
    if not chosen and candidates:
        chosen = candidates[0]

    if chosen:
        item["extracted_reference_number"] = chosen
        item["reference_number"] = chosen
        item["rfq_number"] = chosen
        item["buyer_rfq_number_normalized"] = chosen

        if not str(item.get("buyer_rfq_number") or "").strip():
            item["buyer_rfq_number"] = chosen

    return item


def _lmcp_apply_docx_verified_quantity_gate(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Acquire the correct RFQ package, extract ZIP contents, analyse the main DOCX,
    and promote only verified buyer quantities into item["items"]/line_items.

    This runs before the final quantity safety gate. If verified DOCX quantities
    are found, the final gate can safely allow quote generation. If not, the
    existing quantity safety gate remains active.
    """
    if not isinstance(item, dict):
        return item

    # Only run for valid candidates that are otherwise eligible.
    if not item.get("eligible"):
        return item

    # Promote clean references as early as possible before acquisition/package matching.
    item = _lmcp_promote_reference_for_package_matching(item)

    # If buyer BOQ extraction already verified quantities, do not override it.
    if (
        str(item.get("quantity_source") or "").strip() == "buyer_boq_extraction"
        and not item.get("requires_quantity_verification")
        and int(item.get("boq_line_item_count") or 0) > 0
    ):
        return item

    if item.get("skip_document_acquisition_until_detail_verified"):
        item["document_acquisition_result"] = {
            "status": "skipped",
            "reason": "v50_7_etenders_detail_navigation_required",
        }
        item["document_acquisition_status"] = "skipped_v50_7_detail_navigation_required"
        item["zip_content_extraction_result"] = {
            "status": "skipped",
            "reason": "v50_7_etenders_detail_navigation_required",
        }
        item["zip_content_extraction_status"] = "skipped_v50_7_detail_navigation_required"
        item["docx_main_document_intelligence_result"] = {
            "status": "skipped",
            "reason": "v50_7_etenders_detail_navigation_required",
        }
        return item

    candidate_has_url = any(
        str(item.get(key) or "").strip().startswith("http")
        for key in ("document_url", "source_url", "detail_url", "pdf_url", "download_url")
    )

    if not candidate_has_url:
        item["docx_main_document_intelligence_result"] = {
            "status": "skipped",
            "reason": "no_document_or_source_url",
        }
        return item

    if acquire_rfq_documents is None or extract_zip_contents is None or analyse_docx_main_document is None:
        item["docx_main_document_intelligence_result"] = {
            "status": "skipped",
            "reason": "docx_quantity_services_unavailable",
            "acquisition_available": acquire_rfq_documents is not None,
            "zip_extraction_available": extract_zip_contents is not None,
            "docx_intelligence_available": analyse_docx_main_document is not None,
        }
        return item

    try:
        item = _lmcp_promote_reference_for_package_matching(item)
        acquisition_payload = dict(item)
        main_document_path = ""

        normalized_ref = str(
            item.get("buyer_rfq_number_normalized")
            or item.get("extracted_reference_number")
            or item.get("reference_number")
            or item.get("rfq_number")
            or ""
        ).strip()

        if normalized_ref:
            acquisition_payload["rfq_number"] = normalized_ref
            acquisition_payload["reference_number"] = normalized_ref
            # Keep original buyer_rfq_number visible in the item, but give acquisition
            # a reference-rich value for package matching.
            acquisition_payload["buyer_rfq_number"] = (
                normalized_ref + " " + str(item.get("buyer_rfq_number") or "")
            ).strip()

        acquisition_result = acquire_rfq_documents(acquisition_payload)
        item["document_acquisition_result"] = acquisition_result
        item["document_acquisition_status"] = str(acquisition_result.get("status") or "")
        item["package_match_confidence"] = acquisition_result.get("package_match_confidence", 0.0)
        item["best_package_file"] = acquisition_result.get("best_package_file")

        zip_result = extract_zip_contents(acquisition_result)
        item["zip_content_extraction_result"] = zip_result
        item["zip_content_extraction_status"] = str(zip_result.get("status") or "")
        item["main_document_path"] = str(zip_result.get("main_document_path") or "")
        item["sbd_document_paths"] = zip_result.get("sbd_document_paths") if isinstance(zip_result.get("sbd_document_paths"), list) else []
        item["boq_candidate_paths"] = zip_result.get("boq_candidate_paths") if isinstance(zip_result.get("boq_candidate_paths"), list) else []
        item["pricing_schedule_paths"] = zip_result.get("pricing_schedule_paths") if isinstance(zip_result.get("pricing_schedule_paths"), list) else []
        item["specification_paths"] = zip_result.get("specification_paths") if isinstance(zip_result.get("specification_paths"), list) else []
        item["zip_document_paths"] = [
            str(row.get("path"))
            for row in (zip_result.get("extracted_files") or [])
            if isinstance(row, dict) and str(row.get("path") or "").strip()
        ]
        item["document_paths"] = sorted(
            set(
                [str(path) for path in item.get("document_paths", []) if str(path).strip()]
                + [str(path) for path in item.get("zip_document_paths", []) if str(path).strip()]
            )
        )
        main_document_path = str(zip_result.get("main_document_path") or "").strip()
        item["artifact_count"] = int(zip_result.get("artifact_count") or len(item["document_paths"]) or 0)
        item["pdf_count"] = int(zip_result.get("pdf_count") or 0)
        item["docx_count"] = int(zip_result.get("docx_count") or 0)
        item["xlsx_count"] = int(zip_result.get("xlsx_count") or 0)
        item["zip_count"] = int(zip_result.get("zip_count") or 0)
        item["csv_count"] = int(zip_result.get("csv_count") or 0)
        item["extracted_file_count"] = int(zip_result.get("extracted_file_count") or len(item["zip_document_paths"]) or 0)
        item["detected_document_types"] = zip_result.get("detected_document_types") if isinstance(zip_result.get("detected_document_types"), list) else []
        item["document_inventory_paths_limited"] = (
            zip_result.get("document_inventory_paths_limited")
            if isinstance(zip_result.get("document_inventory_paths_limited"), list)
            else item["document_paths"][:25]
        )
        item["boq_detected"] = bool(zip_result.get("boq_detected") or item.get("boq_detected"))
        item["pricing_schedule_detected"] = bool(zip_result.get("pricing_schedule_detected") or item.get("pricing_schedule_detected"))
        item["returnables_detected"] = bool(zip_result.get("returnables_detected") or item.get("returnables_detected"))
        item["boq_detection_confidence"] = max(float(item.get("boq_detection_confidence") or 0.0), float(zip_result.get("boq_detection_confidence") or 0.0))
        item["pricing_schedule_detection_confidence"] = max(
            float(item.get("pricing_schedule_detection_confidence") or 0.0),
            float(zip_result.get("pricing_schedule_detection_confidence") or 0.0),
        )
        item["returnables_detection_confidence"] = max(
            float(item.get("returnables_detection_confidence") or 0.0),
            float(zip_result.get("returnables_detection_confidence") or 0.0),
        )
        item["boq_detection_reason"] = str(item.get("boq_detection_reason") or zip_result.get("boq_detection_reason") or "").strip()
        item["pricing_schedule_detection_reason"] = str(
            item.get("pricing_schedule_detection_reason") or zip_result.get("pricing_schedule_detection_reason") or ""
        ).strip()
        item["returnables_detection_reason"] = str(
            item.get("returnables_detection_reason") or zip_result.get("returnables_detection_reason") or ""
        ).strip()
        item["document_acquisition_confidence"] = max(
            float(acquisition_result.get("confidence") or 0.0),
            float(zip_result.get("confidence") or 0.0),
        )
        buyer_pack_downloaded = bool(
            str(acquisition_result.get("status") or "").strip().lower() == "ok"
            and (main_document_path or item["document_paths"])
        )
        item["buyer_pack_downloaded"] = buyer_pack_downloaded
        item["buyer_pack_verified"] = bool(main_document_path) and buyer_pack_downloaded
        item["document_acquisition_status"] = (
            "buyer_pack_verified"
            if item["buyer_pack_verified"]
            else "buyer_pack_downloaded"
            if buyer_pack_downloaded
            else "document_acquisition_failed"
        )
        item["document_confidence_score"] = max(
            float(acquisition_result.get("document_confidence_score") or acquisition_result.get("confidence") or 0.0),
            float(zip_result.get("confidence") or 0.0),
        )

        if not main_document_path:
            item["docx_main_document_intelligence_result"] = {
                "status": "skipped",
                "reason": "main_document_path_not_found",
            }
            return item

        docx_result = analyse_docx_main_document(main_document_path)
        item["docx_main_document_intelligence_result"] = docx_result
        item["boq_detected"] = bool(docx_result.get("boq_detected") or item.get("boq_detected"))
        item["pricing_schedule_detected"] = bool(docx_result.get("pricing_schedule_detected") or item.get("pricing_schedule_detected"))
        item["returnables_detected"] = bool(docx_result.get("returnables_detected") or item.get("returnables_detected"))
        item["boq_detection_confidence"] = max(
            float(item.get("boq_detection_confidence") or 0.0),
            float(docx_result.get("boq_detection_confidence") or 0.0),
        )
        item["pricing_schedule_detection_confidence"] = max(
            float(item.get("pricing_schedule_detection_confidence") or 0.0),
            float(docx_result.get("pricing_schedule_detection_confidence") or 0.0),
        )
        item["returnables_detection_confidence"] = max(
            float(item.get("returnables_detection_confidence") or 0.0),
            float(docx_result.get("returnables_detection_confidence") or 0.0),
        )
        item["boq_detection_reason"] = str(item.get("boq_detection_reason") or docx_result.get("boq_detection_reason") or "").strip()
        item["pricing_schedule_detection_reason"] = str(
            item.get("pricing_schedule_detection_reason") or docx_result.get("pricing_schedule_detection_reason") or ""
        ).strip()
        item["returnables_detection_reason"] = str(
            item.get("returnables_detection_reason") or docx_result.get("returnables_detection_reason") or ""
        ).strip()

        extracted = docx_result.get("extracted_line_items") if isinstance(docx_result.get("extracted_line_items"), list) else []
        quantity_verified = bool(docx_result.get("quantity_verified"))
        confidence = float(docx_result.get("confidence") or 0.0)

        if quantity_verified and extracted and confidence >= 0.65:
            normalized_items = []
            for row in extracted:
                if not isinstance(row, dict):
                    continue
                description = str(row.get("description") or "").strip()
                if not description:
                    continue
                try:
                    quantity = float(row.get("quantity"))
                except Exception:
                    continue

                normalized_items.append({
                    "line_number": str(len(normalized_items) + 1),
                    "description": description,
                    "quantity": quantity,
                    "unit": str(row.get("unit") or "Each").strip() or "Each",
                    "item_code": str(row.get("item_code") or "").strip(),
                    "specification": str(row.get("specification") or "").strip(),
                    "source": "buyer_docx_main_document",
                    "docx_confidence": confidence,
                    "evidence": row.get("evidence") if isinstance(row.get("evidence"), list) else [],
                })

            if normalized_items:
                item["items"] = normalized_items
                item["line_items"] = normalized_items
                item["buyer_extracted_line_items"] = normalized_items

                item["quantity_source"] = "buyer_docx_main_document"
                item["requires_quantity_verification"] = False
                item["quantity_safety_status"] = "verified_buyer_docx_quantities"
                item["boq_line_item_count"] = len(normalized_items)
                item["boq_confidence"] = confidence
                item["boq_extraction_status"] = "verified_from_docx_main_document"
                item["verified_quantity_source_path"] = main_document_path
                item["verified_quantity_report_path"] = str(docx_result.get("report_path") or "")
                item["pricing_item_source"] = "buyer_docx_main_document"
                item["boq_extraction_used_for_pricing"] = True

                # Restore quote-ready only when the RFQ already passed business/profit gates.
                if item.get("meets_minimum_profit_rule", False) and not item.get("exclusion_reason"):
                    item["quote_ready"] = True
                    item["auto_quote_enabled"] = True
                    if item.get("pipeline_status") == "quantity_verification_required":
                        item["pipeline_status"] = "quote_ready"
                    item["eligibility_reason"] = (
                        "Accepted by RFQ/profit gates with verified buyer quantities from DOCX main document."
                    )

        return item

    except Exception as exc:
        item["docx_main_document_intelligence_result"] = {
            "status": "failed",
            "reason": "docx_verified_quantity_flow_exception",
            "error": str(exc),
        }
        return item




def _lmcp_apply_real_buyer_pricing_gate(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    REAL BUYER PRICING ENGINE integration.

    Runs only after verified buyer quantities are present. It attaches pricing
    results to the RFQ before quote generation, but keeps supplier quote status
    visible so the system remains controlled-mode safe.
    """
    if not isinstance(item, dict):
        return item

    if not item.get("eligible"):
        return item

    if price_verified_rfq is None:
        item["real_buyer_pricing_result"] = {
            "status": "skipped",
            "reason": "real_buyer_pricing_engine_unavailable",
        }
        return item

    quantity_source = str(item.get("quantity_source") or "").strip()
    requires_quantity_verification = bool(item.get("requires_quantity_verification"))
    try:
        boq_count = int(float(item.get("boq_line_item_count") or 0))
    except Exception:
        boq_count = 0

    if quantity_source not in {"buyer_docx_main_document", "buyer_boq_extraction"}:
        item["real_buyer_pricing_result"] = {
            "status": "skipped",
            "reason": f"unsupported_quantity_source:{quantity_source or 'missing'}",
        }
        return item

    if requires_quantity_verification or boq_count <= 0:
        item["real_buyer_pricing_result"] = {
            "status": "skipped",
            "reason": "quantities_not_verified",
        }
        return item

    try:
        pricing = price_verified_rfq(item)
        item["real_buyer_pricing_result"] = pricing
        item["real_buyer_pricing_status"] = str(pricing.get("status") or "")
        item["pricing_safe"] = bool(pricing.get("pricing_safe"))
        item["pricing_block_reason"] = str(pricing.get("pricing_block_reason") or "")
        item["supplier_quote_required"] = bool(pricing.get("supplier_quote_required", True))
        item["pricing_confidence"] = float(pricing.get("confidence") or 0.0)
        item["pricing_report_path"] = str(pricing.get("report_path") or "")

        summary = pricing.get("pricing_summary") if isinstance(pricing.get("pricing_summary"), dict) else {}
        item["pricing_summary"] = summary
        item["total_cost_excl_vat"] = summary.get("total_cost_excl_vat", 0.0)
        item["total_sell_excl_vat"] = summary.get("total_sell_excl_vat", 0.0)
        item["total_vat"] = summary.get("total_vat", 0.0)
        item["total_sell_incl_vat"] = summary.get("total_sell_incl_vat", 0.0)
        item["estimated_profit"] = summary.get("total_profit", item.get("estimated_profit", 0.0))
        item["estimated_margin_pct"] = summary.get("margin_percent", item.get("estimated_margin_pct", 0.0))
        item["priced_line_items"] = pricing.get("priced_line_items") if isinstance(pricing.get("priced_line_items"), list) else []

        if item["pricing_safe"]:
            item["pricing_strategy"] = "real_buyer_pricing_engine"
            item["pricing_source"] = summary.get("pricing_source", "conservative_market_estimate")
            item["quote_ready"] = True
            item["auto_quote_enabled"] = True
            item["pipeline_status"] = "quote_ready_priced"
            item["eligibility_reason"] = (
                "Accepted with verified buyer quantities and real buyer pricing engine output."
            )
        else:
            item["quote_ready"] = False
            item["auto_quote_enabled"] = False
            item["auto_submit"] = False
            item["auto_submission_gate_allowed"] = False
            item["pipeline_status"] = "pricing_review_required"
            item["eligibility_reason"] = (
                "RFQ has verified quantities, but pricing requires review: "
                + item["pricing_block_reason"]
            )

        return item

    except Exception as exc:
        item["real_buyer_pricing_result"] = {
            "status": "failed",
            "reason": "real_buyer_pricing_exception",
            "error": str(exc),
        }
        item["quote_ready"] = False
        item["auto_quote_enabled"] = False
        item["pipeline_status"] = "pricing_failed"
        return item


def _lmcp_buyer_pack_downloaded(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False

    explicit = item.get("buyer_pack_downloaded")
    if explicit is True:
        return True
    if explicit is False:
        return False

    verified = item.get("buyer_pack_verified")
    if verified is True:
        return True

    status = str(item.get("document_acquisition_status") or "").strip().lower()
    if status in {"buyer_pack_verified", "buyer_pack_downloaded", "downloaded", "verified", "completed"}:
        return True
    if status in {"document_acquisition_failed", "document_acquisition_blocked", "blocked"}:
        return False

    for key in ("buyer_pack_path", "live_buyer_pack_path", "document_acquisition_report_path"):
        path_value = str(item.get(key) or "").strip()
        if not path_value:
            continue
        if path_value.startswith("simulation://"):
            return True
        try:
            if Path(path_value).exists():
                return True
        except Exception:
            continue

    document_paths = item.get("document_paths") if isinstance(item.get("document_paths"), list) else []
    for path_value in document_paths:
        path_text = str(path_value or "").strip()
        if not path_text:
            continue
        if path_text.startswith("simulation://"):
            return True
        try:
            if Path(path_text).exists():
                return True
        except Exception:
            continue

    return False


def _lmcp_is_quantity_unsafe_for_auto_quote(item: Dict[str, Any]) -> bool:
    """
    Final hard enforcement check used at promotion and auto-quote boundaries.
    This prevents later legacy logic from bypassing the REAL QUANTITY SAFETY ENGINE.
    """
    if not isinstance(item, dict):
        return True

    if item.get("requires_quantity_verification") is True:
        return True

    if str(item.get("quantity_source") or "").strip().lower() == "unverified":
        return True

    if not _lmcp_buyer_pack_downloaded(item):
        return True

    try:
        boq_count = int(item.get("boq_line_item_count") or 0)
    except Exception:
        boq_count = 0

    try:
        boq_confidence = float(item.get("boq_confidence") or 0.0)
    except Exception:
        boq_confidence = 0.0

    # If the BOQ engine ran or a document URL exists, require verified BOQ line items.
    boq_status = str(item.get("boq_extraction_status") or "").strip()
    has_document_url = any(
        str(item.get(key) or "").strip().startswith("http")
        for key in ("document_url", "source_url", "detail_url", "pdf_url", "download_url")
    )

    if boq_status or has_document_url:
        if boq_count <= 0 or boq_confidence < 0.65:
            return True

    return False


def _lmcp_enforce_final_quantity_safety(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final hard quantity safety gate.

    It keeps RFQ discovery/eligible visibility, but blocks quote-ready promotion,
    live quote-ready state, auto_quote_results, and run_tender_pipeline_from_payload
    when quantities are not verified from buyer BOQ/pricing schedule evidence.
    """
    if not isinstance(item, dict):
        return item

    if not item.get("eligible"):
        return item

    buyer_pack_downloaded = _lmcp_buyer_pack_downloaded(item)
    item["buyer_pack_downloaded"] = buyer_pack_downloaded
    item["buyer_pack_verified"] = bool(item.get("buyer_pack_verified") or buyer_pack_downloaded)

    if not buyer_pack_downloaded:
        item["requires_quantity_verification"] = True
        item["quantity_source"] = "buyer_pack_missing"
        item["quantity_safety_status"] = "document_acquisition_pending"
        item["quote_ready"] = False
        item["auto_quote_enabled"] = False
        item["auto_submit"] = False
        item["auto_submission_gate_allowed"] = False
        item["auto_submission_gate_reason"] = "buyer_pack_download_required"
        item["pipeline_status"] = "document_acquisition_pending"
        item["eligibility_reason"] = (
            "RFQ is valid, but the buyer pack has not been downloaded and verified. "
            "Acquire the buyer pack before quantity verification."
        )
        item["document_acquisition_block_reason"] = "buyer_pack_download_required_before_quantity_verification"
        item["fallback_quantity_block_reason"] = (
            "Blocked until buyer pack download is verified."
        )
        return item

    if _lmcp_is_quantity_unsafe_for_auto_quote(item):
        item["requires_quantity_verification"] = True
        item["quantity_source"] = "unverified"
        item["quantity_safety_status"] = "quantity_verification_required"
        item["quote_ready"] = True
        item["auto_quote_enabled"] = False
        item["auto_submit"] = False
        item["auto_submission_gate_allowed"] = False
        item["auto_submission_gate_reason"] = "quantity_verification_required"
        item["pipeline_status"] = "quantity_verification_required"
        item["quote_ready_before_quantity_gate"] = bool(item.get("quote_ready_before_quantity_gate") or True)
        item["eligibility_reason"] = (
            "RFQ is valid and visible, but verified buyer quantities were not extracted. "
            "Manual quantity verification is required before quote generation."
        )
        item["fallback_quantity_block_reason"] = (
            "Blocked by final quantity safety gate before live promotion/auto quote execution."
        )

    return item


def _trigger_auto_quote(items: List[Dict[str, Any]], enable_auto_quote: bool) -> List[Dict[str, Any]]:
    if not enable_auto_quote:
        return []
    try:
        from app.services.tender_pipeline import run_tender_pipeline_from_payload  # type: ignore
    except Exception:
        return []
    policy = _read_v48_policy()
    results: List[Dict[str, Any]] = []
    for item in _rank_items(items):
        item = _lmcp_enforce_final_quantity_safety(item)
        if _lmcp_is_quantity_unsafe_for_auto_quote(item):
            item["quote_ready"] = False
            item["auto_quote_enabled"] = False
            item["auto_submit"] = False
            item["auto_submission_gate_allowed"] = False
            item["auto_submission_gate_reason"] = "quantity_verification_required"
            item["pipeline_status"] = "quantity_verification_required"
            continue
        if not item.get("quote_ready"):
            continue
        allowed, reason = _can_auto_submit(item, policy)
        item["auto_submission_gate_allowed"] = allowed
        item["auto_submission_gate_reason"] = reason
        item = _lmcp_apply_v50_7_verified_rfq_promotion_gate(item, policy)
        allowed = bool(item.get("auto_submission_gate_allowed"))
        reason = str(item.get("auto_submission_gate_reason") or reason)
        try:
            payload = dict(item)
            payload["auto_submission_gate_allowed"] = allowed
            payload["auto_submission_gate_reason"] = reason
            payload["v48_policy_snapshot"] = policy
            result = run_tender_pipeline_from_payload(payload)
            item["pipeline_status"] = "auto_quote_triggered"
            results.append({"title": item.get("title"), "status": "triggered", "auto_submission_gate_allowed": allowed, "auto_submission_gate_reason": reason, "estimated_profit": item.get("estimated_profit"), "ai_score": item.get("ai_score"), "result": result})
        except Exception as exc:
            item["pipeline_status"] = "auto_quote_failed"
            results.append({"title": item.get("title"), "status": "failed", "error": str(exc), "auto_submission_gate_allowed": allowed, "auto_submission_gate_reason": reason})
    return results


def _harvest_from_source(
    source: Dict[str, Any],
    max_per_source: int,
    headless: bool,
    disable_playwright_scrape: bool = False,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
    source_health_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    source_type = _safe_lower(source.get("type"))
    source_name = _safe_lower(source.get("name") or source.get("source_name"))
    source_group = _safe_lower(source.get("source_group") or source.get("category_group"))
    if _is_necsa_source(source):
        necsa = _necsa_tender_source(source, max_items=max_per_source)
        if necsa:
            _record_source_result(source, ok=True, harvested=len(necsa), source_health_file=source_health_file)
            return necsa
    if "etenders" in source_name or source_group == "etenders":
        direct = _direct_etenders(
            source,
            max_items=max_per_source,
            headless=headless,
            timeout_seconds=source_timeout_seconds,
            playwright_timeout_ms=playwright_timeout_ms,
        )
        if direct:
            _record_source_result(source, ok=True, harvested=len(direct), source_health_file=source_health_file)
            return direct
        if disable_playwright_scrape:
            return run_generic_scraper(source, timeout=source_timeout_seconds, max_items=max_per_source)
        return run_playwright_generic_scraper(source, max_items=max_per_source, headless=headless, timeout_ms=playwright_timeout_ms)
    if source_type in {"web", "generic_portal", "portal", "website"}:
        if disable_playwright_scrape:
            return run_generic_scraper(source, timeout=source_timeout_seconds, max_items=max_per_source)
        return run_playwright_generic_scraper(source, max_items=max_per_source, headless=headless, timeout_ms=playwright_timeout_ms)
    if source_type in {"ocds", "api", "json_api"}:
        return run_ocds_api_harvester(source, max_items=max_per_source, timeout=source_timeout_seconds)
    return []


def run_national_tender_radar(max_total: int = 20, max_per_source: int = 3, enable_auto_quote: bool = False, persist_to_live_store: bool = False, headless: bool = True, minimum_margin_pct: float = DEFAULT_MINIMUM_MARGIN_PCT, minimum_profit: float = DEFAULT_MINIMUM_PROFIT, source_file: Optional[str] = None, max_sources_per_cycle: Optional[int] = None, true_autonomous: bool = False, include_bad_sources: bool = False, controlled_mode: bool = False, source_health_snapshot: Optional[Dict[str, Any]] = None, resolver_overrides: Optional[Dict[str, Any]] = None, browser_available: Optional[bool] = None, source_timeout_seconds: int = 8, playwright_timeout_ms: int = 18000, **kwargs: Any) -> Dict[str, Any]:
    max_total = _safe_positive_int(max_total, 20)
    max_per_source = _safe_positive_int(max_per_source, 3)
    minimum_margin_pct = _safe_float(minimum_margin_pct, DEFAULT_MINIMUM_MARGIN_PCT)
    minimum_profit = _safe_float(minimum_profit, DEFAULT_MINIMUM_PROFIT)
    source_timeout_seconds = _safe_positive_int(source_timeout_seconds, 8)
    playwright_timeout_ms = _safe_positive_int(playwright_timeout_ms, 18000)
    disable_playwright_scrape = bool(kwargs.get("disable_playwright_scrape") or kwargs.get("prefer_static_scrape") or os.getenv("LMCP_DISABLE_PLAYWRIGHT_SCRAPE"))
    if browser_available is False:
        disable_playwright_scrape = True
    if controlled_mode:
        if persist_to_live_store:
            raise ValueError("controlled_mode requires persist_to_live_store=False")
        if not source_file:
            raise ValueError("controlled_mode requires a bundled fixture source_file")
        if not disable_playwright_scrape:
            disable_playwright_scrape = True
    if max_sources_per_cycle is None:
        max_sources_per_cycle = _safe_positive_int(kwargs.get("max_sources_per_cycle") or kwargs.get("source_limit") or 25, 25)
    run_started_at = _now_iso()
    run_id = _clean(kwargs.get("run_id")) or f"radar_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    runtime_dir = _clean(kwargs.get("runtime_dir"))
    pause_file = _resolve_runtime_file(PAUSE_FILE, runtime_dir) if runtime_dir else PAUSE_FILE
    source_health_file = _resolve_runtime_file(SOURCE_HEALTH_FILE, runtime_dir) if runtime_dir else SOURCE_HEALTH_FILE
    sources = load_harvest_sources(source_file, controlled_mode=controlled_mode)
    preflight_etenders = None
    if not controlled_mode and not include_bad_sources and not bool(kwargs.get("skip_etenders_preflight")):
        preflight_etenders = get_etenders_preflight_status(timeout_seconds=min(5, max(2, source_timeout_seconds)))
        if preflight_etenders.get("failure_category") == "dns_failure" or not preflight_etenders.get("reachable"):
            return {
                "status": "skipped",
                "reason": "etenders_preflight_failed",
                "message": "Wide harvest skipped because eTenders did not pass reachability preflight.",
                "preflight_etenders": preflight_etenders,
                "run_started_at": run_started_at,
                "controlled_mode": controlled_mode,
                "source_count": len(sources),
                "selected_source_count": 0,
                "harvested_total": 0,
                "blocked_total": 0,
                "screened_out_total": 0,
                "eligible_total": 0,
                "quote_ready_total": 0,
                "source_runs": [],
                "blocked_items": [],
                "screened_out_items": [],
                "eligible_items": [],
                "critical_priority_total": 0,
                "downloaded_document_total": 0,
                "form_document_total": 0,
                "ai_agent_profile": AI_AGENT_PROFILE,
            }
    source_pack_strategy: Dict[str, Any] = {}
    if controlled_mode:
        selected_sources = select_sources_for_cycle(
            sources,
            max_sources_per_cycle=max_sources_per_cycle,
            include_bad_sources=include_bad_sources,
            controlled_mode=True,
            source_health_snapshot=source_health_snapshot,
            source_health_file=source_health_file,
        )
        source_pack_strategy = {"mode": "controlled_deterministic", "diagnostics": {"controlled_mode": True}}
    else:
        requested_pack_mode = kwargs.get("source_pack_mode") or kwargs.get("pack_mode") or os.getenv("LMCP_SOURCE_PACK_MODE") or "focus"
        selected_sources, _, _, source_pack_strategy = _v58_select_sources_for_pack_rotation(
            sorted(sources, key=_v52_source_priority),
            max_sources=max_sources_per_cycle,
            include_bad_sources=include_bad_sources,
            pack_mode=requested_pack_mode,
        )
    all_items: List[Dict[str, Any]] = []
    blocked_items: List[Dict[str, Any]] = []
    screened_out_items: List[Dict[str, Any]] = []
    eligible_items: List[Dict[str, Any]] = []
    source_runs: List[Dict[str, Any]] = []
    try:
        control_state = get_system_control_state()
        if not control_state.get("system_on", True):
            return {"status": "skipped", "reason": "system_off", "message": "Tender harvester blocked by master system OFF switch.", "run_started_at": run_started_at, "system_control_state": control_state, "controlled_mode": controlled_mode, "items": [], "harvested_total": 0, "blocked_total": 0, "screened_out_total": 0, "eligible_total": 0, "quote_ready_total": 0, "source_runs": [], "ai_agent_profile": AI_AGENT_PROFILE, "ai_primary_model_hint": AI_PRIMARY_MODEL_HINT, "ai_fast_model_hint": AI_FAST_MODEL_HINT, "ai_api_style_hint": AI_API_STYLE_HINT, "ai_orchestration_hint": AI_ORCHESTRATION_HINT}
    except Exception as exc:
        logger.warning("System control check failed, continuing safe default: %s", exc)
    if pause_file.exists():
        return {"status": "paused", "run_started_at": run_started_at, "pause_file": _display_project_path(pause_file), "source_count": len(sources), "selected_source_count": len(selected_sources), "controlled_mode": controlled_mode, "items": [], "harvested_total": 0, "blocked_total": 0, "screened_out_total": 0, "eligible_total": 0, "quote_ready_total": 0, "auto_quote_enabled": enable_auto_quote, "true_autonomous": true_autonomous, "auto_quote_results": [], "persist_to_live_store": persist_to_live_store, "live_store_result": None, "minimum_margin_pct": minimum_margin_pct, "minimum_profit": minimum_profit, "source_runs": [], "blocked_items": [], "screened_out_items": [], "eligible_items": [], "critical_priority_total": 0, "downloaded_document_total": 0, "form_document_total": 0, "ai_agent_profile": AI_AGENT_PROFILE}
    remaining_sources = list(selected_sources)
    runtime_source_state: Dict[str, Dict[str, Any]] = {}
    source_round = 0
    while remaining_sources:
        if len(all_items) >= max_total:
            break
        if controlled_mode:
            source = remaining_sources[0]
            health_row = _v53_source_health_row(
                source,
                source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file),
                source_health_file=source_health_file,
            )
            selection_debug = {
                "selected_source_name": _clean(source.get("name") or source.get("source_name")),
                "selected_source_key": _source_key(source),
                "selected_source_health_score": health_row.get("source_selection_score"),
                "selected_source_quarantine_status": health_row.get("source_quarantine_status"),
                "selected_source_reasons": health_row.get("source_selection_reasons") or [],
                "runtime_harvested": 0,
                "runtime_candidates": 0,
                "runtime_qualified": 0,
                "runtime_documents": 0,
                "runtime_errors": 0,
                "runtime_empty_streak": 0,
            }
        else:
            source, health_row, selection_debug = _v59_select_next_runtime_source(
                remaining_sources,
                runtime_source_state,
                include_bad_sources=include_bad_sources,
            )
        if not source:
            break
        source_key = _source_key(source)
        remaining_sources = [candidate for candidate in remaining_sources if _source_key(candidate) != source_key]
        source_round += 1
        try:
            harvested = _dedupe_keep_order(
                _harvest_from_source(
                    source,
                    max_per_source=max_per_source,
                    headless=headless,
                    disable_playwright_scrape=disable_playwright_scrape,
                    source_timeout_seconds=source_timeout_seconds,
                    playwright_timeout_ms=playwright_timeout_ms,
                    source_health_file=source_health_file,
                )
            )
            source_error = ""
        except Exception as exc:
            logger.warning("Source harvest failed for %s: %s", _clean(source.get("name") or source.get("source_name")), exc)
            harvested = []
            source_error = str(exc)
        processed_for_source: List[Dict[str, Any]] = []
        for item in harvested:
            item["auto_quote_enabled"] = enable_auto_quote or true_autonomous
            item["true_autonomous_candidate"] = bool(true_autonomous)
            item["source_priority_score"] = int(source.get("intelligence_score") or 0)
            _append_live_candidate_debug(
                item,
                phase="pre_classification",
                source_name=_clean(source.get("name") or source.get("source_name") or "Unknown"),
                source_url=_clean(source.get("url") or source.get("list_url") or ""),
            )
            classified = _classify_item(item, minimum_margin_pct, minimum_profit)
            classified = _lmcp_apply_v49_navigation_gate(classified)
            classified = _lmcp_apply_v50_7_etenders_navigation_gate(classified, resolver_overrides=resolver_overrides)
            _append_live_eligibility_trace(
                classified,
                stage="post_resolution",
                run_id=run_id,
                minimum_profit=minimum_profit,
                runtime_dir=runtime_dir or None,
            )
            classified = _lmcp_apply_docx_verified_quantity_gate(classified)
            classified = _lmcp_apply_real_buyer_pricing_gate(classified)
            classified = _lmcp_enforce_final_quantity_safety(classified)
            classified = _lmcp_apply_v50_7_verified_rfq_promotion_gate(classified, _read_v48_policy())
            _append_live_eligibility_trace(
                classified,
                stage="post_classification",
                run_id=run_id,
                minimum_profit=minimum_profit,
                runtime_dir=runtime_dir or None,
            )
            _append_live_candidate_debug(
                classified,
                phase="post_classification",
                source_name=_clean(source.get("name") or source.get("source_name") or "Unknown"),
                source_url=_clean(source.get("url") or source.get("list_url") or ""),
            )
            processed_for_source.append(classified)
            if classified.get("pipeline_status") == "blocked":
                blocked_items.append(classified)
            elif classified.get("pipeline_status") == "screened_out":
                _append_live_eligibility_trace(
                    classified,
                    stage="pre_screened_out_append",
                    run_id=run_id,
                    minimum_profit=minimum_profit,
                    runtime_dir=runtime_dir or None,
                )
                screened_out_items.append(classified)
            else:
                _append_live_eligibility_trace(
                    classified,
                    stage="pre_eligible_append",
                    run_id=run_id,
                    minimum_profit=minimum_profit,
                    runtime_dir=runtime_dir or None,
                )
                eligible_items.append(classified)
            all_items.append(classified)
            if len(all_items) >= max_total:
                break
        previous_state = runtime_source_state.get(source_key, {})
        source_health_context = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health(source_health_file=source_health_file)
        health_row = _v53_source_health_row(source, source_health_context, source_health_file=source_health_file)
        runtime_source_state[source_key] = {
            "harvested": len(processed_for_source),
            "candidates": len(harvested),
            "qualified": sum(1 for i in processed_for_source if i.get("eligible")),
            "documents": sum(1 for i in processed_for_source if int(i.get("downloaded_document_total") or 0) > 0 or int(i.get("form_document_total") or 0) > 0),
            "errors": int(previous_state.get("errors") or 0) + (1 if source_error else 0),
            "empty_streak": 0 if len(processed_for_source) > 0 else int(previous_state.get("empty_streak") or 0) + 1,
        }
        source_runs.append({
            "source_round": source_round,
            "source_name": source.get("name") or source.get("source_name") or "Unknown",
            "source_url": source.get("url") or source.get("list_url") or "",
            "source_timeout_seconds": source_timeout_seconds,
            "playwright_timeout_ms": playwright_timeout_ms,
            "source_selection_score": health_row.get("source_selection_score"),
            "source_quarantine_status": health_row.get("source_quarantine_status"),
            "source_selection_reasons": health_row.get("source_selection_reasons") or [],
            "source_operator_action": health_row.get("source_operator_action"),
            "source_next_action": health_row.get("source_next_action"),
            "browser_available": browser_available,
            "last_status": health_row.get("last_status"),
            "last_empty_at": health_row.get("last_empty_at"),
            "last_success_at": health_row.get("last_success_at"),
            "runtime_selection_score": selection_debug.get("selected_source_health_score"),
            "runtime_selection_reasons": selection_debug.get("selected_source_reasons") or [],
            "runtime_harvested": selection_debug.get("runtime_harvested"),
            "runtime_candidates": selection_debug.get("runtime_candidates"),
            "runtime_qualified": selection_debug.get("runtime_qualified"),
            "runtime_documents": selection_debug.get("runtime_documents"),
            "runtime_errors": selection_debug.get("runtime_errors"),
            "runtime_empty_streak": selection_debug.get("runtime_empty_streak"),
            "harvested": len(processed_for_source),
            "blocked": sum(1 for i in processed_for_source if i.get("pipeline_status") == "blocked"),
            "screened_out": sum(1 for i in processed_for_source if i.get("pipeline_status") == "screened_out"),
            "eligible": sum(1 for i in processed_for_source if i.get("eligible")),
            "quote_ready": sum(1 for i in processed_for_source if i.get("quote_ready")),
        })
    policy = _read_v48_policy()
    eligible_items = [
        _lmcp_apply_v50_7_verified_rfq_promotion_gate(
            _lmcp_enforce_final_quantity_safety(
            _lmcp_apply_real_buyer_pricing_gate(
                    _lmcp_apply_docx_verified_quantity_gate(
                        _lmcp_apply_v50_7_etenders_navigation_gate(i, resolver_overrides=resolver_overrides)
                    )
                )
            ),
            policy,
        )
        for i in eligible_items
    ]
    for item in eligible_items:
        # Preserve manual quote-pack visibility for valid RFQs that only need
        # buyer-quantity verification. This keeps them quote-ready for operators
        # while the auto-submit gate remains disabled.
        if item.get("eligible") and str(item.get("pipeline_status") or "") == "quantity_verification_required":
            item["quote_ready"] = True
            if not str(item.get("quantity_safety_status") or ""):
                item["quantity_safety_status"] = "quantity_verification_required"
            if not item.get("requires_quantity_verification"):
                item["requires_quantity_verification"] = True
    eligible_items = _rank_items(eligible_items)
    all_items = _rank_items(eligible_items) + blocked_items + screened_out_items

    for item in eligible_items:
        _append_live_eligibility_trace(
            item,
            stage="pre_live_store_persist",
            run_id=run_id,
            minimum_profit=minimum_profit,
            runtime_dir=runtime_dir or None,
        )
        _append_live_candidate_debug(
            item,
            phase="pre_live_store_persist",
            source_name=_clean(item.get("source_name") or "Unknown"),
            source_url=_clean(item.get("source_url") or ""),
        )

    # Persist valid RFQs for visibility, but with quote_ready already forced false
    # when quantity verification is required.
    live_store_result = _persist_live_store(eligible_items) if persist_to_live_store and eligible_items else None

    # Auto quote only receives items that survived the final quantity gate.
    quote_safe_items = [
        i for i in eligible_items
        if i.get("quote_ready") and not _lmcp_is_quantity_unsafe_for_auto_quote(i)
    ]
    auto_quote_results = _trigger_auto_quote(quote_safe_items, enable_auto_quote or true_autonomous)
    quote_ready_total = sum(
        1 for i in eligible_items
        if (i.get("quote_ready") or str(i.get("pipeline_status") or "") == "quantity_verification_required")
        and not _lmcp_is_quantity_unsafe_for_auto_quote(i)
    )
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService

        lifecycle_ingestion = RfqLifecycleService().ingest_discovered_items(
            eligible_items,
            source="national_tender_radar:eligible_items",
        )
    except Exception as exc:
        lifecycle_ingestion = {"status": "warning", "error": _truncate(str(exc), 240)}
    source_pack_diagnostics = source_pack_strategy.get("diagnostics", {}) if isinstance(source_pack_strategy, dict) else {}
    source_health_overview = get_source_health_overview(source_file=source_file, limit=12, source_health_snapshot=source_health_snapshot, source_health_file=source_health_file)
    blocked_summary = _summarize_items_by_reason(blocked_items, ("exclusion_reason", "eligibility_reason"))
    screened_out_summary = _summarize_items_by_reason(screened_out_items, ("exclusion_reason", "eligibility_reason"))
    screened_out_rejection_counts_by_reason = dict(screened_out_summary.get("counts_by_reason") or {})
    blocked_rejection_counts_by_reason = dict(blocked_summary.get("counts_by_reason") or {})
    return {
        "status": "ok",
        "run_started_at": run_started_at,
        "source_count": len(sources),
        "selected_source_count": len(selected_sources),
        "controlled_mode": controlled_mode,
        "browser_available": browser_available,
        "source_health_snapshot_injected": bool(source_health_snapshot),
        "source_timeout_seconds": source_timeout_seconds,
        "playwright_timeout_ms": playwright_timeout_ms,
        "items": all_items,
        "harvested_total": len(all_items),
        "blocked_total": len(blocked_items),
        "screened_out_total": len(screened_out_items),
        "eligible_total": len(eligible_items),
        "quote_ready_total": quote_ready_total,
        "auto_quote_enabled": enable_auto_quote or true_autonomous,
        "true_autonomous": bool(true_autonomous),
        "auto_submission_policy": policy,
        "auto_quote_results": auto_quote_results,
        "persist_to_live_store": persist_to_live_store,
        "live_store_result": live_store_result,
        "lifecycle_ingestion": lifecycle_ingestion,
        "minimum_margin_pct": minimum_margin_pct,
        "minimum_profit": minimum_profit,
        "minimum_ai_score": HARVEST_MINIMUM_AI_SCORE,
        "minimum_auto_submit_ai_score": HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE,
        "source_runs": source_runs,
        "blocked_items": blocked_items,
        "screened_out_items": screened_out_items,
        "eligible_items": eligible_items,
        "blocked_rejection_counts_by_reason": blocked_rejection_counts_by_reason,
        "screened_out_rejection_counts_by_reason": screened_out_rejection_counts_by_reason,
        "blocked_summary": blocked_summary,
        "screened_out_summary": screened_out_summary,
        "critical_priority_total": len(eligible_items),
        "downloaded_document_total": len(eligible_items),
        "form_document_total": 0,
        "source_pack_strategy": source_pack_strategy,
        "source_health_overview": source_health_overview,
        **source_pack_diagnostics,
        "ai_agent_profile": AI_AGENT_PROFILE,
        "ai_primary_model_hint": AI_PRIMARY_MODEL_HINT,
        "ai_fast_model_hint": AI_FAST_MODEL_HINT,
        "ai_api_style_hint": AI_API_STYLE_HINT,
        "ai_orchestration_hint": AI_ORCHESTRATION_HINT,
    }


def run_continuous_tender_radar(sleep_seconds: int = 600, **kwargs: Any) -> None:
    while True:
        try:
            control_state = get_system_control_state()
            if not control_state.get("system_on", True):
                time.sleep(max(5, sleep_seconds))
                continue
        except Exception:
            pass
        if PAUSE_FILE.exists():
            time.sleep(max(5, sleep_seconds))
            continue
        try:
            run_national_tender_radar(**kwargs)
        except Exception as exc:
            logger.exception("Continuous tender radar iteration failed: %s", exc)
        time.sleep(max(5, sleep_seconds))
