from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.quote_pack_models import QuotePack
from app.quote_pack_schemas import (
    ComplianceChecklistBulkUpdate,
    ComplianceChecklistUpdate,
    QuotePackCreate,
    QuotePackItemCreate,
    QuotePackItemUpdate,
    QuotePackResponse,
    QuotePackReviewSummary,
    QuotePackValidationResponse,
    QuoteStatusAction,
    ReviewQueueExportRequest,
    RFQReviewIngestRequest,
)
from app.quote_pack_service import add_quote_item, create_quote, generate_pack, get_quote_or_404
from app.services.operator_auth_service import OperatorAuthError, resolve_request_operator
from app.services.quote_review_service import (
    accept_all_suggested_pricing,
    accept_suggested_pricing,
    approve_quote as approve_quote_review,
    build_pilot_to_review_bridge,
    bulk_mark_standard_company_docs,
    export_review_queue,
    export_pilot_run,
    fast_reject_quote,
    get_review_detail_payload,
    get_review_details,
    ingest_rfq_review_draft,
    list_review_queue,
    list_review_queue_summary,
    list_pilot_runs,
    load_pilot_run,
    mark_needs_manual_review,
    reject_quote as reject_quote_review,
    run_manual_review_pilot,
    submit_quote as submit_quote_review,
    update_single_compliance_item,
    update_compliance_checklist,
    update_pricing_item,
    validate_quote_pack,
)


router = APIRouter(prefix="/quote-packs", tags=["Quotation Packs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_operator(request: Request, action: str):
    try:
        return resolve_request_operator(request, action)
    except OperatorAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _quote_or_404(db: Session, quote_id: int) -> QuotePack:
    try:
        return get_review_details(db, quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _review_summary(quote: QuotePack) -> Dict[str, Any]:
    return {"id": quote.id, "quote_number": quote.quote_number, "project_title": quote.project_title}


@router.post("/", response_model=QuotePackResponse)
def create_quote_pack(payload: QuotePackCreate, db: Session = Depends(get_db)):
    return create_quote(db, payload)


@router.get("/", response_model=List[QuotePackResponse])
def list_quote_packs(db: Session = Depends(get_db)):
    return db.query(QuotePack).order_by(QuotePack.id.desc()).all()


@router.post("/review/extract", response_model=QuotePackResponse)
def review_extract_rfq(
    payload: RFQReviewIngestRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_ingest")
    rfq_data = dict(payload.rfq_data or {})
    if payload.company_data:
        rfq_data.setdefault("company_data", payload.company_data)
    if payload.created_by:
        rfq_data.setdefault("created_by", payload.created_by)
    try:
        return ingest_rfq_review_draft(db, rfq_data, operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/pilot/run")
def quote_pack_run_pilot(
    request: Request,
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_pilot_run")
    rfqs = payload.get("rfqs")
    if not isinstance(rfqs, list):
        raise HTTPException(status_code=400, detail="rfqs must be a list of RFQ entries.")
    try:
        return run_manual_review_pilot(
            db,
            rfq_entries=rfqs,
            operator=operator,
            pilot_name=str(payload.get("pilot_name") or ""),
            limit=int(payload.get("limit") or 10),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pilot/runs")
def quote_pack_list_pilot_runs(request: Request):
    _require_operator(request, "quote_review_pilot_view")
    return {"status": "ok", "runs": list_pilot_runs()}


@router.get("/pilot/runs/{run_id}")
def quote_pack_get_pilot_run(run_id: str, request: Request):
    _require_operator(request, "quote_review_pilot_view")
    try:
        return load_pilot_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pilot/runs/{run_id}/export")
def quote_pack_export_pilot_run(run_id: str, request: Request, format: str = "json"):
    _require_operator(request, "quote_review_pilot_export")
    try:
        export = export_pilot_run(run_id, format)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc

    media_type = {
        "json": "application/json",
        "summary": "application/json",
        "csv": "text/csv",
    }.get(export["format"], "application/octet-stream")
    filename = f"{run_id}.{ 'csv' if export['format'] == 'csv' else 'json' }"
    return FileResponse(path=export["path"], media_type=media_type, filename=filename)


@router.get("/review/rfqs", response_model=List[QuotePackReviewSummary])
def review_list_rfqs(request: Request, db: Session = Depends(get_db)):
    _require_operator(request, "quote_review_view")
    records = list_review_queue_summary(db)
    return [
        {
            "id": record["quote_pack_id"],
            "quote_number": record["quote_number"],
            "project_title": record["rfq_title"],
            "buyer_name": record["buyer"],
            "rfq_reference": "",
            "status": record["status"],
            "province": record["province"],
            "closing_date_text": record["closing_date"],
            "briefing_required": False,
            "extraction_confidence": record["extraction_confidence"],
            "classification_confidence": record["classification_confidence"],
            "estimated_profit": record["estimated_profit"],
            "estimated_margin_percent": record["margin_percent"],
            "validation_status": record["validation_status"],
            "pricing_rows_total": record["pricing_rows_total"],
            "pricing_rows_completed": record["pricing_rows_completed"],
            "pricing_rows_needing_review": record["pricing_rows_needing_review"],
            "suggested_total_quote": record["suggested_total_quote"],
            "compliance_status": record["compliance_status"],
            "easiest_to_approve_rank": record["easiest_to_approve_rank"],
            "easiest_to_approve_score": record["easiest_to_approve_score"],
            "next_action": record["next_action"],
            "approval_ready": record["approval_ready"],
        }
        for record in records
    ]


@router.get("/review/rfqs/export")
def review_export_queue(
    request: Request,
    format: str = "json",
    db: Session = Depends(get_db),
):
    _require_operator(request, "quote_review_view")
    export = export_review_queue(db, format)
    media_type = "text/csv" if export["format"] == "csv" else "application/json"
    filename = os.path.basename(export["path"])
    return FileResponse(path=export["path"], media_type=media_type, filename=filename)


@router.get("/review/rfqs/{quote_id}", response_model=QuotePackResponse)
def review_get_rfq(quote_id: int, request: Request, db: Session = Depends(get_db)):
    _require_operator(request, "quote_review_view")
    return _quote_or_404(db, quote_id)


@router.get("/review/rfqs/{quote_id}/detail")
def review_get_rfq_detail(quote_id: int, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_operator(request, "quote_review_view")
    return get_review_detail_payload(db, quote_id)


@router.get("/review/rfqs/{quote_id}/classification")
def review_get_classification(quote_id: int, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_operator(request, "quote_review_view")
    quote = _quote_or_404(db, quote_id)
    validation = validate_quote_pack(quote)
    return {
        "quote_pack_id": quote.id,
        "classification": {
            "payload_json": quote.classification_payload_json,
            "briefing_required": bool(quote.briefing_required),
            "province": quote.province,
            "buyer_name": quote.buyer_name,
        },
        "validation": validation,
    }


@router.get("/review/rfqs/{quote_id}/pricing-schedule")
def review_get_pricing_schedule(quote_id: int, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_operator(request, "quote_review_view")
    quote = _quote_or_404(db, quote_id)
    pricing_payload = json.loads(quote.pricing_payload_json) if quote.pricing_payload_json else {}
    return {
        "quote_pack_id": quote.id,
        "pricing_payload_json": quote.pricing_payload_json,
        "pricing_payload": pricing_payload,
        "pricing_suggestions": pricing_payload.get("rows") or [],
        "rows_requiring_manual_review": pricing_payload.get("review_rows") or [],
        "minimum_required_quote_total": pricing_payload.get("minimum_required_quote_total"),
        "pricing_confidence_summary": pricing_payload.get("confidence_summary") or {},
        "items": quote.items,
    }


@router.get("/review/rfqs/{quote_id}/pricing-suggestions")
def review_get_pricing_suggestions(quote_id: int, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_operator(request, "quote_review_view")
    quote = _quote_or_404(db, quote_id)
    pricing_payload = json.loads(quote.pricing_payload_json) if quote.pricing_payload_json else {}
    validation = validate_quote_pack(quote)
    return {
        "quote_pack_id": quote.id,
        "pricing_suggestions": pricing_payload.get("rows") or [],
        "rows_requiring_manual_review": pricing_payload.get("review_rows") or [],
        "pricing_confidence_summary": pricing_payload.get("confidence_summary") or {},
        "pricing_autofill_status": pricing_payload.get("pricing_autofill_status"),
        "suggested_total_quote": pricing_payload.get("suggested_total_quote"),
        "suggested_total_profit": pricing_payload.get("suggested_total_profit"),
        "suggested_margin_percent": pricing_payload.get("suggested_margin_percent"),
        "minimum_required_quote_total": validation.get("metrics", {}).get("minimum_required_quote_total"),
        "required_unit_prices": validation.get("metrics", {}).get("required_unit_prices") or [],
    }


@router.get("/{quote_id}", response_model=QuotePackResponse)
def get_quote_pack(quote_id: int, db: Session = Depends(get_db)):
    try:
        return get_quote_or_404(db, quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{quote_id}/validation", response_model=QuotePackValidationResponse)
def get_quote_pack_validation(quote_id: int, request: Request, db: Session = Depends(get_db)):
    _require_operator(request, "quote_review_view")
    quote = _quote_or_404(db, quote_id)
    return validate_quote_pack(quote)


@router.get("/{quote_id}/compliance-checklist")
def get_quote_pack_compliance_checklist(quote_id: int, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_operator(request, "quote_review_view")
    quote = _quote_or_404(db, quote_id)
    return {
        "quote_pack_id": quote.id,
        "compliance_payload_json": quote.compliance_payload_json,
    }


@router.patch("/{quote_id}/compliance-checklist/{item_key}", response_model=QuotePackResponse)
def patch_quote_pack_compliance_item(
    quote_id: int,
    item_key: str,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_update_compliance")
    quote = _quote_or_404(db, quote_id)
    try:
        return update_single_compliance_item(
            db,
            quote,
            item_key,
            str(payload.get("status") or ""),
            operator,
            reason=str(payload.get("reason") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/compliance-checklist/bulk-standard-present", response_model=QuotePackResponse)
def post_quote_pack_compliance_bulk_standard_present(
    quote_id: int,
    request: Request,
    payload: ComplianceChecklistBulkUpdate = Body(default=ComplianceChecklistBulkUpdate()),
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_update_compliance")
    quote = _quote_or_404(db, quote_id)
    try:
        return bulk_mark_standard_company_docs(db, quote, operator, status=payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{quote_id}/compliance-checklist", response_model=QuotePackResponse)
def put_quote_pack_compliance_checklist(
    quote_id: int,
    payload: ComplianceChecklistUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_update_compliance")
    quote = _quote_or_404(db, quote_id)
    try:
        return update_compliance_checklist(db, quote, [item.dict() for item in payload.items], operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/items", response_model=QuotePackResponse)
def add_item(
    quote_id: int,
    payload: QuotePackItemCreate,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        return add_quote_item(db, quote, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{quote_id}/items/{item_id}", response_model=QuotePackResponse)
def patch_quote_pack_item(
    quote_id: int,
    item_id: int,
    payload: QuotePackItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_edit_pricing")
    quote = _quote_or_404(db, quote_id)
    try:
        return update_pricing_item(db, quote, item_id, payload.dict(exclude_unset=True), operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/items/{item_id}/accept-suggested-price", response_model=QuotePackResponse)
def post_accept_suggested_price(
    quote_id: int,
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_edit_pricing")
    quote = _quote_or_404(db, quote_id)
    try:
        return accept_suggested_pricing(db, quote, item_id, operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/items/accept-all-suggested-prices", response_model=QuotePackResponse)
def post_accept_all_suggested_prices(
    quote_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_edit_pricing")
    quote = _quote_or_404(db, quote_id)
    try:
        return accept_all_suggested_pricing(db, quote, operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/generate", response_model=QuotePackResponse)
def generate_quote_pack(
    quote_id: int,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        return generate_pack(db, quote, action.action_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/needs-review", response_model=QuotePackResponse)
def post_quote_pack_needs_review(
    quote_id: int,
    request: Request,
    action: QuoteStatusAction = Body(default=QuoteStatusAction()),
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_mark_manual")
    quote = _quote_or_404(db, quote_id)
    return mark_needs_manual_review(db, quote, operator, comment=action.comment or "")


@router.post("/{quote_id}/submit", response_model=QuotePackResponse)
def submit_quote_pack(
    quote_id: int,
    request: Request,
    action: QuoteStatusAction = Body(default=QuoteStatusAction()),
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_submit")
    quote = _quote_or_404(db, quote_id)
    try:
        return submit_quote_review(db, quote, operator, comment=action.comment or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/approve", response_model=QuotePackResponse)
def approve_quote_pack(
    quote_id: int,
    request: Request,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_approve")
    quote = _quote_or_404(db, quote_id)
    try:
        return approve_quote_review(
            db,
            quote,
            operator,
            override_validation=bool(action.override_validation),
            override_reason=action.override_reason or "",
            comment=action.comment or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/reject", response_model=QuotePackResponse)
def reject_quote_pack(
    quote_id: int,
    request: Request,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_reject")
    quote = _quote_or_404(db, quote_id)
    rejection_reason = action.rejection_reason or action.comment or "Rejected during manual review."
    try:
        return reject_quote_review(db, quote, operator, rejection_reason=rejection_reason, comment=action.comment or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/fast-reject", response_model=QuotePackResponse)
def fast_reject_quote_pack(
    quote_id: int,
    request: Request,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_reject")
    quote = _quote_or_404(db, quote_id)
    try:
        return fast_reject_quote(db, quote, operator, action.reject_reason_code or "", comment=action.comment or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/review/pilot-bridge/latest")
def review_latest_pilot_bridge(request: Request, run_id: str = "") -> Dict[str, Any]:
    _require_operator(request, "quote_review_pilot_view")
    try:
        return build_pilot_to_review_bridge(run_id or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{quote_id}/mark-sent", response_model=QuotePackResponse)
def mark_sent(
    quote_id: int,
    request: Request,
    action: QuoteStatusAction = Body(default=QuoteStatusAction()),
    db: Session = Depends(get_db),
):
    operator = _require_operator(request, "quote_review_submit")
    quote = _quote_or_404(db, quote_id)
    try:
        return submit_quote_review(db, quote, operator, comment=action.comment or "Marked sent after manual approval")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{quote_id}/download/docx")
def download_docx(quote_id: int, db: Session = Depends(get_db)):
    try:
        quote = get_quote_or_404(db, quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not quote.docx_path:
        raise HTTPException(status_code=404, detail="DOCX not generated")
    if not os.path.exists(quote.docx_path):
        raise HTTPException(status_code=404, detail="DOCX file missing on disk")

    return FileResponse(
        path=quote.docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{quote.quote_number}.docx",
    )


@router.get("/{quote_id}/download/pdf")
def download_pdf(quote_id: int, db: Session = Depends(get_db)):
    try:
        quote = get_quote_or_404(db, quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not quote.pdf_path:
        raise HTTPException(status_code=404, detail="PDF not generated")
    if not os.path.exists(quote.pdf_path):
        raise HTTPException(status_code=404, detail="PDF file missing on disk")

    return FileResponse(
        path=quote.pdf_path,
        media_type="application/pdf",
        filename=f"{quote.quote_number}.pdf",
    )
