import json
import subprocess
import os
from pathlib import Path

from app.services.tender_submission_pipeline import TenderSubmissionPipeline


def main():
    pipeline = TenderSubmissionPipeline()

    Path("runtime/test_tender_pack").mkdir(parents=True, exist_ok=True)

    result = pipeline.run(
        tender_root="runtime/test_tender_pack",
        tender_id="TEST-RFQ-PIPELINE-001",
        instructions_text=(
            "Bidders must submit SBD 4, SBD 8, SBD 9 and pricing schedule. "
            "Complete all returnable documents contained in the tender document."
        ),
        mandatory_form_codes=["sbd4", "sbd8", "sbd9", "pricing_schedule"],
        company_data={
            "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "registration_number": "2025/123456/07",
            "vat_number": "4123456789",
            "company_email": "info@lmcp.co.za",
            "company_phone": "0510000000",
            "company_address": "Bloemfontein, Free State, South Africa",
        },
        director_data={
            "director_name": "Lechesa Manaba",
            "director_capacity": "Managing Director",
            "director_email": "director@lmcp.co.za",
            "director_phone": "0820000000",
        },
        tender_data={
            "tender_number": "TEST-RFQ-PIPELINE-001",
            "tender_title": "Test Tender Pipeline",
            "client_name": "Demo Client",
            "submission_date": "2026-03-19",
            "date_signed": "2026-03-19",
            "quote_amount": "R 2 400 441.00",
        },
        signature_path=None,
        form_profile_map={
            "sbd4": "example_sbd4_profile.json"
        },
        enable_archive_extract=True,
    )

    print(json.dumps(result, indent=2))

    final_files = result.get("final_files", [])
    pdf_files = [f for f in final_files if f.lower().endswith(".pdf")]

    if pdf_files:
        latest_pdf = pdf_files[0]
        print(f"\nOpening PDF: {latest_pdf}\n")
        os.system(f'open -a Preview "{latest_pdf}"')
    else:
        print("\nNo PDF file found to open.\n")


if __name__ == "__main__":
    main()
