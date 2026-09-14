from __future__ import annotations

from pathlib import Path

from app.business_intelligence.thazat_outcomes import (
    load_outcomes,
    record_outcome,
    summarize_outcomes,
)


def test_record_outcome_persists_full_procurement_intelligence(tmp_path: Path) -> None:
    record = record_outcome(
        {
            "buyer": "Example Buyer",
            "rfq": "RFQ-001",
            "category": "ICT equipment",
            "closing_date": "2026-09-21",
            "estimated_value": 500_000,
            "suppliers": ["Supplier A", "Supplier B"],
            "supplier_cost": 300_000,
            "landed_cost": 320_000,
            "bid_price": 425_000,
            "compliance_status": "COMPLIANT",
            "competitors": ["Competitor X"],
            "winner": "Competitor X",
            "winning_price": 397_500,
            "award_date": "2026-10-15",
            "amiri_result": "LOST",
            "reason_won_lost": "PRICE",
        },
        runtime_dir=str(tmp_path),
    )

    assert record["buyer"] == "Example Buyer"
    assert record["rfq"] == "RFQ-001"
    assert record["expected_gp"] == 105_000.0
    assert record["expected_margin_percent"] == 24.71
    assert record["learning"]["price_delta_value"] == 27_500.0
    assert record["learning"]["loss_reason"] == "PRICE"

    persisted = load_outcomes(str(tmp_path))
    assert len(persisted) == 1
    assert persisted[0]["winner"] == "Competitor X"

    summary = summarize_outcomes(str(tmp_path))
    assert summary["total_records"] == 1
    assert summary["lost"] == 1
    assert summary["price_losses"] == 1
