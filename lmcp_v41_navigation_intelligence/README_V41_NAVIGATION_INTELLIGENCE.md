# LMCP V41 Navigation Intelligence Engine

V41 reads V40 output and turns it into useful tender intelligence.

## What V41 detects

- Pricing / BOQ candidate pages
- SBD / MBD candidate pages
- Declaration pages
- Submission email
- Submission instruction pages
- Specifications / Terms of Reference pages
- Evaluation / functionality pages
- Whether buyer requires handwritten black-ink forms
- Recommended next actions for the pipeline

## Files

```bash
app/services/navigation_intelligence_v41_service.py
app/api/navigation_intelligence_v41_api.py
```

## Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v41_navigation_intelligence/app/services/navigation_intelligence_v41_service.py app/services/navigation_intelligence_v41_service.py
cp lmcp_v41_navigation_intelligence/app/api/navigation_intelligence_v41_api.py app/api/navigation_intelligence_v41_api.py
```

## Add to app/main.py OPTIONAL_ROUTERS

Add this line after V40:

```python
("navigation_intelligence_v41_router", "app.api.navigation_intelligence_v41_api", "router"),
```

## Compile and restart

```bash
python3 -m py_compile app/services/navigation_intelligence_v41_service.py
python3 -m py_compile app/api/navigation_intelligence_v41_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v41-navigation-intelligence/status
```

## Analyse PDF directly

```bash
curl -X POST http://localhost:8000/v41-navigation-intelligence/analyse-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "REAL-TEST-V41",
    "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "max_pages_scan": 20
  }'
```

## Analyse existing V40 JSON

Use the `output_json` path returned by V40:

```bash
curl -X POST http://localhost:8000/v41-navigation-intelligence/analyse-v40-json \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "REAL-TEST-V41",
    "v40_json_path": "runtime/clickable_navigation_v40/REAL-TEST-V40__V40_CLICKABLE_NAVIGATION_EXTRACTOR__YYYYMMDDHHMMSS.json"
  }'
```
