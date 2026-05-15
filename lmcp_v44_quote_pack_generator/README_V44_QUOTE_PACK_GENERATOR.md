# LMCP V44 Quote Pack Generator

V44 takes V43 pricing output and creates a submission-ready quote pack workspace.

## Outputs

- `formal_quotation_v44.html`
- `buyer_pricing_schedule_v44.csv`
- `quote_engine_payload_v44.json`
- `submission_manifest_v44.json`
- `quote_pack_metadata_v44.json`
- `compliance/` folder with copied compliance docs where available

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v44_quote_pack_generator.zip -d .

cp lmcp_v44_quote_pack_generator/app/services/quote_pack_v44_service.py app/services/quote_pack_v44_service.py
cp lmcp_v44_quote_pack_generator/app/api/quote_pack_v44_api.py app/api/quote_pack_v44_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("quote_pack_v44_router", "app.api.quote_pack_v44_api", "router"),
```

Then:

```bash
python3 -m py_compile app/services/quote_pack_v44_service.py
python3 -m py_compile app/api/quote_pack_v44_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v44-quote-pack/status
```

## Test full workflow

```bash
curl -X POST http://localhost:8000/v44-quote-pack/generate-from-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "REAL-TEST-V44",
    "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "margin_percent": 25,
    "minimum_profit_required": 30000,
    "apply_profit_floor": true,
    "min_confidence": 0.35
  }'
```
