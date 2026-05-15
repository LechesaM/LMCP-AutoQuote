import json
from app.services.tender_pipeline import run_tender_pipeline_from_payload

live_email_payload = {
    "title": "Supply and delivery of office chairs",
    "description": "Supply and delivery of office chairs to client site",
    "buyer_name": "Live Test Buyer",
    "buyer_rfq_number": "RFQ-LIVE-001",
    "rfq_number": "RFQ-LIVE-001",
    "reference_number": "RFQ-LIVE-001",
    "document_number": "RFQ-LIVE-001",
    "quote_number": "LMCP-RFQ-LIVE-001",
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
    "pipeline_test_mode": False,
    "skip_external_calls": False,
    "skip_email_submission": False,
    "skip_supplier_ingestion": True,
    "auto_refresh_csd": False,
    "submission_method": "email",
    "recipient_email": "manabalm@gmail.com",
    "submission_email": "manabalm@gmail.com",
    "buyer_email": "manabalm@gmail.com",
    "_locked_buyer_rfq_number": "RFQ-LIVE-001",
    "_locked_submission_email": "manabalm@gmail.com",
}

result = run_tender_pipeline_from_payload(
    payload=live_email_payload,
    source="manual_live_email_test",
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
    "pdf_path": result.get("pdf_path"),
    "submission_status": result.get("submission_status"),
    "submission_message": result.get("submission_message"),
    "email_status": result.get("email_status"),
    "email_sent": result.get("email_sent"),
}

print(json.dumps(summary, indent=2, default=str))
