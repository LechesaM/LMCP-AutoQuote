import json
import smtplib
from pathlib import Path

import imaplib

from app.services import live_rfq_store
from app.services import rfq_lifecycle_service
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.rfq_state_store import RfqStateStore
from app.services.rfq_supplier_validation_service import (
    RETURNABLE_CONDITIONAL,
    RETURNABLE_ELIGIBILITY_DECLARATION,
    RETURNABLE_PRICING_RULE,
    RETURNABLE_REQUIRED_UPLOAD,
    RETURNABLE_SUBMISSION_FORMAT,
    RfqSupplierValidationService,
)


def _block_external(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("external communication must not be attempted")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", blocked)
    monkeypatch.setattr(smtplib, "SMTP", blocked)
    monkeypatch.setattr(smtplib, "SMTP_SSL", blocked)


def _write_fixture_live_store(tmp_path, monkeypatch):
    store = tmp_path / "live_rfqs.json"
    payload = {
        "status": "ok",
        "items": [
            {
                "rfq_number": "6000080601",
                "reference_number": "6000080601",
                "title": "Supply and delivery of paint and welding materials",
                "buyer_name": "Johannesburg Water",
                "closing_date": "2026-08-01T12:00:00+02:00",
                "status": "Published",
                "line_items": [
                    {
                        "item_number": "5897",
                        "description": "PENETRATING OIL SPRAY 400ML",
                        "quantity": 300,
                        "unit": "EA",
                        "unit_cost": 100,
                        "selling_price": 135,
                    },
                    {
                        "item_number": "1846",
                        "description": "GENERAL PURPOSE E6013 WELDING ELECTRODES",
                        "quantity": 500,
                        "unit": "EA",
                        "unit_cost": 50,
                        "selling_price": 90,
                        "manual_override": True,
                    },
                    {
                        "item_number": "9999",
                        "description": "PAINT BRUSH 50MM",
                        "quantity": 20,
                        "unit": "EA",
                        "unit_cost": 10,
                        "selling_price": 13,
                    },
                ],
                "mandatory_returnables": [
                    {"name": "Attach a valid tax compliance PIN", "source_page": 4},
                    {"name": "Quotation must be on company letterhead", "source_page": 4},
                    {"name": "Total value must include taxes", "source_page": 4},
                    {"name": "No bidder may be in the service of the state", "source_page": 5},
                    {"name": "Manufacturer datasheet must be attached", "source_page": 5},
                    {"name": "Where applicable provide authorization letter", "source_page": 5},
                ],
                "submission_pack_status": "blocked_pending_returnables_review",
            },
            {
                "rfq_number": "UNRELATED",
                "title": "Other active RFQ",
                "buyer_name": "Buyer",
                "closing_date": "2026-08-01T12:00:00+02:00",
                "status": "Published",
            },
        ],
    }
    store.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store)
    monkeypatch.setattr(rfq_lifecycle_service, "MANUAL_PRICING_DIR", tmp_path / "manual_pricing")
    return store


def _service(tmp_path):
    lifecycle = RfqLifecycleService(RfqStateStore(tmp_path / "rfq_lifecycle" / "rfqs.json"))
    return RfqSupplierValidationService(
        supplier_validation_dir=tmp_path / "supplier_validation",
        returnables_review_dir=tmp_path / "returnables_review",
        lifecycle_service=lifecycle,
    )


def test_three_supplier_quote_comparison_rejects_non_compliant_cheapest_and_preserves_no_side_effects(tmp_path, monkeypatch):
    _block_external(monkeypatch)
    live_store = _write_fixture_live_store(tmp_path, monkeypatch)
    before_live = live_store.read_text(encoding="utf-8")
    service = _service(tmp_path)

    payload = {
        "supplier_quotes": [
            {
                "supplier_name": "Cheap Supplier",
                "supplier_quote_reference": "CS-1",
                "line_items": [
                    {
                        "item_number": "5897",
                        "description": "Penetrating oil spray",
                        "quantity": 300,
                        "unit_cost": 80,
                        "stock_availability": "in stock",
                        "lead_time": "2 days",
                    }
                ],
            },
            {
                "supplier_name": "Compliant Supplier",
                "supplier_quote_reference": "OK-1",
                "line_items": [
                    {
                        "item_number": "5897",
                        "description": "Penetrating oil spray",
                        "quantity": 300,
                        "unit_cost": 90,
                        "stock_availability": "in stock",
                        "lead_time": "1 day",
                        "datasheet_attached": True,
                        "compliance_certificate_attached": True,
                    }
                ],
            },
            {
                "supplier_name": "Late Supplier",
                "supplier_quote_reference": "LATE-1",
                "line_items": [
                    {
                        "item_number": "5897",
                        "description": "Penetrating oil spray",
                        "quantity": 300,
                        "unit_cost": 95,
                        "stock_availability": "available",
                        "lead_time": "14 days",
                        "datasheet_attached": True,
                        "compliance_certificate_attached": True,
                    }
                ],
            },
        ]
    }

    result = service.save_supplier_quotes("6000080601", payload)
    row = next(item for item in result["comparison_rows"] if item["item_number"] == "5897")

    assert result["status"] == "ok"
    assert row["supplier_quote_count"] == 3
    assert row["lowest_compliant_cost"] == 90
    assert row["recommended_supplier"]["supplier_name"] == "Compliant Supplier"
    cheap = next(item for item in row["supplier_quotes"] if item["supplier_name"] == "Cheap Supplier")
    assert cheap["eligible_for_preference"] is False
    assert "missing_datasheet" in cheap["missing_documents"]
    assert result["quote_pack_generated"] is False
    assert result["submission_pack_generated"] is False
    assert result["external_connection_attempted"] is False
    assert live_store.read_text(encoding="utf-8") == before_live
    assert not (tmp_path / "runtime").exists()


def test_ambiguous_item_match_is_rejected(tmp_path, monkeypatch):
    _block_external(monkeypatch)
    _write_fixture_live_store(tmp_path, monkeypatch)
    service = _service(tmp_path)
    buyer_rows = [
        {"row_id": "a", "item_number": "1", "description": "Blue paint brush 50mm"},
        {"row_id": "b", "item_number": "2", "description": "Red paint brush 50mm"},
    ]

    match = service.match_quote_line(buyer_rows, {"description": "paint brush 50mm", "unit_cost": 12})

    assert match["status"] == "ambiguous"
    assert match["row_id"] is None


def test_preferred_supplier_selection_is_explicit_and_preserves_provisional_audit_and_override(tmp_path, monkeypatch):
    _block_external(monkeypatch)
    _write_fixture_live_store(tmp_path, monkeypatch)
    service = _service(tmp_path)
    service.save_supplier_quotes(
        "6000080601",
        {
            "supplier_quotes": [
                {
                    "supplier_name": "Weld Supplier",
                    "supplier_quote_reference": "WELD-1",
                    "line_items": [
                        {
                            "item_number": "1846",
                            "description": "E6013 welding electrodes",
                            "quantity": 500,
                            "unit_cost": 45,
                            "stock_availability": "in stock",
                            "lead_time": "1 day",
                            "datasheet_attached": True,
                            "compliance_certificate_attached": True,
                        }
                    ],
                }
            ]
        },
    )

    selected = service.select_preferred_supplier(
        "6000080601",
        {"selections": [{"row_id": "1846", "supplier_name": "Weld Supplier", "supplier_quote_reference": "WELD-1"}]},
    )
    row = next(item for item in selected["comparison_rows"] if item["item_number"] == "1846")
    stored = json.loads((tmp_path / "supplier_validation" / "6000080601.json").read_text(encoding="utf-8"))

    assert row["supplier_validation_status"] == "SUPPLIER_VALIDATED"
    assert row["preferred_supplier"]["pricing_source"] == "supplier_validated"
    assert row["preferred_supplier"]["manual_selling_override_preserved"] is True
    assert stored["audit_history"][0]["previous_pricing_source"] == "operator_provisional_estimate"
    assert stored["safety"]["quote_pack_generated"] is False
    assert stored["safety"]["submission_pack_generated"] is False


def test_returnables_are_classified_and_submission_remains_blocked(tmp_path, monkeypatch):
    _block_external(monkeypatch)
    _write_fixture_live_store(tmp_path, monkeypatch)
    service = _service(tmp_path)

    result = service.get_returnables_review_workspace("6000080601")

    assert result["status"] == "ok"
    assert result["returnable_count"] == 6
    assert result["category_counts"][RETURNABLE_ELIGIBILITY_DECLARATION] == 2
    assert result["category_counts"][RETURNABLE_SUBMISSION_FORMAT] == 1
    assert result["category_counts"][RETURNABLE_PRICING_RULE] == 1
    assert result["category_counts"][RETURNABLE_REQUIRED_UPLOAD] == 1
    assert result["category_counts"][RETURNABLE_CONDITIONAL] == 1
    assert result["submission_blocked"] is True
    assert result["missing_or_unverified_count"] == 6


def test_mandatory_evidence_cannot_be_completed_without_proof_and_conditional_needs_reason(tmp_path, monkeypatch):
    _block_external(monkeypatch)
    _write_fixture_live_store(tmp_path, monkeypatch)
    service = _service(tmp_path)
    workspace = service.get_returnables_review_workspace("6000080601")
    required = next(item for item in workspace["returnables"] if item["category"] == RETURNABLE_REQUIRED_UPLOAD)
    conditional = next(item for item in workspace["returnables"] if item["category"] == RETURNABLE_CONDITIONAL)

    blocked = service.save_returnables_review(
        "6000080601",
        {
            "reviews": [
                {"returnable_id": required["returnable_id"], "review_status": "PRESENT", "approval_state": "APPROVED"},
                {"returnable_id": conditional["returnable_id"], "review_status": "NOT_APPLICABLE", "approval_state": "REVIEWED"},
            ]
        },
    )

    assert blocked["status"] == "blocked"
    assert any("mandatory_evidence_required" in item for item in blocked["errors"])
    assert any("not_applicable_reason_required" in item for item in blocked["errors"])
    assert not (tmp_path / "returnables_review" / "6000080601.json").exists()


def test_returnables_review_save_is_idempotent_with_evidence_and_does_not_complete_submission(tmp_path, monkeypatch):
    _block_external(monkeypatch)
    _write_fixture_live_store(tmp_path, monkeypatch)
    service = _service(tmp_path)
    workspace = service.get_returnables_review_workspace("6000080601")
    required = next(item for item in workspace["returnables"] if item["category"] == RETURNABLE_REQUIRED_UPLOAD)
    payload = {
        "reviews": [
            {
                "returnable_id": required["returnable_id"],
                "review_status": "PRESENT",
                "approval_state": "REVIEWED",
                "evidence_file": "datasheet.pdf",
                "reviewer": "operator",
            }
        ]
    }

    first = service.save_returnables_review("6000080601", payload)
    second = service.save_returnables_review("6000080601", payload)
    stored = json.loads((tmp_path / "returnables_review" / "6000080601.json").read_text(encoding="utf-8"))

    assert first["saved"] is True
    assert second["saved"] is True
    assert len(stored["reviews"]) == 1
    assert stored["safety"]["quote_pack_generated"] is False
    assert stored["safety"]["submission_pack_generated"] is False
    assert second["submission_blocked"] is True


def test_phase33_counts_and_unrelated_rfq_remain_unchanged(tmp_path, monkeypatch):
    _block_external(monkeypatch)
    live_store = _write_fixture_live_store(tmp_path, monkeypatch)
    before = json.loads(live_store.read_text(encoding="utf-8"))
    service = _service(tmp_path)

    service.save_supplier_quotes(
        "6000080601",
        {
            "supplier_quotes": [
                {
                    "supplier_name": "Paint Supplier",
                    "supplier_quote_reference": "P-1",
                    "line_items": [
                        {
                            "item_number": "9999",
                            "description": "Paint brush",
                            "quantity": 20,
                            "unit_cost": 8,
                            "stock_availability": "in stock",
                            "lead_time": "1 day",
                            "datasheet_attached": True,
                            "compliance_certificate_attached": True,
                        }
                    ],
                }
            ]
        },
    )

    after = json.loads(live_store.read_text(encoding="utf-8"))
    assert live_rfq_store.list_active_rfqs()["count"] == 2
    assert before == after
    assert after["items"][1]["rfq_number"] == "UNRELATED"
