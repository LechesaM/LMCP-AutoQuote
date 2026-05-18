from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.live_rfq_store import LiveRFQStore
from app.services.tender_pipeline import run_tender_pipeline_from_payload

router = APIRouter(prefix="/tender-pipeline", tags=["Tender Pipeline"])


class TenderPipelineRunRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"
    persist_to_live_store: bool = True


def _to_dict(result: Any) -> Dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    return {"result": result}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _build_live_store_item(result: Dict[str, Any]) -> Dict[str, Any]:
    buyer = _safe_dict(result.get("buyer"))
    submission_pack = _safe_dict(result.get("submission_pack"))

    item: Dict[str, Any] = {
        "title": result.get("title") or result.get("description") or "Untitled RFQ",
        "description": result.get("description") or result.get("title") or "",
        "buyer_name": result.get("buyer_name") or buyer.get("name") or buyer.get("company_name") or "",
        "buyer_rfq_number": result.get("buyer_rfq_number") or result.get("rfq_number") or result.get("reference_number") or "",
        "rfq_number": result.get("rfq_number") or result.get("buyer_rfq_number") or "",
        "reference_number": result.get("reference_number") or result.get("buyer_rfq_number") or "",
        "quote_number": result.get("quote_number") or "",
        "document_number": result.get("document_number") or "",
        "submission_method": result.get("submission_method") or submission_pack.get("submission_method") or "unknown",
        "recipient_email": result.get("recipient_email") or result.get("buyer_email") or buyer.get("email") or "",
        "buyer_email": result.get("buyer_email") or result.get("recipient_email") or buyer.get("email") or "",
        "eligible": bool(result.get("eligible", False)),
        "quote_ready": bool(result.get("quote_ready", False)),
        "quote_generated": bool(result.get("quote_generated", False)),
        "pdf_generated": bool(result.get("pdf_generated", False)),
        "pipeline_status": result.get("pipeline_status") or "processed",
        "submission_status": result.get("submission_status") or "not_submitted",
        "submission_message": result.get("submission_message") or "",
        "pdf_path": result.get("pdf_path") or result.get("final_pdf_path") or "",
        "final_pdf_path": result.get("final_pdf_path") or result.get("pdf_path") or "",
        "quote_pack_metadata_path": result.get("quote_pack_metadata_path") or "",
        "monthly_quote_folder": result.get("monthly_quote_folder") or "",
        "quote_folder": result.get("quote_folder") or "",
        "quote_pack_dir": result.get("quote_pack_dir") or "",
        "items": deepcopy(result.get("items")) if isinstance(result.get("items"), list) else [],
        "line_items": deepcopy(result.get("line_items")) if isinstance(result.get("line_items"), list) else [],
        "source_rfq": deepcopy(result.get("_original_input_payload")) if isinstance(result.get("_original_input_payload"), dict) else deepcopy(result),
        "updated_at": result.get("updated_at"),
    }
    return item


def _persist_result_to_live_store_if_requested(
    *,
    result_dict: Dict[str, Any],
    persist_to_live_store: bool,
) -> Dict[str, Any]:
    if not persist_to_live_store:
        result_dict["live_store_persisted"] = False
        return result_dict

    try:
        if "results" in result_dict and isinstance(result_dict.get("results"), list):
            items: List[Dict[str, Any]] = []
            for row in result_dict["results"]:
                if isinstance(row, dict):
                    items.append(_build_live_store_item(row))
            if items:
                LiveRFQStore.upsert_rfq(item)
                result_dict["live_store_persisted"] = True
                result_dict["live_store_persisted_count"] = len(items)
            else:
                result_dict["live_store_persisted"] = False
                result_dict["live_store_persisted_count"] = 0
            return result_dict

        live_item = _build_live_store_item(result_dict)
        LiveRFQStore.upsert_rfq(live_item)
        result_dict["live_store_persisted"] = True
        result_dict["live_store_persisted_count"] = 1
        return result_dict

    except Exception as exc:
        result_dict["live_store_persisted"] = False
        result_dict["live_store_persist_error"] = str(exc)
        return result_dict


@router.get("/health", operation_id="tp_health")
def tender_pipeline_health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "tender-pipeline",
    }


@router.get("/demo", operation_id="tp_demo")
def tender_pipeline_demo() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "tender-pipeline",
        "available_routes": [
            "/tender-pipeline/health",
            "/tender-pipeline/demo",
            "/tender-pipeline/run",
            "/tender-pipeline/test-run",
            "/tender-pipeline/live-rfqs",
            "/tender-pipeline/filtered-live-rfqs",
            "/tender-pipeline/scored-live-rfqs",
            "/tender-pipeline/recommended-live-rfqs",
        ],
    }


@router.post("/run", operation_id="tp_run_pipeline")
def run_pipeline(request: TenderPipelineRunRequest) -> Dict[str, Any]:
    merged_payload = dict(request.payload or {})
    merged_payload["source"] = request.source
    merged_payload["persist_to_live_store"] = request.persist_to_live_store

    result = run_tender_pipeline_from_payload(merged_payload)
    result_dict = _to_dict(result)

    result_dict = _persist_result_to_live_store_if_requested(
        result_dict=result_dict,
        persist_to_live_store=request.persist_to_live_store,
    )
    return result_dict


@router.get("/test-run", operation_id="tp_test_run_pipeline")
def test_run_pipeline() -> Dict[str, Any]:
    sample_payload: Dict[str, Any] = {
        "title": "Supply and delivery of office chairs",
        "description": "Supply and delivery of office chairs to client site",
        "buyer_name": "Test Buyer",
        "buyer_rfq_number": "RFQ-TEST-001",
        "submission_method": "email",
        "recipient_email": "lechesam@icloud.com",
        "buyer_email": "lechesam@icloud.com",
        "buyer": {
            "name": "Test Buyer",
            "email": "lechesam@icloud.com",
        },
        "force_quote_ready": True,
        "pipeline_test_mode": False,
        "skip_supplier_ingestion": True,
        "skip_external_calls": False,
        "auto_refresh_csd": False,
        "persist_to_live_store": False,
        "source": "test",
        "items": [
            {
                "description": "Office Chair",
                "quantity": 10,
                "unit": "Each",
                "unit_price": 1500,
            }
        ],
    }

    result = run_tender_pipeline_from_payload(sample_payload)
    result_dict = _to_dict(result)
    result_dict["live_store_persisted"] = False
    return result_dict


@router.get("/live-rfqs", operation_id="tp_get_live_rfqs")
def get_live_rfqs() -> Dict[str, Any]:
    return LiveRFQStore.get_all()


@router.get("/filtered-live-rfqs", operation_id="tp_get_filtered_live_rfqs")
def get_filtered_live_rfqs() -> Dict[str, Any]:
    return LiveRFQStore.get_filtered_from_store()


@router.get("/scored-live-rfqs", operation_id="tp_get_scored_live_rfqs")
def get_scored_live_rfqs() -> Dict[str, Any]:
    return LiveRFQStore.get_scored_from_store()


@router.get("/recommended-live-rfqs", operation_id="tp_get_recommended_live_rfqs")
def get_recommended_live_rfqs() -> Dict[str, Any]:
    data = LiveRFQStore.get_scored_from_store()
    return {
        "updated_at": data.get("updated_at"),
        "count": data.get("recommended_count", 0),
        "items": data.get("recommended_items", []),
    }
