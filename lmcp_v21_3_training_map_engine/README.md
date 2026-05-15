
# LMCP V21.3 Training-Map Engine

This version stops guessing and uses a trained fixed map for `RFQ_Corporate_Gift_Packs.pdf`.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v21_3_training_map_engine.zip -d .
cp lmcp_v21_3_training_map_engine/app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py
cp lmcp_v21_3_training_map_engine/app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py
docker compose restart api
sleep 5
curl http://localhost:8000/sbd-intelligence/status
```

Expected:

```json
"engine_version":"V21.3_TRAINING_MAP_ENGINE"
```

## Detect template

```bash
curl -X POST http://localhost:8000/sbd-intelligence/detect-template \
  -H "Content-Type: application/json" \
  -d '{"input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf"}'
```

## Run training-map completion

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V21-3-TRAINING-MAP",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "signature_image":"runtime/handwriting_simulation/signature.png",
    "ink_color":"black",
    "training_map":true,
    "auto_fill":true,
    "buyer_name":"iSIMANGALISO WETLAND PARK AUTHORITY",
    "bid_description":"SUPPLY AND DELIVERY OF CORPORATE GIFT PACKS"
  }'
```

Open:

```bash
open runtime/tender_form_intelligence/completed_forms/TEST-V21-3-TRAINING-MAP__v21_3_training_map_completed.pdf
```
