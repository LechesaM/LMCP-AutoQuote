from __future__ import annotations

import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Opportunity
from app.compliance_logic import UPLOAD_ROOT, attach_master_documents_to_opportunity, ensure_dir, upsert_opportunity_requirements
from app.compliance_models import ComplianceDocument, OpportunityComplianceFile, OpportunityComplianceRequirement
from app.compliance_registry import COMPLIANCE_REGISTRY
from app.compliance_schemas import (
    ComplianceDocumentOut,
    OpportunityComplianceFileOut,
    OpportunityComplianceRequirementOut,
)

router = APIRouter(prefix="/compliance", tags=["LMCP Compliance Documents"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload/{document_code}", response_model=ComplianceDocumentOut)
def upload_compliance_document(
    document_code: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if document_code not in COMPLIANCE_REGISTRY:
        raise HTTPException(status_code=400, detail="Invalid compliance document code.")

    ensure_dir(UPLOAD_ROOT)

    filename = file.filename or f"{document_code}.bin"
    safe_name = f"{document_code}__{filename}"
    full_path = os.path.join(UPLOAD_ROOT, safe_name)

    with open(full_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    row = ComplianceDocument(
        document_code=document_code,
        document_name=COMPLIANCE_REGISTRY[document_code]["document_name"],
        file_path=full_path,
        file_type=file.content_type or "",
        status="valid",
        notes="Uploaded via API",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/documents", response_model=list[ComplianceDocumentOut])
def list_compliance_documents(db: Session = Depends(get_db)):
    return (
        db.query(ComplianceDocument)
        .order_by(ComplianceDocument.document_code.asc(), ComplianceDocument.uploaded_at.desc())
        .all()
    )


@router.post("/opportunity/{opportunity_id}/detect", response_model=list[OpportunityComplianceRequirementOut])
def detect_compliance_requirements(opportunity_id: int, db: Session = Depends(get_db)):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")

    return upsert_opportunity_requirements(db, opportunity_id)


@router.get("/opportunity/{opportunity_id}/requirements", response_model=list[OpportunityComplianceRequirementOut])
def list_compliance_requirements(opportunity_id: int, db: Session = Depends(get_db)):
    return (
        db.query(OpportunityComplianceRequirement)
        .filter(OpportunityComplianceRequirement.opportunity_id == opportunity_id)
        .order_by(OpportunityComplianceRequirement.document_code.asc())
        .all()
    )


@router.post("/opportunity/{opportunity_id}/attach", response_model=list[OpportunityComplianceFileOut])
def attach_compliance_documents(opportunity_id: int, db: Session = Depends(get_db)):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")

    existing = (
        db.query(OpportunityComplianceRequirement)
        .filter(OpportunityComplianceRequirement.opportunity_id == opportunity_id)
        .count()
    )
    if existing == 0:
        upsert_opportunity_requirements(db, opportunity_id)

    return attach_master_documents_to_opportunity(db, opportunity_id)


@router.get("/opportunity/{opportunity_id}/attached", response_model=list[OpportunityComplianceFileOut])
def list_attached_compliance_documents(opportunity_id: int, db: Session = Depends(get_db)):
    return (
        db.query(OpportunityComplianceFile)
        .filter(OpportunityComplianceFile.opportunity_id == opportunity_id)
        .order_by(OpportunityComplianceFile.document_code.asc())
        .all()
    )


@router.get("/download/{document_id}")
def download_master_compliance_document(document_id: int, db: Session = Depends(get_db)):
    row = db.query(ComplianceDocument).filter(ComplianceDocument.id == document_id).first()
    if row is None or not os.path.exists(row.file_path):
        raise HTTPException(status_code=404, detail="Compliance document not found.")

    return FileResponse(path=row.file_path, filename=os.path.basename(row.file_path))
