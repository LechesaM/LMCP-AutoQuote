from __future__ import annotations

from pathlib import Path

from app.qualification import analyze_rfq_language, assess_submission_readiness, qualify_fixture, qualify_rfq


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "qualification_rfqs"


def test_compulsory_briefing_detection() -> None:
    report = analyze_rfq_language("Compulsory briefing session is mandatory before closing.")

    assert any(item["name"] == "compulsory_briefing_session" for item in report["detected_patterns"])
    assert "briefing_compulsory" in report["risk_flags"]
    assert "compulsory briefing session" in report["manual_review_triggers"]


def test_site_inspection_detection() -> None:
    report = analyze_rfq_language("Mandatory site inspection required before submission.")

    assert any(item["name"] == "mandatory_site_inspection" for item in report["detected_patterns"])
    assert "site_inspection_required" in report["risk_flags"]


def test_functionality_threshold_detection() -> None:
    report = analyze_rfq_language("Functionality scoring with minimum functionality threshold of 70% applies.")

    assert any(item["name"] == "functionality_scoring" for item in report["detected_patterns"])
    assert any(item["name"] == "minimum_functionality_threshold" for item in report["detected_patterns"])
    assert "functionality threshold" in report["manual_review_triggers"]


def test_cidb_and_local_content_detection() -> None:
    report = analyze_rfq_language("CIDB registration and local content compliance are mandatory.")

    assert any(item["name"] == "cidb_requirement" for item in report["detected_patterns"])
    assert any(item["name"] == "local_content_requirement" for item in report["detected_patterns"])


def test_oem_accreditation_detection() -> None:
    report = analyze_rfq_language("OEM accreditation certificate required for certified installer status.")

    assert any(item["name"] == "oem_or_accreditation_requirement" for item in report["detected_patterns"])
    assert "OEM or accreditation requirement" in report["manual_review_triggers"]


def test_sample_requirement_detection() -> None:
    report = analyze_rfq_language("Sample required with the bid and demo sample must be submitted.")

    assert any(item["name"] == "sample_requirement" for item in report["detected_patterns"])
    assert "sample requirement" in report["manual_review_triggers"]


def test_warranty_detection() -> None:
    report = analyze_rfq_language("A 12 month warranty and guarantee period applies.")

    assert any(item["name"] == "warranty_requirement" for item in report["detected_patterns"])


def test_disqualification_clauses_detected() -> None:
    report = analyze_rfq_language("Late submissions will not be accepted and non-compliance will result in disqualification.")

    assert any(item["name"] == "disqualification_clauses" for item in report["detected_patterns"])
    assert "disqualification clause" in report["disqualification_triggers"]


def test_email_submission_readiness_ready() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_002_idt_household_products.json")

    assert result["readiness_state"] == "READY"
    assert result["recommendation"] == "GO"
    assert result["next_operator_action"]


def test_physical_submission_readiness_manual_only() -> None:
    readiness = assess_submission_readiness(
        compliance_matrix={"missing_required_count": 0, "blockers": []},
        submission_method={"method": "physical_delivery"},
        quote_pack_ready=True,
        pricing_schedule_ready=True,
        risk_engine={"risk_level": "medium", "disqualification_triggers": []},
    )

    assert readiness["readiness_state"] == "MANUAL_ONLY"
    assert readiness["manual_only"] is True


def test_missing_docs_readiness_missing_docs() -> None:
    readiness = assess_submission_readiness(
        compliance_matrix={"missing_required_count": 3, "blockers": ["SBD4 missing", "CSD missing", "Pricing schedule missing"]},
        submission_method={"method": "email"},
        quote_pack_ready=False,
        pricing_schedule_ready=False,
        risk_engine={"risk_level": "low", "disqualification_triggers": []},
    )

    assert readiness["readiness_state"] == "MISSING_DOCS"
    assert readiness["blockers"]


def test_excluded_category_readiness_blocked() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-BLOCK",
            "title": "Catering services",
            "buyer_name": "City of Example",
            "category": "catering",
            "submission_instructions": "Submit by email to bids@example.com",
            "extracted_text": "Catering service delivery.",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
        }
    )

    assert result["readiness_state"] == "BLOCKED"
    assert result["recommendation"] == "REJECT"


def test_sansa_risk_classified_high_manual_review() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_003_sansa_prefab_container.json")

    assert result["risk_level"] in {"high", "blocked"}
    assert result["recommendation"] == "MANUAL_REVIEW"
    assert "physical submission" in " ".join(result["manual_review_triggers"]).lower()


def test_safcol_supplier_match_suitable_but_logistics_medium() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_004_safcol_damsakke_with_pump.json")

    assert result["supplier_match_score"] >= 55
    assert result["supplier_match_intelligence"]["logistics_complexity"] == "medium"
    assert result["supplier_match_intelligence"]["supplier_domain"] == "industrial/equipment suppliers"


def test_idt_ready_when_docs_complete() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_002_idt_household_products.json")

    assert result["readiness_state"] == "READY"
    assert result["supplier_match_score"] >= 70
    assert result["recommendation"] == "GO"


def test_atns_sample_requirement_triggers_manual_review_warning() -> None:
    result = qualify_rfq(
        {
            "tender_id": "R-ATNS-SAMPLE",
            "title": "ATNS network equipment",
            "buyer_name": "ATNS",
            "category": "equipment_supply",
            "submission_instructions": "Submit by email to procurement@atns.co.za",
            "extracted_text": "Supply and delivery of network equipment. Sample required with bid. SBD4, SBD6.1, SBD8, SBD9, BBBEE, CSD, Tax PIN, director IDs, bank confirmation, pricing schedule and quotation on company letterhead required.",
            "estimated_profit": 55000.0,
            "gross_margin_ratio": 0.32,
        }
    )

    assert result["recommendation"] == "MANUAL_REVIEW"
    assert "sample requirement" in " ".join(result["manual_review_triggers"]).lower()


def test_next_operator_action_generated() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_001_atns_gbex_units.json")

    assert result["next_operator_action"]
    assert "autonomous" not in result["next_operator_action"].lower()


def test_no_autonomous_submission_action_generated() -> None:
    result = qualify_fixture(FIXTURES_DIR / "rfq_002_idt_household_products.json")

    assert "autonomous" not in result["next_operator_action"].lower()
    assert "autonomous" not in " ".join(result["warnings"]).lower()
