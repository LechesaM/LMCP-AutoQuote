from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader

from app.services.sbd_auto_detection_engine import SBDAutoDetectionEngine


class AutoProfileGeneratorError(Exception):
    pass


class AutoProfileGenerator:
    """
    Generates starter form-profile JSON files from tender/SBD/MBD PDFs.

    Purpose:
    - Detect the likely form type from the PDF
    - Create a usable starter profile JSON in app/data/form_profiles
    - Give the form filler and submission pipeline a real profile to route to

    Notes:
    - This creates a STARTER profile, not a perfect final profile.
    - Signature coordinates may still need x/y tuning after first render.
    """

    DEFAULT_PROFILE_DIR = "app/data/form_profiles"

    BASE_PROFILES: Dict[str, Dict[str, Any]] = {
        "municipal_mbd1_profile.json": {
            "name": "municipal_mbd1_profile",
            "template_type": "mbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name", "service provider name"],
                "postal_address": ["postal address"],
                "company_address": ["street address", "physical address"],
                "company_phone": ["telephone number", "telephone"],
                "company_cellphone": ["cellphone number", "cellphone"],
                "company_email": ["e-mail address", "email address"],
                "vat_number": ["vat registration number", "vat no"],
                "csd_number": ["csd no", "csd number"],
                "tcs_pin": ["tcs pin", "tax compliance status"],
                "signatory_capacity": ["capacity under which this bid is signed", "capacity"],
                "date_signed": ["date", "signature date"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "NAME OF BIDDER", "x_offset": 170, "y_offset": -2, "width": 300, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "postal_address", "anchor_text": "POSTAL ADDRESS", "x_offset": 170, "y_offset": -2, "width": 300, "height": 26, "font_size": 10, "multiline": True, "max_lines": 2, "whiteout": True},
                {"field_name": "company_address", "anchor_text": "STREET ADDRESS", "x_offset": 170, "y_offset": -2, "width": 300, "height": 26, "font_size": 10, "multiline": True, "max_lines": 2, "whiteout": True},
                {"field_name": "company_phone", "anchor_text": "TELEPHONE NUMBER", "x_offset": 215, "y_offset": -2, "width": 120, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_cellphone", "anchor_text": "CELLPHONE NUMBER", "x_offset": 170, "y_offset": -2, "width": 220, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_email", "anchor_text": "E-MAIL ADDRESS", "x_offset": 170, "y_offset": -2, "width": 280, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "vat_number", "anchor_text": "VAT REGISTRATION NUMBER", "x_offset": 170, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "tcs_pin", "anchor_text": "TCS PIN:", "x_offset": 55, "y_offset": -2, "width": 90, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "csd_number", "anchor_text": "CSD No:", "x_offset": 55, "y_offset": -2, "width": 120, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "CAPACITY UNDER WHICH THIS BID IS SIGNED", "x_offset": 230, "y_offset": -2, "width": 250, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "DATE", "x_offset": 45, "y_offset": -2, "width": 110, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 255, "y": 102, "width": 150, "height": 42},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
            "xlsx_signature_anchor": "E20",
            "xlsx_witness_1_signature_anchor": "E24",
            "xlsx_witness_2_signature_anchor": "J24",
        },
        "municipal_mbd4_profile.json": {
            "name": "municipal_mbd4_profile",
            "template_type": "mbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name"],
                "signatory_name": ["full name of bidder", "full name", "name in print"],
                "signatory_capacity": ["capacity", "position"],
                "date_signed": ["date"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of bidder", "x_offset": 140, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_name", "anchor_text": "Full name of bidder", "x_offset": 150, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 50, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 120, "y": 105, "width": 150, "height": 40},
            "witness_1_signature_coordinates": {"page": 0, "x": 120, "y": 60, "width": 130, "height": 34},
            "witness_2_signature_coordinates": {"page": 0, "x": 290, "y": 60, "width": 130, "height": 34},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
        },
        "municipal_mbd8_profile.json": {
            "name": "municipal_mbd8_profile",
            "template_type": "mbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name"],
                "signatory_name": ["full name", "name in print"],
                "signatory_capacity": ["capacity", "position"],
                "date_signed": ["date"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of bidder", "x_offset": 140, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_name", "anchor_text": "Full name", "x_offset": 85, "y_offset": -2, "width": 220, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 50, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 120, "y": 105, "width": 150, "height": 40},
            "witness_1_signature_coordinates": {"page": 0, "x": 120, "y": 60, "width": 130, "height": 34},
            "witness_2_signature_coordinates": {"page": 0, "x": 290, "y": 60, "width": 130, "height": 34},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
        },
        "municipal_mbd9_profile.json": {
            "name": "municipal_mbd9_profile",
            "template_type": "mbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name"],
                "signatory_name": ["full name", "name in print"],
                "signatory_capacity": ["capacity", "position"],
                "date_signed": ["date"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of Bidder", "x_offset": 140, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_name", "anchor_text": "Full Name", "x_offset": 85, "y_offset": -2, "width": 220, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 50, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 120, "y": 105, "width": 150, "height": 40},
            "witness_1_signature_coordinates": {"page": 0, "x": 120, "y": 60, "width": 130, "height": 34},
            "witness_2_signature_coordinates": {"page": 0, "x": 290, "y": 60, "width": 130, "height": 34},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
        },
        "sbd1_profile.json": {
            "name": "sbd1_profile",
            "template_type": "sbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name", "supplier information"],
                "postal_address": ["postal address"],
                "company_address": ["street address", "physical address"],
                "company_phone": ["telephone number", "telephone"],
                "company_cellphone": ["cellphone number", "cellphone"],
                "contact_person": ["contact person", "contract person"],
                "company_email": ["e-mail address", "email address"],
                "vat_number": ["vat registration number", "vat no"],
                "csd_number": ["central supplier database no", "csd no", "csd number"],
                "tcs_pin": ["tax compliance system pin", "tcs pin"],
                "signatory_capacity": ["capacity under which this bid is signed", "capacity"],
                "date_signed": ["date", "signature date"],
                "total_bid_price": ["total bid price", "total bid price inc. vat"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "NAME OF BIDDER", "x_offset": 160, "y_offset": -2, "width": 280, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "postal_address", "anchor_text": "POSTAL ADDRESS", "x_offset": 160, "y_offset": -2, "width": 280, "height": 26, "font_size": 10, "multiline": True, "max_lines": 2, "whiteout": True},
                {"field_name": "company_address", "anchor_text": "STREET ADDRESS", "x_offset": 160, "y_offset": -2, "width": 280, "height": 26, "font_size": 10, "multiline": True, "max_lines": 2, "whiteout": True},
                {"field_name": "company_phone", "anchor_text": "TELEPHONE NUMBER", "x_offset": 150, "y_offset": -2, "width": 130, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_cellphone", "anchor_text": "CELLPHONE NUMBER", "x_offset": 150, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "contact_person", "anchor_text": "CONTRACT PERSON", "x_offset": 135, "y_offset": -2, "width": 200, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_email", "anchor_text": "E-MAIL ADDRESS", "x_offset": 150, "y_offset": -2, "width": 260, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "vat_number", "anchor_text": "VAT REGISTRATION NUMBER", "x_offset": 160, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "total_bid_price", "anchor_text": "TOTAL BID PRICE", "x_offset": 130, "y_offset": -2, "width": 150, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "tcs_pin", "anchor_text": "TAX COMPLIANCE SYSTEM PIN", "x_offset": 150, "y_offset": -2, "width": 120, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "csd_number", "anchor_text": "CENTRAL SUPPLIER DATABASE No", "x_offset": 160, "y_offset": -2, "width": 140, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "CAPACITY UNDER WHICH THIS BID IS SIGNED", "x_offset": 220, "y_offset": -2, "width": 250, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "DATE", "x_offset": 45, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 110, "y": 95, "width": 150, "height": 40},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
        },
        "sbd4_profile.json": {
            "name": "sbd4_profile",
            "template_type": "sbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name"],
                "signatory_name": ["full name of bidder", "full name", "name in print"],
                "signatory_capacity": ["capacity", "position"],
                "date_signed": ["date"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of bidder", "x_offset": 135, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_name", "anchor_text": "Full name of bidder", "x_offset": 145, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 45, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 115, "y": 100, "width": 150, "height": 40},
            "witness_1_signature_coordinates": {"page": 0, "x": 115, "y": 58, "width": 130, "height": 34},
            "witness_2_signature_coordinates": {"page": 0, "x": 290, "y": 58, "width": 130, "height": 34},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
        },
        "sbd6_1_profile.json": {
            "name": "sbd6_1_profile",
            "template_type": "sbd_form",
            "field_aliases": {
                "company_name": ["name of tenderer", "name of bidder", "bidder name"],
                "date_signed": ["date"],
                "signatory_capacity": ["capacity", "position"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of tenderer", "x_offset": 150, "y_offset": -2, "width": 250, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity under which this bid is signed", "x_offset": 220, "y_offset": -2, "width": 250, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 45, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 110, "y": 95, "width": 150, "height": 40},
            "docx_signature_placeholder": "{{signature}}",
        },
        "sbd8_profile.json": {
            "name": "sbd8_profile",
            "template_type": "sbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name"],
                "signatory_name": ["full name", "name in print"],
                "signatory_capacity": ["capacity", "position"],
                "date_signed": ["date"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of bidder", "x_offset": 135, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_name", "anchor_text": "Full name", "x_offset": 85, "y_offset": -2, "width": 220, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 45, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 115, "y": 100, "width": 150, "height": 40},
            "witness_1_signature_coordinates": {"page": 0, "x": 115, "y": 58, "width": 130, "height": 34},
            "witness_2_signature_coordinates": {"page": 0, "x": 290, "y": 58, "width": 130, "height": 34},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
        },
        "sbd9_profile.json": {
            "name": "sbd9_profile",
            "template_type": "sbd_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name"],
                "signatory_name": ["full name", "name in print"],
                "signatory_capacity": ["capacity", "position"],
                "date_signed": ["date"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of Bidder", "x_offset": 135, "y_offset": -2, "width": 240, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_name", "anchor_text": "Full Name", "x_offset": 85, "y_offset": -2, "width": 220, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 45, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 115, "y": 100, "width": 150, "height": 40},
            "witness_1_signature_coordinates": {"page": 0, "x": 115, "y": 58, "width": 130, "height": 34},
            "witness_2_signature_coordinates": {"page": 0, "x": 290, "y": 58, "width": 130, "height": 34},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
        },
        "authority_to_sign_profile.json": {
            "name": "authority_to_sign_profile",
            "template_type": "authority_form",
            "field_aliases": {
                "company_name": ["name of bidder", "bidder name", "name of tenderer", "company name"],
                "signatory_name": ["full name", "name in full", "authorised signatory", "authorized signatory"],
                "signatory_capacity": ["capacity", "position", "designation"],
                "director_name": ["director name", "member name"],
                "date_signed": ["date"],
                "witness_1_name": ["witness 1", "first witness"],
                "witness_2_name": ["witness 2", "second witness"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of bidder", "x_offset": 140, "y_offset": -2, "width": 260, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_name", "anchor_text": "Name of tenderer", "x_offset": 150, "y_offset": -2, "width": 260, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_name", "anchor_text": "Full name", "x_offset": 85, "y_offset": -2, "width": 220, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "director_name", "anchor_text": "Director", "x_offset": 65, "y_offset": -2, "width": 200, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "witness_1_name", "anchor_text": "Witness 1", "x_offset": 80, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "witness_2_name", "anchor_text": "Witness 2", "x_offset": 80, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 45, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 120, "y": 105, "width": 150, "height": 40},
            "witness_1_signature_coordinates": {"page": 0, "x": 120, "y": 60, "width": 130, "height": 34},
            "witness_2_signature_coordinates": {"page": 0, "x": 290, "y": 60, "width": 130, "height": 34},
            "docx_signature_placeholder": "{{signature}}",
            "docx_witness_1_signature_placeholder": "{{witness_1_signature}}",
            "docx_witness_2_signature_placeholder": "{{witness_2_signature}}",
            "xlsx_signature_anchor": "E20",
            "xlsx_witness_1_signature_anchor": "E24",
            "xlsx_witness_2_signature_anchor": "J24",
        },
        "pricing_schedule_profile.json": {
            "name": "pricing_schedule_profile",
            "template_type": "pricing_schedule",
            "field_aliases": {
                "company_name": ["name of bidder", "supplier name", "company name"],
                "vat_number": ["vat registration number", "vat no"],
                "csd_number": ["csd no", "csd number"],
                "tender_number": ["tender number", "bid number", "rfq number", "reference number"],
                "date_signed": ["date"],
                "signatory_capacity": ["capacity", "position"],
                "contact_person": ["contact person"],
                "company_email": ["email address", "e-mail address"],
                "company_phone": ["telephone number", "telephone"],
            },
            "anchor_rules": [
                {"field_name": "company_name", "anchor_text": "Name of bidder", "x_offset": 140, "y_offset": -2, "width": 260, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_name", "anchor_text": "Supplier name", "x_offset": 120, "y_offset": -2, "width": 260, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "vat_number", "anchor_text": "VAT REGISTRATION NUMBER", "x_offset": 160, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "csd_number", "anchor_text": "CSD No", "x_offset": 55, "y_offset": -2, "width": 120, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "tender_number", "anchor_text": "Tender number", "x_offset": 110, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "tender_number", "anchor_text": "Bid number", "x_offset": 90, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "contact_person", "anchor_text": "Contact person", "x_offset": 100, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_email", "anchor_text": "E-MAIL ADDRESS", "x_offset": 150, "y_offset": -2, "width": 260, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "company_phone", "anchor_text": "TELEPHONE NUMBER", "x_offset": 150, "y_offset": -2, "width": 140, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "signatory_capacity", "anchor_text": "Capacity", "x_offset": 70, "y_offset": -2, "width": 180, "height": 14, "font_size": 10, "whiteout": True},
                {"field_name": "date_signed", "anchor_text": "Date", "x_offset": 45, "y_offset": -2, "width": 100, "height": 14, "font_size": 10, "whiteout": True},
            ],
            "signature_coordinates": {"page": 0, "x": 120, "y": 95, "width": 150, "height": 40},
            "docx_signature_placeholder": "{{signature}}",
            "xlsx_signature_anchor": "E20",
        },
    }

    def __init__(self, profile_dir: str = DEFAULT_PROFILE_DIR) -> None:
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def generate_profile_from_pdf(
        self,
        input_pdf_path: str,
        output_filename: Optional[str] = None,
        force_template_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        input_path = Path(input_pdf_path)
        if not input_path.exists():
            raise AutoProfileGeneratorError(f"PDF not found: {input_pdf_path}")

        detections = SBDAutoDetectionEngine.detect_pdf(str(input_path))
        best_profile_name = force_template_name or SBDAutoDetectionEngine.choose_best_profile(detections)

        if not best_profile_name:
            best_profile_name = self._guess_generic_profile_from_text(str(input_path))

        if best_profile_name not in self.BASE_PROFILES:
            raise AutoProfileGeneratorError(
                f"No starter template found for detected profile '{best_profile_name}'."
            )

        starter = deepcopy(self.BASE_PROFILES[best_profile_name])

        if output_filename:
            final_filename = output_filename
        else:
            stem = self._sanitize_filename_part(input_path.stem)
            suffix = self._sanitize_filename_part(Path(best_profile_name).stem)
            final_filename = f"{stem}__{suffix}.json"

        output_path = self.profile_dir / final_filename

        inferred_page = self._infer_primary_form_page(str(input_path), detections)
        self._apply_page_index_to_signature_coordinates(starter, inferred_page)
        self._apply_page_index_to_anchor_rules(starter, inferred_page)

        starter["name"] = Path(final_filename).stem

        output_path.write_text(json.dumps(starter, indent=2), encoding="utf-8")

        return {
            "status": "success",
            "input_pdf_path": str(input_path),
            "output_profile_path": str(output_path),
            "detected_profile_template": best_profile_name,
            "detections": [
                {
                    "form_code": d.form_code,
                    "confidence": d.confidence,
                    "buyer_family": d.buyer_family,
                    "stamp_allowed": d.stamp_allowed,
                    "witness_required": d.witness_required,
                    "suggested_profile": d.suggested_profile,
                    "page_index": d.page_index,
                }
                for d in detections
            ],
            "inferred_primary_page_index": inferred_page,
            "note": "Starter profile generated. Signature and anchor positions may still need small tuning after first render.",
        }

    def _guess_generic_profile_from_text(self, input_pdf_path: str) -> str:
        text = self._extract_text_blob(input_pdf_path, max_pages=20)

        if re.search(r"\bauthority to sign\b|\bcertificate of authority\b", text, flags=re.IGNORECASE):
            return "authority_to_sign_profile.json"

        if re.search(
            r"\bpricing schedule\b|\bfirm prices\b|\bprice schedule\b|\bbill of quantities\b",
            text,
            flags=re.IGNORECASE,
        ):
            return "pricing_schedule_profile.json"

        return "pricing_schedule_profile.json"

    def _extract_text_blob(self, input_pdf_path: str, max_pages: int = 20) -> str:
        reader = PdfReader(input_pdf_path)
        parts: List[str] = []

        max_page_count = min(max_pages, len(reader.pages))
        for idx in range(max_page_count):
            page = reader.pages[idx]
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text:
                parts.append(text)

        return "\n".join(parts)

    def _infer_primary_form_page(self, input_pdf_path: str, detections: List[Any]) -> int:
        if detections:
            ranked = sorted(
                detections,
                key=lambda d: (d.confidence, -(d.page_index or 0)),
                reverse=True,
            )
            best = ranked[0]
            if best.page_index is not None:
                return int(best.page_index)

        reader = PdfReader(input_pdf_path)
        for idx, page in enumerate(reader.pages[:20]):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            normalized = text.lower()
            if any(token in normalized for token in [
                "invitation to bid",
                "declaration of interest",
                "certificate of independent bid determination",
                "declaration of bidder",
                "pricing schedule",
                "authority to sign",
            ]):
                return idx

        return 0

    def _apply_page_index_to_signature_coordinates(self, profile: Dict[str, Any], page_index: int) -> None:
        for key in (
            "signature_coordinates",
            "witness_1_signature_coordinates",
            "witness_2_signature_coordinates",
        ):
            if isinstance(profile.get(key), dict):
                profile[key]["page"] = page_index

    def _apply_page_index_to_anchor_rules(self, profile: Dict[str, Any], page_index: int) -> None:
        rules = profile.get("anchor_rules")
        if not isinstance(rules, list):
            return
        for rule in rules:
            if isinstance(rule, dict):
                rule["page"] = page_index

    def _sanitize_filename_part(self, value: str, default: str = "profile") -> str:
        text = str(value or "").strip()
        text = re.sub(r"[^\w\-.]+", "_", text)
        text = text.strip("._")
        return text or default


if __name__ == "__main__":
    generator = AutoProfileGenerator()
    sample = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "test_tender_pack" / "sample_sbd.pdf")
    result = generator.generate_profile_from_pdf(sample)
    print(json.dumps(result, indent=2))
