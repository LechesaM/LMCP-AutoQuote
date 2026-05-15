from pprint import pprint

from app.services.tender_pipeline import run_tender_pipeline_from_payload

payload = {
    "title": "Supply and Delivery of Office Chairs",
    "description": "Supply and delivery of 50 ergonomic office chairs",
    "buyer_name": "City of Johannesburg",
    "submission_method": "email",
    "recipient_email": "lechesam@icloud.com",
    "items": [
        {
            "description": "Ergonomic Office Chair",
            "quantity": 50,
            "unit": "Each",
            "unit_price": 2127.81,
            "line_total": 106390.50
        }
    ],
    "supporting_documents": [
        "runtime/test_tender_pack/Sample_SBD.pdf"
    ],
    "force_quote_ready": True,
    "pipeline_test_mode": True,
}

result = run_tender_pipeline_from_payload(payload)

print("\n=== PIPELINE RESULT ===")
pprint(result)

print("\n=== QUICK CHECKS ===")
print("quote_generated:", result.get("quote_generated"))
print("pdf_generated:", result.get("pdf_generated"))
print("pdf_path:", result.get("pdf_path"))
print("form_fill_status:", result.get("form_fill_status"))
print("filled_form_outputs:", result.get("filled_form_outputs"))
print("filled_form_pdfs:", result.get("filled_form_pdfs"))
print("submission_attachments:", result.get("submission_attachments"))

filled_form_results = result.get("filled_form_results") or []
print("\n=== FILLED FORM RESULTS ===")
for idx, item in enumerate(filled_form_results, start=1):
    print(f"\nForm #{idx}")
    pprint(item)
