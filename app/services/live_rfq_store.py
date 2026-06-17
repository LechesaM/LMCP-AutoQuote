from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.runtime_paths import get_runtime_paths

logger = logging.getLogger(__name__)


def _resolve_live_rfq_store_path() -> Path:
    explicit_path = str(os.getenv("LMCP_LIVE_RFQS_PATH") or os.getenv("LIVE_RFQS_PATH") or "").strip()
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    runtime_root = get_runtime_paths().runtime_root
    return runtime_root / "live_rfqs.json"


LIVE_RFQ_STORE_PATH = _resolve_live_rfq_store_path()
LIVE_RFQ_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return _clean(value).lower() in {"1", "true", "yes", "y", "on", "complete", "completed", "ok", "verified"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _parse_date(value: Any) -> Optional[datetime]:
    text = _clean(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt)
        except Exception:
            continue
    return None


def _first_text(item: Dict[str, Any], keys: List[str], nested_keys: List[str] | None = None) -> str:
    for key in keys:
        value = _clean(item.get(key))
        if value:
            return value
    if nested_keys:
        acquisition = item.get("document_acquisition_result")
        if isinstance(acquisition, dict):
            for key in nested_keys:
                value = _clean(acquisition.get(key))
                if value:
                    return value
    return ""


def _coalesce_bool(item: Dict[str, Any], key: str, fallback: bool = False) -> bool:
    value = item.get(key)
    if isinstance(value, bool):
        return value or fallback
    if value is not None and _clean(value) != "":
        parsed = _truthy(value)
        return parsed or fallback
    return fallback


def _status_from_components(*, complete: bool, failed: bool, attempted: bool, complete_label: str = "downloaded") -> str:
    if complete:
        return complete_label
    if failed:
        return "failed"
    return "not_attempted"


def _quote_ready_allowed(item: Dict[str, Any]) -> bool:
    intelligence = item if isinstance(item, dict) else {}
    return bool(
        _truthy(intelligence.get("buyer_pack_downloaded") or intelligence.get("buyer_pack_verified"))
        and _truthy(intelligence.get("boq_detected"))
        and _truthy(intelligence.get("pricing_schedule_detected"))
        and _truthy(intelligence.get("returnables_detected"))
        and _truthy(intelligence.get("quote_pack_generated"))
    )


def _lifecycle_stage_label(item: Dict[str, Any], intelligence: Dict[str, Any] | None = None) -> str:
    state = _clean((item or {}).get("current_state") or (item or {}).get("lifecycle_state")).upper()
    intelligence = intelligence if isinstance(intelligence, dict) else summarize_rfq_document_intelligence(item or {})
    buyer_pack_downloaded = bool(intelligence.get("buyer_pack_downloaded"))
    boq_detected = bool(intelligence.get("boq_detected"))
    pricing_schedule_detected = bool(intelligence.get("pricing_schedule_detected"))
    returnables_detected = bool(intelligence.get("returnables_detected"))
    quote_pack_generated = bool(intelligence.get("quote_pack_generated"))
    quote_ready = bool(
        buyer_pack_downloaded
        and boq_detected
        and pricing_schedule_detected
        and returnables_detected
        and quote_pack_generated
    )
    submission_ready = quote_ready and (
        state in {"SUBMISSION_READY", "SUBMISSION_READY_MANUAL", "EXTERNALLY_SUBMITTED", "SUBMITTED", "PROOF_CAPTURED"}
        or _truthy((item or {}).get("submission_ready"))
    )
    if submission_ready:
        return "SUBMISSION READY"
    if quote_ready:
        return "QUOTE READY"
    if quote_pack_generated:
        return "QUOTE PACK GENERATED"
    if returnables_detected:
        return "RETURNABLES DETECTED"
    if pricing_schedule_detected:
        return "PRICING DETECTED"
    if boq_detected:
        return "BOQ DETECTED"
    if buyer_pack_downloaded:
        if _component_attempted(item or {}, "document_intelligence_report_path", "document_parse_summary_path", "boq_extraction_status", "pricing_schedule_extraction_status", "returnables_extraction_status"):
            return "DOCUMENTS CLASSIFIED"
        return "BUYER PACK ACQUIRED"
    return "DISCOVERED"


def _acquisition_readiness_components(item: Dict[str, Any], intelligence: Dict[str, Any]) -> Dict[str, int]:
    return {
        "buyer_pack": 20 if bool(intelligence.get("buyer_pack_downloaded")) else 0,
        "boq": 20 if bool(intelligence.get("boq_detected")) else 0,
        "pricing_schedule": 20 if bool(intelligence.get("pricing_schedule_detected")) else 0,
        "returnables": 20 if bool(intelligence.get("returnables_detected")) else 0,
        "quote_pack": 20 if bool(intelligence.get("quote_pack_generated")) else 0,
    }


def _list_has_content(value: Any) -> bool:
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict):
                if any(_clean(v) for v in row.values()):
                    return True
            elif _clean(row):
                return True
    return False


def _list_count(value: Any) -> int:
    if isinstance(value, list):
        return sum(1 for row in value if row not in (None, "", {}, []))
    return 0


def _path_size_bytes(path_value: Any) -> int:
    text = _clean(path_value)
    if not text:
        return 0
    try:
        path = Path(text)
        if not path.exists():
            return 0
        if path.is_file():
            return int(path.stat().st_size)
        if path.is_dir():
            total = 0
            for child in path.rglob("*"):
                if child.is_file():
                    total += int(child.stat().st_size)
            return total
    except Exception:
        return 0
    return 0


def _component_attempted(item: Dict[str, Any], *keys: str) -> bool:
    if any(_clean(item.get(key)) for key in keys):
        return True
    acquisition = item.get("document_acquisition_result")
    if isinstance(acquisition, dict):
        if any(_clean(acquisition.get(key)) for key in keys):
            return True
        for nested_key in ("downloaded_files", "prioritized_documents", "sbd_files", "specification_files", "pricing_schedule_files", "boq_candidate_files"):
            if _list_has_content(acquisition.get(nested_key)):
                return True
    return False


def summarize_rfq_document_intelligence(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "rfq_discovered": False,
            "buyer_pack_downloaded": False,
            "buyer_pack_download_failed": False,
            "buyer_pack_download_timestamp": "",
            "buyer_pack_source": "",
            "download_failure_reason": "",
            "boq_detected": False,
            "pricing_schedule_detected": False,
            "returnables_detected": False,
            "extraction_failure_reason": "",
            "eligibility_failure_reason": "",
            "quote_pack_generated": False,
            "quote_pack_readiness_score": 0,
            "buyer_pack_status": "not_attempted",
            "boq_status": "not_attempted",
            "pricing_schedule_status": "not_attempted",
            "returnables_status": "not_attempted",
            "quote_pack_status": "not_attempted",
            "quote_pack_readiness_components": {
                "buyer_pack": 0,
                "boq": 0,
                "pricing_schedule": 0,
                "returnables": 0,
            },
        }

    acquisition = item.get("document_acquisition_result")
    acquisition = acquisition if isinstance(acquisition, dict) else {}
    parse_summary = item.get("document_parse_summary") if isinstance(item.get("document_parse_summary"), dict) else {}
    docx_result = item.get("docx_main_document_intelligence_result") if isinstance(item.get("docx_main_document_intelligence_result"), dict) else {}
    zip_result = item.get("zip_content_extraction_result") if isinstance(item.get("zip_content_extraction_result"), dict) else {}

    rfq_discovered = _coalesce_bool(item, "rfq_discovered", True)
    buyer_pack_downloaded = _coalesce_bool(item, "buyer_pack_downloaded", _buyer_pack_downloaded(item))
    buyer_pack_verified = _coalesce_bool(item, "buyer_pack_verified", buyer_pack_downloaded)
    download_status = _clean(item.get("document_acquisition_status") or acquisition.get("status")).lower()
    buyer_pack_download_failed = _coalesce_bool(
        item,
        "buyer_pack_download_failed",
        download_status in {"document_acquisition_failed", "document_acquisition_blocked", "blocked", "failed", "error", "no_documents_downloaded"}
        or bool(_clean(item.get("download_failure_reason") or item.get("document_acquisition_failure_reason") or acquisition.get("error") or acquisition.get("message"))),
    )
    buyer_pack_download_timestamp = _first_text(
        item,
        ["buyer_pack_download_timestamp", "document_acquisition_timestamp", "document_download_timestamp", "downloaded_at", "acquired_at", "updated_at"],
        ["buyer_pack_download_timestamp", "document_acquisition_timestamp", "document_download_timestamp", "downloaded_at", "acquired_at", "updated_at"],
    )
    buyer_pack_source = _first_text(
        item,
        ["buyer_pack_source", "document_acquisition_source", "source_url", "detail_url", "document_url"],
        ["source_url", "detail_url", "document_url", "buyer_pack_path", "live_buyer_pack_path"],
    )
    download_failure_reason = _clean(
        item.get("download_failure_reason")
        or item.get("buyer_pack_download_failure_reason")
        or item.get("document_acquisition_failure_reason")
        or acquisition.get("error")
        or acquisition.get("message")
        or (download_status if buyer_pack_download_failed else "")
    )

    document_parse_attempted = any(
        _clean(item.get(key))
        for key in (
            "document_intelligence_report_path",
            "document_parse_summary_path",
            "boq_extraction_status",
            "pricing_schedule_extraction_status",
            "returnables_extraction_status",
        )
    ) or bool(parse_summary) or bool(docx_result) or bool(zip_result)

    boq_detection_confidence = max(
        _safe_float(item.get("boq_detection_confidence"), 0.0),
        _safe_float(parse_summary.get("boq_detection_confidence") or parse_summary.get("boq_confidence"), 0.0),
        _safe_float(docx_result.get("boq_detection_confidence") or docx_result.get("boq_confidence"), 0.0),
        _safe_float(zip_result.get("boq_detection_confidence") or zip_result.get("boq_confidence"), 0.0),
    )
    pricing_schedule_detection_confidence = max(
        _safe_float(item.get("pricing_schedule_detection_confidence"), 0.0),
        _safe_float(parse_summary.get("pricing_schedule_detection_confidence") or parse_summary.get("pricing_schedule_confidence"), 0.0),
        _safe_float(docx_result.get("pricing_schedule_detection_confidence") or docx_result.get("pricing_schedule_confidence"), 0.0),
        _safe_float(zip_result.get("pricing_schedule_detection_confidence") or zip_result.get("pricing_schedule_confidence"), 0.0),
    )
    returnables_detection_confidence = max(
        _safe_float(item.get("returnables_detection_confidence"), 0.0),
        _safe_float(parse_summary.get("returnables_detection_confidence") or parse_summary.get("commercial_returnables_confidence"), 0.0),
        _safe_float(docx_result.get("returnables_detection_confidence"), 0.0),
        _safe_float(zip_result.get("returnables_detection_confidence") or zip_result.get("commercial_returnable_confidence"), 0.0),
    )

    boq_detection_reason = _clean(
        item.get("boq_detection_reason")
        or parse_summary.get("boq_detection_reason")
        or docx_result.get("boq_detection_reason")
        or zip_result.get("boq_detection_reason")
    )
    pricing_schedule_detection_reason = _clean(
        item.get("pricing_schedule_detection_reason")
        or parse_summary.get("pricing_schedule_detection_reason")
        or docx_result.get("pricing_schedule_detection_reason")
        or zip_result.get("pricing_schedule_detection_reason")
    )
    returnables_detection_reason = _clean(
        item.get("returnables_detection_reason")
        or parse_summary.get("returnables_detection_reason")
        or docx_result.get("returnables_detection_reason")
        or zip_result.get("returnables_detection_reason")
    )

    boq_detected = _coalesce_bool(
        item,
        "boq_detected",
        bool(_list_has_content(item.get("boqs")))
        or bool(_list_has_content(item.get("boq_candidate_paths")))
        or bool(_list_has_content(zip_result.get("boq_candidate_paths")))
        or bool(_list_has_content(((zip_result.get("classified_files") or {}).get("boq_candidate_files")) if isinstance(zip_result.get("classified_files"), dict) else []))
        or _truthy(parse_summary.get("boq_detected"))
        or _truthy(parse_summary.get("has_boq"))
        or _truthy(docx_result.get("boq_detected"))
        or _truthy(zip_result.get("boq_detected"))
        or boq_detection_confidence >= 0.55,
    )
    pricing_schedule_detected = _coalesce_bool(
        item,
        "pricing_schedule_detected",
        bool(_list_has_content(item.get("pricing_schedules")))
        or bool(_list_has_content(item.get("pricing_schedule_paths")))
        or bool(_list_has_content(zip_result.get("pricing_schedule_paths")))
        or bool(_list_has_content(((zip_result.get("classified_files") or {}).get("pricing_schedule_files")) if isinstance(zip_result.get("classified_files"), dict) else []))
        or _truthy(parse_summary.get("pricing_schedule_detected"))
        or _truthy(parse_summary.get("pricing_schedule"))
        or _truthy(docx_result.get("pricing_schedule_detected"))
        or _truthy(zip_result.get("pricing_schedule_detected"))
        or pricing_schedule_detection_confidence >= 0.55,
    )
    returnables_detected = _coalesce_bool(
        item,
        "returnables_detected",
        bool(_list_has_content(item.get("returnable_files")))
        or bool(_list_has_content(item.get("sbd_document_paths")))
        or bool(_list_has_content(zip_result.get("sbd_document_paths")))
        or bool(_list_has_content(((zip_result.get("classified_files") or {}).get("sbd_files")) if isinstance(zip_result.get("classified_files"), dict) else []))
        or _truthy(parse_summary.get("sbd_detected"))
        or _truthy(parse_summary.get("sbd_or_returnables_detected"))
        or _truthy(docx_result.get("returnables_detected"))
        or _truthy(zip_result.get("returnables_detected"))
        or returnables_detection_confidence >= 0.45,
    )
    quote_pack_path = _clean(item.get("quote_pack_path") or item.get("quote_pack_workspace") or item.get("quote_pack_pdf_path"))
    quote_pack_artifact_exists = _coalesce_bool(
        item,
        "quote_pack_artifact_exists",
        bool(quote_pack_path) and _path_size_bytes(quote_pack_path) > 0,
    )
    quote_pack_artifact_size_bytes = int(
        _safe_float(item.get("quote_pack_artifact_size_bytes"), 0.0)
        or _path_size_bytes(quote_pack_path)
    )
    quote_pack_generated = _coalesce_bool(
        item,
        "quote_pack_generated",
        quote_pack_artifact_exists,
    )
    if quote_pack_generated and not quote_pack_artifact_exists:
        quote_pack_generated = False
    quote_pack_generation_diagnostics = item.get("quote_pack_generation_diagnostics")
    if not isinstance(quote_pack_generation_diagnostics, dict):
        quote_pack_generation_diagnostics = {}

    extraction_failure_reason = _clean(
        item.get("extraction_failure_reason")
        or item.get("document_extraction_failure_reason")
        or item.get("document_parse_failure_reason")
    )
    extraction_tokens: List[str] = []
    if buyer_pack_downloaded and document_parse_attempted:
        if not boq_detected:
            extraction_tokens.append("boq_not_detected")
        if not pricing_schedule_detected:
            extraction_tokens.append("pricing_schedule_not_detected")
        if not returnables_detected:
            extraction_tokens.append("returnables_not_detected")
    if not extraction_failure_reason and extraction_tokens:
        extraction_failure_reason = ";".join(extraction_tokens)

    eligibility_reason_blob = " ".join(
        _clean(value)
        for value in (
            item.get("eligibility_failure_reason"),
            item.get("eligibility_reason"),
            item.get("rejection_reason"),
            item.get("qualification_reason"),
        )
        if _clean(value)
    )
    qualification_summary = item.get("qualification_summary")
    if isinstance(qualification_summary, dict):
        eligibility_reason_blob = " ".join(
            part
            for part in [eligibility_reason_blob, " ".join(_clean(v) for v in _safe_list(qualification_summary.get("reasons"))), " ".join(_clean(v) for v in _safe_list(qualification_summary.get("rejection_reasons")))]
            if part
        ).strip()

    eligibility_failure_reason = _clean(
        item.get("eligibility_failure_reason")
        or item.get("eligibility_reason")
        or item.get("rejection_reason")
        or item.get("qualification_reason")
    )
    if not eligibility_failure_reason and eligibility_reason_blob:
        eligibility_failure_reason = eligibility_reason_blob

    buyer_pack_attempted = _component_attempted(
        item,
        "buyer_pack_path",
        "live_buyer_pack_path",
        "document_acquisition_report_path",
        "buyer_pack_download_timestamp",
        "document_acquisition_timestamp",
        "download_failure_reason",
        "document_acquisition_status",
    ) or bool(acquisition)
    boq_attempted = _component_attempted(
        item,
        "boq_detected",
        "boq_extraction_status",
        "document_intelligence_report_path",
    )
    pricing_attempted = _component_attempted(
        item,
        "pricing_schedule_detected",
        "pricing_schedule_extraction_status",
        "document_intelligence_report_path",
    )
    returnables_attempted = _component_attempted(
        item,
        "returnables_detected",
        "returnables_extraction_status",
        "document_intelligence_report_path",
    )
    quote_pack_attempted = _component_attempted(
        item,
        "quote_pack_path",
        "quote_pack_workspace",
        "quote_pack_dir",
        "quote_pack_json_path",
        "quote_pack_pdf_path",
        "submission_package",
    ) or bool(quote_pack_generated)

    buyer_pack_status = _status_from_components(
        complete=buyer_pack_downloaded,
        failed=buyer_pack_download_failed,
        attempted=buyer_pack_attempted,
        complete_label="downloaded",
    )
    boq_status = _status_from_components(
        complete=boq_detected,
        failed=boq_attempted and not boq_detected,
        attempted=boq_attempted or buyer_pack_downloaded,
        complete_label="detected",
    )
    pricing_status = _status_from_components(
        complete=pricing_schedule_detected,
        failed=pricing_attempted and not pricing_schedule_detected,
        attempted=pricing_attempted or buyer_pack_downloaded,
        complete_label="detected",
    )
    returnables_status = _status_from_components(
        complete=returnables_detected,
        failed=returnables_attempted and not returnables_detected,
        attempted=returnables_attempted or buyer_pack_downloaded,
        complete_label="detected",
    )
    quote_pack_status = _status_from_components(
        complete=quote_pack_generated,
        failed=bool(_clean(item.get("quote_pack_generation_failure_reason") or item.get("quote_pack_failure_reason"))) or (quote_pack_attempted and not quote_pack_generated),
        attempted=quote_pack_attempted or buyer_pack_downloaded,
        complete_label="generated",
    )

    readiness_components = _acquisition_readiness_components(
        item,
        {
            "buyer_pack_downloaded": buyer_pack_downloaded,
            "boq_detected": boq_detected,
            "pricing_schedule_detected": pricing_schedule_detected,
            "returnables_detected": returnables_detected,
            "quote_pack_generated": quote_pack_generated,
        },
    )
    readiness_score = sum(readiness_components.values())
    quote_ready_allowed = bool(
        buyer_pack_downloaded and boq_detected and pricing_schedule_detected and returnables_detected and quote_pack_generated
    )
    lifecycle_stage = _lifecycle_stage_label(
        {
            **item,
            "buyer_pack_downloaded": buyer_pack_downloaded,
            "boq_detected": boq_detected,
            "pricing_schedule_detected": pricing_schedule_detected,
            "returnables_detected": returnables_detected,
            "quote_pack_generated": quote_pack_generated,
            "submission_status": item.get("submission_status"),
            "current_state": item.get("current_state"),
        },
        {
            "buyer_pack_downloaded": buyer_pack_downloaded,
            "boq_detected": boq_detected,
            "pricing_schedule_detected": pricing_schedule_detected,
            "returnables_detected": returnables_detected,
            "quote_pack_generated": quote_pack_generated,
        },
    )

    artifact_count = int(
        item.get("artifact_count")
        or zip_result.get("artifact_count")
        or _list_count(item.get("document_paths"))
        or _list_count(zip_result.get("document_inventory_paths_limited"))
        or 0
    )
    pdf_count = int(item.get("pdf_count") or zip_result.get("pdf_count") or 0)
    docx_count = int(item.get("docx_count") or zip_result.get("docx_count") or 0)
    xlsx_count = int(item.get("xlsx_count") or zip_result.get("xlsx_count") or 0)
    zip_count = int(item.get("zip_count") or zip_result.get("zip_count") or 0)
    csv_count = int(item.get("csv_count") or zip_result.get("csv_count") or 0)
    extracted_file_count = int(item.get("extracted_file_count") or zip_result.get("extracted_file_count") or 0)
    detected_document_types = item.get("detected_document_types") if isinstance(item.get("detected_document_types"), list) else zip_result.get("detected_document_types")
    document_inventory_paths_limited = (
        item.get("document_inventory_paths_limited")
        if isinstance(item.get("document_inventory_paths_limited"), list)
        else zip_result.get("document_inventory_paths_limited")
    )
    document_inventory_paths_limited = document_inventory_paths_limited if isinstance(document_inventory_paths_limited, list) else []

    return {
        "rfq_discovered": rfq_discovered,
        "buyer_pack_downloaded": buyer_pack_downloaded,
        "buyer_pack_verified": buyer_pack_verified,
        "buyer_pack_download_failed": buyer_pack_download_failed,
        "buyer_pack_download_timestamp": buyer_pack_download_timestamp,
        "buyer_pack_source": buyer_pack_source,
        "download_failure_reason": download_failure_reason,
        "boq_detected": boq_detected,
        "pricing_schedule_detected": pricing_schedule_detected,
        "returnables_detected": returnables_detected,
        "boq_detection_confidence": round(boq_detection_confidence, 4),
        "pricing_schedule_detection_confidence": round(pricing_schedule_detection_confidence, 4),
        "returnables_detection_confidence": round(returnables_detection_confidence, 4),
        "boq_detection_reason": boq_detection_reason,
        "pricing_schedule_detection_reason": pricing_schedule_detection_reason,
        "returnables_detection_reason": returnables_detection_reason,
        "extraction_failure_reason": extraction_failure_reason,
        "eligibility_failure_reason": eligibility_failure_reason,
        "quote_pack_generated": quote_pack_generated,
        "quote_pack_artifact_exists": quote_pack_artifact_exists,
        "quote_pack_artifact_size_bytes": quote_pack_artifact_size_bytes,
        "quote_pack_generation_diagnostics": quote_pack_generation_diagnostics,
        "quote_pack_readiness_score": readiness_score,
        "artifact_count": artifact_count,
        "pdf_count": pdf_count,
        "docx_count": docx_count,
        "xlsx_count": xlsx_count,
        "zip_count": zip_count,
        "csv_count": csv_count,
        "extracted_file_count": extracted_file_count,
        "main_document_path": _clean(item.get("main_document_path") or zip_result.get("main_document_path") or acquisition.get("main_document_path")),
        "quote_pack_path": quote_pack_path,
        "detected_document_types": detected_document_types if isinstance(detected_document_types, list) else [],
        "document_inventory_paths_limited": document_inventory_paths_limited[:25],
        "buyer_pack_status": buyer_pack_status,
        "boq_status": boq_status,
        "pricing_schedule_status": pricing_status,
        "returnables_status": returnables_status,
        "quote_pack_status": quote_pack_status,
        "acquisition_readiness_score": readiness_score,
        "acquisition_readiness_components": readiness_components,
        "quote_ready_allowed": quote_ready_allowed,
        "lifecycle_stage": lifecycle_stage,
        "lifecycle_stage_label": lifecycle_stage,
        "quote_pack_readiness_score": readiness_score,
        "quote_pack_readiness_components": readiness_components,
    }


def _buyer_pack_downloaded(item: Dict[str, Any]) -> bool:
    if bool(item.get("buyer_pack_downloaded")) or bool(item.get("buyer_pack_verified")):
        return True

    status = _clean(item.get("document_acquisition_status")).lower()
    if status in {"buyer_pack_verified", "buyer_pack_downloaded", "downloaded", "verified", "completed"}:
        return True

    for key in ("buyer_pack_path", "live_buyer_pack_path", "document_acquisition_report_path"):
        if _clean(item.get(key)):
            return True

    acquisition = item.get("document_acquisition_result")
    if isinstance(acquisition, dict):
        for key in (
            "buyer_pack_path",
            "live_buyer_pack_path",
            "main_document_path",
            "document_acquisition_report_path",
        ):
            if _clean(acquisition.get(key)):
                return True

        downloaded_files = acquisition.get("downloaded_files")
        if isinstance(downloaded_files, list):
            for downloaded in downloaded_files:
                if isinstance(downloaded, dict) and _clean(downloaded.get("path")):
                    return True

        prioritized_documents = acquisition.get("prioritized_documents")
        if isinstance(prioritized_documents, list):
            for downloaded in prioritized_documents:
                if isinstance(downloaded, dict) and _clean(downloaded.get("path")):
                    return True

    return False


def _rfq_identifier(item: Dict[str, Any]) -> str:
    for key in ("buyer_rfq_number", "rfq_number", "reference_number", "document_number", "quote_number", "title"):
        value = _clean(item.get(key))
        if value:
            return value
    return _clean(item.get("source_url")) or _clean(item.get("title")) or "rfq"


def _is_acquisition_blocked(item: Dict[str, Any]) -> bool:
    status = _clean(item.get("document_acquisition_status")).lower()
    return status in {
        "document_acquisition_blocked",
        "blocked",
        "no_documents_downloaded",
        "failed",
        "document_acquisition_failed",
    }


def _is_qualified_for_acquisition(item: Dict[str, Any]) -> bool:
    archived = _clean(item.get("status")).lower() == "archived"
    closing_date = _parse_date(item.get("closing_date"))
    profit = _safe_float(item.get("estimated_profit"), 0.0)
    briefing_required = bool(item.get("briefing_required"))
    if archived or briefing_required or profit < 30000:
        return False
    if closing_date is None:
        return False
    return closing_date.date() > datetime.now(timezone.utc).date()


def _buyer_pack_path(item: Dict[str, Any]) -> str:
    for key in ("buyer_pack_path", "live_buyer_pack_path", "document_acquisition_report_path"):
        value = _clean(item.get(key))
        if value:
            return value

    acquisition = item.get("document_acquisition_result")
    if isinstance(acquisition, dict):
        for key in ("buyer_pack_path", "live_buyer_pack_path", "main_document_path", "document_acquisition_report_path"):
            value = _clean(acquisition.get(key))
            if value:
                return value
        downloaded_files = acquisition.get("downloaded_files")
        if isinstance(downloaded_files, list):
            for downloaded in downloaded_files:
                if isinstance(downloaded, dict):
                    value = _clean(downloaded.get("path"))
                    if value:
                        return value
    return ""


def _search_blob(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in (
        "title",
        "buyer_name",
        "description",
        "scope",
        "category",
        "submission_method",
        "notes",
        "document_url",
        "detail_url",
        "source_url",
    ):
        value = _clean(item.get(key))
        if value:
            parts.append(value)
    acquisition = item.get("document_acquisition_result")
    if isinstance(acquisition, dict):
        for key in ("title", "buyer_name", "buyer_rfq_number", "report_path", "live_buyer_pack_path", "main_document_path"):
            value = _clean(acquisition.get(key))
            if value:
                parts.append(value)
        for key in ("pricing_schedule_files", "boq_candidate_files", "sbd_files", "specification_files"):
            value = acquisition.get(key)
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict):
                        parts.extend(_clean(v) for v in row.values() if _clean(v))
    return " ".join(parts).lower()


def _has_quantity_evidence(item: Dict[str, Any]) -> bool:
    line_items = item.get("line_items")
    if isinstance(line_items, list):
        for row in line_items:
            if isinstance(row, dict) and (
                _clean(row.get("quantity"))
                or _clean(row.get("unit"))
                or _clean(row.get("uom"))
                or _clean(row.get("description"))
            ):
                return True

    items = item.get("items")
    if isinstance(items, list):
        for row in items:
            if isinstance(row, dict) and (
                _clean(row.get("quantity"))
                or _clean(row.get("unit"))
                or _clean(row.get("uom"))
                or _clean(row.get("description"))
            ):
                return True

    acquisition = item.get("document_acquisition_result")
    if isinstance(acquisition, dict):
        for key in ("pricing_schedule_files", "boq_candidate_files"):
            files = acquisition.get(key)
            if isinstance(files, list) and any(isinstance(row, dict) for row in files):
                return True
        for key in ("main_document_path", "live_buyer_pack_path"):
            if _clean(acquisition.get(key)):
                return True

    return False


def _procurement_shape(item: Dict[str, Any]) -> str:
    blob = _search_blob(item)
    engineering_hits = sum(
        1
        for term in (
            "engineering services",
            "engineering design",
            "engineering consultancy",
            "engineering consultant",
            "electrical engineering",
            "mechanical engineering",
            "civil engineering",
            "structural engineering",
        )
        if term in blob
    )
    professional_hits = sum(
        1
        for term in (
            "professional services",
            "consulting",
            "consultancy",
            "advisory",
            "advisory services",
            "design",
            "architect",
            "project management",
            "feasibility study",
            "strategy",
        )
        if term in blob
    )
    supply_hits = sum(
        1
        for term in (
            "supply and delivery",
            "supply & delivery",
            "supply, delivery",
            "delivery of",
            "supply of",
            "procurement of",
            "purchase of",
            "goods",
            "materials",
            "equipment",
        )
        if term in blob
    )
    if supply_hits > 0 and engineering_hits == 0 and professional_hits == 0:
        return "supply_delivery"
    if supply_hits > 0 and (engineering_hits > 0 or professional_hits > 0):
        return "mixed_or_ambiguous"
    if engineering_hits > 0 and professional_hits == 0:
        return "engineering_services"
    if professional_hits > 0 and engineering_hits == 0:
        return "professional_services"
    if engineering_hits > 0 and professional_hits > 0:
        return "mixed_or_ambiguous"
    return "unknown"


def _shape_label(shape: str) -> str:
    mapping = {
        "supply_delivery": "Supply & Delivery",
        "professional_services": "Professional Services",
        "engineering_services": "Engineering Services",
        "consulting": "Consulting",
        "construction": "Construction",
        "mixed_or_ambiguous": "Mixed / Ambiguous",
        "unknown": "Other",
    }
    return mapping.get(shape, "Other")


def _supply_delivery_submission_shape(item: Dict[str, Any]) -> bool:
    blob = _search_blob(item)
    if _procurement_shape(item) != "supply_delivery":
        return False
    if any(term in blob for term in ("compulsory briefing", "mandatory briefing", "briefing required", "site meeting required")):
        return False
    if any(term in blob for term in ("engineering services", "professional services", "consulting", "consultancy", "design services")):
        return False
    return True


def _benchmark_candidate(item: Dict[str, Any]) -> bool:
    return (
        _buyer_pack_downloaded(item)
        and _supply_delivery_submission_shape(item)
        and _has_quantity_evidence(item)
        and _is_qualified_for_acquisition(item)
    )


def _safe_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _load_store() -> Dict[str, Any]:
    if not LIVE_RFQ_STORE_PATH.exists():
        return {"status": "ok", "updated_at": _now_iso(), "count": 0, "items": []}
    try:
        data = json.loads(LIVE_RFQ_STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"status": "ok", "updated_at": _now_iso(), "count": 0, "items": []}
        items = data.get("items")
        if not isinstance(items, list):
            data["items"] = []
        data["count"] = len(data.get("items", []))
        return data
    except Exception as exc:
        logger.warning("Failed to load live RFQ store: %s", exc)
        return {"status": "ok", "updated_at": _now_iso(), "count": 0, "items": []}


def _save_store(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {
        "status": "ok",
        "updated_at": _now_iso(),
        "count": len(items),
        "items": items,
    }
    LIVE_RFQ_STORE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _rfq_key(item: Dict[str, Any]) -> str:
    for key in (
        "buyer_rfq_number",
        "rfq_number",
        "reference_number",
        "document_number",
        "quote_number",
        "title",
    ):
        value = _clean(item.get(key))
        if value:
            return value.lower()
    return _clean(item.get("source_url")).lower() + "|" + _clean(item.get("title")).lower()


def _merge_rfq(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(old)
    merged.update({k: v for k, v in new.items() if v not in (None, "")})

    # Resolver-confirmed eTenders fields must overwrite stale listing-page values.
    if str(new.get("v50_8_extended_resolution_status") or "").strip().lower() in {
        "verified_document",
        "verified_tenderdetails_document",
    }:
        for key in (
            "detail_url",
            "document_url",
            "v50_8_discovered_tender_id",
            "v50_8_extended_resolution_status",
            "v50_8_extended_resolution_summary",
            "v50_8_extended_resolution",
            "v50_9_1_tenderdetails_inspect_result",
            "v50_9_6_hidden_api_result",
            "downloaded_document_paths",
            "downloaded_document_path",
            "buyer_pack_path",
            "live_buyer_pack_path",
        ):
            value = new.get(key)
            if value not in (None, "", [], {}):
                merged[key] = value

    merged["updated_at"] = _now_iso()
    if "created_at" not in merged:
        merged["created_at"] = _now_iso()
    merged.update(summarize_rfq_document_intelligence(merged))
    return merged


def get_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def read_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def list_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def save_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = _safe_list(items)
    for item in items:
        item.setdefault("created_at", _now_iso())
        item["updated_at"] = _now_iso()
        item.update(summarize_rfq_document_intelligence(item))
    return _save_store(items)


def replace_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return save_live_rfqs(items)


def append_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def append_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return promote_live_rfqs(items)


def upsert_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    existing = _load_store()
    items = existing.get("items", [])
    item = dict(item or {})
    item.setdefault("created_at", _now_iso())
    item["updated_at"] = _now_iso()
    item.update(summarize_rfq_document_intelligence(item))

    target_key = _rfq_key(item)
    replaced = False
    output: List[Dict[str, Any]] = []
    for current in items:
        if _rfq_key(current) == target_key:
            output.append(_merge_rfq(current, item))
            replaced = True
        else:
            output.append(current)

    if not replaced:
        output.append(item)

    saved = _save_store(output)
    saved["action"] = "updated" if replaced else "inserted"
    saved["rfq_key"] = target_key
    return saved


def upsert_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def save_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def persist_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def promote_rfq_to_live_store(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def promote_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = _safe_list(items)
    existing = _load_store()
    current_items = existing.get("items", [])
    indexed = {_rfq_key(item): item for item in current_items}

    for item in items:
        row = dict(item)
        if (
            bool(row.get("eligible"))
            and str(row.get("pipeline_status") or "").strip().lower() == "quantity_verification_required"
        ):
            row["quote_ready"] = True
        row.setdefault("created_at", _now_iso())
        row["updated_at"] = _now_iso()
        key = _rfq_key(row)
        if key in indexed:
            indexed[key] = _merge_rfq(indexed[key], row)
        else:
            row.update(summarize_rfq_document_intelligence(row))
            indexed[key] = row

    saved = _save_store(list(indexed.values()))
    saved["action"] = "promoted"
    saved["promoted_count"] = len(items)
    return saved


def delete_live_rfq(rfq_key: str) -> Dict[str, Any]:
    existing = _load_store()
    items = existing.get("items", [])
    rfq_key = _clean(rfq_key).lower()
    kept = [item for item in items if _rfq_key(item) != rfq_key]
    saved = _save_store(kept)
    saved["action"] = "deleted"
    saved["rfq_key"] = rfq_key
    return saved


def clear_live_rfqs() -> Dict[str, Any]:
    return _save_store([])


def get_buyer_pack_acquisition_report() -> Dict[str, Any]:
    data = _load_store()
    items = data.get("items", [])

    qualified_items = [item for item in items if _is_qualified_for_acquisition(item)]
    verified_items = [item for item in qualified_items if _buyer_pack_downloaded(item)]
    blocked_items = [item for item in qualified_items if not _buyer_pack_downloaded(item) and _is_acquisition_blocked(item)]
    pending_items = [
        item for item in qualified_items
        if not _buyer_pack_downloaded(item) and not _is_acquisition_blocked(item)
    ]

    qualified_count = len(qualified_items)
    verified_count = len(verified_items)

    return {
        "status": "ok",
        "timestamp": _now_iso(),
        "qualified_rfqs": qualified_count,
        "buyer_pack_verified": verified_count,
        "acquisition_pending": len(pending_items),
        "acquisition_blocked": len(blocked_items),
        "acquisition_success_rate": round((verified_count / max(qualified_count, 1)) * 100.0, 2),
        "qualification_rule": {
            "closing_date": "future",
            "estimated_profit_minimum": 30000.0,
            "briefing_required": False,
            "status_excluded": ["archived"],
        },
    }


def get_document_intelligence_funnel_metrics() -> Dict[str, Any]:
    data = _load_store()
    items = data.get("items", [])
    discovered = 0
    buyer_pack = 0
    boq = 0
    pricing = 0
    returnables = 0
    quote_pack = 0
    quote_ready = 0
    failures = {
        "buyer_pack_failure": 0,
        "boq_detection_failure": 0,
        "pricing_detection_failure": 0,
        "returnables_detection_failure": 0,
        "quote_pack_generation_failure": 0,
    }

    for item in items:
        intelligence = summarize_rfq_document_intelligence(item)
        if bool(intelligence.get("rfq_discovered", True)):
            discovered += 1
        if intelligence.get("buyer_pack_status") == "downloaded":
            buyer_pack += 1
        elif intelligence.get("buyer_pack_status") == "failed":
            failures["buyer_pack_failure"] += 1
        if intelligence.get("boq_status") == "detected":
            boq += 1
        elif intelligence.get("boq_status") == "failed":
            failures["boq_detection_failure"] += 1
        if intelligence.get("pricing_schedule_status") == "detected":
            pricing += 1
        elif intelligence.get("pricing_schedule_status") == "failed":
            failures["pricing_detection_failure"] += 1
        if intelligence.get("returnables_status") == "detected":
            returnables += 1
        elif intelligence.get("returnables_status") == "failed":
            failures["returnables_detection_failure"] += 1
        if intelligence.get("quote_pack_status") == "generated":
            quote_pack += 1
        elif intelligence.get("quote_pack_status") == "failed":
            failures["quote_pack_generation_failure"] += 1
        if (
            intelligence.get("buyer_pack_status") == "downloaded"
            and intelligence.get("boq_status") == "detected"
            and intelligence.get("pricing_schedule_status") == "detected"
            and intelligence.get("returnables_status") == "detected"
            and intelligence.get("quote_pack_status") == "generated"
        ):
            quote_ready += 1

    return {
        "status": "ok",
        "timestamp": _now_iso(),
        "discovered_count": discovered,
        "buyer_pack_count": buyer_pack,
        "boq_count": boq,
        "pricing_count": pricing,
        "returnables_count": returnables,
        "quote_pack_count": quote_pack,
        "quote_ready_count": quote_ready,
        **failures,
    }


def get_external_submission_candidate_queue(limit: int = 3) -> Dict[str, Any]:
    data = _load_store()
    items = data.get("items", [])

    candidates = [
        item for item in items
        if _is_qualified_for_acquisition(item) and _buyer_pack_downloaded(item)
    ]
    candidates = sorted(
        candidates,
        key=lambda item: (
            -_safe_float(item.get("estimated_profit"), 0.0),
            _parse_date(item.get("closing_date")) or datetime.max,
            _clean(item.get("buyer_name")).lower(),
            _rfq_identifier(item).lower(),
        ),
    )

    queue: List[Dict[str, Any]] = []
    for index, item in enumerate(candidates[: max(1, int(limit or 3))], start=1):
        queue.append(
            {
                "priority": index,
                "rfq_id": _rfq_identifier(item),
                "buyer": _clean(item.get("buyer_name")),
                "closing_date": _clean(item.get("closing_date")),
                "profit_estimate": _safe_float(item.get("estimated_profit"), 0.0),
                "buyer_pack_path": _buyer_pack_path(item),
                "verification_status": _clean(item.get("document_acquisition_status")) or (
                    "buyer_pack_verified" if _buyer_pack_downloaded(item) else "document_acquisition_pending"
                ),
            }
        )

    return {
        "status": "ok",
        "timestamp": _now_iso(),
        "count": len(queue),
        "items": queue,
        "filter": {
            "buyer_pack_verified": True,
            "closing_date": "future",
            "estimated_profit_minimum": 30000.0,
            "briefing_required": False,
            "status_excluded": ["archived"],
        },
    }


def get_benchmark_candidate_search(limit: int = 5) -> Dict[str, Any]:
    data = _load_store()
    items = data.get("items", [])

    candidates = []
    for item in items:
        if not _buyer_pack_downloaded(item):
            continue
        if not _supply_delivery_submission_shape(item):
            continue
        if not _has_quantity_evidence(item):
            continue
        if not _is_qualified_for_acquisition(item):
            continue
        candidates.append(item)

    candidates = sorted(
        candidates,
        key=lambda item: (
            -_safe_float(item.get("estimated_profit"), 0.0),
            _parse_date(item.get("closing_date")) or datetime.max,
            _clean(item.get("buyer_name")).lower(),
            _rfq_identifier(item).lower(),
        ),
    )

    queue: List[Dict[str, Any]] = []
    for index, item in enumerate(candidates[: max(1, int(limit or 5))], start=1):
        queue.append(
            {
                "priority": index,
                "rfq_id": _rfq_identifier(item),
                "buyer": _clean(item.get("buyer_name")),
                "closing_date": _clean(item.get("closing_date")),
                "profit_estimate": _safe_float(item.get("estimated_profit"), 0.0),
                "buyer_pack_path": _buyer_pack_path(item),
                "procurement_shape": _procurement_shape(item),
                "quantity_verification_possible": _has_quantity_evidence(item),
                "buyer_pack_verified": _buyer_pack_downloaded(item),
            }
        )

    return {
        "status": "ok",
        "timestamp": _now_iso(),
        "count": len(queue),
        "items": queue,
        "filter": {
            "buyer_pack_verified": True,
            "supply_delivery_submission_shape": True,
            "quantity_verification_possible": True,
            "closing_date": "future",
            "briefing_required": False,
            "estimated_profit_minimum": 30000.0,
        },
    }


def get_procurement_shape_distribution_report() -> Dict[str, Any]:
    data = _load_store()
    items = data.get("items", [])

    buckets = {
        "supply_delivery": 0,
        "professional_services": 0,
        "engineering_services": 0,
        "consulting": 0,
        "construction": 0,
        "mixed_or_ambiguous": 0,
        "unknown": 0,
    }
    verified_buckets = dict.fromkeys(buckets.keys(), 0)
    benchmark_candidate_count = 0

    for item in items:
        shape = _procurement_shape(item)
        buckets[shape] = buckets.get(shape, 0) + 1
        if _buyer_pack_downloaded(item):
            verified_buckets[shape] = verified_buckets.get(shape, 0) + 1
        if _benchmark_candidate(item):
            benchmark_candidate_count += 1

    return {
        "status": "ok",
        "timestamp": _now_iso(),
        "live_rfqs": len(items),
        "benchmark_candidate_count": benchmark_candidate_count,
        "benchmark_conversion_pct": round((benchmark_candidate_count / max(sum(verified_buckets.values()), 1)) * 100.0, 2),
        "shape_distribution": {
            _shape_label(key): value for key, value in buckets.items()
        },
        "buyer_pack_verified_shape_distribution": {
            _shape_label(key): value for key, value in verified_buckets.items()
        },
    }


def get_source_shape_performance_report(limit: int = 10) -> Dict[str, Any]:
    data = _load_store()
    items = data.get("items", [])
    source_rows: Dict[str, Dict[str, Any]] = {}

    for item in items:
        source_name = _clean(item.get("source_name") or item.get("source") or item.get("buyer_name") or "unknown")
        if source_name not in source_rows:
            source_rows[source_name] = {
                "source_name": source_name,
                "live_rfqs": 0,
                "buyer_pack_verified": 0,
                "benchmark_candidates": 0,
                "shape_distribution": {
                    "Supply & Delivery": 0,
                    "Professional Services": 0,
                    "Engineering Services": 0,
                    "Consulting": 0,
                    "Construction": 0,
                    "Mixed / Ambiguous": 0,
                    "Other": 0,
                },
            }

        row = source_rows[source_name]
        shape = _shape_label(_procurement_shape(item))
        row["live_rfqs"] += 1
        row["shape_distribution"][shape] = row["shape_distribution"].get(shape, 0) + 1
        if _buyer_pack_downloaded(item):
            row["buyer_pack_verified"] += 1
        if _benchmark_candidate(item):
            row["benchmark_candidates"] += 1

    rows = list(source_rows.values())
    for row in rows:
        verified = max(row["buyer_pack_verified"], 1)
        row["benchmark_conversion_pct"] = round((row["benchmark_candidates"] / verified) * 100.0, 2)
        row["supply_delivery_share_pct"] = round((row["shape_distribution"]["Supply & Delivery"] / max(row["live_rfqs"], 1)) * 100.0, 2)
        row["benchmark_quality_score"] = round(
            (row["benchmark_candidates"] * 100.0)
            + (row["shape_distribution"]["Supply & Delivery"] * 10.0)
            - (row["shape_distribution"]["Professional Services"] * 4.0)
            - (row["shape_distribution"]["Engineering Services"] * 4.0)
            - (row["shape_distribution"]["Consulting"] * 4.0)
            - (row["shape_distribution"]["Construction"] * 4.0),
            2,
        )

    rows.sort(key=lambda row: (row["benchmark_quality_score"], row["benchmark_candidates"], row["supply_delivery_share_pct"], row["live_rfqs"], row["source_name"]), reverse=True)

    return {
        "status": "ok",
        "timestamp": _now_iso(),
        "source_count": len(rows),
        "top_sources": rows[: max(1, limit)],
        "all_sources": rows,
        "shape_labels": [
            "Supply & Delivery",
            "Professional Services",
            "Engineering Services",
            "Consulting",
            "Construction",
            "Mixed / Ambiguous",
            "Other",
        ],
    }


# =============================================================================
# COMPATIBILITY SHIM FOR API IMPORTS
# =============================================================================

class LiveRFQStore:
    """
    Compatibility wrapper for older API code that imports LiveRFQStore as a class.
    Maps class-style calls to the function-based live RFQ store already in this file.
    """

    @staticmethod
    def _call_first(names, *args, **kwargs):
        for name in names:
            func = globals().get(name)
            if callable(func):
                return func(*args, **kwargs)
        return None

    @staticmethod
    def get_all() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "get_live_rfqs",
                "get_all_live_rfqs",
                "load_live_rfqs",
                "read_live_rfqs",
            ]
        )
        if isinstance(result, dict):
            return result
        if callable(globals().get("_load_store")):
            return _load_store()
        return {"updated_at": _now_iso(), "count": 0, "items": []}

    @staticmethod
    def get_filtered_from_store() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "get_filtered_live_rfqs",
                "get_filtered_rfqs",
                "filter_live_rfqs",
            ]
        )
        if isinstance(result, dict):
            return result

        data = LiveRFQStore.get_all()
        items = data.get("items", [])
        filtered_items = [
            item for item in items
            if not bool(item.get("blocked", False))
        ]

        return {
            "updated_at": data.get("updated_at", _now_iso()),
            "count": len(filtered_items),
            "items": filtered_items,
        }

    @staticmethod
    def get_scored_from_store() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "get_scored_live_rfqs",
                "score_live_rfqs_from_store",
                "get_recommended_live_rfqs",
            ]
        )
        if isinstance(result, dict):
            return result

        data = LiveRFQStore.get_filtered_from_store()
        items = data.get("items", [])

        scored_items = sorted(
            items,
            key=lambda item: float(item.get("score", 0) or 0),
            reverse=True,
        )

        recommended_items = [
            item for item in scored_items
            if bool(item.get("eligible", False)) or bool(item.get("quote_ready", False))
        ]

        return {
            "updated_at": data.get("updated_at", _now_iso()),
            "count": len(scored_items),
            "items": scored_items,
            "recommended_count": len(recommended_items),
            "recommended_items": recommended_items,
        }

    @staticmethod
    def upsert(item: Dict[str, Any]) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "upsert_live_rfq",
                "save_live_rfq",
                "save_live_rfq_item",
                "append_live_rfq",
            ],
            item,
        )
        if isinstance(result, dict):
            return result
        return {"status": "ok"}

    @staticmethod
    def promote(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "promote_live_rfqs",
                "promote_rfqs_to_live_store",
                "save_live_rfqs",
            ],
            items,
        )
        if isinstance(result, dict):
            return result
        return {"status": "ok", "promoted_count": len(items)}

    @staticmethod
    def delete(rfq_key: str) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["delete_live_rfq"], rfq_key)
        if isinstance(result, dict):
            return result
        return {"status": "ok", "rfq_key": rfq_key}

    @staticmethod
    def clear() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["clear_live_rfqs"])
        if isinstance(result, dict):
            return result
        return {"status": "ok"}

    @staticmethod
    def get_buyer_pack_acquisition_report() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["get_buyer_pack_acquisition_report"])
        if isinstance(result, dict):
            return result
        return {
            "status": "ok",
            "timestamp": _now_iso(),
            "qualified_rfqs": 0,
            "buyer_pack_verified": 0,
            "acquisition_pending": 0,
            "acquisition_blocked": 0,
            "acquisition_success_rate": 0.0,
        }

    @staticmethod
    def get_external_submission_candidate_queue(limit: int = 3) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["get_external_submission_candidate_queue"], limit)
        if isinstance(result, dict):
            return result
        return {"status": "ok", "timestamp": _now_iso(), "count": 0, "items": []}

    @staticmethod
    def get_benchmark_candidate_search(limit: int = 5) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["get_benchmark_candidate_search"], limit)
        if isinstance(result, dict):
            return result
        return {"status": "ok", "timestamp": _now_iso(), "count": 0, "items": []}

    @staticmethod
    def get_procurement_shape_distribution_report() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["get_procurement_shape_distribution_report"])
        if isinstance(result, dict):
            return result
        return {"status": "ok", "timestamp": _now_iso(), "live_rfqs": 0, "benchmark_candidate_count": 0, "benchmark_conversion_pct": 0.0}

    @staticmethod
    def get_source_shape_performance_report(limit: int = 10) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["get_source_shape_performance_report"], limit)
        if isinstance(result, dict):
            return result
        return {"status": "ok", "timestamp": _now_iso(), "source_count": 0, "top_sources": [], "all_sources": []}

    @staticmethod
    def get_document_intelligence_state(item: Dict[str, Any]) -> Dict[str, Any]:
        return summarize_rfq_document_intelligence(item)
