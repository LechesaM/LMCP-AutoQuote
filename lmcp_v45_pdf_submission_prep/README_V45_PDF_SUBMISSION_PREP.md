# LMCP V45 PDF Renderer and Submission Prep

V45 takes a V44 quote pack workspace and produces:

- `formal_quotation_v45.pdf`
- `email_draft_v45.json`
- `submission_manifest_v45.json`
- `attachments/`
- zipped final bundle

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v45_pdf_submission_prep.zip -d .

cp lmcp_v45_pdf_submission_prep/app/services/submission_pack_v45_service.py app/services/submission_pack_v45_service.py
cp lmcp_v45_pdf_submission_prep/app/api/submission_pack_v45_api.py app/api/submission_pack_v45_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("submission_pack_v45_router", "app.api.submission_pack_v45_api", "router"),
```

Then:

```bash
python3 -m py_compile app/services/submission_pack_v45_service.py
python3 -m py_compile app/api/submission_pack_v45_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v45-submission-pack/status
```

If ReportLab is missing:

```bash
docker compose exec api pip install reportlab
```

## Prepare from existing V44 workspace

```bash
curl -X POST http://localhost:8000/v45-submission-pack/prepare-from-v44-workspace \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_path": "runtime/quote_pack_v44/REAL-TEST-V44__LMCP-QUOTE-20260501124222",
    "create_zip": true
  }'
```

## Full workflow from PDF

```bash
curl -X POST http://localhost:8000/v45-submission-pack/prepare-from-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "REAL-TEST-V45",
    "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "margin_percent": 25,
    "minimum_profit_required": 30000,
    "apply_profit_floor": true,
    "min_confidence": 0.35,
    "create_zip": true
  }'
```
