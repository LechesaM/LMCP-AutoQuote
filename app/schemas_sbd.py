from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class CompanyDirectorCreate(BaseModel):
    full_name: str
    id_number: Optional[str] = None
    position: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None


class CompanyDirectorOut(BaseModel):
    id: int
    full_name: str
    id_number: Optional[str] = None
    position: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


class CompanyProfileCreateUpdate(BaseModel):
    legal_name: str
    trading_name: Optional[str] = None
    registration_number: Optional[str] = None
    vat_number: Optional[str] = None
    csd_supplier_number: Optional[str] = None
    tax_pin: Optional[str] = None
    bbbee_level: Optional[str] = None
    bbbee_expiry: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    physical_address: Optional[str] = None
    postal_address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_branch_code: Optional[str] = None
    bank_account_type: Optional[str] = None


class CompanyProfileOut(CompanyProfileCreateUpdate):
    id: int
    directors: List[CompanyDirectorOut] = []

    class Config:
        from_attributes = True


class SBDRequirementOut(BaseModel):
    id: int
    opportunity_id: int
    form_code: str
    required: bool
    detected: bool
    source_file: Optional[str] = None
    version: Optional[str] = None
    status: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class SBDFieldValueUpdate(BaseModel):
    form_code: str
    field_name: str
    field_value: str
    source: Optional[str] = "manual"


class SBDFieldValueOut(BaseModel):
    id: int
    opportunity_id: int
    form_code: str
    field_name: str
    field_value: Optional[str] = None
    source: str

    class Config:
        from_attributes = True


class SBDGeneratedFileOut(BaseModel):
    id: int
    opportunity_id: int
    form_code: str
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    signed_status: str

    class Config:
        from_attributes = True


class ComplianceCheckOut(BaseModel):
    id: int
    opportunity_id: int
    check_code: str
    status: str
    message: str

    class Config:
        from_attributes = True
