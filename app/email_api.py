from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SubmissionRecord
from app.schemas import SubmissionEmailRequest, SubmissionRecordOut
from app.submission_emailer import submit_quote_by_email

router = APIRouter(prefix="/email-submissions", tags=["Email Auto-Submission"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/send", response_model=SubmissionRecordOut)
def send_submission_email(request: SubmissionEmailRequest, db: Session = Depends(get_db)):
    try:
        record = submit_quote_by_email(
            db=db,
            quote_draft_id=request.quote_draft_id,
            recipient_email=request.recipient_email,
            cc_email=request.cc_email,
            subject=request.subject,
            body=request.body,
            auto_use_opportunity_email=request.auto_use_opportunity_email,
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission email failed: {str(e)}")


@router.get("/", response_model=list[SubmissionRecordOut])
def list_submission_records(db: Session = Depends(get_db)):
    rows = db.query(SubmissionRecord).order_by(SubmissionRecord.created_at.desc()).all()
    return rows


@router.get("/{submission_id}", response_model=SubmissionRecordOut)
def get_submission_record(submission_id: int, db: Session = Depends(get_db)):
    row = db.query(SubmissionRecord).filter(SubmissionRecord.id == submission_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Submission record not found.")
    return row
