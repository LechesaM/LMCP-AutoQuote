import json
from pathlib import Path

from app.services.rfq_requirement_pack_service import build_pricing_workspace_contract, build_requirement_pack


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rfq_requirement_intelligence"


def _pack(name):
    payload = json.loads((FIXTURE_DIR / name).read_text())
    return build_requirement_pack(
        payload["rows"],
        rfq_id=payload["rfq_id"],
        buyer_name=payload["buyer_name"],
        reference_number=payload["reference_number"],
        title=payload["title"],
    )


def _group_by_material(pack, material):
    return [group for group in pack["supplier_sourcing_groups"] if group["material_number"] == material][0]


def test_jw_6000080569_embedded_schedule_is_pricing_ready_and_supplier_quantity_800():
    pack = _pack("jw_6000080569_embedded_schedule.json")

    assert pack["buyer_row_count"] == 4
    assert pack["embedded_pricing_schedule_detected"] is True
    assert pack["standalone_boq_detected"] is False
    assert pack["supplier_group_count"] == 1
    assert pack["supplier_sourcing_groups"][0]["total_quantity"] == 800.0
    assert pack["supplier_sourcing_groups"][0]["brand_required"] is True
    assert pack["supplier_sourcing_groups"][0]["datasheet_required"] is True
    assert pack["pricing_ready_from_requirements"] is True
    assert pack["operator_review_required"] is False


def test_jw_rfq004_hytran_conflicts_preserve_both_tables_and_recommend_formal_schedule():
    pack = _pack("jw_rfq004_hytran_conflict.json")
    conflicts = pack["requirement_conflicts"]

    assert pack["buyer_row_count"] == 7
    assert pack["specification_table_detected"] is True
    assert pack["embedded_pricing_schedule_detected"] is True
    assert pack["requirement_conflict_count"] == 2
    assert {conflict["material_number"] for conflict in conflicts} == {"47835564", "51508555"}
    assert all(conflict["recommended_source"] == "formal_buyer_pricing_schedule" for conflict in conflicts)
    assert sorted(conflict["recommended_value"] for conflict in conflicts) == [5.0, 5.0]
    assert pack["operator_review_required"] is True
    assert pack["pricing_ready_from_requirements"] is False
    assert any(row["commercial_flags"]["transport"] for row in pack["buyer_rows"])


def test_jw_6000080579_repeated_hand_tools_preserve_nine_rows_and_six_supplier_groups():
    pack = _pack("jw_6000080579_repeated_hand_tools.json")

    assert pack["buyer_row_count"] == 9
    assert pack["supplier_group_count"] == 6
    assert _group_by_material(pack, "327")["total_quantity"] == 80.0
    assert _group_by_material(pack, "302")["total_quantity"] == 224.0
    assert _group_by_material(pack, "328")["total_quantity"] == 280.0
    assert {group["material_number"] for group in pack["supplier_sourcing_groups"]} >= {"315", "1304", "316"}
    assert any(req["name"] == "Brand name required" for req in pack["technical_requirements"])
    assert any(req["name"] == "Manufacturer datasheet required" for req in pack["technical_requirements"])
    assert any(row["sample_may_be_required"] for row in pack["buyer_rows"])
    assert any("SANS 1022" in row["standards"] for row in pack["buyer_rows"])
    assert any("ISO 9001" in row["standards"] for row in pack["buyer_rows"])
    assert pack["pricing_ready_from_requirements"] is True


def test_pricing_workspace_contract_for_conflict_fixture_has_blocking_reviews():
    pack = _pack("jw_rfq004_hytran_conflict.json")
    contract = build_pricing_workspace_contract(pack)

    assert contract["pricing_ready"] is False
    assert contract["operator_review_required"] is True
    assert len(contract["blocking_reviews"]) == 2
