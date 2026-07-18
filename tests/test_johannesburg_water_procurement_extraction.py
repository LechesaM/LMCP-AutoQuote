import json
from pathlib import Path


JW_PAGES = [
    {
        "page": 1,
        "text": """
MATERIAL NUMBER DESCRIPTION BRAND NAME OFFERED UOM QTY REQURIED PRICE QUOTED EXCL. OF VAT DIS
5897   PENETRATING OIL SPRAY 400ML EA              300
1846   GENERAL PURPOSE E6013 WELDING ELECTRODES
3.15MM 5KG BOX RADIOGRAPHIC QUALITY AWS A5.1
SANS 2560 E380 RC11 CLASIFICATION
EA              500
508   PAINT AEROSOL RED ENAMEL 250 GRAM EA               50
509   PAINT AEROSOL YELLOW ENAMEL 250 GRAM EA               12
2307   PAINT AEROSOL BLACK ENAMEL 250 GRAM EA                8
2308   PAINT AEROSOL WHITE 250 GRAM EA               44
1287   TOOL DISC CUTTING STEEL 230 X 3 X 22.23MM EN 12413
APPROVED
EA              600
1288   TOOL DISC CUTTING STEEL 115 X 2.5 X 22.23MM EN EA              770
Mthetho Maqutyana
""",
    },
    {
        "page": 2,
        "text": """
MATERIAL NUMBER DESCRIPTION BRAND NAME OFFERED UOM QTY REQURIED PRICE QUOTED EXCL. OF VAT DIS
12413 APPROVED
1927   TOOL BRUSH STAINLESS STEEL WIRE 290MM WELDERS
WITH A LONG HANDLE
EA               50
1986   TOOL HAMMER CHIPPING SPRING HANDLE EA               50
Notes:
""",
    },
    {
        "page": 4,
        "text": """
ALL SUPPLIERS RESPONDING TO QUOTATIONS SHOULD BE REGISTERED ON CENTRAL SUPPLIER DATABASE (CSD)
1. QUOTATIONS MUST BE ON COMPANY LETTERHEADS
2. QUOTATIONS RECEIVED AFTER CLOSIND DATE AND
TIME WILL NOT BE ACCEPTED.
3. QUOTATIONS WITHOUT BRAND NAMES WHERE
REQUIRED WILL NOT BE ACCEPTED
4. TOTAL QUOTATION VALUE TO INCLUDE ALL APPLICABLE TAXES.
5. SUBMIT A COPY OF A VALID BBBEE CERTIFICATE OR SWORN
AFFIDAVIT.
6. ENSURE THAT ALL ATTACHED MBD'S ARE DULY COMPLETED AND
SIGNED
7. SUBMIT A COPY OF VALID LEASE AGREEMENT OR MUNICIPAL
ACCOUNT STATEMENT NOT OLDER THAN 3 MONTHS
Directors:
""",
    },
    {
        "page": 5,
        "text": """
MANDATORY REQUIREMENTS:
1.1 Full Completion of the Bill of Quantities (BOQ)/ Specification (where applicable)
1.2 Attendance of compulsory site briefing (where applicable)
1.3 Attachment of datasheet, reference letter, proof of certification, proof of accreditation, functionality requirements (where applicable)
1.4 No RFQ will be considered from persons in the service of the state
1.5 No Bidder who is blacklisted by National Treasury or any National Authority due to non-performance will be considered
1.6 All Quotes should be on PDF (MS WORD, MS EXCEL, PICTURES ARE NOT ALLOWED) and On Company Letterhead
1.7 Submission of a Joint Venture Agreement, where applicable, which has been properly signed by all parties
Directors:
""",
    },
]


def _active_rfq():
    return {
        "rfq_number": "6000080601",
        "reference_number": "6000080601",
        "buyer_name": "Johannesburg Water",
        "title": "Supply and deliver materials as per attached RFQ.",
        "closing_date": "2026-07-24T12:00:00+02:00",
        "status": "open",
        "documents": [
            {
                "file_name": "6000080601_Paint and Welding Materials_JHB Water.pdf",
                "download_url": "https://example.test/6000080601.pdf",
            }
        ],
        "manual_submission_required": True,
        "autonomous_downstream_enabled": False,
    }


def test_johannesburg_water_pages_extract_pricing_rows_and_returnables():
    from app.services.document_ingestion_service import (
        extract_johannesburg_water_pricing_rows_from_pages,
        extract_johannesburg_water_returnables_from_pages,
    )

    rows = extract_johannesburg_water_pricing_rows_from_pages(
        JW_PAGES,
        source_document="6000080601_Paint and Welding Materials_JHB Water.pdf",
        reference_number="6000080601",
    )
    returnables = extract_johannesburg_water_returnables_from_pages(
        JW_PAGES,
        source_document="6000080601_Paint and Welding Materials_JHB Water.pdf",
    )

    assert len(rows) == 10
    assert rows[0]["material_number"] == "5897"
    assert rows[0]["quantity"] == 300.0
    assert rows[0]["unit"] == "EA"
    assert rows[0]["source_page"] == 1
    assert rows[-1]["material_number"] == "1986"
    assert rows[-1]["source_page"] == 2
    assert all(row["unit_price"] is None and row["line_total"] is None for row in rows)
    assert all(row["source_document"].endswith(".pdf") for row in rows)

    assert len(returnables) == 14
    assert any("BBBEE CERTIFICATE" in item["requirement_description"] for item in returnables)
    assert any("Full Completion of the Bill of Quantities" in item["requirement_description"] for item in returnables)
    assert all(item["manual_review_required"] is True for item in returnables)
    assert {item["source_page"] for item in returnables} == {4, 5}


def test_procurement_extraction_populates_dashboard_and_pricing_contract(monkeypatch, tmp_path):
    from app.services import document_ingestion_service as service

    pdf_path = tmp_path / "6000080601_Paint and Welding Materials_JHB Water.pdf"
    pdf_path.write_text("synthetic")
    monkeypatch.setattr(service, "_source_page_texts_from_pdf", lambda path: JW_PAGES)

    result = service.build_johannesburg_water_procurement_extraction(pdf_path, rfq=_active_rfq())

    assert len(result["line_items"]) == 10
    assert len(result["pricing_schedule"]["rows"]) == 10
    assert result["boqs"][0]["type"] == "BOQ"
    assert result["pricing_schedules"][0]["type"] == "Pricing Schedule"
    assert result["rfq_requirement_rows_count"] == 10
    assert result["pricing_ready_from_requirements"] is True
    assert result["manual_pricing_ready"] is True
    assert result["supplier_quotes_required_for_pricing"] is False
    assert len(result["mandatory_returnables"]) == 14
    assert len(result["missing_returnables"]) == 14
    assert result["returnables_assessment_status"] == "unassessed"
    assert result["submission_pack_status"] == "blocked_pending_returnables_review"
    assert result["operator_approval_required"] is True
    assert result["manual_submission_required"] is True


def test_one_rfq_live_store_update_is_idempotent_and_preserves_operator_pricing(monkeypatch, tmp_path):
    from app.services import document_ingestion_service as service

    pdf_path = tmp_path / "6000080601_Paint and Welding Materials_JHB Water.pdf"
    pdf_path.write_text("synthetic")
    monkeypatch.setattr(service, "_source_page_texts_from_pdf", lambda path: JW_PAGES)

    target = _active_rfq()
    target["line_items"] = [{"material_number": "5897", "supplier_rate": 12.5, "operator_notes": "keep"}]
    unrelated = {
        "rfq_number": "UNRELATED-1",
        "buyer_name": "Other Buyer",
        "title": "Supply stationery",
        "closing_date": "2026-07-30T12:00:00+02:00",
        "status": "open",
    }
    store_path = tmp_path / "live_rfqs.json"
    store_path.write_text(json.dumps({"status": "ok", "count": 2, "items": [target, unrelated]}, indent=2))

    first = service.apply_procurement_extraction_to_live_rfq("6000080601", pdf_path, store_path=store_path)
    second = service.apply_procurement_extraction_to_live_rfq("6000080601", pdf_path, store_path=store_path)
    data = json.loads(store_path.read_text())
    updated = data["items"][0]

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert first["pricing_row_count"] == 10
    assert second["pricing_row_count"] == 10
    assert len(updated["line_items"]) == 10
    assert [row["material_number"] for row in updated["line_items"]].count("5897") == 1
    assert updated["line_items"][0]["supplier_rate"] == 12.5
    assert updated["line_items"][0]["operator_notes"] == "keep"
    assert updated["operational_classification"] if "operational_classification" in updated else "ACTIVE"
    assert data["items"][1] == unrelated
