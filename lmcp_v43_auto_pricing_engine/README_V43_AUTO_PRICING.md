# LMCP V43 Auto Pricing Engine

V43 cleans V42 false positives and builds quote-engine-ready priced line items.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v43_auto_pricing_engine.zip -d .

cp lmcp_v43_auto_pricing_engine/app/services/auto_pricing_v43_service.py app/services/auto_pricing_v43_service.py
cp lmcp_v43_auto_pricing_engine/app/api/auto_pricing_v43_api.py app/api/auto_pricing_v43_api.py
cp lmcp_v43_auto_pricing_engine/app_main_v43_auto_pricing.py app/main.py

python3 -m py_compile app/services/auto_pricing_v43_service.py
python3 -m py_compile app/api/auto_pricing_v43_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v43-auto-pricing/status
```

## Test full PDF workflow

```bash
curl -X POST http://localhost:8000/v43-auto-pricing/auto-price-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "REAL-TEST-V43",
    "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "max_pages_scan": 25,
    "margin_percent": 25,
    "minimum_profit_required": 30000,
    "apply_profit_floor": true,
    "min_confidence": 0.35
  }'
```

## Use existing V42 output

```bash
curl -X POST http://localhost:8000/v43-auto-pricing/auto-price-v42-json \
  -H "Content-Type: application/json" \
  -d '{
    "v42_json_path": "runtime/pricing_table_extraction_v42/REAL-TEST-V42__V42_PRICING_TABLE_EXTRACTION_ENGINE__YYYYMMDDHHMMSS.json",
    "buyer_rfq_number": "REAL-TEST-V43"
  }'
```
