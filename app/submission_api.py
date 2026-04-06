from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import QuoteDraft
from app.submission_pack import build_submission_pack


router = APIRouter(tags=["Submission Pack"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/submission-pack/{quote_id}")
def generate_submission_pack(quote_id: int, db: Session = Depends(get_db)):
    quote = db.query(QuoteDraft).filter(QuoteDraft.id == quote_id).first()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    pdf_path = build_submission_pack(db, quote)

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"LMCP_Submission_Pack_{quote.quote_number}.pdf"
    )
