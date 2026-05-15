# LMCP V47.3 Attach to Live Browser Session

V47.3 connects to a Chrome/Chromium browser that you already opened with remote debugging.

It does:
- Attach to the currently open browser page
- Fill visible fields using V47.1 plan
- Capture screenshots
- Keep upload queue ready

It does NOT:
- bypass CAPTCHA
- auto-click final submit
- upload ZIP files
- close your browser intentionally

## 1. Start Chrome with remote debugging on Mac

Close Chrome first, then run:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/Users/Shared/LMCP-AutoQuote-Server/runtime/chrome_v47_3_profile
```

Then login and navigate manually to the correct tender submission page.

## 2. Install V47.3

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v47_3_attach_live_browser.zip -d .

cp lmcp_v47_3_attach_live_browser/app/services/live_browser_attach_v47_3_service.py app/services/live_browser_attach_v47_3_service.py
cp lmcp_v47_3_attach_live_browser/app/api/live_browser_attach_v47_3_api.py app/api/live_browser_attach_v47_3_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("live_browser_attach_v47_3_router", "app.api.live_browser_attach_v47_3_api", "router"),
```

Restart:

```bash
docker compose restart api
sleep 8
curl http://localhost:8000/v47-live-browser/status
```

## 3. Attach and assist

```bash
curl -X POST http://localhost:8000/v47-live-browser/attach-and-assist \
  -H "Content-Type: application/json" \
  -d '{
    "autofill_plan_json": "runtime/portal_form_autofill_v47_1/REAL-TEST-V47__AUTOFILL-20260501160345/portal_autofill_plan_v47_1.json",
    "cdp_url": "http://host.docker.internal:9222",
    "fill_visible_fields": true,
    "capture_screenshots": true,
    "stop_before_submit": true
  }'
```

If running the API outside Docker, use:

```json
"cdp_url": "http://127.0.0.1:9222"
```
