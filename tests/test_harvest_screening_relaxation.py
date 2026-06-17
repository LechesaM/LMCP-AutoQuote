from __future__ import annotations

from app.services.tender_harvester import _classify_item


def _classify(title: str, description: str):
    item = {
        "title": title,
        "description": description,
        "raw_text": f"{title} {description}",
        "submission_method": "portal",
        "buyer_rfq_number": "",
        "reference_number": "",
        "rfq_number": "",
    }
    return _classify_item(item, minimum_margin_pct=25.0, minimum_profit=30000.0)


def test_mixed_scope_quote_ready_rfqs_are_not_hard_blocked() -> None:
    result = _classify(
        "Supplies: General",
        "SUPPLY AND DELIVERY OF ROAD BLOCK MINI BUS WITH SOFTWARE FOR TRAFFIC SERVICES 09/06/2026 in 16 days",
    )

    assert result["eligible"] is True
    assert result["quote_ready"] is True
    assert result["exclusion_reason"] == ""
    assert result["pipeline_status"] == "quote_ready"


def test_repair_and_installation_supply_rfq_can_still_pass() -> None:
    result = _classify(
        "Repair and installation of machinery and equipment",
        "Repair and installation of machinery and equipment SUPPLY, DELIVER, OFF-LOADING AND INSTALLATION OF TRAINING MACHINERY AND EQUIPMENT FOR ALL OCCUPATIONAL PROGRAMS 10/06/2026 in 36 days",
    )

    assert result["eligible"] is True
    assert result["quote_ready"] is True
    assert result["exclusion_reason"] == ""
    assert result["pipeline_status"] == "quote_ready"
