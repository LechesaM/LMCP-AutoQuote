from app.services.rfq_requirement_pack_service import build_supplier_sourcing_groups, normalize_requirement_rows


def test_supplier_groups_consolidate_exact_material_numbers():
    rows = normalize_requirement_rows(
        [
            {"material_number": "327", "description": "350 mm pipe wrench", "quantity": 40, "unit": "each"},
            {"material_number": "327", "description": "350 mm pipe wrench", "quantity": 40, "unit": "each"},
        ],
        source_type="embedded_pricing_schedule",
    )
    groups = build_supplier_sourcing_groups(rows)

    assert len(groups) == 1
    assert groups[0]["material_number"] == "327"
    assert groups[0]["total_quantity"] == 80.0
    assert len(groups[0]["buyer_requirement_row_ids"]) == 2


def test_different_specifications_are_not_merged():
    rows = normalize_requirement_rows(
        [
            {"material_number": "X1", "description": "Valve", "specification": "Brass", "quantity": 1, "unit": "each"},
            {"material_number": "X1", "description": "Valve", "specification": "Steel", "quantity": 1, "unit": "each"},
        ],
        source_type="embedded_pricing_schedule",
    )
    groups = build_supplier_sourcing_groups(rows)

    assert len(groups) == 2


def test_exact_part_number_matching_and_safe_description_matching():
    rows = normalize_requirement_rows(
        [
            {"part_number": "ABC-1", "description": "Filter", "quantity": 2, "unit": "each"},
            {"part_no": "ABC-1", "description": "Filter cartridge", "quantity": 3, "unit": "each"},
            {"description": "Blue pen", "quantity": 10, "unit": "each"},
            {"description": "Blue pen", "quantity": 5, "unit": "each"},
        ],
        source_type="embedded_pricing_schedule",
    )
    groups = build_supplier_sourcing_groups(rows)

    by_part = [group for group in groups if group["part_number"] == "ABC-1"][0]
    by_desc = [group for group in groups if group["description"] == "Blue pen"][0]
    assert by_part["total_quantity"] == 5.0
    assert by_desc["total_quantity"] == 15.0
