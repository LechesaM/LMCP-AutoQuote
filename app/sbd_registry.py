from __future__ import annotations

from typing import Dict, List


SBD_REGISTRY: Dict[str, Dict] = {
    "SBD1": {
        "name": "Invitation to Bid",
        "version": "2025",
        "fields": [
            "bid_number",
            "bid_description",
            "closing_date",
            "closing_time",
            "legal_name",
            "registration_number",
            "vat_number",
            "csd_supplier_number",
            "tax_pin",
            "contact_person",
            "contact_email",
            "contact_phone",
            "physical_address",
            "postal_address",
        ],
    },
    "SBD4": {
        "name": "Declaration of Interest",
        "version": "2025",
        "fields": [
            "legal_name",
            "registration_number",
            "tax_number",
            "vat_number",
            "directors_summary",
            "conflict_declared",
            "conflict_details",
            "signatory_name",
            "signatory_capacity",
            "declaration_date",
        ],
    },
    "SBD6.1": {
        "name": "Preference Points Claim Form",
        "version": "2025",
        "fields": [
            "legal_name",
            "registration_number",
            "bbbee_level",
            "bbbee_expiry",
            "points_system",
            "price_total",
            "preference_points_claimed",
            "signatory_name",
            "signatory_capacity",
            "declaration_date",
        ],
    },
    "SBD8": {
        "name": "Declaration of Bidder's Past Supply Chain Management Practices",
        "version": "2025",
        "fields": [
            "legal_name",
            "registration_number",
            "scm_practices_declared",
            "scm_practices_details",
            "signatory_name",
            "signatory_capacity",
            "declaration_date",
        ],
    },
    "SBD9": {
        "name": "Certificate of Independent Bid Determination",
        "version": "2025",
        "fields": [
            "legal_name",
            "registration_number",
            "bid_number",
            "independent_bid_confirmed",
            "signatory_name",
            "signatory_capacity",
            "declaration_date",
        ],
    },
    "SBD7.1": {
        "name": "Contract Form - Purchase of Goods/Works",
        "version": "2025",
        "fields": [
            "legal_name",
            "registration_number",
            "bid_number",
            "award_value",
            "award_date",
            "signatory_name",
            "signatory_capacity",
        ],
    },
}


KEYWORD_MAP = {
    "SBD1": ["sbd 1", "sbd1", "invitation to bid"],
    "SBD4": ["sbd 4", "sbd4", "declaration of interest"],
    "SBD6.1": ["sbd 6.1", "sbd6.1", "preference points claim form"],
    "SBD8": ["sbd 8", "sbd8", "past supply chain management practices"],
    "SBD9": ["sbd 9", "sbd9", "independent bid determination"],
    "SBD7.1": ["sbd 7.1", "sbd7.1", "contract form"],
}


def all_sbd_codes() -> List[str]:
    return list(SBD_REGISTRY.keys())


def get_sbd_definition(form_code: str) -> Dict:
    return SBD_REGISTRY[form_code]
