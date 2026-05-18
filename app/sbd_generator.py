from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from docx import Document
from sqlalchemy.orm import Session

from app.sbd_registry import SBD_REGISTRY
from app.sbd_models import (
    SBDGeneratedFile,
    SBDFieldValue,
    TenderSBDRequirement,
)


BASE_DIR = Path(__file__).resolve().parent.parent
SBD_TEMPLATE_DIR = BASE_DIR / "app" / "templates" / "forms"
GENERATED_ROOT = os.path.join(str(BASE_DIR), "generated", "sbd")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def normalize_placeholder_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value)


def strip_signature_fields(values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prevent accidental signing during draft generation.
    """
    blocked_keys = {
        "signature",
        "signature_image",
        "signature_block",
        "signature_path",
        "signed_by",
        "signed_at",
        "signed_date",
        "digital_signature",
    }

    cleaned = dict(values or {})

    for key in list(cleaned.keys()):
        if key in blocked_keys:
            cleaned[key] = ""

    cleaned.setdefault("signature_status", "UNSIGNED - PENDING REVIEW")
    cleaned.setdefault("signature_date", "")

    return cleaned


def replace_text_in_paragraph(paragraph, replacements: Dict[str, Any]) -> None:
    if not paragraph.text:
        return

    text = paragraph.text
    original = text

    for key, value in replacements.items():
        text = text.replace(f"{{{{{key}}}}}", normalize_placeholder_value(value))

    if text != original:
        for run in paragraph.runs:
            run.text = ""
        if paragraph.runs:
            paragraph.runs[0].text = text
        else:
            paragraph.add_run(text)


def replace_text_in_table(table, replacements: Dict[str, Any]) -> None:
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                replace_text_in_paragraph(paragraph, replacements)
            for nested_table in cell.tables:
                replace_text_in_table(nested_table, replacements)


def replace_placeholders_in_doc(doc: Document, replacements: Dict[str, Any]) -> None:
    for paragraph in doc.paragraphs:
        replace_text_in_paragraph(paragraph, replacements)

    for table in doc.tables:
        replace_text_in_table(table, replacements)


def convert_docx_to_pdf(docx_path: str, output_dir: str) -> str:
    soffice_bin = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice_bin:
        raise RuntimeError(
            "LibreOffice/soffice is not installed or not on PATH. "
            "Install LibreOffice to enable DOCX to PDF conversion."
        )

    cmd = [
        soffice_bin,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        output_dir,
        docx_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to convert DOCX to PDF.\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    pdf_path = os.path.join(
        output_dir,
        os.path.splitext(os.path.basename(docx_path))[0] + ".pdf",
    )

    if not os.path.exists(pdf_path):
        raise RuntimeError(f"Converted PDF not found: {pdf_path}")

    return pdf_path


def get_sbd_template_path(form_code: str) -> Path:
    normalized = str(form_code).strip().upper().replace(" ", "")
    filename_map = {
        "SBD1": "sbd_1.docx",
        "SBD4": "sbd_4.docx",
        "SBD6.1": "sbd_6_1.docx",
        "SBD8": "sbd_8.docx",
        "SBD9": "sbd_9.docx",
    }

    if normalized not in filename_map:
        raise ValueError(f"Unsupported SBD form code: {form_code}")

    template_path = SBD_TEMPLATE_DIR / filename_map[normalized]

    if not template_path.exists():
        raise FileNotFoundError(
            f"SBD template not found for {form_code}: {template_path}"
        )

    return template_path


def upsert_sbd_value(
    db: Session,
    opportunity_id: int,
    form_code: str,
    field_name: str,
    field_value: Any,
) -> SBDValue:
    row = (
        db.query(SBDValue)
        .filter(
            SBDValue.opportunity_id == opportunity_id,
            SBDValue.form_code == form_code,
            SBDValue.field_name == field_name,
        )
        .first()
    )

    if row is None:
        row = SBDValue(
            opportunity_id=opportunity_id,
            form_code=form_code,
            field_name=field_name,
            field_value=normalize_placeholder_value(field_value),
        )
        db.add(row)
    else:
        row.field_value = normalize_placeholder_value(field_value)

    return row


def seed_default_sbd_values(db: Session, opportunity) -> None:
    """
    Seeds basic SBD values from opportunity attributes if present.
    Safe defaults only. Does not apply any signature.
    """
    default_map_by_form: Dict[str, Dict[str, Any]] = {
        "SBD1": {
            "bid_number": getattr(opportunity, "bid_number", "") or getattr(opportunity, "reference_number", ""),
            "bid_description": getattr(opportunity, "title", "") or getattr(opportunity, "description", ""),
            "closing_date": getattr(opportunity, "closing_date", ""),
            "closing_time": getattr(opportunity, "closing_time", ""),
            "legal_name": getattr(opportunity, "company_name", ""),
            "registration_number": getattr(opportunity, "company_registration_number", ""),
            "vat_number": getattr(opportunity, "company_vat_number", ""),
            "csd_supplier_number": getattr(opportunity, "company_csd_number", ""),
            "tax_pin": getattr(opportunity, "company_tax_pin", ""),
            "contact_person": getattr(opportunity, "contact_person", ""),
            "contact_email": getattr(opportunity, "contact_email", ""),
            "contact_phone": getattr(opportunity, "contact_phone", ""),
            "physical_address": getattr(opportunity, "physical_address", ""),
            "postal_address": getattr(opportunity, "postal_address", ""),
        },
        "SBD4": {
            "legal_name": getattr(opportunity, "company_name", ""),
            "registration_number": getattr(opportunity, "company_registration_number", ""),
            "director_list": getattr(opportunity, "director_list", ""),
            "has_conflict": getattr(opportunity, "has_conflict", ""),
            "conflict_details": getattr(opportunity, "conflict_details", ""),
        },
        "SBD6.1": {
            "legal_name": getattr(opportunity, "company_name", ""),
            "registration_number": getattr(opportunity, "company_registration_number", ""),
            "bbee_level": getattr(opportunity, "bbee_level", ""),
            "bbee_certificate_number": getattr(opportunity, "bbee_certificate_number", ""),
            "emee_qse_status": getattr(opportunity, "emee_qse_status", ""),
        },
        "SBD8": {
            "legal_name": getattr(opportunity, "company_name", ""),
            "registration_number": getattr(opportunity, "company_registration_number", ""),
            "has_scm_issues": getattr(opportunity, "has_scm_issues", ""),
            "scm_details": getattr(opportunity, "scm_details", ""),
        },
        "SBD9": {
            "legal_name": getattr(opportunity, "company_name", ""),
            "registration_number": getattr(opportunity, "company_registration_number", ""),
            "authorized_representative": getattr(opportunity, "authorized_representative", ""),
            "signature_date": "",
            "signature_status": "UNSIGNED - PENDING REVIEW",
        },
    }

    for form_code, values in default_map_by_form.items():
        for field_name, field_value in values.items():
            upsert_sbd_value(
                db=db,
                opportunity_id=opportunity.id,
                form_code=form_code,
                field_name=field_name,
                field_value=field_value,
            )

    db.commit()


def get_form_values(db: Session, opportunity_id: int, form_code: str) -> Dict[str, Any]:
    rows = (
        db.query(SBDValue)
        .filter(
            SBDValue.opportunity_id == opportunity_id,
            SBDValue.form_code == form_code,
        )
        .all()
    )

    values: Dict[str, Any] = {row.field_name: row.field_value for row in rows}

    definition = SBD_REGISTRY.get(form_code, {})
    for field_name in definition.get("fields", []):
        values.setdefault(field_name, "")

    values.setdefault("signature_status", "UNSIGNED - PENDING REVIEW")
    values.setdefault("signature_date", "")

    return values


def generate_sbd_docx(db: Session, opportunity, form_code: str) -> str:
    template_path = get_sbd_template_path(form_code)
    values = get_form_values(db, opportunity.id, form_code)
    values = strip_signature_fields(values)

    definition = SBD_REGISTRY.get(form_code)
    if not definition:
        raise ValueError(f"No SBD registry definition found for form code: {form_code}")

    folder = os.path.join(GENERATED_ROOT, str(opportunity.id))
    ensure_dir(folder)

    base_filename = f"{form_code.replace('.', '_').lower()}_unsigned"
    docx_filename = f"{base_filename}.docx"
    pdf_filename = f"{base_filename}.pdf"

    docx_full_path = os.path.join(folder, docx_filename)
    pdf_full_path = os.path.join(folder, pdf_filename)

    doc = Document(str(template_path))
    replace_placeholders_in_doc(doc, values)
    doc.save(docx_full_path)

    pdf_path = convert_docx_to_pdf(docx_full_path, folder)

    if pdf_path != pdf_full_path and os.path.exists(pdf_path):
        pdf_full_path = pdf_path

    return pdf_full_path


def upsert_generated_file(
    db: Session,
    opportunity_id: int,
    form_code: str,
    docx_path: str,
) -> SBDGeneratedFile:
    row = (
        db.query(SBDGeneratedFile)
        .filter(
            SBDGeneratedFile.opportunity_id == opportunity_id,
            SBDGeneratedFile.form_code == form_code,
        )
        .first()
    )

    if row is None:
        row = SBDGeneratedFile(
            opportunity_id=opportunity_id,
            form_code=form_code,
        )
        db.add(row)

    row.docx_path = docx_path
    if not getattr(row, "signed_status", None):
        row.signed_status = "unsigned"

    db.commit()
    db.refresh(row)
    return row


def generate_all_required_sbd_files(db: Session, opportunity) -> List[SBDGeneratedFile]:
    seed_default_sbd_values(db, opportunity)

    requirements = (
        db.query(TenderSBDRequirement)
        .filter(TenderSBDRequirement.opportunity_id == opportunity.id)
        .all()
    )

    output: List[SBDGeneratedFile] = []

    for req in requirements:
        if not req.required and not req.detected:
            continue

        generated_path = generate_sbd_docx(db, opportunity, req.form_code)
        gen = upsert_generated_file(
            db=db,
            opportunity_id=opportunity.id,
            form_code=req.form_code,
            docx_path=generated_path,
        )

        req.status = "generated"
        output.append(gen)

    db.commit()
    return output


def generate_sbd_forms(*args, **kwargs):
    """
    Compatibility wrapper.

    submission_pack.py expects `generate_sbd_forms(...)` to exist.
    This wrapper tries common SBD generator function names already present
    in this file and delegates to the first one it finds.
    """
    candidate_names = [
        "build_sbd_forms",
        "create_sbd_forms",
        "generate_forms",
        "generate_sbd_bundle",
        "build_forms",
        "build_sbd_bundle",
        "preview_sbd_forms",
        "render_sbd_forms",
        "generate_all_required_sbd_files",
    ]

    for name in candidate_names:
        func = globals().get(name)
        if callable(func):
            return func(*args, **kwargs)

    raise NotImplementedError(
        "No SBD generation function found in app.sbd_generator. "
        "Expected one of: " + ", ".join(candidate_names)
    )
