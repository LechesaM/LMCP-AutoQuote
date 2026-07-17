from app.services.rfq_requirement_pack_service import build_requirement_pack, normalize_requirement_rows


def test_embedded_pdf_schedule_creates_canonical_buyer_rows_without_boq_filename():
    rows = normalize_requirement_rows(
        [
            {
                "buyer_line_number": "1",
                "description": "Supply paper",
                "qty": "20",
                "uom": "reams",
                "source_document": "Main Document.pdf",
                "source_page": 1,
                "source_table": "pricing_table",
                "source_row": 1,
            }
        ],
        source_type="embedded_pricing_schedule",
        reference_number="RFQ-PDF-001",
    )
    pack = build_requirement_pack(rows, reference_number="RFQ-PDF-001")

    assert pack["embedded_pricing_schedule_detected"] is True
    assert pack["standalone_boq_detected"] is False
    assert pack["buyer_row_count"] == 1
    assert pack["pricing_ready_from_requirements"] is True


def test_original_buyer_order_and_repeated_lines_are_preserved():
    rows = normalize_requirement_rows(
        [
            {"buyer_line_number": "10", "description": "Same item", "quantity": 300, "unit": "each"},
            {"buyer_line_number": "20", "description": "Same item", "quantity": 100, "unit": "each"},
            {"buyer_line_number": "30", "description": "Same item", "quantity": 300, "unit": "each"},
        ],
        source_type="embedded_pricing_schedule",
    )

    assert [row["buyer_line_number"] for row in rows] == ["10", "20", "30"]
    assert [row["quantity"] for row in rows] == [300.0, 100.0, 300.0]


def test_multiline_description_and_blank_pages_do_not_create_rows():
    rows = normalize_requirement_rows(
        [
            {"description": "Heavy duty pipe wrench continued specification text", "quantity": 4, "unit": "each"},
            {"description": "", "quantity": "", "unit": ""},
            {"description": "Description Quantity Unit Price Total Price", "quantity": "", "unit": ""},
        ],
        source_type="embedded_pricing_schedule",
    )

    assert len(rows) == 1
    assert rows[0]["description"].startswith("Heavy duty")


def test_subtotal_vat_and_grand_total_rows_are_excluded():
    rows = normalize_requirement_rows(
        [
            {"description": "Supply gloves", "quantity": 10, "unit": "each"},
            {"description": "Subtotal", "amount": 100},
            {"description": "VAT", "amount": 15},
            {"description": "Grand Total", "amount": 115},
        ],
        source_type="embedded_pricing_schedule",
    )

    assert len(rows) == 1
    assert rows[0]["description"] == "Supply gloves"


def test_brand_datasheet_sample_and_standards_are_extracted():
    rows = normalize_requirement_rows(
        [
            {
                "description": "Pipe wrench brand name required manufacturer datasheet required samples may be required SANS 1022 ISO 9001",
                "quantity": 2,
                "unit": "each",
            }
        ],
        source_type="embedded_pricing_schedule",
    )

    assert rows[0]["brand_required"] is True
    assert rows[0]["datasheet_required"] is True
    assert rows[0]["sample_may_be_required"] is True
    assert "SANS 1022" in rows[0]["standards"]
    assert "ISO 9001" in rows[0]["standards"]
