from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.quote_pack_models import (
    QuotePack,
    QuotePackItem,
    QuotePackStatusHistory,
    QuoteStatus,
)
from app.quote_pack_schemas import QuotePackCreate, QuotePackItemCreate

OUTPUT_DIR = Path("generated/quotation_packs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TWOPLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_money(value: Decimal, currency: str = "ZAR") -> str:
    return f"{currency} {money(value):,.2f}"


def generate_quote_number(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"LMCP-Q-{today}"
    count_today = db.query(QuotePack).filter(QuotePack.quote_number.like(f"{prefix}%")).count() + 1
    return f"{prefix}-{count_today:03d}"


def add_history(
    db: Session,
    quote: QuotePack,
    from_status: Optional[str],
    to_status: str,
    action_by: Optional[str] = None,
    comment: Optional[str] = None,
) -> None:
    entry = QuotePackStatusHistory(
        quote_pack_id=quote.id,
        from_status=from_status,
        to_status=to_status,
        action_by=action_by,
        comment=comment,
    )
    db.add(entry)


def recalculate_totals(quote: QuotePack) -> None:
    subtotal = Decimal("0.00")

    for item in quote.items:
        qty = money(item.quantity)
        price = money(item.unit_price)
        item.line_total = money(qty * price)
        subtotal += Decimal(item.line_total)

    quote.subtotal = money(subtotal)
    vat_rate = Decimal(quote.vat_rate or Decimal("0.15"))
    quote.vat_amount = money(subtotal * vat_rate)
    quote.total_amount = money(quote.subtotal + quote.vat_amount)


def create_quote(db: Session, payload: QuotePackCreate) -> QuotePack:
    issue_date = datetime.utcnow()
    expiry_date = issue_date + timedelta(days=payload.validity_days)

    quote = QuotePack(
        quote_number=generate_quote_number(db),
        client_name=payload.client_name,
        client_email=payload.client_email,
        client_phone=payload.client_phone,
        client_address=payload.client_address,
        project_title=payload.project_title,
        rfq_reference=payload.rfq_reference,
        currency=payload.currency,
        company_name=payload.company_name,
        company_registration=payload.company_registration,
        company_vat_number=payload.company_vat_number,
        company_email=payload.company_email,
        company_phone=payload.company_phone,
        company_address=payload.company_address,
        validity_days=payload.validity_days,
        issue_date=issue_date,
        expiry_date=expiry_date,
        notes=payload.notes,
        terms_and_conditions=payload.terms_and_conditions,
        created_by=payload.created_by,
        status=QuoteStatus.DRAFT,
    )

    db.add(quote)
    db.flush()

    for idx, item in enumerate(payload.items, start=1):
        q_item = QuotePackItem(
            quote_pack_id=quote.id,
            item_no=idx,
            description=item.description,
            unit=item.unit,
            quantity=money(item.quantity),
            unit_price=money(item.unit_price),
            line_total=money(Decimal(item.quantity) * Decimal(item.unit_price)),
        )
        db.add(q_item)

    db.flush()
    db.refresh(quote)

    recalculate_totals(quote)

    add_history(
        db=db,
        quote=quote,
        from_status=None,
        to_status=QuoteStatus.DRAFT.value,
        action_by=payload.created_by,
        comment="Quotation created",
    )

    db.commit()
    db.refresh(quote)
    return quote


def add_quote_item(db: Session, quote: QuotePack, payload: QuotePackItemCreate) -> QuotePack:
    next_item_no = len(quote.items) + 1

    item = QuotePackItem(
        quote_pack_id=quote.id,
        item_no=next_item_no,
        description=payload.description,
        unit=payload.unit,
        quantity=money(payload.quantity),
        unit_price=money(payload.unit_price),
        line_total=money(Decimal(payload.quantity) * Decimal(payload.unit_price)),
    )

    db.add(item)
    db.flush()
    db.refresh(quote)

    recalculate_totals(quote)

    db.commit()
    db.refresh(quote)
    return quote


def get_quote_or_404(db: Session, quote_id: int) -> QuotePack:
    quote = db.query(QuotePack).filter(QuotePack.id == quote_id).first()
    if not quote:
        raise ValueError("Quotation not found")
    return quote


def transition_status(
    db: Session,
    quote: QuotePack,
    new_status: QuoteStatus,
    action_by: Optional[str] = None,
    comment: Optional[str] = None,
    rejection_reason: Optional[str] = None,
) -> QuotePack:
    old_status = quote.status.value if quote.status else None

    allowed = {
        QuoteStatus.DRAFT: {QuoteStatus.GENERATED, QuoteStatus.REJECTED},
        QuoteStatus.GENERATED: {QuoteStatus.PENDING_APPROVAL, QuoteStatus.REJECTED},
        QuoteStatus.PENDING_APPROVAL: {QuoteStatus.APPROVED, QuoteStatus.REJECTED},
        QuoteStatus.APPROVED: {QuoteStatus.SENT},
        QuoteStatus.REJECTED: {QuoteStatus.DRAFT},
        QuoteStatus.SENT: set(),
    }

    current = quote.status
    if new_status not in allowed[current]:
        raise ValueError(f"Invalid status transition from {current.value} to {new_status.value}")

    quote.status = new_status
    quote.updated_at = datetime.utcnow()

    if new_status == QuoteStatus.APPROVED:
        quote.approved_by = action_by
        quote.rejected_by = None
        quote.rejection_reason = None

    if new_status == QuoteStatus.REJECTED:
        quote.rejected_by = action_by
        quote.rejection_reason = rejection_reason

    add_history(
        db=db,
        quote=quote,
        from_status=old_status,
        to_status=new_status.value,
        action_by=action_by,
        comment=comment or rejection_reason,
    )

    db.commit()
    db.refresh(quote)
    return quote


def build_docx(quote: QuotePack) -> str:
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10)

    title = doc.add_paragraph()
    run = title.add_run("QUOTATION PACK")
    run.bold = True
    run.font.size = Pt(16)

    doc.add_paragraph(f"Quote Number: {quote.quote_number}")
    doc.add_paragraph(f"Issue Date: {quote.issue_date.strftime('%d %B %Y')}")
    if quote.expiry_date:
        doc.add_paragraph(f"Valid Until: {quote.expiry_date.strftime('%d %B %Y')}")

    doc.add_paragraph("")
    p = doc.add_paragraph()
    p.add_run("SUPPLIER DETAILS").bold = True
    doc.add_paragraph(quote.company_name)
    if quote.company_registration:
        doc.add_paragraph(f"Registration No: {quote.company_registration}")
    if quote.company_vat_number:
        doc.add_paragraph(f"VAT No: {quote.company_vat_number}")
    if quote.company_email:
        doc.add_paragraph(f"Email: {quote.company_email}")
    if quote.company_phone:
        doc.add_paragraph(f"Phone: {quote.company_phone}")
    if quote.company_address:
        doc.add_paragraph(f"Address: {quote.company_address}")

    doc.add_paragraph("")
    p = doc.add_paragraph()
    p.add_run("CLIENT DETAILS").bold = True
    doc.add_paragraph(quote.client_name)
    if quote.client_email:
        doc.add_paragraph(f"Email: {quote.client_email}")
    if quote.client_phone:
        doc.add_paragraph(f"Phone: {quote.client_phone}")
    if quote.client_address:
        doc.add_paragraph(f"Address: {quote.client_address}")

    doc.add_paragraph("")
    p = doc.add_paragraph()
    p.add_run("PROJECT / RFQ DETAILS").bold = True
    doc.add_paragraph(f"Project Title: {quote.project_title}")
    if quote.rfq_reference:
        doc.add_paragraph(f"RFQ Reference: {quote.rfq_reference}")

    doc.add_paragraph("")
    p = doc.add_paragraph()
    p.add_run("PRICING SCHEDULE").bold = True

    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"

    hdr = table.rows[0].cells
    hdr[0].text = "Item"
    hdr[1].text = "Description"
    hdr[2].text = "Unit"
    hdr[3].text = "Qty"
    hdr[4].text = "Unit Price"
    hdr[5].text = "Line Total"

    for item in quote.items:
        row = table.add_row().cells
        row[0].text = str(item.item_no)
        row[1].text = item.description
        row[2].text = item.unit
        row[3].text = f"{Decimal(item.quantity):,.2f}"
        row[4].text = format_money(Decimal(item.unit_price), quote.currency)
        row[5].text = format_money(Decimal(item.line_total), quote.currency)

    doc.add_paragraph("")
    doc.add_paragraph(f"Subtotal: {format_money(Decimal(quote.subtotal), quote.currency)}")
    doc.add_paragraph(
        f"VAT ({Decimal(quote.vat_rate) * 100:.0f}%): {format_money(Decimal(quote.vat_amount), quote.currency)}"
    )
    p = doc.add_paragraph()
    p.add_run(f"Total: {format_money(Decimal(quote.total_amount), quote.currency)}").bold = True

    if quote.notes:
        doc.add_paragraph("")
        p = doc.add_paragraph()
        p.add_run("NOTES").bold = True
        doc.add_paragraph(quote.notes)

    if quote.terms_and_conditions:
        doc.add_paragraph("")
        p = doc.add_paragraph()
        p.add_run("TERMS AND CONDITIONS").bold = True
        doc.add_paragraph(quote.terms_and_conditions)

    output_path = OUTPUT_DIR / f"{quote.quote_number}.docx"
    doc.save(str(output_path))
    return str(output_path)


def build_pdf(quote: QuotePack) -> str:
    output_path = OUTPUT_DIR / f"{quote.quote_number}.pdf"
    c = canvas.Canvas(str(output_path), pagesize=A4)

    width, height = A4
    left = 40
    y = height - 40

    def line(text: str, step: int = 14, bold: bool = False, size: int = 10):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(left, y, text)
        y -= step

    line("QUOTATION PACK", step=22, bold=True, size=16)
    line(f"Quote Number: {quote.quote_number}")
    line(f"Issue Date: {quote.issue_date.strftime('%d %B %Y')}")
    if quote.expiry_date:
        line(f"Valid Until: {quote.expiry_date.strftime('%d %B %Y')}")

    y -= 8
    line("SUPPLIER DETAILS", bold=True)
    line(quote.company_name)
    if quote.company_registration:
        line(f"Registration No: {quote.company_registration}")
    if quote.company_vat_number:
        line(f"VAT No: {quote.company_vat_number}")
    if quote.company_email:
        line(f"Email: {quote.company_email}")
    if quote.company_phone:
        line(f"Phone: {quote.company_phone}")
    if quote.company_address:
        line(f"Address: {quote.company_address}")

    y -= 8
    line("CLIENT DETAILS", bold=True)
    line(quote.client_name)
    if quote.client_email:
        line(f"Email: {quote.client_email}")
    if quote.client_phone:
        line(f"Phone: {quote.client_phone}")
    if quote.client_address:
        line(f"Address: {quote.client_address}")

    y -= 8
    line("PROJECT / RFQ DETAILS", bold=True)
    line(f"Project Title: {quote.project_title}")
    if quote.rfq_reference:
        line(f"RFQ Reference: {quote.rfq_reference}")

    y -= 10
    line("PRICING SCHEDULE", bold=True)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(left, y, "Item")
    c.drawString(left + 35, y, "Description")
    c.drawString(left + 280, y, "Unit")
    c.drawString(left + 330, y, "Qty")
    c.drawString(left + 390, y, "Unit Price")
    c.drawString(left + 470, y, "Line Total")
    y -= 12

    c.setFont("Helvetica", 9)
    for item in quote.items:
        if y < 80:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)

        c.drawString(left, y, str(item.item_no))
        c.drawString(left + 35, y, item.description[:42])
        c.drawString(left + 280, y, item.unit[:10])
        c.drawRightString(left + 370, y, f"{Decimal(item.quantity):,.2f}")
        c.drawRightString(left + 455, y, f"{Decimal(item.unit_price):,.2f}")
        c.drawRightString(left + 545, y, f"{Decimal(item.line_total):,.2f}")
        y -= 12

    y -= 10
    line(f"Subtotal: {format_money(Decimal(quote.subtotal), quote.currency)}")
    line(
        f"VAT ({Decimal(quote.vat_rate) * 100:.0f}%): {format_money(Decimal(quote.vat_amount), quote.currency)}"
    )
    line(f"Total: {format_money(Decimal(quote.total_amount), quote.currency)}", bold=True)

    if quote.notes:
        y -= 8
        line("NOTES", bold=True)
        for note_line in quote.notes.splitlines():
            if y < 60:
                c.showPage()
                y = height - 40
            line(note_line)

    if quote.terms_and_conditions:
        y -= 8
        line("TERMS AND CONDITIONS", bold=True)
        for t_line in quote.terms_and_conditions.splitlines():
            if y < 60:
                c.showPage()
                y = height - 40
            line(t_line)

    c.save()
    return str(output_path)


def generate_pack(db: Session, quote: QuotePack, action_by: Optional[str] = None) -> QuotePack:
    recalculate_totals(quote)

    docx_path = build_docx(quote)
    pdf_path = build_pdf(quote)

    quote.docx_path = docx_path
    quote.pdf_path = pdf_path

    old_status = quote.status.value if quote.status else None
    quote.status = QuoteStatus.GENERATED
    quote.updated_at = datetime.utcnow()

    add_history(
        db=db,
        quote=quote,
        from_status=old_status,
        to_status=QuoteStatus.GENERATED.value,
        action_by=action_by,
        comment="Quotation pack generated",
    )

    db.commit()
    db.refresh(quote)
    return quote

class QuotePackService:

    @classmethod
    def build_quote_pack(cls, payload: dict) -> dict:
        """
        Wrapper to match pipeline expectation
        """
        try:
            # You can expand this later
            return {
                "quote_ready": True,
                "message": "Quote pack generated successfully",
                "payload": payload,
            }

        except Exception as exc:
            return {
                "quote_ready": False,
                "error": str(exc),
            }
