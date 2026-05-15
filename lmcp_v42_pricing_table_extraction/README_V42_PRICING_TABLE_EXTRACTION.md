# LMCP V42 Pricing Table Extraction Engine

V42 uses V41 navigation intelligence to scan likely pricing/BOQ pages and extract buyer schedule line items.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v42_pricing_table_extraction.zip -d .

cp lmcp_v42_pricing_table_extraction/app/services/pricing_table_extraction_v42_service.py app/services/pricing_table_extraction_v42_service.py
cp lmcp_v42_pricing_table_extraction/app/api/pricing_table_extraction_v42_api.py app/api/pricing_table_extraction_v42_api.py
cp lmcp_v42_pricing_table_extraction/app_main_v42_pricing_table_extraction.py app/main.py

python3 -m py_compile app/services/pricing_table_extraction_v42_service.py
python3 -m py_compile app/api/pricing_table_extraction_v42_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v42-pricing-table-extraction/status
```

## Full V41 + V42 workflow

```bash
curl -X POST http://localhost:8000/v42-pricing-table-extraction/analyse-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "REAL-TEST-V42",
    "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "max_pages_scan": 25,
    "min_confidence": 0.45
  }'
```

## Explicit page scan

```bash
curl -X POST http://localhost:8000/v42-pricing-table-extraction/extract-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "REAL-TEST-V42",
    "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "pages": [2,3,4,8,9,10],
    "min_confidence": 0.35
  }'
```\n