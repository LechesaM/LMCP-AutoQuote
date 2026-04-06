from app.services.universal_form_filler import UniversalFormFiller, build_lmcp_default_form_data

filler = UniversalFormFiller()

data = build_lmcp_default_form_data(
    tender_data={
        "tender_number": "TEST-RFQ-001",
        "date_signed": "2026-03-19",
        "quote_amount": "R 2 400 441.00"
    },
    company_data={
        "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "registration_number": "2025/123456/07",
        "vat_number": "4123456789"
    },
    director_data={
        "director_name": "Lechesa Manaba",
        "director_capacity": "Managing Director"
    }
)

result = filler.fill_form(
    input_path="runtime/incoming_docs/SBD4.pdf",
    data=data,
    output_basename="TEST_SBD4_COMPLETED",
    profile_name="example_sbd4_profile.json",
    signature_path=None,
    convert_to_pdf=True
)

print(result)
