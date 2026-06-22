import imaplib
import email
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from email.header import decode_header

DB_PATH = Path("runtime/workflow/workflow_layer.db")
ATTACHMENT_DIR = Path("runtime/supplier_responses/attachments")
RESPONSE_LOG_PATH = Path("runtime/supplier_responses/response_listener_log.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def decode_mime_text(value):
    if not value:
        return ""

    decoded_parts = decode_header(value)
    output = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            output += part.decode(encoding or "utf-8", errors="replace")
        else:
            output += part

    return output


def get_known_rfqs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        rfq_reference,
        supplier_name,
        response_due_at,
        status
    FROM rfq_batches
    """)

    rows = cur.fetchall()
    conn.close()

    return {
        row[0]: {
            "supplier_name": row[1],
            "response_due_at": row[2],
            "status": row[3]
        }
        for row in rows
    }


def upsert_supplier_response(
    rfq_reference,
    supplier_name,
    response_status,
    notes=None
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO supplier_responses (
        rfq_reference,
        supplier_name,
        response_status,
        notes,
        received_at,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        rfq_reference,
        supplier_name,
        response_status,
        notes,
        utc_now(),
        utc_now()
    ))

    cur.execute("""
    UPDATE rfq_batches
    SET status = ?
    WHERE rfq_reference = ?
    """, (
        response_status,
        rfq_reference
    ))

    conn.commit()
    conn.close()


def extract_email_text(msg):
    body_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")

            if "attachment" in disposition.lower():
                continue

            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(
                        payload.decode(charset, errors="replace")
                    )
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(
                payload.decode(charset, errors="replace")
            )

    return "\n".join(body_parts)


def save_attachments(msg, rfq_reference):
    saved_files = []
    target_dir = ATTACHMENT_DIR / rfq_reference
    target_dir.mkdir(parents=True, exist_ok=True)

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition") or "")

        if "attachment" not in disposition.lower():
            continue

        filename = part.get_filename()

        if not filename:
            continue

        filename = decode_mime_text(filename)
        safe_filename = filename.replace("/", "_").replace("\\", "_")

        file_path = target_dir / safe_filename

        with open(file_path, "wb") as f:
            f.write(part.get_payload(decode=True))

        saved_files.append(str(file_path))

    return saved_files


def match_rfq_reference(subject, body, known_rfqs):
    combined = f"{subject}\n{body}"

    for rfq_reference in known_rfqs.keys():
        if rfq_reference in combined:
            return rfq_reference

    return None


def listen_for_responses(
    mailbox="INBOX",
    search_criteria='UNSEEN',
    mark_seen=False
):
    imap_server = os.getenv("IMAP_SERVER")
    imap_port = int(os.getenv("IMAP_PORT", "993"))
    imap_username = os.getenv("IMAP_USERNAME")
    imap_password = os.getenv("IMAP_PASSWORD")

    if not imap_server or not imap_username or not imap_password:
        raise RuntimeError(
            "Missing IMAP settings. Set IMAP_SERVER, IMAP_PORT, IMAP_USERNAME, IMAP_PASSWORD."
        )

    known_rfqs = get_known_rfqs()
    listener_log = []

    mail = imaplib.IMAP4_SSL(imap_server, imap_port)
    mail.login(imap_username, imap_password)
    mail.select(mailbox)

    status, messages = mail.search(None, search_criteria)

    if status != "OK":
        raise RuntimeError(f"IMAP search failed: {status}")

    message_ids = messages[0].split()

    for message_id in message_ids:
        fetch_mode = "(RFC822)" if mark_seen else "(BODY.PEEK[])"
        status, msg_data = mail.fetch(message_id, fetch_mode)

        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_mime_text(msg.get("Subject"))
        from_email = decode_mime_text(msg.get("From"))
        body = extract_email_text(msg)

        rfq_reference = match_rfq_reference(
            subject=subject,
            body=body,
            known_rfqs=known_rfqs
        )

        if not rfq_reference:
            listener_log.append({
                "message_id": message_id.decode(),
                "from": from_email,
                "subject": subject,
                "matched": False,
                "reason": "no_rfq_reference_found",
                "processed_at": utc_now()
            })
            continue

        supplier_name = known_rfqs[rfq_reference]["supplier_name"]
        saved_attachments = save_attachments(msg, rfq_reference)

        notes = json.dumps({
            "from": from_email,
            "subject": subject,
            "attachments": saved_attachments
        })

        upsert_supplier_response(
            rfq_reference=rfq_reference,
            supplier_name=supplier_name,
            response_status="response_received",
            notes=notes
        )

        listener_log.append({
            "message_id": message_id.decode(),
            "from": from_email,
            "subject": subject,
            "matched": True,
            "rfq_reference": rfq_reference,
            "supplier_name": supplier_name,
            "attachments_saved": saved_attachments,
            "processed_at": utc_now()
        })

        print(f"MATCHED: {supplier_name} | {rfq_reference}")

    mail.logout()

    RESPONSE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": utc_now(),
        "messages_checked": len(message_ids),
        "matched_responses": sum(1 for item in listener_log if item["matched"]),
        "unmatched_messages": sum(1 for item in listener_log if not item["matched"]),
        "responses": listener_log
    }

    with open(RESPONSE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("\nRESPONSE LISTENER RESULT")
    print("=" * 80)
    print(f"Messages checked:   {payload['messages_checked']}")
    print(f"Matched responses:  {payload['matched_responses']}")
    print(f"Unmatched messages: {payload['unmatched_messages']}")
    print(f"Log:                {RESPONSE_LOG_PATH}")

    return payload


if __name__ == "__main__":
    listen_for_responses(
        mailbox="INBOX",
        search_criteria="UNSEEN",
        mark_seen=False
    )
