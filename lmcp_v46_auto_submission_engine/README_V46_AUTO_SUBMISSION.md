# LMCP V46 Auto Submission Engine

V46 prepares or sends buyer email submissions from V45 packs.

Important rule:

> ZIP files are never attached to buyer emails.

ZIP bundles may remain for internal archive only.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v46_auto_submission_engine.zip -d .

cp lmcp_v46_auto_submission_engine/app/services/auto_submission_v46_service.py app/services/auto_submission_v46_service.py
cp lmcp_v46_auto_submission_engine/app/api/auto_submission_v46_api.py app/api/auto_submission_v46_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("auto_submission_v46_router", "app.api.auto_submission_v46_api", "router"),
```

Then:

```bash
python3 -m py_compile app/services/auto_submission_v46_service.py
python3 -m py_compile app/api/auto_submission_v46_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v46-auto-submission/status
```

## Dry-run from existing V45 workspace

```bash
curl -X POST http://localhost:8000/v46-auto-submission/submit-from-v45-workspace \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_path": "runtime/submission_pack_v45/REAL-TEST-V44__LMCP-QUOTE-20260501124222",
    "buyer_rfq_number": "REAL-TEST-V46",
    "dry_run": true,
    "allow_send": false
  }'
```

## Real SMTP send

Only after SMTP environment variables are configured:

```bash
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true
```

Then:

```bash
curl -X POST http://localhost:8000/v46-auto-submission/submit-from-v45-workspace \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_path": "runtime/submission_pack_v45/REAL-TEST-V44__LMCP-QUOTE-20260501124222",
    "buyer_rfq_number": "REAL-TEST-V46",
    "dry_run": false,
    "allow_send": true
  }'
```
