def build_rfq_email(
    supplier_name,
    rfq_reference,
    tender_id,
    total_items,
    response_due_date
):
    subject = f"RFQ Request | {rfq_reference} | Tender {tender_id}"

    body = f"""
Dear {supplier_name},

Please provide a quotation for the attached RFQ package.

RFQ Reference:
{rfq_reference}

Tender:
{tender_id}

Number of Items:
{total_items}

Required Return Date:
{response_due_date}

Please include:

- Unit rates
- Total prices
- VAT status
- Delivery lead times
- Stock availability
- Commercial exclusions
- Payment terms

Kind regards,

LMCP AutoQuote Procurement
"""

    return {
        "subject": subject,
        "body": body.strip()
    }
