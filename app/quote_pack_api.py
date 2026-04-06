from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List

from app.database import SessionLocal
from app.quote_pack_models import QuotePack, QuoteStatus
from app.quote_pack_schemas import (
    QuotePackCreate,
    QuotePackResponse,
    QuoteStatusAction,
    QuotePackItemCreate,
)
from app.quote_pack_service import (
    create_quote,
    add_quote_item,
    generate_pack,
    get_quote_or_404,
    transition_status,
)

router = APIRouter(prefix="/quote-packs", tags=["Quotation Packs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=QuotePackResponse)
def create_quote_pack(payload: QuotePackCreate, db: Session = Depends(get_db)):
    quote = create_quote(db, payload)
    return quote


@router.get("/", response_model=List[QuotePackResponse])
def list_quote_packs(db: Session = Depends(get_db)):
    return db.query(QuotePack).order_by(QuotePack.id.desc()).all()


@router.get("/{quote_id}", response_model=QuotePackResponse)
def get_quote_pack(quote_id: int, db: Session = Depends(get_db)):
    try:
        quote = get_quote_or_404(db, quote_id)
        return quote
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{quote_id}/items", response_model=QuotePackResponse)
def add_item(
    quote_id: int,
    payload: QuotePackItemCreate,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        quote = add_quote_item(db, quote, payload)
        return quote
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{quote_id}/generate", response_model=QuotePackResponse)
def generate_quote_pack(
    quote_id: int,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        quote = generate_pack(db, quote, action.action_by)
        return quote
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{quote_id}/submit", response_model=QuotePackResponse)
def submit_for_approval(
    quote_id: int,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        quote = transition_status(
            db=db,
            quote=quote,
            new_status=QuoteStatus.PENDING_APPROVAL,
            action_by=action.action_by,
            comment=action.comment,
        )
        return quote
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{quote_id}/approve", response_model=QuotePackResponse)
def approve_quote(
    quote_id: int,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        quote = transition_status(
            db=db,
            quote=quote,
            new_status=QuoteStatus.APPROVED,
            action_by=action.action_by,
            comment=action.comment,
        )
        return quote
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{quote_id}/reject", response_model=QuotePackResponse)
def reject_quote(
    quote_id: int,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        quote = transition_status(
            db=db,
            quote=quote,
            new_status=QuoteStatus.REJECTED,
            action_by=action.action_by,
            comment=action.comment,
            rejection_reason=action.rejection_reason,
        )
        return quote
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{quote_id}/mark-sent", response_model=QuotePackResponse)
def mark_sent(
    quote_id: int,
    action: QuoteStatusAction,
    db: Session = Depends(get_db),
):
    try:
        quote = get_quote_or_404(db, quote_id)
        quote = transition_status(
            db=db,
            quote=quote,
            new_status=QuoteStatus.SENT,
            action_by=action.action_by,
            comment=action.comment,
        )
        return quote
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{quote_id}/download/docx")
def download_docx(quote_id: int, db: Session = Depends(get_db)):
    try:
        quote = get_quote_or_404(db, quote_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

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
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not quote.pdf_path:
        raise HTTPException(status_code=404, detail="PDF not generated")

    if not os.path.exists(quote.pdf_path):
        raise HTTPException(status_code=404, detail="PDF file missing on disk")

    return FileResponse(
        path=quote.pdf_path,
        media_type="application/pdf",
        filename=f"{quote.quote_number}.pdf",
    )
