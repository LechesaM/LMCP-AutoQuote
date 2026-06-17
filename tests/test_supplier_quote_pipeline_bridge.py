from app.services.supplier_quote_pipeline_bridge import attach_supplier_quotes_to_result


def test_attach_supplier_quotes_rebuilds_comparison_from_source_entries_and_pricing(tmp_path) -> None:
    source_root = tmp_path / "bridge_source_quotes"
    source_root.mkdir(parents=True, exist_ok=True)

    acme_path = source_root / "Acme_Office_Supplies_quote.txt"
    bright_path = source_root / "Bright_Stationers_quote.txt"
    acme_path.write_text("Acme Office Supplies quote for REAL-PILOT-001.\n", encoding="utf-8")
    bright_path.write_text("Bright Stationers quote for REAL-PILOT-001.\n", encoding="utf-8")

    result = attach_supplier_quotes_to_result(
        {
            "tender_id": "REAL-PILOT-001",
            "rfq_number": "REAL-PILOT-001",
            "source_quote_entries": [
                {"copied_to": str(acme_path)},
                {"copied_to": str(bright_path)},
            ],
            "items": [
                {
                    "item_number": 1,
                    "description": "Tender supply and delivery line item",
                    "quantity": 1,
                    "unit_price": 48500.0,
                    "supplier_name": "Acme Office Supplies",
                    "supplier_quote_ref": "Acme-Office-Supplies-REAL-PILOT-001",
                }
            ],
            "supplier_quote_comparison": {
                "comparison_status": "ready",
                "comparison_ready": True,
                "supplier_quotes": [],
                "recommended_supplier": {
                    "supplier_name": "PILOT-001",
                    "quote_reference": "REAL-PILOT-001",
                    "quoted_total": 0.0,
                    "traceability_chain": [],
                },
                "runner_up_supplier": {},
                "estimated_savings_vs_runner_up": 0.0,
            },
        }
    )

    comparison = result["supplier_quote_comparison"]
    assert comparison["comparison_status"] == "partial_evidence"
    assert len(comparison["supplier_quotes"]) == 2
    assert comparison["recommended_supplier"]["supplier_name"] == "Acme Office Supplies"
    assert comparison["recommended_supplier"]["quoted_total"] == 48500.0
    assert comparison["recommended_supplier"]["traceability_chain"]
    assert comparison["runner_up_supplier"]["supplier_name"] == "Bright Stationers"
    assert comparison["runner_up_supplier"]["traceability_chain"]
    assert comparison["estimated_savings_vs_runner_up"] is None


def test_attach_supplier_quotes_rebuilds_from_pricing_rows_when_no_files_exist() -> None:
    result = attach_supplier_quotes_to_result(
        {
            "tender_id": "RFQ_004",
            "rfq_number": "RFQ_004",
            "rows": [
                {
                    "item_number": 1,
                    "description": "Damsakke complete with pump",
                    "quantity": 5,
                    "unit_price": 28000.0,
                    "line_total": 140000.0,
                    "supplier_name": "Industrial Pump Supplies",
                    "supplier_quote_ref": "Industrial-Pump-Supplies-RFQ-004",
                }
            ],
        }
    )

    comparison = result["supplier_quote_comparison"]
    assert comparison["comparison_status"] == "ready"
    assert len(comparison["supplier_quotes"]) == 1
    assert comparison["recommended_supplier"]["supplier_name"] == "Industrial Pump Supplies"
    assert comparison["recommended_supplier"]["quoted_total"] == 140000.0
    assert comparison["recommended_supplier"]["traceability_chain"]
    assert comparison["runner_up_supplier"] == {}
    assert result["supplier_quotes_found"] is True


def test_attach_supplier_quotes_reports_missing_evidence_without_placeholder_record() -> None:
    result = attach_supplier_quotes_to_result(
        {
            "tender_id": "RFQ_EMPTY",
            "rfq_number": "RFQ_EMPTY",
        }
    )

    comparison = result["supplier_quote_comparison"]
    assert comparison["comparison_status"] == "missing_supplier_quotes"
    assert comparison["comparison_ready"] is False
    assert comparison["supplier_quotes"] == []
    assert comparison["recommended_supplier"] == {}
    assert comparison["runner_up_supplier"] == {}
    assert result["supplier_quotes_found"] is False
