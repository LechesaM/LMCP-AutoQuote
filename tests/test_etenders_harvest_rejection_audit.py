from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_etenders_harvest_rejection import audit_etenders_harvest_rejection


def _item(
    rfq_id: str,
    *,
    buyer_name: str = "National Treasury eTenders",
    category: str = "supply",
    rejected: bool = True,
    qualified: bool = False,
    acquisition_status: str = "skipped",
    rejection_reasons: list[str] | None = None,
    supply_delivery: bool = False,
    valid_submission: bool = False,
    excluded: bool = False,
    briefing_compulsory: bool = False,
    qualification_result: dict | None = None,
) -> dict:
    qualification_result = qualification_result or {
        "qualification_status": "rejected" if rejected else "qualified",
        "qualified": qualified,
        "rejected": rejected,
        "review_required": False,
        "is_supply_delivery": supply_delivery,
        "has_valid_submission_method": valid_submission,
        "excluded_by_business_rules": excluded,
        "briefing_compulsory": briefing_compulsory,
        "estimated_contract_value": None,
        "estimated_profit_value": None,
        "province_ok": True,
        "days_to_deadline": None,
        "rejection_reasons": rejection_reasons or [],
        "review_reasons": [],
    }
    return {
        "identity": {"rfq_id": rfq_id, "buyer_name": buyer_name},
        "raw_extracted": {"rfq_id": rfq_id, "buyer_name": buyer_name, "category": category},
        "filtered": {
            "rejected": rejected,
            "qualified": qualified,
            "qualification_status": "rejected" if rejected else "qualified",
            "recommendation": "REJECT" if rejected else "APPROVE",
            "qualification_result": qualification_result,
        },
        "acquisition": {
            "status": acquisition_status,
            "downloaded_count": 0,
            "seed_urls": [],
            "document_confidence_score": 0.0,
        },
        "persist": {"raw_upserted": True, "filtered_upserted": True},
    }


def test_harvest_rejection_audit_separates_harvest_from_acquisition(tmp_path: Path) -> None:
    input_path = tmp_path / "etenders_harvest_items.json"
    input_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-20T00:00:00Z",
                "count": 3,
                "items": [
                    _item(
                        "RFQ-001",
                        rejection_reasons=["Tender is not clearly supply and delivery", "No valid submission route identified"],
                        supply_delivery=False,
                        valid_submission=False,
                        acquisition_status="skipped",
                    ),
                    _item(
                        "RFQ-002",
                        rejection_reasons=["Tender is not clearly supply and delivery"],
                        supply_delivery=False,
                        valid_submission=True,
                        acquisition_status="failed",
                    ),
                    _item(
                        "RFQ-003",
                        rejected=False,
                        qualified=True,
                        acquisition_status="skipped",
                        supply_delivery=True,
                        valid_submission=True,
                    ),
                ],
            }
        ),
        encoding="utf-8",
    )

    result = audit_etenders_harvest_rejection(input_path=input_path, output_dir=tmp_path / "out")

    payload = result["payload"]
    metrics = payload["metrics"]
    assert metrics["harvested_items"] == 3
    assert metrics["persisted_raw_items"] == 3
    assert metrics["qualified_items"] == 1
    assert metrics["rejected_items"] == 2
    assert metrics["acquisition_skipped_items"] == 2
    assert metrics["acquisition_failed_items"] == 1
    assert metrics["top_rejection_causes"][0][0] == "not_supply_and_delivery"
    assert (tmp_path / "out" / "etenders_harvest_rejection_audit.json").exists()
    assert (tmp_path / "out" / "etenders_harvest_rejection_audit.md").exists()
    assert Path(result["docs_path"]).exists()


def test_harvest_rejection_audit_registry_is_not_mutated(tmp_path: Path) -> None:
    registry_path = Path("app/data/harvest_sources.json")
    before = registry_path.stat().st_mtime_ns

    input_path = tmp_path / "etenders_harvest_items.json"
    input_path.write_text(json.dumps({"status": "ok", "count": 0, "items": []}), encoding="utf-8")

    audit_etenders_harvest_rejection(input_path=input_path, output_dir=tmp_path / "out")

    assert registry_path.stat().st_mtime_ns == before


def test_harvest_rejection_audit_accepts_items_alias(tmp_path: Path) -> None:
    input_path = tmp_path / "run-123" / "etenders_harvest_items.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        json.dumps({"status": "ok", "count": 1, "items": [_item("RFQ-ALIAS", rejection_reasons=["Tender is not clearly supply and delivery"])]}),
        encoding="utf-8",
    )

    result = audit_etenders_harvest_rejection(input_path=input_path, output_dir=tmp_path / "out")
    assert result["payload"]["metrics"]["harvested_items"] == 1
    assert result["payload"]["metrics"]["rejected_items"] == 1


def test_harvest_rejection_audit_counts_prepared_and_deferred_acquisition(tmp_path: Path) -> None:
    input_path = tmp_path / "etenders_harvest_items.json"
    input_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-20T00:00:00Z",
                "count": 2,
                "items": [
                    _item("RFQ-PREPARED", acquisition_status="prepared", qualification_result={"qualification_status": "qualified", "qualified": True, "rejected": False, "review_required": False, "is_supply_delivery": True, "has_valid_submission_method": True, "excluded_by_business_rules": False, "briefing_compulsory": False, "estimated_contract_value": 1000, "estimated_profit_value": 250, "province_ok": True, "days_to_deadline": 10, "rejection_reasons": [], "review_reasons": []}, rejected=False, qualified=True, supply_delivery=True, valid_submission=True),
                    _item("RFQ-DEFERRED", acquisition_status="deferred"),
                ],
            }
        ),
        encoding="utf-8",
    )

    result = audit_etenders_harvest_rejection(input_path=input_path, output_dir=tmp_path / "out")
    metrics = result["payload"]["metrics"]
    assert metrics["acquisition_prepared_items"] == 1
    assert metrics["acquisition_deferred_items"] == 1
