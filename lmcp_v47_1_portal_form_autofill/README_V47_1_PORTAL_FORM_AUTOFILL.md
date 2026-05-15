# LMCP V47.1 Portal Form Auto-Fill Assistant

V47.1 creates a safe auto-fill plan for portal submissions.

It does:
- Build portal form values
- Build selector candidates
- Build upload instructions
- Build Playwright-ready assist plan
- Create operator checklist

It does NOT:
- Submit final portal forms
- Bypass CAPTCHA
- Upload ZIP files

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v47_1_portal_form_autofill.zip -d .

cp lmcp_v47_1_portal_form_autofill/app/services/portal_form_autofill_v47_1_service.py app/services/portal_form_autofill_v47_1_service.py
cp lmcp_v47_1_portal_form_autofill/app/api/portal_form_autofill_v47_1_api.py app/api/portal_form_autofill_v47_1_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("portal_form_autofill_v47_1_router", "app.api.portal_form_autofill_v47_1_api", "router"),
```

Then:

```bash
python3 -m py_compile app/services/portal_form_autofill_v47_1_service.py
python3 -m py_compile app/api/portal_form_autofill_v47_1_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v47-portal-autofill/status
```

## Generate plan

```bash
curl -X POST http://localhost:8000/v47-portal-autofill/generate-plan \
  -H "Content-Type: application/json" \
  -d '{
    "portal_manifest_json": "runtime/portal_submission_v47/REAL-TEST-V47__PORTAL-20260501132714/portal_submission_manifest_v47.json"
  }'
```
