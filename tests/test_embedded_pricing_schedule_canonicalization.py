import json
import sys
import types
from pathlib import Path


def test_boq_extraction_emits_requirement_pack_for_embedded_csv_schedule(tmp_path, monkeypatch):
    from app.services import rfq_boq_extraction_engine as engine

    csv_path = tmp_path / "Main Document.csv"
    csv_path.write_text(
        "Item,Description,Quantity,Unit,Unit Price,Total Price\n"
        "1,Supply copy paper,20,reams,,\n"
        "2,Supply pens,100,each,,\n"
    )

    monkeypatch.setattr(engine, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(engine, "DOWNLOAD_DIR", tmp_path / "runtime" / "downloads")
    monkeypatch.setattr(engine, "REPORT_DIR", tmp_path / "runtime" / "reports")
    monkeypatch.setattr(engine, "EXTRACTED_DIR", tmp_path / "runtime" / "extracted")

    result = engine.extract_rfq_boq(
        {
            "title": "Embedded pricing schedule fixture",
            "buyer_rfq_number": "RFQ-CSV-001",
            "document_intelligence_result": {
                "downloads": [{"status": "downloaded", "path": str(csv_path), "url": "fixture://main"}]
            },
        }
    )

    assert result["line_item_count"] == 2
    assert result["rfq_requirement_rows_count"] == 2
    assert result["verified_requirement_rows_count"] == 2
    assert result["pricing_ready_from_requirements"] is True
    assert {row["source_type"] for row in result["rfq_requirement_rows"]} == {"embedded_pricing_schedule"}
    assert Path(result["paths"]["normalized_boq"]).is_relative_to(tmp_path)


def test_docx_embedded_schedule_mapping_preserves_review_rows(tmp_path, monkeypatch):
    from app.services import rfq_docx_main_document_intelligence as engine

    docx_path = tmp_path / "RFQ Document.docx"
    docx_path.write_text("synthetic")

    monkeypatch.setattr(engine, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(
        engine,
        "_read_docx",
        lambda path: {
            "status": "ok",
            "error": "",
            "paragraphs": ["Pricing Schedule"],
            "text": "Pricing Schedule",
            "tables": [
                [
                    ["Item", "Description", "Quantity", "Unit", "Unit Price", "Total Price"],
                    ["1", "Supply copy paper", "20", "reams", "", ""],
                    ["2", "Supply envelopes", "", "", "", ""],
                ]
            ],
        },
    )

    result = engine.analyse_docx_main_document(docx_path)

    assert result["status"] == "ok"
    assert result["has_pricing_schedule"] is True
    assert result["rfq_requirement_rows_count"] == 2
    assert result["verified_requirement_rows_count"] == 1
    assert result["requirement_rows_review_count"] == 1
    assert result["pricing_ready_from_requirements"] is False
    assert {row["source_type"] for row in result["rfq_requirement_rows"]} == {"embedded_pricing_schedule"}
    assert Path(result["report_path"]).is_relative_to(tmp_path)


def test_v42_pdf_pricing_mapping_preserves_page_and_raw_evidence(tmp_path, monkeypatch):
    from app.services import pricing_table_extraction_v42_service as engine

    pdf_path = tmp_path / "Main Document.pdf"
    pdf_path.write_text("synthetic")

    class FakeTable:
        def extract(self):
            return [["1", "Supply safety gloves", "10 each", "R 0.00", "R 0.00"]]

    class FakeFinder:
        tables = [FakeTable()]

    class FakePage:
        def find_tables(self):
            return FakeFinder()

        def get_text(self, mode):
            return "Pricing Schedule\n1 Supply safety gloves qty 10 each Unit Price R 0.00 Total Price R 0.00"

    class FakeDoc:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            return FakePage()

        def close(self):
            return None

    fake_fitz = types.SimpleNamespace(open=lambda path: FakeDoc())
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    result = engine.extract_pricing_tables_from_pdf(
        str(pdf_path),
        buyer_rfq_number="RFQ-V42-001",
        output_dir=str(tmp_path / "v42"),
    )

    assert result["status"] == "ok"
    assert result["rfq_requirement_rows_count"] >= 1
    assert result["verified_requirement_rows_count"] >= 1
    assert result["pricing_ready_from_requirements"] is True
    first = result["rfq_requirement_rows"][0]
    assert first["source_type"] == "embedded_pricing_schedule"
    assert first["source_document"] == str(pdf_path)
    assert first["source_page"] == 1


def test_tender_harvester_requirement_rows_satisfy_quantity_gate():
    from app.services import tender_harvester

    item = {
        "eligible": True,
        "quote_ready": True,
        "rfq_requirement_rows": [
            {
                "description": "Supply copy paper",
                "quantity": 20,
                "unit": "reams",
                "source_type": "embedded_pricing_schedule",
                "confidence": 0.9,
                "review_required": False,
            }
        ],
        "verified_requirement_rows_count": 1,
        "pricing_ready_from_requirements": True,
        "boq_line_item_count": 0,
        "boq_confidence": 0.0,
    }

    result = tender_harvester._lmcp_apply_quantity_safety_gate(item)

    assert result["requires_quantity_verification"] is False
    assert result["quantity_source"] == "rfq_requirement_rows"
    assert result["quantity_safety_status"] == "verified_requirement_pack_quantities"
    assert result["line_items"][0]["source"] == "embedded_pricing_schedule"
    assert tender_harvester._lmcp_is_quantity_unsafe_for_auto_quote(result) is False


def test_missing_requirement_quantities_remain_blocked():
    from app.services import tender_harvester

    item = {
        "eligible": True,
        "quote_ready": True,
        "rfq_requirement_rows": [
            {
                "description": "Supply copy paper",
                "quantity": None,
                "unit": "",
                "source_type": "embedded_pricing_schedule",
                "confidence": 0.9,
                "review_required": True,
            }
        ],
        "verified_requirement_rows_count": 0,
        "pricing_ready_from_requirements": False,
        "boq_line_item_count": 0,
        "boq_confidence": 0.0,
    }

    result = tender_harvester._lmcp_apply_quantity_safety_gate(item)

    assert result["requires_quantity_verification"] is True
    assert result["quantity_safety_status"] == "quantity_verification_required"
    assert result["pricing_ready_from_requirements"] is False


def test_no_production_runtime_store_writes(monkeypatch, tmp_path):
    protected = {
        Path("runtime/live_rfqs.json").resolve(),
        Path("runtime/rfq_lifecycle/rfqs.json").resolve(),
    }
    opened_for_write = []
    original_open = Path.open
    original_write_text = Path.write_text
    original_write_bytes = Path.write_bytes

    def assert_not_protected(path, mode=""):
        resolved = Path(path).resolve()
        if resolved in protected and any(flag in mode for flag in ("w", "a", "+")):
            opened_for_write.append(str(resolved))

    def guarded_open(self, mode="r", *args, **kwargs):
        assert_not_protected(self, mode)
        return original_open(self, mode, *args, **kwargs)

    def guarded_write_text(self, *args, **kwargs):
        assert_not_protected(self, "w")
        return original_write_text(self, *args, **kwargs)

    def guarded_write_bytes(self, *args, **kwargs):
        assert_not_protected(self, "w")
        return original_write_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "write_text", guarded_write_text)
    monkeypatch.setattr(Path, "write_bytes", guarded_write_bytes)

    from app.services.rfq_requirement_pack_service import build_requirement_pack, normalize_requirement_rows

    rows = normalize_requirement_rows(
        [{"description": "Supply pens", "quantity": 10, "unit": "each"}],
        source_type="embedded_pricing_schedule",
    )
    pack = build_requirement_pack(rows)

    assert pack["pricing_ready_from_requirements"] is True
    assert opened_for_write == []
