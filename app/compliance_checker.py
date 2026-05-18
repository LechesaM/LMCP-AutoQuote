from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from app.sbd_models import ComplianceCheck, SBDFieldValue, SBDGeneratedFile, TenderSBDRequirement


MANDATORY_CORE_FIELDS = {
    "SBD1": ["legal_name", "registration_number", "contact_person"],
    "SBD4": ["legal_name", "signatory_name", "declaration_date"],
    "SBD6.1": ["legal_name", "bbbee_level", "signatory_name"],
    "SBD8": ["legal_name", "signatory_name"],
    "SBD9": ["legal_name", "bid_number", "signatory_name"],
}


def clear_existing_checks(db: Session, opportunity_id: int) -> None:
    rows = db.query(ComplianceCheck).filter(ComplianceCheck.opportunity_id == opportunity_id).all()
    for row in rows:
        db.delete(row)
    db.commit()


def add_check(db: Session, opportunity_id: int, check_code: str, status: str, message: str) -> None:
    row = ComplianceCheck(
        opportunity_id=opportunity_id,
        check_code=check_code,
        status=status,
        message=message,
    )
    db.add(row)


def get_field_value(db: Session, opportunity_id: int, form_code: str, field_name: str) -> str:
    row = (
        db.query(SBDFieldValue)
        .filter(
            SBDFieldValue.opportunity_id == opportunity_id,
            SBDFieldValue.form_code == form_code,
            SBDFieldValue.field_name == field_name,
        )
        .first()
    )
    return row.field_value.strip() if row and row.field_value else ""


def run_compliance_checks(db: Session, opportunity_id: int) -> List[ComplianceCheck]:
    clear_existing_checks(db, opportunity_id)

    requirements = (
        db.query(TenderSBDRequirement)
        .filter(TenderSBDRequirement.opportunity_id == opportunity_id)
        .all()
    )

    generated = (
        db.query(SBDGeneratedFile)
        .filter(SBDGeneratedFile.opportunity_id == opportunity_id)
        .all()
    )
    generated_map = {g.form_code: g for g in generated}

    for req in requirements:
        if req.required and req.form_code not in generated_map:
            add_check(
                db,
                opportunity_id,
                f"{req.form_code}_generated",
                "fail",
                f"{req.form_code} is required but no generated file exists.",
            )
        elif req.form_code in generated_map:
            add_check(
                db,
                opportunity_id,
                f"{req.form_code}_generated",
                "pass",
                f"{req.form_code} generated successfully.",
            )

        for field_name in MANDATORY_CORE_FIELDS.get(req.form_code, []):
            value = get_field_value(db, opportunity_id, req.form_code, field_name)
            if not value:
                add_check(
                    db,
                    opportunity_id,
                    f"{req.form_code}_{field_name}",
                    "warning",
                    f"{req.form_code} field '{field_name}' is empty.",
                )
            else:
                add_check(
                    db,
                    opportunity_id,
                    f"{req.form_code}_{field_name}",
                    "pass",
                    f"{req.form_code} field '{field_name}' is populated.",
                )

    db.commit()

    return (
        db.query(ComplianceCheck)
        .filter(ComplianceCheck.opportunity_id == opportunity_id)
        .order_by(ComplianceCheck.id.asc())
        .all()
    )
