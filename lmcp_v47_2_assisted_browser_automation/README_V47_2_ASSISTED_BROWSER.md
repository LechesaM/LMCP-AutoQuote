# LMCP V47.2 Assisted Browser Automation

V47.2 uses the V47.1 autofill plan to open a portal, attempt safe field filling, create an upload queue, and capture screenshots.

It does NOT:
- bypass CAPTCHA
- auto-click final submit
- guess upload fields blindly
- upload ZIP files

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v47_2_assisted_browser_automation.zip -d .

cp lmcp_v47_2_assisted_browser_automation/app/services/assisted_browser_v47_2_service.py app/services/assisted_browser_v47_2_service.py
cp lmcp_v47_2_assisted_browser_automation/app/api/assisted_browser_v47_2_api.py app/api/assisted_browser_v47_2_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("assisted_browser_v47_2_router", "app.api.assisted_browser_v47_2_api", "router"),
```

Then:

```bash
python3 -m py_compile app/services/assisted_browser_v47_2_service.py
python3 -m py_compile app/api/assisted_browser_v47_2_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v47-assisted-browser/status
```

If Playwright is missing:

```bash
docker compose exec api pip install playwright
docker compose exec api playwright install chromium
```

## Run from V47.1 plan

```bash
curl -X POST http://localhost:8000/v47-assisted-browser/run-from-plan \
  -H "Content-Type: application/json" \
  -d '{
    "autofill_plan_json": "runtime/portal_form_autofill_v47_1/REAL-TEST-V47__AUTOFILL-20260501160345/portal_autofill_plan_v47_1.json",
    "headless": true,
    "stop_before_submit": true
  }'
```
