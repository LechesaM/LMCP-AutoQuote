from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader, PdfWriter
import io
import os
from datetime import datetime


SIGNATURE_PATH = "app/signatures/director_signature.png"
STAMP_PATH = "app/signatures/company_stamp.png"


def sign_pdf(input_pdf, output_pdf):

    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)

        # signature
        if os.path.exists(SIGNATURE_PATH):
            can.drawImage(SIGNATURE_PATH, 350, 80, width=150, height=50)

        # stamp
        if os.path.exists(STAMP_PATH):
            can.drawImage(STAMP_PATH, 100, 70, width=100, height=100)

        # date
        today = datetime.today().strftime("%Y-%m-%d")
        can.drawString(350, 60, f"Signed: {today}")

        can.save()

        packet.seek(0)

        overlay = PdfReader(packet)

        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)
