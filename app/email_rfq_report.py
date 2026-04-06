import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.database import SessionLocal
from app.models import Opportunity


SMTP_SERVER = "smtp.mail.me.com"
SMTP_PORT = 587

EMAIL_SENDER = "lechesam@me.com"
EMAIL_PASSWORD = "xnrv-rojk-scbv-iavh"

EMAIL_RECEIVER = "lechesam@me.com"


def send_rfq_email():

    db = SessionLocal()

    opportunities = db.query(Opportunity).all()

    body = "LMCP HARVESTED RFQs\n\n"

    for o in opportunities:
        body += f"""
-------------------------------------
ID: {o.id}
Title: {o.title}
Buyer: {o.buyer}
Source: {o.source}
Published: {o.published_at}
Closing: {o.closing_date}
URL: {o.source_url}
"""

    db.close()

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = "LMCP Harvested RFQs"

    msg.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()

    server.login(EMAIL_SENDER, EMAIL_PASSWORD)

    server.send_message(msg)

    server.quit()

    print("RFQ email sent successfully")


if __name__ == "__main__":
    send_rfq_email()
