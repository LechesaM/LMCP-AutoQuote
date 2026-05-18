from __future__ import annotations

from datetime import date
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field


router = APIRouter(prefix="/sbd", tags=["SBD Forms"])


# ---------------------------------------------------------
# In-memory profile store for now
# Later we can move this into the database permanently
# ---------------------------------------------------------
COMPANY_PROFILE = {
    "company_name": "Lechesa Manaba Consulting & Projects (Pty) Ltd",
    "registration_number": "2012/159509/07",
    "vat_number": "4260295953",
    "tax_pin": "2C151C823M",
    "csd_number": "MAAA0002664",
    "bbbee_level": "1",
    "physical_address": "1787 Dube Steet, Batho Location, Bloemfontein, 9323",
    "postal_address": "1787 Dube Steet, Batho Location, Bloemfontein, 932",
    "telephone": "",
    "email": "lechesam@me.com",
    "contact_person": "Lechesa Manaba",
    "directors": [],
    "signatory_name": "Lechesa Manaba",
    "signatory_capacity": "Managing Director",
    "signature_path": "app/static/signatures/default_signature.png",
}


RELATED_COMPANIES = [
    {
        "company_name": "Mampudi Kgwebong (Pty) Ltd",
        "registration_number": "2012/156056/07",
    },
    {
        "company_name": "Goods 4u South Africa (Pty) Ltd",
        "registration_number": "2015/188051/07",
    },
    {
        "company_name": "Rasebetsa Trading (Pty) Ltd",
        "registration_number": "2016/014596/07",
    },
    {
        "company_name": "Sochi Industrial (Pty) Ltd",
        "registration_number": "2018/634795/07",
    },
    {
        "company_name": "BBD Serving Mangaung (Pty) Ltd",
        "registration_number": "2021/800163/07",
    },
    {
        "company_name": "Paradigm Lounge (Pty) Ltd",
        "registration_number": "2022/479536/07",
    },
    {
        "company_name": "Amiri Mawingu Group (Pty) Ltd",
        "registration_number": "2024/480881/01",
    },
]


# ---------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------
class DirectorCreate(BaseModel):
    full_name: str = Field(..., description="Director full name")
    id_number: str = Field(..., description="South African ID number or passport number")
    position: str = Field(..., description="Director position in company")
    citizenship: Optional[str] = Field(default="South African")
    is_signatory: bool = Field(default=False)


class RelatedCompanyCreate(BaseModel):
    company_name: str
    registration_number: str


class CompanyProfileUpdate(BaseModel):
    company_name: str
    registration_number: str
    vat_number: Optional[str] = ""
    tax_pin: Optional[str] = ""
    csd_number: Optional[str] = ""
    bbbee_level: Optional[str] = ""
    physical_address: Optional[str] = ""
    postal_address: Optional[str] = ""
    telephone: Optional[str] = ""
    email: EmailStr
    contact_person: str
    signatory_name: Optional[str] = "Lechesa Manaba"
    signatory_capacity: Optional[str] = "Managing Director"
    signature_path: Optional[str] = "app/static/signatures/default_signature.png"


class CompanyProfileOut(BaseModel):
    company_name: str
    registration_number: str
    vat_number: str
    tax_pin: str
    csd_number: str
    bbbee_level: str
    physical_address: str
    postal_address: str
    telephone: str
    email: EmailStr
    contact_person: str
    signatory_name: str
    signatory_capacity: str
    signature_path: str
    directors: List[DirectorCreate]


class SBD1TenderInput(BaseModel):
    bid_number: str
    bid_description: str
    closing_date: str
    closing_time: str
    department_name: str


class SBD1Output(BaseModel):
    form_name: str
    section_a: Dict[str, Any]
    section_b: Dict[str, Any]
    foreign_supplier_questionnaire: Dict[str, Any]
    directors: List[dict]
    declaration: Dict[str, Any]
    ready_for_pdf: bool


class SBD4Input(BaseModel):
    bid_number: str
    bid_description: str
    department_name: str

    question_1_state_employee: bool = False
    question_1_details: Optional[str] = ""

    question_2_family_state_employee: bool = False
    question_2_details: Optional[str] = ""

    question_3_partner_with_state_employee: Optional[bool] = False
    question_3_details: Optional[str] = ""

    question_4_person_in_service_of_state_involved: bool = False
    question_4_details: Optional[str] = ""

    question_5_any_relationship_with_employees: bool = False
    question_5_details: Optional[str] = ""

    question_6_knowledge_of_other_related_bidders: bool = False
    question_6_details: Optional[str] = ""

    question_7_director_trustee_shareholder_in_other_bidding_entity: bool = False
    question_7_details: Optional[str] = ""

    question_8_any_other_conflict_of_interest: bool = False
    question_8_details: Optional[str] = ""


class SBD4Output(BaseModel):
    form_name: str
    bid_details: Dict[str, Any]
    bidder_details: Dict[str, Any]
    disclosure_answers: Dict[str, Any]
    declaration: Dict[str, Any]
    ready_for_pdf: bool


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------
def normalize_company_name(name: str) -> str:
    return " ".join(name.lower().replace("–", "-").split()).strip()


def get_signatory_director() -> Optional[dict]:
    for director in COMPANY_PROFILE["directors"]:
        if director.get("is_signatory") is True:
            return director
    return None


def validate_company_profile() -> None:
    required_fields = [
        ("company_name", COMPANY_PROFILE["company_name"]),
        ("registration_number", COMPANY_PROFILE["registration_number"]),
        ("email", COMPANY_PROFILE["email"]),
        ("contact_person", COMPANY_PROFILE["contact_person"]),
        ("signatory_name", COMPANY_PROFILE["signatory_name"]),
        ("signatory_capacity", COMPANY_PROFILE["signatory_capacity"]),
    ]

    missing = [field_name for field_name, value in required_fields if not str(value).strip()]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Company profile is incomplete. Missing required fields: {', '.join(missing)}"
        )


def build_blank_foreign_supplier_questionnaire() -> dict:
    return {
        "included_in_form": True,
        "auto_completed": False,
        "validation_required": False,
        "completion_status": "left_blank",
        "note": "Foreign Supplier Questionnaire is included in SBD1 but intentionally not completed by the system.",
        "fields": {
            "is_the_entity_a_foreign_owned_entity": "",
            "is_the_entity_a_foreign_based_supplier": "",
            "does_the_entity_have_a_local_agent": "",
            "local_agent_name": "",
            "local_agent_registration_number": "",
            "local_agent_contact_person": "",
            "local_agent_email": "",
            "local_agent_telephone": "",
            "local_agent_physical_address": "",
            "local_agent_postal_address": "",
        },
    }


def get_related_companies_excluding_bidder(bidder_name: str) -> List[dict]:
    bidder_normalized = normalize_company_name(bidder_name)

    filtered = []
    for company in RELATED_COMPANIES:
        if normalize_company_name(company["company_name"]) != bidder_normalized:
            filtered.append(company)

    return filtered


def build_related_companies_disclosure_text(bidder_name: str) -> str:
    filtered_companies = get_related_companies_excluding_bidder(bidder_name)

    if not filtered_companies:
        return "No related companies/entities to disclose."

    lines = ["The following related companies/entities are disclosed:", ""]
    for index, company in enumerate(filtered_companies, start=1):
        lines.append(
            f"{index}. {company['company_name']} – {company['registration_number']}"
        )

    lines.append("")
    lines.append(
        f"{bidder_name} is excluded from this disclosure list as it is the bidding entity submitting the tender."
    )

    return "\n".join(lines)


def should_auto_answer_question_23() -> bool:
    return len(RELATED_COMPANIES) > 0


def build_sbd1_payload(tender: SBD1TenderInput) -> dict:
    signatory_director = get_signatory_director()

    return {
        "form_name": "SBD 1 - Invitation to Bid",
        "section_a": {
            "bid_number": tender.bid_number,
            "bid_description": tender.bid_description,
            "closing_date": tender.closing_date,
            "closing_time": tender.closing_time,
            "department_name": tender.department_name,
        },
        "section_b": {
            "name_of_bidder": COMPANY_PROFILE["company_name"],
            "registration_number": COMPANY_PROFILE["registration_number"],
            "vat_registration_number": COMPANY_PROFILE["vat_number"],
            "tax_compliance_pin": COMPANY_PROFILE["tax_pin"],
            "csd_supplier_number": COMPANY_PROFILE["csd_number"],
            "bbbee_status_level": COMPANY_PROFILE["bbbee_level"],
            "physical_address": COMPANY_PROFILE["physical_address"],
            "postal_address": COMPANY_PROFILE["postal_address"],
            "telephone_number": COMPANY_PROFILE["telephone"],
            "email_address": COMPANY_PROFILE["email"],
            "contact_person": COMPANY_PROFILE["contact_person"],
        },
        "foreign_supplier_questionnaire": build_blank_foreign_supplier_questionnaire(),
        "directors": COMPANY_PROFILE["directors"],
        "declaration": {
            "signatory_name": COMPANY_PROFILE["signatory_name"],
            "signatory_capacity": COMPANY_PROFILE["signatory_capacity"],
            "signature_path": COMPANY_PROFILE["signature_path"],
            "signature_date": str(date.today()),
            "signatory_director": signatory_director,
        },
        "ready_for_pdf": True,
    }


def build_sbd4_payload(payload: SBD4Input) -> dict:
    signatory_director = get_signatory_director()

    auto_q23_answer = should_auto_answer_question_23()
    auto_q231_details = build_related_companies_disclosure_text(COMPANY_PROFILE["company_name"])

    q23_answer = payload.question_3_partner_with_state_employee
    if q23_answer is None:
        q23_answer = auto_q23_answer

    q231_details = payload.question_3_details.strip() if payload.question_3_details else ""
    if not q231_details and q23_answer:
        q231_details = auto_q231_details

    return {
        "form_name": "SBD 4 - Bidder's Disclosure",
        "bid_details": {
            "bid_number": payload.bid_number,
            "bid_description": payload.bid_description,
            "department_name": payload.department_name,
        },
        "bidder_details": {
            "company_name": COMPANY_PROFILE["company_name"],
            "registration_number": COMPANY_PROFILE["registration_number"],
            "vat_number": COMPANY_PROFILE["vat_number"],
            "csd_number": COMPANY_PROFILE["csd_number"],
            "contact_person": COMPANY_PROFILE["contact_person"],
            "telephone": COMPANY_PROFILE["telephone"],
            "email": COMPANY_PROFILE["email"],
            "physical_address": COMPANY_PROFILE["physical_address"],
            "postal_address": COMPANY_PROFILE["postal_address"],
        },
        "disclosure_answers": {
            "question_1_state_employee": {
                "answer": payload.question_1_state_employee,
                "details": payload.question_1_details or "",
            },
            "question_2_family_state_employee": {
                "answer": payload.question_2_family_state_employee,
                "details": payload.question_2_details or "",
            },
            "question_2_3_related_entities_disclosure": {
                "answer": q23_answer,
                "details": q231_details,
                "auto_generated": q231_details == auto_q231_details and q23_answer is True,
            },
            "question_4_person_in_service_of_state_involved": {
                "answer": payload.question_4_person_in_service_of_state_involved,
                "details": payload.question_4_details or "",
            },
            "question_5_any_relationship_with_employees": {
                "answer": payload.question_5_any_relationship_with_employees,
                "details": payload.question_5_details or "",
            },
            "question_6_knowledge_of_other_related_bidders": {
                "answer": payload.question_6_knowledge_of_other_related_bidders,
                "details": payload.question_6_details or "",
            },
            "question_7_director_trustee_shareholder_in_other_bidding_entity": {
                "answer": payload.question_7_director_trustee_shareholder_in_other_bidding_entity,
                "details": payload.question_7_details or "",
            },
            "question_8_any_other_conflict_of_interest": {
                "answer": payload.question_8_any_other_conflict_of_interest,
                "details": payload.question_8_details or "",
            },
        },
        "declaration": {
            "signatory_name": COMPANY_PROFILE["signatory_name"],
            "signatory_capacity": COMPANY_PROFILE["signatory_capacity"],
            "signature_path": COMPANY_PROFILE["signature_path"],
            "signature_date": str(date.today()),
            "signatory_director": signatory_director,
        },
        "ready_for_pdf": True,
    }


# ---------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------
@router.get("/company-profile", response_model=CompanyProfileOut)
def get_company_profile():
    return CompanyProfileOut(
        company_name=COMPANY_PROFILE["company_name"],
        registration_number=COMPANY_PROFILE["registration_number"],
        vat_number=COMPANY_PROFILE["vat_number"],
        tax_pin=COMPANY_PROFILE["tax_pin"],
        csd_number=COMPANY_PROFILE["csd_number"],
        bbbee_level=COMPANY_PROFILE["bbbee_level"],
        physical_address=COMPANY_PROFILE["physical_address"],
        postal_address=COMPANY_PROFILE["postal_address"],
        telephone=COMPANY_PROFILE["telephone"],
        email=COMPANY_PROFILE["email"],
        contact_person=COMPANY_PROFILE["contact_person"],
        signatory_name=COMPANY_PROFILE["signatory_name"],
        signatory_capacity=COMPANY_PROFILE["signatory_capacity"],
        signature_path=COMPANY_PROFILE["signature_path"],
        directors=[DirectorCreate(**d) for d in COMPANY_PROFILE["directors"]],
    )


@router.post("/company-profile", response_model=CompanyProfileOut)
def update_company_profile(payload: CompanyProfileUpdate):
    COMPANY_PROFILE["company_name"] = payload.company_name
    COMPANY_PROFILE["registration_number"] = payload.registration_number
    COMPANY_PROFILE["vat_number"] = payload.vat_number or ""
    COMPANY_PROFILE["tax_pin"] = payload.tax_pin or ""
    COMPANY_PROFILE["csd_number"] = payload.csd_number or ""
    COMPANY_PROFILE["bbbee_level"] = payload.bbbee_level or ""
    COMPANY_PROFILE["physical_address"] = payload.physical_address or ""
    COMPANY_PROFILE["postal_address"] = payload.postal_address or ""
    COMPANY_PROFILE["telephone"] = payload.telephone or ""
    COMPANY_PROFILE["email"] = str(payload.email)
    COMPANY_PROFILE["contact_person"] = payload.contact_person
    COMPANY_PROFILE["signatory_name"] = payload.signatory_name or "Lechesa Manaba"
    COMPANY_PROFILE["signatory_capacity"] = payload.signatory_capacity or "Managing Director"
    COMPANY_PROFILE["signature_path"] = payload.signature_path or "app/static/signatures/default_signature.png"

    return get_company_profile()


@router.get("/company-profile/directors", response_model=List[DirectorCreate])
def list_directors():
    return [DirectorCreate(**d) for d in COMPANY_PROFILE["directors"]]


@router.post("/company-profile/directors", response_model=List[DirectorCreate])
def add_director(payload: DirectorCreate):
    for director in COMPANY_PROFILE["directors"]:
        if director["id_number"] == payload.id_number:
            raise HTTPException(status_code=400, detail="Director with this ID number already exists.")

    if payload.is_signatory:
        for director in COMPANY_PROFILE["directors"]:
            director["is_signatory"] = False

    COMPANY_PROFILE["directors"].append(payload.model_dump())
    return list_directors()


@router.delete("/company-profile/directors/{id_number}", response_model=List[DirectorCreate])
def delete_director(id_number: str):
    before = len(COMPANY_PROFILE["directors"])
    COMPANY_PROFILE["directors"] = [
        d for d in COMPANY_PROFILE["directors"] if d["id_number"] != id_number
    ]
    after = len(COMPANY_PROFILE["directors"])

    if before == after:
        raise HTTPException(status_code=404, detail="Director not found.")

    return list_directors()


# ---------------------------------------------------------
# Related companies endpoints
# ---------------------------------------------------------
@router.get("/related-companies", response_model=List[RelatedCompanyCreate])
def list_related_companies():
    return [RelatedCompanyCreate(**company) for company in RELATED_COMPANIES]


@router.post("/related-companies", response_model=List[RelatedCompanyCreate])
def add_related_company(payload: RelatedCompanyCreate):
    for company in RELATED_COMPANIES:
        if normalize_company_name(company["company_name"]) == normalize_company_name(payload.company_name):
            raise HTTPException(status_code=400, detail="Related company already exists.")

    RELATED_COMPANIES.append(payload.model_dump())
    return list_related_companies()


@router.delete("/related-companies/{registration_number}", response_model=List[RelatedCompanyCreate])
def delete_related_company(registration_number: str):
    before = len(RELATED_COMPANIES)
    remaining = [c for c in RELATED_COMPANIES if c["registration_number"] != registration_number]

    if len(remaining) == before:
        raise HTTPException(status_code=404, detail="Related company not found.")

    RELATED_COMPANIES.clear()
    RELATED_COMPANIES.extend(remaining)
    return list_related_companies()


@router.get("/sbd4/question-2.3/auto-disclosure")
def preview_auto_disclosure_for_question_23():
    bidder_name = COMPANY_PROFILE["company_name"]
    return {
        "question_2_3_answer": should_auto_answer_question_23(),
        "question_2_3_1_details": build_related_companies_disclosure_text(bidder_name),
    }


# ---------------------------------------------------------
# SBD1 endpoint
# ---------------------------------------------------------
@router.post("/sbd1/preview", response_model=SBD1Output)
def preview_sbd1(payload: SBD1TenderInput):
    validate_company_profile()
    result = build_sbd1_payload(payload)
    return SBD1Output(**result)


# ---------------------------------------------------------
# SBD4 endpoint
# ---------------------------------------------------------
@router.post("/sbd4/preview", response_model=SBD4Output)
def preview_sbd4(payload: SBD4Input):
    validate_company_profile()
    result = build_sbd4_payload(payload)
    return SBD4Output(**result)
