from __future__ import annotations

from pathlib import Path

from app.qualification.qualification_engine import build_qualification_summary, qualify_fixture, qualify_rfq, qualify_text


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "qualification_rfqs"


def test_idt_household_products_goes_when_profitability_passes() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_002_idt_household_products.json")

    assert result["category"] == "household_products"
    assert result["recommendation"] == "GO"
    assert result["quote_candidate"] is True
    assert result["supplier_domain"]["supplier_domain"] == "FMCG wholesalers"


def test_safcol_classifies_as_equipment_supply() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_004_safcol_damsakke_with_pump.json")

    assert result["category"] == "equipment_supply"
    assert result["recommendation"] in {"GO", "MANUAL_REVIEW"}
    assert result["supplier_domain"]["supplier_domain"] == "industrial/equipment suppliers"


def test_sansa_classifies_as_technical_fabrication_manual_review() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_003_sansa_prefab_container.json")

    assert result["category"] == "technical_fabrication"
    assert result["recommendation"] == "MANUAL_REVIEW"
    assert result["manual_review_required"] is True


def test_thulamela_building_materials_requires_manual_review_due_to_physical_handling() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_005_thulamela_building_materials.json")

    assert result["category"] == "building_materials"
    assert result["recommendation"] == "MANUAL_REVIEW"
    assert result["submission_method"]["method"] in {"physical_delivery", "courier_hand_delivery"}


def test_atns_classifies_as_equipment_supply_with_validation_review() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_001_atns_gbex_units.json")

    assert result["category"] == "equipment_supply"
    assert result["recommendation"] == "MANUAL_REVIEW"
    assert result["classification"]["manual_review_required"] is True


def test_catering_is_rejected() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-CATERING",
            "title": "Catering services for event",
            "category": "catering",
            "extracted_text": "Catering and food service delivery by email.",
            "estimated_profit": 60000.0,
            "gross_margin_ratio": 0.3,
        }
    )

    assert result["recommendation"] == "REJECT"
    assert result["classification"]["excluded_category"] is True


def test_it_equipment_is_rejected() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-IT",
            "title": "IT equipment supply",
            "category": "it equipment",
            "extracted_text": "Laptops and printers to be submitted by email.",
            "estimated_profit": 60000.0,
            "gross_margin_ratio": 0.3,
        }
    )

    assert result["recommendation"] == "REJECT"
    assert result["category"] == "it_equipment"


def test_medical_consumables_are_rejected() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-MEDICAL",
            "title": "Medical consumables supply",
            "category": "medical consumables",
            "extracted_text": "Medical consumables and medical supplies delivery by email.",
            "estimated_profit": 60000.0,
            "gross_margin_ratio": 0.3,
        }
    )

    assert result["recommendation"] == "REJECT"
    assert result["category"] == "medical_consumables"


def test_fuel_diesel_is_rejected() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-FUEL",
            "title": "Diesel supply",
            "category": "fuel",
            "extracted_text": "Bulk diesel and petrol supply.",
            "estimated_profit": 60000.0,
            "gross_margin_ratio": 0.3,
        }
    )

    assert result["recommendation"] == "REJECT"
    assert result["category"] == "fuel_diesel"


def test_submission_methods_are_detected() -> None:
    email = qualify_text("Submit by email to procurement@example.com", {"estimated_profit": 50000.0, "gross_margin_ratio": 0.3})
    portal = qualify_text("Submit on the e-tender portal at https://portal.example.co.za", {"estimated_profit": 50000.0, "gross_margin_ratio": 0.3})
    physical = qualify_text("Hand delivery to the tender box at municipal offices", {"estimated_profit": 50000.0, "gross_margin_ratio": 0.3})

    assert email["submission_method"]["method"] == "email"
    assert email["submission_method"]["automation_candidate"] is True
    assert portal["submission_method"]["method"] == "portal"
    assert physical["submission_method"]["method"] in {"physical_delivery", "courier_hand_delivery"}


def test_compliance_documents_are_detected() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-COMP",
            "title": "Supply and delivery of goods",
            "category": "consumables",
            "extracted_text": "SBD4, SBD6.1, CSD, BBBEE, pricing schedule and quotation on company letterhead required.",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
        }
    )
    matrix = {item["item"]: item for item in result["compliance_matrix"]["items"]}

    assert matrix["SBD4"]["detected"] is True
    assert matrix["SBD6.1"]["detected"] is True
    assert matrix["CSD"]["detected"] is True
    assert matrix["BBBEE"]["detected"] is True
    assert matrix["Pricing schedule"]["detected"] is True
    assert matrix["Quotation on company letterhead"]["detected"] is True


def test_supplier_domain_mapping_works() -> None:
    result = qualify_rfq({"tender_id": "R-DOMAIN", "title": "Building materials", "category": "building materials", "estimated_profit": 50000.0, "gross_margin_ratio": 0.3})

    assert result["supplier_domain"]["supplier_domain"] == "hardware/building suppliers"


def test_profit_gate_rejects_below_threshold() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-PROFIT",
            "title": "Household products",
            "category": "household_products",
            "estimated_profit": 29999.0,
            "gross_margin_ratio": 0.3,
            "extracted_text": "Email submission with pricing schedule.",
        }
    )

    assert result["recommendation"] == "REJECT"
    assert result["viability"]["profit_gate"] is False


def test_margin_gate_rejects_below_threshold() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-MARGIN",
            "title": "Household products",
            "category": "household_products",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.2,
            "extracted_text": "Email submission with pricing schedule.",
        }
    )

    assert result["recommendation"] == "REJECT"
    assert result["viability"]["margin_gate"] is False


def test_final_recommendation_rules_are_enforced() -> None:
    go = qualify_rfq(
        {
            "tender_id": "R-GO",
            "title": "Household products",
            "buyer_name": "Independent Development Trust (IDT)",
            "category": "household_products",
            "submission_instructions": "Submit by email to bids@example.com",
            "extracted_text": "SBD4, SBD6.1, SBD8, SBD9, BBBEE, CSD, Tax PIN, director IDs, bank confirmation, supplier code of conduct, company registration/CIPC, SARS tax clearance, pricing schedule and quotation on company letterhead required.",
            "estimated_profit": 55000.0,
            "gross_margin_ratio": 0.32,
        }
    )
    review = qualify_rfq(
        {
            "tender_id": "R-REVIEW",
            "title": "Technical fabrication item",
            "category": "technical_fabrication",
            "submission_instructions": "Submit by email to bids@example.com",
            "extracted_text": "SBD4, pricing schedule and quotation on company letterhead required.",
            "estimated_profit": 55000.0,
            "gross_margin_ratio": 0.32,
        }
    )
    reject = qualify_rfq(
        {
            "tender_id": "R-REJECT",
            "title": "Diesel supply",
            "category": "fuel",
            "extracted_text": "Bulk diesel supply by email.",
            "estimated_profit": 55000.0,
            "gross_margin_ratio": 0.32,
        }
    )

    assert go["recommendation"] == "GO"
    assert review["recommendation"] == "MANUAL_REVIEW"
    assert reject["recommendation"] == "REJECT"


def test_supply_delivery_matrix_enforces_goods_only_rule() -> None:
    cases = [
        {
            "title": "Supply and delivery of stationery",
            "category": "stationery",
            "extracted_text": "Supply and delivery of stationery by email with pricing schedule.",
            "expected_is_supply_delivery": True,
            "expected_qualification_status": "qualified",
            "expected_recommendation": "GO",
            "expected_auto_quote_recommended": True,
            "expected_rejection_codes": [],
        },
        {
            "title": "Supply and delivery of PPE",
            "category": "ppe",
            "extracted_text": "Supply and delivery of PPE and safety wear by email.",
            "expected_is_supply_delivery": True,
            "expected_qualification_status": "qualified",
            "expected_recommendation": "GO",
            "expected_auto_quote_recommended": True,
            "expected_rejection_codes": [],
        },
        {
            "title": "Supply and delivery of furniture",
            "category": "furniture",
            "extracted_text": "Supply and delivery of office furniture by email.",
            "expected_is_supply_delivery": True,
            "expected_qualification_status": "qualified",
            "expected_recommendation": "GO",
            "expected_auto_quote_recommended": True,
            "expected_rejection_codes": [],
        },
        {
            "title": "Supply and delivery of building materials",
            "category": "building materials",
            "extracted_text": "Supply and delivery of building materials to site by email.",
            "expected_is_supply_delivery": True,
            "expected_qualification_status": "review_required",
            "expected_recommendation": "MANUAL_REVIEW",
            "expected_auto_quote_recommended": False,
            "expected_rejection_codes": [],
        },
        {
            "title": "Supply and delivery of cleaning chemicals",
            "category": "cleaning chemicals",
            "extracted_text": "Supply and delivery of cleaning chemicals and detergents by email.",
            "expected_is_supply_delivery": True,
            "expected_qualification_status": "qualified",
            "expected_recommendation": "GO",
            "expected_auto_quote_recommended": True,
            "expected_rejection_codes": [],
        },
        {
            "title": "Appointment of professional engineering services firm",
            "category": "professional engineering services",
            "extracted_text": "Appointment of professional engineering services firm for upgrade works. Submit by email.",
            "expected_is_supply_delivery": False,
            "expected_qualification_status": "rejected",
            "expected_recommendation": "REJECT",
            "expected_auto_quote_recommended": False,
            "expected_rejection_codes": ["not_supply_and_delivery", "engineering_services_scope", "professional_services_scope"],
        },
        {
            "title": "Consulting services for strategy support",
            "category": "consulting services",
            "extracted_text": "Consulting services for advisory support. Submit by email.",
            "expected_is_supply_delivery": False,
            "expected_qualification_status": "rejected",
            "expected_recommendation": "REJECT",
            "expected_auto_quote_recommended": False,
            "expected_rejection_codes": ["not_supply_and_delivery", "consulting_services_scope", "professional_services_scope"],
        },
        {
            "title": "Legal services panel appointment",
            "category": "legal services",
            "extracted_text": "Legal services appointment for litigation support. Submit by email.",
            "expected_is_supply_delivery": False,
            "expected_qualification_status": "rejected",
            "expected_recommendation": "REJECT",
            "expected_auto_quote_recommended": False,
            "expected_rejection_codes": ["not_supply_and_delivery", "legal_services_scope", "professional_services_scope"],
        },
        {
            "title": "Project management services for capital programme",
            "category": "project management services",
            "extracted_text": "Project management services for delivery oversight. Submit by email.",
            "expected_is_supply_delivery": False,
            "expected_qualification_status": "rejected",
            "expected_recommendation": "REJECT",
            "expected_auto_quote_recommended": False,
            "expected_rejection_codes": ["not_supply_and_delivery", "project_management_services_scope", "professional_services_scope"],
        },
        {
            "title": "Architectural services for office redesign",
            "category": "architectural services",
            "extracted_text": "Architectural services for concept design and drawings. Submit by email.",
            "expected_is_supply_delivery": False,
            "expected_qualification_status": "rejected",
            "expected_recommendation": "REJECT",
            "expected_auto_quote_recommended": False,
            "expected_rejection_codes": ["not_supply_and_delivery", "architectural_services_scope", "professional_services_scope"],
        },
    ]

    for index, case in enumerate(cases, start=1):
        result = qualify_rfq(
            {
                "tender_id": f"R-MATRIX-{index}",
                "title": case["title"],
                "category": case["category"],
                "extracted_text": case["extracted_text"],
                "submission_method": "email",
                "estimated_profit": 60000.0,
                "gross_margin_ratio": 0.3,
            }
        )

        assert result["is_supply_delivery"] is case["expected_is_supply_delivery"]
        assert result["qualification_status"] == case["expected_qualification_status"]
        assert result["recommendation"] == case["expected_recommendation"]
        assert result["auto_quote_recommended"] is case["expected_auto_quote_recommended"]
        assert result["rejection_codes"] == case["expected_rejection_codes"]


def test_validation_readiness_reports_ready_for_complete_supply_delivery() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-VALIDATION-READY",
            "title": "Supply and delivery of office consumables",
            "buyer_name": "Metro Procurement Unit",
            "category": "office supplies",
            "submission_method": "email",
            "source_url": "https://example.org/tenders/R-VALIDATION-READY",
            "detail_url": "https://example.org/tenders/R-VALIDATION-READY/detail",
            "closing_date": "2030-01-01T12:00:00Z",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
            "document_confidence_score": 0.92,
        }
    )

    validation = result["validation_readiness"]
    assert validation["readiness_state"] == "READY"
    assert validation["reason_codes"] == []
    assert validation["compliance_readiness_score"] == 100
    assert result["validation_readiness_state"] == "READY"
    assert result["validation_subtype"] == "NONE"
    assert result["metadata_completeness_state"] == "COMPLETE"


def test_validation_readiness_flags_blockers_and_review_codes() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-VALIDATION-BLOCKED",
            "title": "Catering services for event",
            "buyer_name": "City of Example",
            "category": "catering",
            "submission_method": "email",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
            "document_confidence_score": 0.62,
        }
    )

    validation = result["validation_readiness"]
    assert validation["readiness_state"] == "NOT_READY"
    assert "missing_closing_date" in validation["blocking_reason_codes"]
    assert "excluded_category" in validation["blocking_reason_codes"]
    assert "missing_source_or_detail_url" in validation["review_reason_codes"]
    assert validation["document_confidence_score"] >= 0.55
    assert result["validation_subtype"] == "METADATA_COMPLETENESS"


def test_no_autonomous_submission_action_appears() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-NO-AUTO",
            "title": "Household products",
            "buyer_name": "Independent Development Trust (IDT)",
            "category": "household_products",
            "submission_instructions": "Submit by email to bids@example.com",
            "extracted_text": "SBD4, SBD6.1, SBD8, SBD9, BBBEE, CSD, Tax PIN, director IDs, bank confirmation, supplier code of conduct, company registration/CIPC, SARS tax clearance, pricing schedule and quotation on company letterhead required.",
            "estimated_profit": 55000.0,
            "gross_margin_ratio": 0.32,
        }
    )

    assert "autonomous" not in " ".join(result["warnings"]).lower()
    assert result["recommendation"] == "GO"


def test_qualification_summary_aggregates_counts() -> None:
    summary = build_qualification_summary(
        [
            {"recommendation": "GO", "risk_level": "low", "supplier_domain": {"supplier_domain": "FMCG wholesalers"}, "submission_method": {"method": "email"}, "automation_suitability_score": 95.0, "blockers": []},
            {"recommendation": "MANUAL_REVIEW", "risk_level": "medium", "supplier_domain": {"supplier_domain": "fabrication specialists"}, "submission_method": {"method": "portal"}, "automation_suitability_score": 70.0, "blockers": ["manual review"]},
            {"recommendation": "REJECT", "risk_level": "high", "supplier_domain": {"supplier_domain": "excluded supplier domain"}, "submission_method": {"method": "physical_delivery"}, "automation_suitability_score": 10.0, "blockers": ["excluded category"]},
        ]
    )

    assert summary["recommendation_counts"]["GO"] == 1
    assert summary["recommendation_counts"]["MANUAL_REVIEW"] == 1
    assert summary["recommendation_counts"]["REJECT"] == 1
