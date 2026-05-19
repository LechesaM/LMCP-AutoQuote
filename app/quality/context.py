from __future__ import annotations

from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.persistence.repositories import WorkflowRepository


def _workflow_repo() -> WorkflowRepository:
    paths = get_runtime_paths()
    return WorkflowRepository(jsonl_path=paths.manual_production_file("workflow_state.jsonl"))


def _details(record: Dict[str, Any]) -> Dict[str, Any]:
    details = record.get("details")
    return details if isinstance(details, dict) else {}


def _unwrap_quality_payload(details: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    for key in keys:
        value = details.get(key)
        if isinstance(value, dict):
            return value
    return details


def _first_matching_details(limit: int, predicate) -> Dict[str, Any]:
    for record in _workflow_repo().fetch_recent(limit=limit):
        details = _details(record)
        if predicate(record, details):
            return details
    return {}


def _looks_like_rfq(details: Dict[str, Any]) -> bool:
    rfq_keys = {"tender_id", "buyer_name", "title", "category", "closing_date", "line_items"}
    return bool(rfq_keys.intersection(details.keys())) or "rfq_record" in details


def _looks_like_schedule(details: Dict[str, Any]) -> bool:
    schedule_keys = {"rows", "items", "line_items", "schedule_rows", "completed_buyer_schedule_path"}
    return bool(schedule_keys.intersection(details.keys())) or "buyer_pricing_schedule_completion" in details


def _looks_like_quote_pack(details: Dict[str, Any]) -> bool:
    quote_keys = {"generated_pdf_path", "generated_json_path", "completed_buyer_schedule_path", "artifacts"}
    return bool(quote_keys.intersection(details.keys())) or "quote_pack" in details


def _looks_like_supplier_quotes(details: Dict[str, Any]) -> bool:
    return "supplier_quotes" in details or "quotes" in details


def build_quality_context(limit: int = 50) -> Dict[str, Any]:
    rfq_payload = _first_matching_details(
        limit,
        lambda _record, details: _looks_like_rfq(details) or _record.get("stage") in {"discovered", "extracted", "evaluated"},
    )
    schedule_payload = _first_matching_details(
        limit,
        lambda _record, details: _looks_like_schedule(details) or _record.get("stage") in {"priced", "quote_generated"},
    )
    quote_pack_payload = _first_matching_details(
        limit,
        lambda _record, details: _looks_like_quote_pack(details) or _record.get("stage") in {"quote_generated", "approval_required", "approved"},
    )
    supplier_payload = _first_matching_details(
        limit,
        lambda _record, details: _looks_like_supplier_quotes(details),
    )
    return {
        "rfq_payload": _unwrap_quality_payload(rfq_payload, ["rfq_record", "rfq"]),
        "schedule_payload": _unwrap_quality_payload(schedule_payload, ["buyer_pricing_schedule_completion", "pricing_schedule"]),
        "quote_pack_payload": _unwrap_quality_payload(quote_pack_payload, ["quote_pack"]),
        "supplier_quotes": supplier_payload.get("supplier_quotes") or supplier_payload.get("quotes") or [],
    }
