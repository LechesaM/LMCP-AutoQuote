# Safe Sending Mode (Prototype)

This prototype can send emails **only** if all safety gates pass.

## Gates
1) `SEND_ENABLED=true` (default false)
2) Outbox item is `approved_to_send=true`
3) The RFQ text (including extracted PDF text) **explicitly allows email submission**
   - Conservative pattern match (deny by default)
4) Daily rate limit: `MAX_SENDS_PER_DAY`

## Audit/Evidence
Before sending, the system writes an evidence JSON bundle to `/evidence` containing:
- Opportunity snapshot
- Outbox subject/body
- Attachment list
- Policy decision

It stores:
- `evidence_packs` DB row (sha256 + path)
- `send_events` DB rows (blocked/sent/error)

## How to enable
Edit `.env`:
- `SEND_ENABLED=true`
- Configure SMTP: `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS`
- `MAIL_FROM=...`

Restart:
```bash
docker compose up --build
```

Send via:
- API: `POST /outbox/{id}/send`
- UI: click **Send** next to an approved draft
