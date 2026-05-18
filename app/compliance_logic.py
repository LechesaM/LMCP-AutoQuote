from __future__ import annotations

import os
import shutil
from typing import List

from sqlalchemy.orm import Session

from app.compliance_models import (
    ComplianceDocument,
    OpportunityComplianceFile,
    OpportunityComplianceRequirement,
)
from app.compliance_registry import COMPLIANCE_REGISTRY, get_all_compliance_codes


UPLOAD_ROOT = "/app/uploads/compliance"
ATTACH_ROOT = "/app/generated/compliance_attachments"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def upsert_opportunity_requirements(db: Session, opportunity_id: int) -> List[OpportunityComplianceRequirement]:
    rows = []

    for code in get_all_compliance_codes():
        row = (
            db.query(OpportunityComplianceRequirement)
            .filter(
                OpportunityComplianceRequirement.opportunity_id == opportunity_id,
                OpportunityComplianceRequirement.document_code == code,
            )
            .first()
        )

        if row is None:
            row = OpportunityComplianceRequirement(
                opportunity_id=opportunity_id,
                document_code=code,
            )
            db.add(row)

        row.required = COMPLIANCE_REGISTRY[code]["required_by_default"]
        row.detected = True
        row.notes = "Default LMCP compliance requirement."
        row.status = "pending"
        rows.append(row)

    db.commit()

    for row in rows:
        db.refresh(row)

    return rows


def attach_master_documents_to_opportunity(db: Session, opportunity_id: int) -> List[OpportunityComplianceFile]:
    ensure_dir(os.path.join(ATTACH_ROOT, str(opportunity_id)))

    requirements = (
        db.query(OpportunityComplianceRequirement)
        .filter(OpportunityComplianceRequirement.opportunity_id == opportunity_id)
        .all()
    )

    attached_rows = []

    for req in requirements:
        master = (
            db.query(ComplianceDocument)
            .filter(ComplianceDocument.document_code == req.document_code)
            .order_by(ComplianceDocument.uploaded_at.desc())
            .first()
        )

        row = (
            db.query(OpportunityComplianceFile)
            .filter(
                OpportunityComplianceFile.opportunity_id == opportunity_id,
                OpportunityComplianceFile.document_code == req.document_code,
            )
            .first()
        )

        if row is None:
            row = OpportunityComplianceFile(
                opportunity_id=opportunity_id,
                document_code=req.document_code,
            )
            db.add(row)

        if master and os.path.exists(master.file_path):
            dest = os.path.join(
                ATTACH_ROOT,
                str(opportunity_id),
                os.path.basename(master.file_path),
            )
            shutil.copy2(master.file_path, dest)

            row.master_document_id = master.id
            row.attached_file_path = dest
            row.status = "attached"
            req.status = "attached"
        else:
            row.master_document_id = None
            row.attached_file_path = None
            row.status = "missing"
            req.status = "missing"

        attached_rows.append(row)

    db.commit()

    for row in attached_rows:
        db.refresh(row)

    return attached_rows
