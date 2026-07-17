from datetime import datetime, timezone
from pathlib import Path
import json

from app.services.supplier_outreach_service import (
    DEFAULT_MANDATORY_CC,
    DEFAULT_SUPPLIER_MAILBOX,
    RESPONSE_COVERAGE_NONE_FALLBACK,
    build_canonical_supplier_outreach_request,
    evaluate_followup_draft_preparation,
    prepare_supplier_outreach_gmail_drafts,
    build_followup_model,
    build_no_response_pricing_state,
    build_supplier_email_model,
    build_supplier_outreach_status,
    enforce_mandatory_cc,
    select_supplier_targets,
    supplier_outreach_config,
    write_supplier_outreach_dry_run,
)


FIXTURE_PACK = Path("/tmp/lmcp-reprocess-6000080579/outputs/rfq_requirement_pack.json")
FIXTURE_PRICING = Path("/tmp/lmcp-pricing-workspace-6000080579/outputs/pricing_workspace_result.json")


def _pack():
    return json.loads(FIXTURE_PACK.read_text(encoding="utf-8"))


def _pricing():
    return json.loads(FIXTURE_PRICING.read_text(encoding="utf-8"))


def test_supplier_outreach_configuration_defaults_and_cc_enforcement():
    config = supplier_outreach_config({})
    assert config["supplier_rfq_email"] == DEFAULT_SUPPLIER_MAILBOX
    assert config["supplier_rfq_cc"] == DEFAULT_MANDATORY_CC
    assert config["minimum_supplier_target"] == 3
    assert config["followup_days"] == 2
    assert config["supplier_outreach_automation_enabled"] is False
    assert config["buyer_autonomous_submission_enabled"] is False
    assert enforce_mandatory_cc([], config) == [DEFAULT_MANDATORY_CC]
    assert enforce_mandatory_cc(["other@example.com"], config) == ["other@example.com", DEFAULT_MANDATORY_CC]


def test_selects_minimum_three_supplier_targets_for_dry_run():
    suppliers = select_supplier_targets(minimum_supplier_target=3)
    assert len(suppliers) == 3
    assert all("@" in supplier["supplier_email"] for supplier in suppliers)


def test_supplier_selection_dedupes_excludes_missing_and_reports_fewer_than_three():
    suppliers = select_supplier_targets(
        [
            {"supplier_name": "A", "supplier_email": "a@example.com"},
            {"supplier_name": "A copy", "supplier_email": "A@example.com"},
            {"supplier_name": "No Email"},
            {"supplier_name": "B", "supplier_email": "b@example.com"},
        ],
        minimum_supplier_target=3,
    )
    assert [supplier["supplier_email"].lower() for supplier in suppliers] == ["a@example.com", "b@example.com"]


def test_initial_supplier_email_contains_required_rfq_and_technical_content():
    pack = _pack()
    created_at = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    email = build_supplier_email_model(
        supplier={"supplier_name": "Test Supplier", "supplier_email": "supplier@example.com"},
        requirement_pack=pack,
        request_id="LMCP-SRFQ-6000080579-TEST",
        created_at=created_at,
        response_deadline="2026-07-19T08:00:00+00:00",
        delivery_destination="Zandfontein & Ennerdale",
        requested_delivery_period="Supplier to confirm",
    )
    body = email["body"]
    assert email["from"] == DEFAULT_SUPPLIER_MAILBOX
    assert DEFAULT_MANDATORY_CC in email["cc"]
    assert "Supplier RFQ | Buyer RFQ 6000080579" in email["subject"]
    assert "LMCP-SRFQ-6000080579-TEST" in email["subject"]
    assert "Group | Material/Item Ref | Description | Qty | Unit" in body
    assert "327" in body and "80" in body
    assert "302" in body and "224" in body
    assert "328" in body and "280" in body
    assert "Offered brand required: True" in body
    assert "Manufacturer datasheet required: True" in body
    assert "Sample may be requested: True" in body
    assert "SANS 1028" in body
    assert "ISO 6787" in body
    assert "SANS 1211" in body
    assert "SANS 387" in body
    assert email["live_email_sent"] is False
    assert email["sent"] is False
    assert email["contacted"] is False
    assert email["request_sent_at"] is None


def test_canonical_supplier_request_validation_and_review_blocks():
    pack = _pack()
    supplier = {"supplier_name": "Test Supplier", "supplier_email": "supplier@example.com"}
    request = build_canonical_supplier_outreach_request(
        supplier=supplier,
        requirement_pack=pack,
        request_id="REQ-1",
        created_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        response_deadline="2026-07-19T08:00:00+00:00",
        delivery_location="Johannesburg",
        delivery_requirements="Supplier to confirm",
    )
    assert request["approval_state"] == "APPROVED_FOR_DRAFT"
    assert len(request["items"]) == 6
    assert "manufacturer datasheet" in request["required_documents"]
    assert "compliance certificate" in request["required_documents"]
    assert request["mandatory_cc"] == DEFAULT_MANDATORY_CC

    missing_quantity_pack = json.loads(json.dumps(pack))
    missing_quantity_pack["supplier_sourcing_groups"][0]["total_quantity"] = None
    blocked = build_canonical_supplier_outreach_request(
        supplier=supplier,
        requirement_pack=missing_quantity_pack,
        request_id="REQ-2",
        created_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
    )
    assert blocked["approval_state"] == "REVIEW_REQUIRED"
    assert any(reason.startswith("missing_quantity") for reason in blocked["validation"]["review_reasons"])

    missing_unit_pack = json.loads(json.dumps(pack))
    missing_unit_pack["supplier_sourcing_groups"][0]["unit"] = ""
    blocked_unit = build_canonical_supplier_outreach_request(
        supplier=supplier,
        requirement_pack=missing_unit_pack,
        request_id="REQ-3",
        created_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
    )
    assert any(reason.startswith("missing_unit") for reason in blocked_unit["validation"]["review_reasons"])


def test_followup_keeps_request_id_and_mandatory_cc():
    pack = _pack()
    created_at = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    email = build_supplier_email_model(
        supplier={"supplier_name": "Test Supplier", "supplier_email": "supplier@example.com"},
        requirement_pack=pack,
        request_id="LMCP-SRFQ-6000080579-TEST",
        created_at=created_at,
        response_deadline="2026-07-19T08:00:00+00:00",
    )
    followup = build_followup_model(email)
    assert followup["request_id"] == email["request_id"]
    assert DEFAULT_MANDATORY_CC in followup["cc"]
    assert followup["live_email_sent"] is False
    assert followup["followup_preconditions"]["same_stage_followup_not_already_sent"] is True


def test_followup_clock_starts_only_from_recorded_send_event():
    email = {"request_sent_at": None}
    now = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)
    blocked = evaluate_followup_draft_preparation(initial_request=email, now=now)
    assert blocked["eligible"] is False
    assert blocked["reason"] == "initial_request_not_sent"

    sent = {"request_sent_at": "2026-07-17T08:00:00+00:00"}
    eligible = evaluate_followup_draft_preparation(initial_request=sent, now=now)
    assert eligible["eligible"] is True
    response = evaluate_followup_draft_preparation(initial_request=sent, now=now, supplier_response_recorded=True)
    assert response["eligible"] is False
    assert response["reason"] == "supplier_response_recorded"


def test_no_response_pricing_state_does_not_block_pricing():
    status = build_supplier_outreach_status(
        supplier_count=3,
        minimum_supplier_target=3,
        initial_email_count=3,
        followup_count=3,
        sourcing_deadline="2026-07-19T08:00:00+00:00",
        pricing_cutoff="2026-07-20T08:00:00+00:00",
    )
    state = build_no_response_pricing_state(status)
    assert state["pricing_ready"] is True
    assert state["supplier_pricing_confirmed"] is False
    assert state["supplier_quote_coverage"] == RESPONSE_COVERAGE_NONE_FALLBACK
    assert state["manual_pricing_review_required"] is True


def test_6000080579_dry_run_outputs(tmp_path):
    result = write_supplier_outreach_dry_run(
        requirement_pack=_pack(),
        pricing_workspace_result=_pricing(),
        output_dir=tmp_path,
        created_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
    )
    assert result["status"] == "PASS"
    assert len(result["suppliers"]) == 3
    assert len(result["email_models"]) == 3
    assert len(result["followup_schedules"]) == 3
    assert len(result["audit_records"]) == 3
    assert result["supplier_outreach_status"]["suppliers_contacted"] == 0
    assert result["supplier_outreach_status"]["followups_due"] == 0
    assert result["no_response_pricing_state"]["pricing_ready"] is True
    assert result["no_response_pricing_state"]["supplier_pricing_confirmed"] is False
    assert result["config"]["buyer_autonomous_submission_enabled"] is False
    assert (tmp_path / "supplier_outreach_validation_report.json").exists()


def test_supplier_gmail_draft_preparation_uses_draft_transport_and_preserves_state(tmp_path):
    dry_run = write_supplier_outreach_dry_run(
        requirement_pack=_pack(),
        pricing_workspace_result=_pricing(),
        output_dir=tmp_path / "dry",
        created_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
    )
    first = prepare_supplier_outreach_gmail_drafts(
        email_models=dry_run["email_models"],
        output_dir=tmp_path / "drafts",
        requirement_pack_version=_pack().get("requirement_pack_version", ""),
    )
    second = prepare_supplier_outreach_gmail_drafts(
        email_models=dry_run["email_models"],
        output_dir=tmp_path / "drafts",
        requirement_pack_version=_pack().get("requirement_pack_version", ""),
    )
    assert first["emails_sent"] == 0
    assert first["supplier_contacted"] is False
    assert first["followup_scheduled"] is False
    assert all(item["draft_status"] == "DRAFT" for item in first["draft_results"])
    assert all(item["request_sent_at"] is None for item in first["draft_results"])
    assert second["emails_sent"] == 0
    assert all(item["status"] in {"created_new_draft", "reused_existing_draft"} for item in second["draft_results"])
