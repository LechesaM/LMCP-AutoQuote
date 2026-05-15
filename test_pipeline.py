import json
from app.services.tender_pipeline import run_tender_pipeline_from_payload

email_payload = {
    "title": "Supply and delivery of office chairs",
    "description": "Supply and delivery of office chairs to client site",
    "buyer_name": "Test Buyer",
    "buyer_rfq_number": "RFQ-TEST-001",
    "rfq_number": "RFQ-TEST-001",
    "reference_number": "RFQ-TEST-001",
    "document_number": "RFQ-TEST-001",
    "quote_number": "LMCP-RFQ-TEST-001",
    "items": [
        {
            "description": "Office chair",
            "quantity": 10,
            "unit": "Each",
            "unit_price": 1500.0,
            "line_total": 15000.0,
        }
    ],
    "force_quote_ready": True,
    "pipeline_test_mode": True,
    "skip_external_calls": True,
    "skip_email_submission": False,
    "skip_supplier_ingestion": True,
    "auto_refresh_csd": False,
    "submission_method": "email",
    "recipient_email": "lechesam@icloud.com",
    "submission_email": "lechesam@icloud.com",
    "buyer_email": "lechesam@icloud.com",
    "_locked_buyer_rfq_number": "RFQ-TEST-001",
    "_locked_submission_email": "lechesam@icloud.com",
}

portal_payload = {
    **email_payload,
    "submission_method": "portal",
    "recipient_email": None,
    "submission_email": None,
    "buyer_email": None,
    "_locked_submission_email": None,
}

physical_payload = {
    **email_payload,
    "submission_method": "physical",
    "recipient_email": "lmcpaqsystem@gmail.com",
    "submission_email": "lmcpaqsystem@gmail.com",
    "buyer_email": "lmcpaqsystem@gmail.com",
    "_locked_submission_email": "lmcpaqsystem@gmail.com",
}

def run_test(name, payload):
    print("\n" + "=" * 80)
    print(f"TEST: {name}")
    print("=" * 80)

    result = run_tender_pipeline_from_payload(
        payload=payload,
        source=f"manual_test_{name.lower()}",
        persist_to_live_store=False,
    )

    summary = {
        "quote_ready": result.get("quote_ready"),
        "pdf_generated": result.get("pdf_generated"),
        "submission_method": result.get("submission_method"),
        "submission_channel": result.get("submission_channel"),
        "recipient_email": result.get("recipient_email"),
        "buyer_rfq_number": result.get("buyer_rfq_number"),
        "document_number": result.get("document_number"),
        "quote_number": result.get("quote_number"),
        "quote_folder": result.get("quote_folder"),
        "monthly_quote_folder": result.get("monthly_quote_folder"),
        "folder_path": result.get("folder_path"),
        "folder_name": result.get("folder_name"),
        "pdf_path": result.get("pdf_path"),
        "final_pdf_path": result.get("final_pdf_path"),
        "submission_pack": result.get("submission_pack"),
        "email_status": result.get("email_status"),
        "submission_status": result.get("submission_status"),
        "submission_message": result.get("submission_message"),
    }

    print(json.dumps(summary, indent=2, default=str))

    bad_hits = []
    for key in ["quote_folder", "monthly_quote_folder", "folder_path", "folder_name"]:
        value = str(result.get(key) or "")
        if "RFQ-MISSING" in value or "UNKNOWN" in value:
            bad_hits.append((key, value))

    sp = result.get("submission_pack") or {}
    if "RFQ-MISSING" in str(sp.get("buyer_rfq_number") or ""):
        bad_hits.append(("submission_pack.buyer_rfq_number", sp.get("buyer_rfq_number")))
    if "RFQ-MISSING" in str(sp.get("document_number") or ""):
        bad_hits.append(("submission_pack.document_number", sp.get("document_number")))

    if bad_hits:
        print("\nFAILED LOCK CHECKS:")
        for key, value in bad_hits:
            print(f"- {key}: {value}")
    else:
        print("\nLOCK CHECKS PASSED")

    return result

email_result = run_test("EMAIL", email_payload)
portal_result = run_test("PORTAL", portal_payload)
physical_result = run_test("PHYSICAL", physical_payload)

print("\n" + "=" * 80)
print("FINAL TEST SUMMARY")
print("=" * 80)
print(json.dumps({
    "email": {
        "quote_ready": email_result.get("quote_ready"),
        "pdf_generated": email_result.get("pdf_generated"),
        "submission_method": email_result.get("submission_method"),
        "submission_channel": email_result.get("submission_channel"),
        "recipient_email": email_result.get("recipient_email"),
        "quote_folder": email_result.get("quote_folder"),
        "pdf_path": email_result.get("pdf_path"),
    },
    "portal": {
        "quote_ready": portal_result.get("quote_ready"),
        "pdf_generated": portal_result.get("pdf_generated"),
        "submission_method": portal_result.get("submission_method"),
        "submission_channel": portal_result.get("submission_channel"),
        "recipient_email": portal_result.get("recipient_email"),
        "quote_folder": portal_result.get("quote_folder"),
        "pdf_path": portal_result.get("pdf_path"),
    },
    "physical": {
        "quote_ready": physical_result.get("quote_ready"),
        "pdf_generated": physical_result.get("pdf_generated"),
        "submission_method": physical_result.get("submission_method"),
        "submission_channel": physical_result.get("submission_channel"),
        "recipient_email": physical_result.get("recipient_email"),
        "quote_folder": physical_result.get("quote_folder"),
        "pdf_path": physical_result.get("pdf_path"),
    },
}, indent=2, default=str))
