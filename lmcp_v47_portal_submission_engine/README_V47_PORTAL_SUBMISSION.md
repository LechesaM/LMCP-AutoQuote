# LMCP V47 Portal Submission Engine

V47 prepares portal-ready upload files and proof tracking.

Important:
- It does **not** bypass CAPTCHA.
- It does **not** auto-click final submit without operator confirmation.
- ZIP files are not allowed for portal upload unless a future buyer-specific rule explicitly allows them.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v47_portal_submission_engine.zip -d .

cp lmcp_v47_portal_submission_engine/app/services/portal_submission_v47_service.py app/services/portal_submission_v47_service.py
cp lmcp_v47_portal_submission_engine/app/api/portal_submission_v47_api.py app/api/portal_submission_v47_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("portal_submission_v47_router", "app.api.portal_submission_v47_api", "router"),
```

Then:

```bash
python3 -m py_compile app/services/portal_submission_v47_service.py
python3 -m py_compile app/api/portal_submission_v47_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v47-portal-submission/status
```

## Prepare portal pack from V45 workspace

```bash
curl -X POST http://localhost:8000/v47-portal-submission/prepare-from-v45-workspace \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_path": "runtime/submission_pack_v45/REAL-TEST-V44__LMCP-QUOTE-20260501124222",
    "buyer_rfq_number": "REAL-TEST-V47",
    "buyer_name": "iSimangaliso Wetland Park Authority",
    "portal_url": "https://www.etenders.gov.za"
  }'
```

## Record proof after manual portal submission

```bash
curl -X POST http://localhost:8000/v47-portal-submission/record-proof \
  -H "Content-Type: application/json" \
  -d '{
    "portal_manifest_json": "runtime/portal_submission_v47/REAL-TEST-V47__PORTAL-YYYYMMDDHHMMSS/portal_submission_manifest_v47.json",
    "portal_receipt_number": "PORTAL-RECEIPT-123",
    "submitted_by": "Lechesa Manaba",
    "proof_files": [],
    "notes": "Submission completed through portal."
  }'
```
