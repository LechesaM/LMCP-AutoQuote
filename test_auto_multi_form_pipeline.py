from pathlib import Path
import json

from app.services.auto_multi_form_pipeline import AutoMultiFormPipeline

TENDER_ROOT = "runtime/test_tender_pack"
TENDER_ID = "AUTO_MULTI_FORM_LIVE_TEST"

DIRECTOR_SIGNATURE = "app/assets/signatures/director.png"
WITNESS_1_SIGNATURE = "app/assets/signatures/witness_1.png"
WITNESS_2_SIGNATURE = "app/assets/signatures/witness_2.png"

COMPANY_DATA = {
    "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
    "company_email": "lechesam@me.com",
    "company_phone": "0826338492",
}

DIRECTOR_DATA = {
    "signatory_name": "Lechesa Manaba",
    "signatory_capacity": "Managing Director",
    "witness_1_name": "Nobuhle Cath",
    "witness_2_name": "Charlie Champion Moeng",
}

TENDER_DATA = {
    "date_signed": "2026-04-14",
}

print("=== START FULL SYSTEM TEST ===")

pipeline = AutoMultiFormPipeline()

result = pipeline.run(
    tender_root=TENDER_ROOT,
    tender_id=TENDER_ID,
    company_data=COMPANY_DATA,
    director_data=DIRECTOR_DATA,
    tender_data=TENDER_DATA,
    signature_path=DIRECTOR_SIGNATURE,
    witness_1_signature_path=WITNESS_1_SIGNATURE,
    witness_2_signature_path=WITNESS_2_SIGNATURE,
)

print(json.dumps(result, indent=2))

print("=== END TEST ===")
