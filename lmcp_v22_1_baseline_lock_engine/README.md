
# LMCP V22.1 Baseline Lock Engine

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v22_1_baseline_lock_engine.zip -d .
cp lmcp_v22_1_baseline_lock_engine/app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py
cp lmcp_v22_1_baseline_lock_engine/app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py
cp lmcp_v22_1_baseline_lock_engine/app/api/tender_form_intelligence_api.py app/api/sbd_intelligence_api.py
docker compose restart api
sleep 8
curl http://localhost:8000/sbd-intelligence/status
```

## Test

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"FINAL-V22-1-BASELINE",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "auto_fill": true,
    "use_glyph_handwriting": true,
    "debug": true
  }'
```
