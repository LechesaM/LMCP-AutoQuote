from app.config import settings

def draft_email(buyer: str, title: str, ref: str, closing_at: str, url: str):
    subject = f"RFQ Response: {ref} | {title}".strip()

    body = f"""Dear Procurement Team,

We acknowledge the opportunity published by {buyer} and wish to submit our response for:

Reference: {ref}
Title: {title}
Closing date/time: {closing_at}
Source link: {url}

Please find our quotation and supporting documents attached. Our offer covers supply and delivery as required in the RFQ, subject to the final confirmed specifications and quantities.

Supplier details:
{settings.your_company_name}
Email: {settings.your_contact_email}
Tel: {settings.your_contact_phone}
Location: {settings.your_location}

Kindly confirm receipt and advise if any additional documentation is required.

Yours faithfully,
{settings.your_company_name}
"""
    return subject, body
