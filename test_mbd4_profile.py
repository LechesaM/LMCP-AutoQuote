from app.services.universal_form_filler import UniversalFormFiller, build_lmcp_default_form_data

print("=== START MBD4 PROFILE TEST ===")

filler = UniversalFormFiller()

data = build_lmcp_default_form_data(
    tender_data={
        "date_signed": "2026-04-14",
        "tender_number": "133-2025-2026",
        "rfq_number": "133-2025-2026",
        "client_name": "Test Municipality",
    },
    company_data={
        "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "company_email": "lechesam@me.com",
        "company_phone": "0826338492",
    },
    director_data={
        "director_name": "Lechesa Manaba",
        "signatory_name": "Lechesa Manaba",
        "director_capacity": "Managing Director",
        "signatory_capacity": "Managing Director",
        "witness_1_name": "Nobuhle Cath",
        "witness_2_name": "Charlie Champion Moeng",
    },
)

result = filler.fill_form(
    input_path="runtime/test_tender_pack/133-2025-2026 Tender Document.pdf",
    profile_name="133-2025-2026_Tender_Document__mbd_4__municipal_mbd4_profile.json",
    data=data,
    output_basename="TEST_MBD4_PROFILE",

    signature_path="app/assets/signatures/director.png",
    witness_1_signature_path="app/assets/signatures/witness_1.png",
    witness_2_signature_path="app/assets/signatures/witness_2.png",
    convert_to_pdf=True,
)

print(result)
print("=== END MBD4 PROFILE TEST ===")
