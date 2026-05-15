# LMCP V47.4 Smart Upload Engine

V47.4 attaches to your live browser session and detects upload fields.

It can run in planning mode or execution mode.

It never clicks final submit and never uploads ZIP files.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v47_4_smart_upload_engine.zip -d .

cp lmcp_v47_4_smart_upload_engine/app/services/smart_upload_v47_4_service.py app/services/smart_upload_v47_4_service.py
cp lmcp_v47_4_smart_upload_engine/app/api/smart_upload_v47_4_api.py app/api/smart_upload_v47_4_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("smart_upload_v47_4_router", "app.api.smart_upload_v47_4_api", "router"),
```

Restart:

```bash
docker compose restart api
sleep 8
curl http://localhost:8000/v47-smart-upload/status
```

## Planning mode first

```bash
curl -X POST http://localhost:8000/v47-smart-upload/attach-and-upload \
  -H "Content-Type: application/json" \
  -d '{
    "autofill_plan_json": "runtime/portal_form_autofill_v47_1/REAL-TEST-V47__AUTOFILL-20260501160345/portal_autofill_plan_v47_1.json",
    "cdp_url": "ws://host.docker.internal:9222/devtools/browser/YOUR_BROWSER_ID",
    "execute_uploads": false,
    "capture_screenshots": true,
    "stop_before_submit": true
  }'
```

## Execution mode only after planning looks correct

```bash
curl -X POST http://localhost:8000/v47-smart-upload/attach-and-upload \
  -H "Content-Type: application/json" \
  -d '{
    "autofill_plan_json": "runtime/portal_form_autofill_v47_1/REAL-TEST-V47__AUTOFILL-20260501160345/portal_autofill_plan_v47_1.json",
    "cdp_url": "ws://host.docker.internal:9222/devtools/browser/YOUR_BROWSER_ID",
    "execute_uploads": true,
    "capture_screenshots": true,
    "stop_before_submit": true
  }'
```
