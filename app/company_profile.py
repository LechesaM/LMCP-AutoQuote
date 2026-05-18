from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from app.sbd_models import CompanyProfile, CompanyDirector


DEFAULT_DIRECTORS = [
    {
        "full_name": "Lechesa Manaba",
        "id_number": "8509085860080",
        "position": "Managing Director",
        "mobile": "0826338492",
        "email": "lechesam@me.com",
    }
]


def seed_default_directors(db: Session, profile: CompanyProfile) -> None:
    existing = (
        db.query(CompanyDirector)
        .filter(CompanyDirector.company_profile_id == profile.id)
        .count()
    )

    if existing > 0:
        return

    for item in DEFAULT_DIRECTORS:
        director = CompanyDirector(
            company_profile_id=profile.id,
            full_name=item["full_name"],
            id_number=item.get("id_number"),
            position=item.get("position"),
            mobile=item.get("mobile"),
            email=item.get("email"),
        )
        db.add(director)

    db.commit()


def get_or_create_default_company_profile(db: Session) -> CompanyProfile:
    profile = db.query(CompanyProfile).order_by(CompanyProfile.id.asc()).first()
    if profile:
        seed_default_directors(db, profile)
        return profile

    profile = CompanyProfile(
        legal_name="Lechesa Manaba Consulting and Projects (Pty) Ltd",
        trading_name="LM Consulting and Projects",
        registration_number="2012/159509/07",
        vat_number="4260295953",
        csd_supplier_number="MAAA0002664",
        tax_pin="2C151C823M",
        bbbee_level="1",
        bbbee_expiry="24 July 2026",
        contact_person="Lechesa Manaba",
        contact_email="lechesam@me.com",
        contact_phone="0826338492",
        physical_address="1787 Dube Street, Batho Location, Bloemfontein, 9323",
        postal_address="1787 Dube Street, Batho Location, Bloemfontein, 9323",
        bank_name="Capitec Business Bank",
        bank_account_name="Lechesa Manaba Consulting and Projects (Pty) Ltd",
        bank_account_number="1052 5119 88",
        bank_branch_code="470010",
        bank_account_type="Cheque",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    seed_default_directors(db, profile)

    return profile


def profile_to_sbd_defaults(profile: CompanyProfile) -> Dict[str, str]:
    return {
        "legal_name": profile.legal_name or "",
        "trading_name": profile.trading_name or "",
        "registration_number": profile.registration_number or "",
        "vat_number": profile.vat_number or "",
        "csd_supplier_number": profile.csd_supplier_number or "",
        "tax_pin": profile.tax_pin or "",
        "bbbee_level": profile.bbbee_level or "",
        "bbbee_expiry": profile.bbbee_expiry or "",
        "contact_person": profile.contact_person or "",
        "contact_email": profile.contact_email or "",
        "contact_phone": profile.contact_phone or "",
        "physical_address": profile.physical_address or "",
        "postal_address": profile.postal_address or "",
        "bank_name": profile.bank_name or "",
        "bank_account_name": profile.bank_account_name or "",
        "bank_account_number": profile.bank_account_number or "",
        "bank_branch_code": profile.bank_branch_code or "",
        "bank_account_type": profile.bank_account_type or "",
    }


def directors_to_lines(directors: List[CompanyDirector]) -> str:
    if not directors:
        return "No directors captured yet."

    lines = []
    for idx, d in enumerate(directors, start=1):
        line = f"{idx}. {d.full_name}"
        if d.position:
            line += f" | {d.position}"
        if d.id_number:
            line += f" | ID: {d.id_number}"
        if d.email:
            line += f" | Email: {d.email}"
        if d.mobile:
            line += f" | Mobile: {d.mobile}"
        lines.append(line)

    return "\n".join(lines)
DEFAULT_RELATED_ENTERPRISES = [
    "Mampudi Kgwebong (Pty) Ltd",
    "Paradigm Lounge (Pty) Ltd",
    "Amiri Mawingu Group (Pty) Ltd",
    "Goods 4U South Africa (Pty) Ltd",
    "Rasebetsa Trading (Pty) Ltd",
    "Sochi Industrial (Pty) Ltd",
    "BBD Serving Mangaung (Pty) Ltd",
]
