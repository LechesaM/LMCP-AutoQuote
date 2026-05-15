from __future__ import annotations

from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parents[2]
BRANDING_DIR = BASE_DIR / "app" / "branding"

BRANDING_DIR.mkdir(parents=True, exist_ok=True)

COMPANY_BRANDING: Dict[str, str] = {
    "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
    "trading_name": "Lechesa Manaba",
    "email": "lechesam@me.com",
    "phone": "",
    "registration_number": "",
    "vat_number": "",
    "address_line_1": "",
    "address_line_2": "",
    "tagline": "Delivering Excellence in Supply and Infrastructure Solutions",
    "currency": "ZAR",
}

LOGO_PATH = BRANDING_DIR / "logo.png"


def get_company_branding() -> Dict[str, str]:
    return COMPANY_BRANDING.copy()


def get_logo_path() -> Path:
    if not LOGO_PATH.exists():
        raise FileNotFoundError(
            f"Logo not found at {LOGO_PATH}. Place your logo at app/branding/logo.png"
        )
    return LOGO_PATH
