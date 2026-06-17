import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from pathlib import Path


class PDFQuoteGenerator:

    OUTPUT_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "quotes"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def generate_pdf(cls, payload) -> str:
        filename = f"{payload.pack_id}.pdf"
        filepath = cls.OUTPUT_DIR / filename

        doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        styles = getSampleStyleSheet()

        elements = []

        # Header
        elements.append(Paragraph(payload.company.company_name, styles["Title"]))
        elements.append(Spacer(1, 10))

        # Tender Info
        elements.append(Paragraph(f"Tender: {payload.rfq.title}", styles["Normal"]))
        elements.append(Paragraph(f"Issuing Entity: {payload.rfq.issuing_entity}", styles["Normal"]))
        elements.append(Spacer(1, 10))

        # Table
        table_data = [["Description", "Qty", "Unit Price", "Total"]]

        for item in payload.line_items:
            table_data.append([
                item.description,
                str(item.quantity),
                f"R {item.unit_price:,.2f}",
                f"R {item.total_price:,.2f}",
            ])

        table = Table(table_data)
        table.setStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ])

        elements.append(table)
        elements.append(Spacer(1, 20))

        # Totals
        elements.append(Paragraph(f"Subtotal: R {payload.pricing.subtotal:,.2f}", styles["Normal"]))
        elements.append(Paragraph(f"VAT: R {payload.pricing.vat_amount:,.2f}", styles["Normal"]))
        elements.append(Paragraph(f"Total: R {payload.pricing.total_including_vat:,.2f}", styles["Normal"]))

        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Prepared by Lechesa Manaba Consulting and Projects (Pty) Ltd", styles["Italic"]))

        doc.build(elements)

        return str(filepath)
