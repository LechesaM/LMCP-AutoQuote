from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict

from app.services.tender_pipeline import run_tender_pipeline_from_payload


def print_header(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def print_result(label: str, result: Dict[str, Any]) -> None:
    print_header(label)
    print(json.dumps(result, indent=2, default=str))


def assert_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AssertionError(f"{name} failed | expected={expected!r} | actual={actual!r}")
    print(f"[OK] {name}: {expected!r}")


def assert_true(name: str, value: Any) -> None:
    if value is not True:
        raise AssertionError(f"{name} failed | expected=True | actual={value!r}")
    print(f"[OK] {name}: True")


def assert_not_none(name: str, value: Any) -> None:
    if value is None:
        raise AssertionError(f"{name} failed | value is None")
    if isinstance(value, str) and not value.strip():
        raise AssertionError(f"{name} failed | value is empty string")
    print(f"[OK] {name}: {value!r}")


def build_base_payload() -> Dict[str, Any]:
    return {
        "title": "Supply and delivery of office chairs",
        "description": "Supply and delivery of office chairs to client site",
        "buyer_name": "Test Buyer",
        "buyer_rfq_number": "RFQ-TEST-001",
        "rfq_number": "RFQ-TEST-001",
        "reference_number": "RFQ-TEST-001",
        "document_number": "RFQ-TEST-001",
        "quote_number": "LMCP-RFQ-TEST-001",
        "buyer_email": "lechesam@icloud.com",
        "recipient_email": "lechesam@icloud.com",
        "buyer": {
            "name": "Test Buyer",
            "company_name": "Test Buyer",
            "email": "lechesam@icloud.com",
            "rfq_number": "RFQ-TEST-001",
        },
        "force_quote_ready": True,
        "pipeline_test_mode": True,
        "skip_supplier_ingestion": True,
        "skip_external_calls": True,
        "skip_email_submission": True,
        "auto_refresh_csd": False,
        "persist_to_live_store": False,
        "source": "test",
        "category": "Supply / Delivery",
        "items": [
            {
                "description": "Office Chair",
                "quantity": 10,
                "unit": "Each",
                "unit_price": 1500,
                "line_total": 15000,
            },
            {
                "description": "Executive Desk",
                "quantity": 2,
                "unit": "Each",
                "unit_price": 7500,
                "line_total": 15000,
            },
        ],
    }


def run_email_test() -> Dict[str, Any]:
    payload = build_base_payload()
    payload["submission_method"] = "email"
    payload["submission_email"] = "lechesam@icloud.com"
    payload["recipient_email"] = "lechesam@icloud.com"
    payload["buyer_email"] = "lechesam@icloud.com"

    result = run_tender_pipeline_from_payload(
        payload=payload,
        source="manual_test_email",
        persist_to_live_store=False,
    )

    print_result("EMAIL TEST RESULT", result)

    assert_true("email.quote_ready", result.get("quote_ready"))
    assert_true("email.pdf_generated", result.get("pdf_generated"))
    assert_equal("email.submission_method", result.get("submission_method"), "email")
    assert_equal("email.submission_channel", result.get("submission_channel"), "email")
    assert_not_none(
        "email.recipient_email",
        result.get("recipient_email")
        or (result.get("submission_pack") or {}).get("recipient_email")
        or (result.get("_original_input_payload") or {}).get("recipient_email")
        or (result.get("_original_input_payload") or {}).get("submission_email")
        or (result.get("_original_input_payload") or {}).get("buyer_email")
    )
    assert_equal("email.buyer_rfq_number", result.get("buyer_rfq_number"), "RFQ-TEST-001")
    assert_equal("email.rfq_number", result.get("rfq_number"), "RFQ-TEST-001")
    assert_equal("email.reference_number", result.get("reference_number"), "RFQ-TEST-001")
    assert_equal("email.document_number", result.get("document_number"), "RFQ-TEST-001")
    assert_not_none("email.pdf_path", result.get("pdf_path"))

    return result


def run_portal_test() -> Dict[str, Any]:
    payload = build_base_payload()
    payload["submission_method"] = "portal"
    payload["portal_url"] = "https://example.com/tender-portal"

    result = run_tender_pipeline_from_payload(
        payload=payload,
        source="manual_test_portal",
        persist_to_live_store=False,
    )

    print_result("PORTAL TEST RESULT", result)

    assert_true("portal.quote_ready", result.get("quote_ready"))
    assert_true("portal.pdf_generated", result.get("pdf_generated"))
    assert_equal("portal.submission_method", result.get("submission_method"), "portal")
    assert_equal("portal.submission_channel", result.get("submission_channel"), "portal")
    assert_equal("portal.buyer_rfq_number", result.get("buyer_rfq_number"), "RFQ-TEST-001")
    assert_not_none("portal.pdf_path", result.get("pdf_path"))

    return result


def run_physical_test() -> Dict[str, Any]:
    payload = build_base_payload()
    payload["submission_method"] = "physical"
    payload["recipient_email"] = None
    payload["buyer_email"] = None
    payload["submission_email"] = None

    result = run_tender_pipeline_from_payload(
        payload=payload,
        source="manual_test_physical",
        persist_to_live_store=False,
    )

    print_result("PHYSICAL TEST RESULT", result)

    assert_true("physical.quote_ready", result.get("quote_ready"))
    assert_true("physical.pdf_generated", result.get("pdf_generated"))
    assert_equal("physical.submission_method", result.get("submission_method"), "physical")
    assert_equal("physical.submission_channel", result.get("submission_channel"), "physical_via_email")
    assert_equal("physical.recipient_email", result.get("recipient_email"), "lmcpaqsystem@gmail.com")
    assert_equal("physical.buyer_rfq_number", result.get("buyer_rfq_number"), "RFQ-TEST-001")
    assert_not_none("physical.pdf_path", result.get("pdf_path"))

    return result


def run_catering_block_test() -> Dict[str, Any]:
    payload = build_base_payload()
    payload["title"] = "Catering services for workshop"
    payload["description"] = "Provision of meals, refreshments and catering services"
    payload["category"] = "Catering"
    payload["force_quote_ready"] = False
    payload["pipeline_test_mode"] = False
    payload["submission_method"] = "email"

    result = run_tender_pipeline_from_payload(
        payload=payload,
        source="manual_test_catering_block",
        persist_to_live_store=False,
    )

    print_result("CATERING BLOCK TEST RESULT", result)

    print("\n[INFO] Catering test should be blocked only after you add catering keywords to DISALLOWED_CATEGORY_KEYWORDS.")
    print("[INFO] If this still comes back quote_ready=True, your catering exclusion patch is not yet active.")

    return result


def main() -> None:
    summary: Dict[str, Any] = {}

    try:
        summary["email"] = run_email_test()
        summary["portal"] = run_portal_test()
        summary["physical"] = run_physical_test()
        summary["catering_block"] = run_catering_block_test()

        print_header("FINAL TEST SUMMARY")
        print(json.dumps(
            {
                "email": {
                    "quote_ready": summary["email"].get("quote_ready"),
                    "pdf_generated": summary["email"].get("pdf_generated"),
                    "submission_method": summary["email"].get("submission_method"),
                    "submission_channel": summary["email"].get("submission_channel"),
                    "recipient_email": summary["email"].get("recipient_email"),
                    "pdf_path": summary["email"].get("pdf_path"),
                },
                "portal": {
                    "quote_ready": summary["portal"].get("quote_ready"),
                    "pdf_generated": summary["portal"].get("pdf_generated"),
                    "submission_method": summary["portal"].get("submission_method"),
                    "submission_channel": summary["portal"].get("submission_channel"),
                    "recipient_email": summary["portal"].get("recipient_email"),
                    "pdf_path": summary["portal"].get("pdf_path"),
                },
                "physical": {
                    "quote_ready": summary["physical"].get("quote_ready"),
                    "pdf_generated": summary["physical"].get("pdf_generated"),
                    "submission_method": summary["physical"].get("submission_method"),
                    "submission_channel": summary["physical"].get("submission_channel"),
                    "recipient_email": summary["physical"].get("recipient_email"),
                    "pdf_path": summary["physical"].get("pdf_path"),
                },
                "catering_block": {
                    "eligible": summary["catering_block"].get("eligible"),
                    "quote_ready": summary["catering_block"].get("quote_ready"),
                    "submission_status": summary["catering_block"].get("submission_status"),
                    "submission_message": summary["catering_block"].get("submission_message"),
                },
            },
            indent=2,
            default=str,
        ))

        print("\nALL CHANNEL TESTS COMPLETED.")

    except AssertionError as exc:
        print_header("TEST FAILED")
        print(str(exc))
        raise

    except Exception as exc:
        print_header("UNEXPECTED ERROR")
        print(str(exc))
        raise


if __name__ == "__main__":
    main()
