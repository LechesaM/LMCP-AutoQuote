
# LMCP V21.9 Realism Engine

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v21_9_realism_engine.zip -d .
cp lmcp_v21_9_realism_engine/app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py
cp lmcp_v21_9_realism_engine/app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py
docker compose restart api
sleep 8
curl http://localhost:8000/sbd-intelligence/status
```

Expected:

```json
"engine_version":"V21.9_REALISM_ENGINE"
```

## Test

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"FINAL-V21-9-REALISM",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "auto_fill": true,
    "use_glyph_handwriting": true,
    "debug": true
  }'
```

Open:

```bash
open runtime/tender_form_intelligence/completed_forms/FINAL-V21-9-REALISM__v21_9_realism_completed.pdf
```
