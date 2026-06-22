from __future__ import annotations

from app.services.tender_qualification import qualify_opportunity


def test_qualify_opportunity_reads_dict_fields() -> None:
    opportunity = {
        "title": "Supply and Delivery of Stationery and Pre-Printed Stationery for the period of 36 months",
        "description": "Supply and Delivery of Stationery and Pre-Printed Stationery for the period of 36 months",
        "category": "supply",
        "buyer_name": "Kwadukuza Municipality",
        "province": "Gauteng",
        "submission_method": "portal",
        "source_url": "https://www.etenders.gov.za/Home/opportunities",
        "closing_at": "2026-07-30T10:00:00+02:00",
        "estimated_contract_value": 150000.0,
    }

    result = qualify_opportunity(opportunity)

    assert result.submission_method == "portal"
    assert result.province == "Gauteng"
    assert result.days_to_deadline is not None
    assert result.qualification_status in {"qualified", "review_required"}
