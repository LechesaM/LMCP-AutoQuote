import os
from app.services.universal_form_filler import UniversalFormFiller, build_lmcp_default_form_data

filler = UniversalFormFiller()

data = build_lmcp_default_form_data(
    tender_data={
        "date_signed": "2026-04-16",
        "rfq_number": "JGDM2025/26-027",
        "client_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "name_of_bidder": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "bidder_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "surname_and_name": "Lechesa Manaba",
        "capacity": "Director",
        "designation": "Director",
        "position": "Director",
        "address": "Bloemfontein, Free State, South Africa",
        "street_address": "Bloemfontein, Free State, South Africa",
        "postal_address": "Bloemfontein, Free State, South Africa",
        "telephone": "0826338492",
        "cellphone_number": "0826338492",
        "email": "lechesam@me.com",
        "email_address": "lechesam@me.com",
        "tcs_pin": "",
        "csd_number": "",
        "signed_place": "BLOEMFONTEIN",
    }
)

print("Director:", os.path.exists("app/assets/signatures/Director.png"))
print("Witness 1:", os.path.exists("app/assets/signatures/Witness_1.png"))
print("Witness 2:", os.path.exists("app/assets/signatures/Witness_2.png"))

result = filler.fill_form(
    input_path="runtime/test_tender_pack/Sample_SBD.pdf",
    data=data,
    signature_path="app/assets/signatures/Director.png",
    witness_1_signature_path="app/assets/signatures/Witness_1.png",
    witness_2_signature_path="app/assets/signatures/Witness_2.png",
    enable_handwriting=False,
)

print(result)
