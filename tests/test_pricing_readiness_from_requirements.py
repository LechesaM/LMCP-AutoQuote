from app.services.rfq_requirement_pack_service import build_pricing_workspace_contract, build_requirement_pack


def test_embedded_schedule_can_create_pricing_readiness_with_blank_price_columns():
    pack = build_requirement_pack(
        [
            {
                "description": "Supply copy paper",
                "quantity": 20,
                "unit": "reams",
                "unit_price": "",
                "total_price": "",
                "source_type": "embedded_pricing_schedule",
            }
        ]
    )

    assert pack["pricing_ready_from_requirements"] is True
    assert pack["operator_review_required"] is False


def test_missing_quantities_create_review_and_not_pricing_ready():
    pack = build_requirement_pack(
        [{"description": "Supply copy paper", "quantity": "", "unit": "", "source_type": "embedded_pricing_schedule"}]
    )

    assert pack["buyer_row_count"] == 1
    assert pack["pricing_ready_from_requirements"] is False
    assert pack["operator_review_required"] is True


def test_lump_sum_and_transport_rows_are_valid_when_explicit():
    pack = build_requirement_pack(
        [
            {"description": "Transport", "quantity": 1, "unit": "lot", "source_type": "formal_buyer_pricing_schedule"},
            {"description": "Lump sum installation", "quantity": "", "unit": "lump sum", "source_type": "formal_buyer_pricing_schedule"},
        ]
    )

    assert pack["buyer_row_count"] == 2
    assert pack["pricing_ready_from_requirements"] is True
    assert pack["buyer_rows"][0]["commercial_flags"]["transport"] is True
    assert pack["buyer_rows"][1]["commercial_flags"]["lump_sum"] is True


def test_pricing_workspace_contract_preserves_buyer_rows_and_supplier_groups():
    pack = build_requirement_pack(
        [
            {"material_number": "327", "description": "Pipe wrench", "quantity": 40, "unit": "each", "source_type": "embedded_pricing_schedule"},
            {"material_number": "327", "description": "Pipe wrench", "quantity": 40, "unit": "each", "source_type": "embedded_pricing_schedule"},
        ]
    )
    contract = build_pricing_workspace_contract(pack)

    assert len(contract["buyer_pricing_rows"]) == 2
    assert len(contract["supplier_sourcing_groups"]) == 1
    assert contract["pricing_ready"] is True
