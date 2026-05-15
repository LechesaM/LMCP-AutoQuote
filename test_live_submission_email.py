from pathlib import Path
from app.services.document_ingestion_service import ingest_document

pdf_path = Path("runtime/playwright/downloads/Tender BSM 110 26 Supply and Delivery of Stationery from 1 July 2026 to 30 June 2027 with adverts.pdf")

result = ingest_document(
    pdf_path,
    metadata={
        "pricing_overrides": {"1": 32.50, "2": 54.00, "3": 185.00},
        "default_unit_price": 10.00,
        "vat_rate": 15.0,
        "currency": "ZAR",
        "prices_include_vat": True,
        "buyer_name": "STELLENBOSCH MUNICIPALITY",
        "buyer_rfq_number": "B/SM 110/26",
        "title": "SUPPLY AND DELIVERY OF STATIONERY FOR A CONTRACT PERIOD FROM 1 JULY 2026 TO 30 JUNE 2027",
        "pdf_output_dir": "runtime/generated_quotes",
        "submission_recipients": [
            "Bulelwa.Dolomba@stellenbosch.gov.za",
            "Minane.Jooste@stellenbosch.gov.za"
        ],
    }
)

print("smtp_preflight:", result.get("smtp_preflight", {}))
print("submission_email_ready:", result.get("submission_email_ready"))
print("submission_email_sent:", result.get("submission_email_sent"))
print("email_send_result:", result.get("email_send_result", {}))
print("submission_email_payload:", result.get("submission_email_payload", {}))


