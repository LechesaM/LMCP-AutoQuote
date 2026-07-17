from app.services.rfq_requirement_pack_service import build_requirement_pack, detect_requirement_conflicts, normalize_requirement_rows


def test_quantity_conflict_detected_across_specification_and_formal_schedule():
    rows = normalize_requirement_rows(
        [
            {
                "material_number": "47835564",
                "description": "Transmission Filter 47835564",
                "quantity": 1,
                "unit": "each",
                "source_type": "specification_table",
                "source_table": "spec",
                "source_row": 1,
                "source_document": "spec.pdf",
            },
            {
                "material_number": "47835564",
                "description": "Transmission Filter 47835564",
                "quantity": 5,
                "unit": "each",
                "source_type": "formal_buyer_pricing_schedule",
                "source_table": "mbd31",
                "source_row": 1,
                "source_document": "pricing.pdf",
            },
        ],
        reference_number="RFQ-CONFLICT",
    )
    conflicts = detect_requirement_conflicts(rows)

    assert len(conflicts) == 1
    assert conflicts[0]["conflict_type"] == "quantity_mismatch"
    assert conflicts[0]["recommended_value"] == 5.0
    assert conflicts[0]["recommended_source"] == "formal_buyer_pricing_schedule"
    assert conflicts[0]["operator_review_required"] is True


def test_repeated_lines_in_same_pricing_schedule_are_not_conflicts():
    rows = normalize_requirement_rows(
        [
            {"material_number": "327", "description": "Pipe wrench", "quantity": 40, "unit": "each", "source_type": "embedded_pricing_schedule", "source_table": "pricing", "source_row": 1},
            {"material_number": "327", "description": "Pipe wrench", "quantity": 40, "unit": "each", "source_type": "embedded_pricing_schedule", "source_table": "pricing", "source_row": 2},
        ]
    )

    assert detect_requirement_conflicts(rows) == []


def test_unresolved_conflicts_block_pricing_readiness():
    pack = build_requirement_pack(
        [
            {"material_number": "51508555", "description": "Hydraulic Filter", "quantity": 1, "unit": "each", "source_type": "specification_table", "source_table": "spec"},
            {"material_number": "51508555", "description": "Hydraulic Filter", "quantity": 5, "unit": "each", "source_type": "formal_buyer_pricing_schedule", "source_table": "pricing"},
        ]
    )

    assert pack["requirement_conflict_count"] == 1
    assert pack["operator_review_required"] is True
    assert pack["pricing_ready_from_requirements"] is False
    assert pack["pricing_basis"]["selected_source_type"] == "formal_buyer_pricing_schedule"
