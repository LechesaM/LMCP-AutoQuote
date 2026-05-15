from pathlib import Path
from pypdf import PdfReader
from app.services.universal_form_filler import UniversalFormFiller, SignatureCoordinate

input_pdf = "runtime/test_tender_pack/133-2025-2026 Tender Document.pdf"
output_pdf = "runtime/generated_forms/TEST_DIRECT_SIGNATURE.pdf"
signature_path = "app/assets/signatures/director.png"

print("INPUT EXISTS:", Path(input_pdf).exists())
print("SIGNATURE EXISTS:", Path(signature_path).exists())

reader = PdfReader(input_pdf)
print("PAGE COUNT:", len(reader.pages))

filler = UniversalFormFiller()

coord = SignatureCoordinate(
    page=1,
    x=120,
    y=105,
    width=180,
    height=50,
)

filler._stamp_all_signatures_on_pdf(
    input_pdf=input_pdf,
    output_pdf=output_pdf,
    signature_path=signature_path,
    signature_coordinates=coord,
    witness_1_signature_path=None,
    witness_1_signature_coordinates=None,
    witness_2_signature_path=None,
    witness_2_signature_coordinates=None,
)

print("DONE:", output_pdf)

