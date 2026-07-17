#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.gmail_draft_transport_service import (
    DraftReference,
    EmailTransportOperationBlocked,
    GmailApiDraftClient,
    GmailAttachmentRequest,
    GmailDraftRequest,
    GmailDraftTransportService,
    dataclass_to_dict,
)
from app.services.gmail_draft_idempotency_ledger import (
    canonical_key_for_request,
    diagnose_message,
    expected_payload_for_request,
    load_ledger_with_status,
    locked_ledger,
    resolve_or_create_draft,
    save_ledger_atomic,
)
from app.services.gmail_oauth_provider import GMAIL_DRAFT_SCOPES, GmailOAuthProvider
from app.services.supplier_outreach_service import (
    DEFAULT_MANDATORY_CC,
    DEFAULT_SUPPLIER_MAILBOX,
    EMAIL_TYPE_CLARIFICATION,
    EMAIL_TYPE_FOLLOWUP_1,
    EMAIL_TYPE_INITIAL,
    RESPONSE_COVERAGE_NONE_FALLBACK,
    build_no_response_pricing_state,
)


REQUEST_ID = "LMCP-SRFQ-6000080579-341E812698"
RFQ_REFERENCE = "6000080579"
OUTPUT_ROOT = Path("/tmp/lmcp-gmail-real-draft-validation-6000080579")
LEDGER_PATH = OUTPUT_ROOT / "state" / "draft_idempotency_ledger.json"
WARNING = "THIS IS A CONTROLLED LMCP AUTOQUOTE GMAIL DRAFT-ONLY VALIDATION. DO NOT SEND."
SUBJECT_PREFIX = "LMCP CONTROLLED DRAFT TEST — DO NOT SEND"

GROUPS = [
    ("327", "Straight Pipe Wrench 350 mm Heavy Duty", 80, "EA", "SANS 1028"),
    ("315", "Shifting/Open-End Adjustable Spanner 250 mm Heavy Duty", 50, "EA", "ISO 6787; SANS 1211"),
    ("302", "Club Hammer 1.8 kg Steel-Reinforced Polymer Handle", 224, "EA", "SANS 387"),
    ("328", "Straight Pipe Wrench 450 mm Heavy Duty", 280, "EA", "SANS 1028"),
    ("1304", "Cold Flat Chisel 200 mm x 20 mm", 40, "EA", ""),
    ("316", "Shifting/Open-End Adjustable Spanner 300 mm Heavy Duty", 40, "EA", "ISO 6787; SANS 1211"),
]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _safe_output_root(root: Path) -> Path:
    resolved = root.resolve()
    if Path("/tmp").resolve() not in [resolved] + list(resolved.parents):
        raise SystemExit(f"Refusing non-/tmp output path: {resolved}")
    return resolved


def _preflight() -> Dict[str, Any]:
    required = {
        "LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY",
        "LMCP_GMAIL_USER_ID": "me",
        "LMCP_SUPPLIER_RFQ_EMAIL": DEFAULT_SUPPLIER_MAILBOX,
        "LMCP_SUPPLIER_RFQ_CC": DEFAULT_MANDATORY_CC,
    }
    env_status = {key: ("configured" if os.environ.get(key) else "missing") for key in required}
    value_checks = {key: os.environ.get(key) == expected for key, expected in required.items()}
    credential_checks = {
        "client_secret_configured": bool(os.environ.get("LMCP_GMAIL_CLIENT_SECRET_FILE")),
        "token_configured": bool(os.environ.get("LMCP_GMAIL_TOKEN_FILE")),
    }
    return {
        "env_status": env_status,
        "value_checks": value_checks,
        "credential_checks": credential_checks,
        "passed": all(value_checks.values()) and all(credential_checks.values()),
    }


def _attachments(root: Path) -> List[GmailAttachmentRequest]:
    attachment_root = root / "attachments"
    attachment_root.mkdir(parents=True, exist_ok=True)
    payloads = [
        ("supplier_pricing_request_schedule.json", "application/json", {"rfq": RFQ_REFERENCE, "groups": GROUPS}, "pricing_request_schedule"),
        ("technical_requirements_summary.json", "application/json", {"standards": ["SANS 1028", "ISO 6787", "SANS 1211", "SANS 387"], "brand_required": True, "datasheet_required": True}, "technical_requirements"),
        ("supplier_response_template.json", "application/json", {"fields": ["offered_brand", "manufacturer", "model_or_part_number", "unit_rate_ex_vat", "delivery_period"]}, "supplier_response_template"),
    ]
    out: List[GmailAttachmentRequest] = []
    for filename, mime_type, payload, doc_type in payloads:
        data = json.dumps(payload, indent=2).encode("utf-8")
        (attachment_root / filename).write_bytes(data)
        out.append(GmailAttachmentRequest(filename=filename, mime_type=mime_type, content=data, logical_document_type=doc_type).normalised())
    return out


def _schedule_text() -> str:
    lines = ["Sourcing groups:", "Material | Description | Quantity | Unit | Standards"]
    for material, description, quantity, unit, standards in GROUPS:
        lines.append(f"{material} | {description} | {quantity} | {unit} | {standards}")
    return "\n".join(lines)


def _body(kind: str) -> str:
    common = [
        WARNING,
        "",
        f"RFQ reference: {RFQ_REFERENCE}",
        f"LMCP supplier request ID: {REQUEST_ID}",
        "",
        _schedule_text(),
        "",
        "Required supplier response fields:",
        "- offered brand",
        "- manufacturer",
        "- model or part number",
        "- unit rate excluding VAT",
        "- total excluding VAT",
        "- VAT",
        "- total including VAT",
        "- delivery costs",
        "- delivery period",
        "- stock availability",
        "- quotation validity",
        "- warranty",
        "",
        "Required documents:",
        "- formal supplier quotation",
        "- manufacturer datasheet",
        "- product brochure",
        "- compliance certificates",
        "- sample availability",
        "- delivery schedule",
        "",
        "Applicable standards and conditions:",
        "- SANS 1028",
        "- ISO 6787",
        "- SANS 1211",
        "- SANS 387",
        "- offered brand required",
        "- manufacturer datasheet required",
        "- sample may be requested",
    ]
    if kind == "followup":
        common.insert(2, "This is a validation follow-up draft. No supplier request was previously sent.")
        common.insert(3, "Theoretical first follow-up due date: initial request creation + 2 calendar days.")
        common.append("Outstanding: brands, datasheets, prices and delivery information.")
    if kind == "clarification":
        return "\n".join([
            WARNING,
            "",
            f"RFQ reference: {RFQ_REFERENCE}",
            f"LMCP supplier request ID: {REQUEST_ID}",
            "",
            "Controlled clarification draft. Please provide only:",
            "- offered brand",
            "- manufacturer datasheet",
            "- delivery period",
            "- formal supplier quotation",
        ])
    return "\n".join(common)


def _request(kind: str, attachments: List[GmailAttachmentRequest]) -> GmailDraftRequest:
    labels = {
        "initial": "Initial Supplier RFQ",
        "followup": "Follow-Up",
        "clarification": "Clarification",
    }
    types = {
        "initial": EMAIL_TYPE_INITIAL,
        "followup": EMAIL_TYPE_FOLLOWUP_1,
        "clarification": EMAIL_TYPE_CLARIFICATION,
    }
    request = GmailDraftRequest(
        to=[DEFAULT_SUPPLIER_MAILBOX],
        cc=[DEFAULT_MANDATORY_CC],
        subject=f"{SUBJECT_PREFIX} | {labels[kind]} | {RFQ_REFERENCE} | {REQUEST_ID}",
        body_text=_body(kind),
        attachments=attachments,
        supplier_request_id=REQUEST_ID,
        rfq_id=f"TEMP-RFQ-{RFQ_REFERENCE}",
        email_type=types[kind],
        idempotency_key="",
    )
    request.idempotency_key = canonical_key_for_request(DEFAULT_SUPPLIER_MAILBOX, request, _ledger_kind(kind))
    return request


def _ledger_kind(kind: str) -> str:
    return "follow-up" if kind == "followup" else kind


def run(output_root: Path) -> Dict[str, Any]:
    output_root = _safe_output_root(output_root)
    for child in ["attachments", "audit", "reports", "state"]:
        (output_root / child).mkdir(parents=True, exist_ok=True)

    preflight = _preflight()
    if not preflight["passed"]:
        report = {
            "result": "BLOCKED",
            "blocked_before_gmail_connection": True,
            "preflight": preflight,
            "gmail_connected": False,
            "drafts_created": 0,
            "emails_sent": 0,
        }
        _write_json(output_root / "reports" / "gmail_real_draft_validation_blocked_report.json", report)
        _write_json(output_root / "reports" / "created_files.json", sorted(str(p) for p in output_root.rglob("*") if p.is_file()))
        return report

    provider = GmailOAuthProvider()
    gmail_resource = provider.get_authenticated_client()
    profile = gmail_resource.users().getProfile(userId=os.environ.get("LMCP_GMAIL_USER_ID", "me")).execute()
    authenticated_email = str(profile.get("emailAddress") or "").lower()
    if authenticated_email != DEFAULT_SUPPLIER_MAILBOX:
        raise SystemExit("Authenticated Gmail mailbox does not match required supplier mailbox.")

    service = GmailDraftTransportService(
        gmail_client=GmailApiDraftClient(gmail_resource),
        env=os.environ,
        controlled_test_mode=True,
    )
    attachments = _attachments(output_root)
    request_pairs: List[Tuple[str, GmailDraftRequest]] = [
        ("initial", _request("initial", attachments)),
        ("follow-up", _request("followup", attachments)),
        ("clarification", _request("clarification", attachments)),
    ]

    blocked: Dict[str, Any] = {}
    dummy_ref = DraftReference(
        redacted_draft_reference="redacted-dummy",
        redacted_message_reference="redacted-dummy",
        thread_reference="redacted-dummy",
        created_timestamp="",
        transport_mode="DRAFT_ONLY",
        status="DRAFT",
    )
    first_request = request_pairs[0][1]
    for operation, call in [
        ("send_email", lambda: service.send_email(first_request)),
        ("send_draft", lambda: service.send_draft(dummy_ref)),
        ("smtp_fallback_send", lambda: service.smtp_fallback_send(first_request)),
        ("scheduler_dispatch", lambda: service.scheduler_dispatch(first_request)),
    ]:
        try:
            call()
            blocked[operation] = {"blocked": False}
        except EmailTransportOperationBlocked as exc:
            blocked[operation] = {"blocked": True, **exc.to_dict()}

    ledger_path = output_root / "state" / "draft_idempotency_ledger.json"
    ledger_corrupt = False
    ledger_error = ""
    resolutions = []
    with locked_ledger(ledger_path):
        ledger, ledger_corrupt, ledger_error = load_ledger_with_status(ledger_path)
        for draft_type, req in request_pairs:
            req.idempotency_key = canonical_key_for_request(DEFAULT_SUPPLIER_MAILBOX, req, draft_type)
            resolutions.append(
                resolve_or_create_draft(
                    service=service,
                    ledger=ledger,
                    draft_type=draft_type,
                    request=req,
                    expected_subject=req.subject,
                    allow_create=not ledger_corrupt,
                )
            )
        save_ledger_atomic(ledger_path, ledger)

    drafts = [resolution.message for resolution in resolutions]
    controlled_messages = _controlled_messages(service)
    duplicate_inventory = _duplicate_inventory(controlled_messages)
    validation = _validate(drafts, controlled_messages, resolutions, blocked)
    new_drafts_created = sum(1 for resolution in resolutions if resolution.new_draft_created)
    canonical_reused = sum(1 for resolution in resolutions if resolution.canonical_reused)
    duplicates_detected = sum(resolution.duplicates_detected for resolution in resolutions)
    duplicate_suppressed = sum(1 for resolution in resolutions if resolution.duplicate_suppressed)
    result = "PASS" if all(validation.values()) else "FAIL"
    if result == "PASS" and duplicates_detected:
        result = "PASS_WITH_EXISTING_DUPLICATES"
    report = {
        "result": result,
        "authenticated_mailbox": "configured_expected",
        "scope": GMAIL_DRAFT_SCOPES[0],
        "transport_mode": os.environ.get("LMCP_EMAIL_TRANSPORT_MODE"),
        "drafts_created": new_drafts_created,
        "new_drafts_created": new_drafts_created,
        "canonical_drafts_reused": canonical_reused,
        "duplicate_suppressed": duplicate_suppressed,
        "duplicates_detected": duplicates_detected,
        "controlled_drafts_listed": len(controlled_messages),
        "drafts": [dataclass_to_dict(d.summary) for d in drafts],
        "resolutions": [resolution.to_dict() for resolution in resolutions],
        "duplicate_inventory": duplicate_inventory,
        "ledger_path": str(ledger_path),
        "ledger_permissions": oct(ledger_path.stat().st_mode & 0o777) if ledger_path.exists() else "",
        "ledger_corrupt_before_run": ledger_corrupt,
        "ledger_error": ledger_error,
        "send_blocks": blocked,
        "validation_checks": validation,
        "pricing_independence": _pricing_independence(),
        "emails_sent": 0,
    }
    _write_json(output_root / "audit" / "gmail_real_draft_audit_redacted.json", {
        "draft_references": [dataclass_to_dict(resolution.reference) for resolution in resolutions],
        "send_blocks": blocked,
    })
    _write_json(output_root / "reports" / "gmail_real_draft_validation_report.json", report)
    _write_json(output_root / "reports" / "controlled_draft_duplicate_inventory.json", duplicate_inventory)
    _write_json(output_root / "reports" / "created_files.json", sorted(str(p) for p in output_root.rglob("*") if p.is_file()))
    return report


def run_clarification_diagnostic(output_root: Path) -> Dict[str, Any]:
    output_root = _safe_output_root(output_root)
    for child in ["attachments", "reports"]:
        (output_root / child).mkdir(parents=True, exist_ok=True)

    preflight = _preflight()
    if not preflight["passed"]:
        report = {
            "result": "BLOCKED",
            "blocked_before_gmail_connection": True,
            "preflight": preflight,
            "gmail_connected": False,
            "drafts_created": 0,
            "emails_sent": 0,
            "diagnostic_mode": "clarification_discovery_read_only",
        }
        _write_json(output_root / "reports" / "clarification_discovery_diagnostic_blocked.json", report)
        return report

    provider = GmailOAuthProvider()
    gmail_resource = provider.get_authenticated_client()
    profile = gmail_resource.users().getProfile(userId=os.environ.get("LMCP_GMAIL_USER_ID", "me")).execute()
    authenticated_email = str(profile.get("emailAddress") or "").lower()
    if authenticated_email != DEFAULT_SUPPLIER_MAILBOX:
        raise SystemExit("Authenticated Gmail mailbox does not match required supplier mailbox.")

    service = GmailDraftTransportService(
        gmail_client=GmailApiDraftClient(gmail_resource),
        env=os.environ,
        controlled_test_mode=True,
    )
    attachments = _attachments(output_root)
    request = _request("clarification", attachments)
    expected = expected_payload_for_request("clarification", request, request.subject)
    candidates = []
    inspected = 0
    for message in service.list_draft_messages():
        inspected += 1
        subject = message.summary.subject or ""
        body = message.body_text or ""
        if (
            REQUEST_ID in body
            or REQUEST_ID in subject
            or "Clarification" in subject
            or message.summary.supplier_request_id == REQUEST_ID
        ):
            candidates.append(diagnose_message(message, expected))
    matching = [candidate for candidate in candidates if candidate["materially_equivalent"]]
    report = {
        "result": "PASS",
        "diagnostic_mode": "clarification_discovery_read_only",
        "gmail_connected": True,
        "drafts_inspected": inspected,
        "clarification_candidates": len(candidates),
        "matching_clarification_candidates": len(matching),
        "historical_clarification_exists": bool(candidates),
        "historical_clarification_materially_equivalent": bool(matching),
        "candidates": candidates,
        "drafts_created": 0,
        "emails_sent": 0,
    }
    _write_json(output_root / "reports" / "clarification_discovery_diagnostic.json", report)
    _write_json(output_root / "reports" / "created_files.json", sorted(str(p) for p in output_root.rglob("*") if p.is_file()))
    return report


def _controlled_messages(service: GmailDraftTransportService):
    out = []
    for message in service.list_draft_messages():
        if message.summary.supplier_request_id == REQUEST_ID and message.summary.subject.startswith(SUBJECT_PREFIX):
            out.append(message)
    return out


def _duplicate_inventory(messages):
    by_type: Dict[str, List[Any]] = {"initial": [], "follow-up": [], "clarification": []}
    for message in messages:
        subject = message.summary.subject
        if "Initial Supplier RFQ" in subject:
            by_type["initial"].append(message)
        elif "Follow-Up" in subject:
            by_type["follow-up"].append(message)
        elif "Clarification" in subject:
            by_type["clarification"].append(message)
    inventory = {}
    for draft_type, values in by_type.items():
        ordered = sorted(values, key=lambda msg: (msg.reference.created_timestamp or "", msg.reference.redacted_draft_reference or ""))
        inventory[draft_type] = {
            "matching_drafts": len(ordered),
            "canonical_selected": 1 if ordered else 0,
            "duplicates": max(0, len(ordered) - 1),
            "subject": ordered[0].summary.subject if ordered else "",
            "canonical_redacted_reference": ordered[0].reference.redacted_draft_reference if ordered else "",
            "duplicate_redacted_references": [msg.reference.redacted_draft_reference for msg in ordered[1:]],
            "manual_cleanup_recommended": len(ordered) > 1,
        }
    return inventory


def _validate(drafts, controlled, resolutions, blocked):
    body = "\n".join(d.body_text for d in drafts)
    subjects = [d.summary.subject for d in drafts]
    return {
        "three_canonical_drafts": len(drafts) == 3,
        "at_least_three_controlled_drafts_listed": len(controlled) >= 3,
        "expected_subjects": all(subject.startswith(SUBJECT_PREFIX) for subject in subjects),
        "recipient_correct": all(d.summary.recipient == [DEFAULT_SUPPLIER_MAILBOX] for d in drafts),
        "mandatory_cc_correct": all(d.summary.cc == [DEFAULT_MANDATORY_CC] for d in drafts),
        "no_bcc": all("bcc" not in {k.lower() for k in d.decoded_headers} for d in drafts),
        "warning_present": all(WARNING in d.body_text for d in drafts),
        "request_id_present": all(REQUEST_ID in d.body_text for d in drafts),
        "rfq_reference_present": all(RFQ_REFERENCE in d.body_text for d in drafts),
        "quantities_present": all(value in body for value in ["327 | Straight Pipe Wrench 350 mm Heavy Duty | 80 | EA", "302 | Club Hammer 1.8 kg Steel-Reinforced Polymer Handle | 224 | EA", "328 | Straight Pipe Wrench 450 mm Heavy Duty | 280 | EA"]),
        "requirements_present": all(value in body for value in ["offered brand", "manufacturer datasheet", "sample may be requested"]),
        "standards_present": all(value in body for value in ["SANS 1028", "ISO 6787", "SANS 1211", "SANS 387"]),
        "attachment_count": all(d.summary.attachment_count == 3 for d in drafts),
        "draft_state": all(d.summary.draft_status == "DRAFT" for d in drafts),
        "no_internal_pricing": not any(term in body.lower() for term in ["internal cost", "markup", "margin", "profit"]),
        "send_blocks": all(v.get("blocked") for v in blocked.values()),
        "no_extra_creation_required_for_duplicate_call": all(resolution.new_draft_created is False for resolution in resolutions) or len(controlled) == 3,
    }


def _pricing_independence() -> Dict[str, Any]:
    state = build_no_response_pricing_state({
        "supplier_quote_coverage": RESPONSE_COVERAGE_NONE_FALLBACK,
        "pricing_confidence": "controlled_fallback_requires_operator_review",
    })
    state["buyer_quote_preparation_allowed"] = True
    state["buyer_autonomous_submission_enabled"] = False
    state["supplier_marked_contacted"] = False
    state["request_marked_sent"] = False
    state["followup_scheduled"] = False
    state["response_received"] = False
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Real Gmail draft-only validation for RFQ 6000080579.")
    parser.add_argument("--output", default=str(OUTPUT_ROOT))
    parser.add_argument("--diagnose-clarification-only", action="store_true")
    args = parser.parse_args()
    report = run_clarification_diagnostic(Path(args.output)) if args.diagnose_clarification_only else run(Path(args.output))
    print(json.dumps({
        "result": report.get("result"),
        "drafts_created": report.get("drafts_created", 0),
        "canonical_drafts_reused": report.get("canonical_drafts_reused", 0),
        "duplicates_detected": report.get("duplicates_detected", 0),
        "emails_sent": report.get("emails_sent", 0),
        "controlled_drafts_listed": report.get("controlled_drafts_listed", 0),
    }, indent=2))
    return 0 if str(report.get("result")).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
