from app.services.tender_pipeline import run_tender_pipeline_from_payload
import json

sample_payload = {
    "title": "Supply and delivery of office chairs",
    "description": "Supply and delivery of office chairs to client site",
    "buyer_name": "Test Buyer",
    "buyer_rfq_number": "RFQ-TEST-001",
    "submission_method": "email",
    "recipient_email": "lechesam@icloud.com",
    "buyer_email": "lechesam@icloud.com",
    "force_quote_ready": True,
    "pipeline_test_mode": True,
    "skip_supplier_ingestion": True,
    "skip_external_calls": True,
    "auto_refresh_csd": False,
    "items": [
        {
            "description": "Office Chair",
            "quantity": 10,
            "unit": "Each",
            "unit_price": 1500
        }
    ]
}

result = run_tender_pipeline_from_payload(sample_payload)

print("\n========== NEW PIPELINE RESULT ==========\n")
print(json.dumps(result, indent=2, default=str))
