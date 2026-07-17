import json
from pathlib import Path

from app.services.rfq_requirement_pack_service import (
    SOURCE_PRIORITY,
    build_pricing_workspace_contract,
    build_requirement_pack,
    normalize_requirement_row,
    normalize_requirement_rows,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rfq_requirement_pack"


def _fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text())


def test_alias_normalization_and_pricing_ready_from_embedded_schedule():
    payload = _fixture("embedded_pricing_schedule.json")
    rows = normalize_requirement_rows(
        payload["rows"],
        source_type=payload["source_type"],
        source_document=payload["filename"],
    )
    pack = build_requirement_pack(rows, reference_number="RFQ-EMBED-001")

    assert pack["buyer_row_count"] == 2
    assert pack["verified_buyer_row_count"] == 2
    assert pack["review_buyer_row_count"] == 0
    assert pack["pricing_schedule_detected"] is True
    assert pack["standalone_boq_detected"] is False
    assert pack["pricing_ready_from_requirements"] is True
    assert rows[0]["quantity"] == 20.0
    assert rows[0]["unit"] == "reams"
    assert rows[0]["buyer_rate"] is None
    assert rows[0]["buyer_amount"] is None


def test_missing_quantities_are_preserved_for_review_not_pricing_ready():
    payload = _fixture("missing_quantities.json")
    rows = normalize_requirement_rows(
        payload["rows"],
        source_type=payload["source_type"],
        source_document=payload["filename"],
    )
    pack = build_requirement_pack(rows)

    assert pack["buyer_row_count"] == 1
    assert pack["verified_buyer_row_count"] == 0
    assert pack["review_buyer_row_count"] == 1
    assert pack["pricing_ready_from_requirements"] is False
    assert rows[0]["review_required"] is True
    assert "missing_quantity" in rows[0]["review_reasons"]


def test_repeated_buyer_lines_are_preserved_without_physical_duplicate_evidence():
    rows = normalize_requirement_rows(
        [
            {"description": "Supply toner cartridges", "quantity": "5", "unit": "each"},
            {"item_description": "Supply toner cartridges", "qty": 5, "uom": "each"},
        ],
        source_type="embedded_pricing_schedule",
    )

    assert len(rows) == 2


def test_clear_physical_extractor_duplicate_is_suppressed():
    rows = normalize_requirement_rows(
        [
            {
                "description": "Supply toner cartridges",
                "quantity": "5",
                "unit": "each",
                "source_document": "Main.pdf",
                "source_table": "table_1",
                "source_row": 3,
            },
            {
                "item_description": "Supply toner cartridges",
                "qty": 5,
                "uom": "each",
                "source_document": "Main.pdf",
                "source_table": "table_1",
                "source_row": 3,
            },
        ],
        source_type="embedded_pricing_schedule",
    )

    assert len(rows) == 1


def test_lump_sum_optional_and_total_rows():
    payload = _fixture("lump_sum_optional_totals.json")
    rows = normalize_requirement_rows(
        payload["rows"],
        source_type=payload["source_type"],
        source_document=payload["filename"],
    )
    pack = build_requirement_pack(rows)

    assert len(rows) == 2
    assert rows[0]["quantity"] is None
    assert rows[0]["review_required"] is False
    assert "lump_sum_basis" in rows[0]["evidence"]
    assert rows[1]["commercial_flags"]["optional"] is True
    assert all("Total Price" not in row["description"] for row in rows)
    assert pack["pricing_ready_from_requirements"] is True


def test_source_evidence_and_page_table_are_preserved():
    row = normalize_requirement_row(
        {
            "item_number": "7",
            "product_description": "Supply archive boxes",
            "qty": "12",
            "uom": "box",
            "source_page": 9,
            "source_table": "table_2",
            "evidence": ["pdf_table"],
        },
        source_type="embedded_pricing_schedule",
        source_document="Main Document.pdf",
    )

    assert row is not None
    assert row["line_number"] == "7"
    assert row["buyer_line_number"] == "7"
    assert row["requirement_row_id"].startswith("REQ-")
    assert row["source_document"] == "Main Document.pdf"
    assert row["source_page"] == 9
    assert row["source_table"] == "table_2"
    assert row["source_type"] == "embedded_pricing_schedule"
    assert "pdf_table" in row["evidence"]


def test_python39_contract_and_source_priority_constants():
    assert SOURCE_PRIORITY["formal_buyer_pricing_schedule"] > SOURCE_PRIORITY["specification_table"]
    assert SOURCE_PRIORITY["embedded_pricing_schedule"] > SOURCE_PRIORITY["main_document_table"]


def test_pricing_workspace_contract_blocks_review_rows():
    pack = build_requirement_pack(
        [{"description": "Supply archive boxes", "quantity": "", "unit": ""}],
        reference_number="RFQ-REVIEW",
    )
    contract = build_pricing_workspace_contract(pack)

    assert contract["pricing_ready"] is False
    assert contract["operator_review_required"] is True
    assert contract["blocking_reviews"]
