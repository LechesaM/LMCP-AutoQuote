from app.services.stamp_service import StampService
from app.services.pdf_stamp_injector import PdfStampInjector

print("=== START DIRECT STAMP TEST ===")

stamp_path = StampService.ensure_default_stamp()
print("STAMP:", stamp_path)

input_pdf = "runtime/test_tender_pack/sample_sbd.pdf"
output_pdf = "runtime/generated_forms/sample_sbd_stamped.pdf"

out = PdfStampInjector.stamp_pdf(
    input_pdf_path=input_pdf,
    output_pdf_path=output_pdf,
    x=380,
    y=90,
    width=140,
    height=52,
)

print("STAMPED PDF:", out)
print("=== END DIRECT STAMP TEST ===")
