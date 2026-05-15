
# LMCP V21.5 Real Handwriting Engine

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v21_5_real_handwriting_engine.zip -d .
cp lmcp_v21_5_real_handwriting_engine/app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py
cp lmcp_v21_5_real_handwriting_engine/app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py
docker compose restart api
sleep 5
curl http://localhost:8000/sbd-intelligence/status
```

Expected:

```json
"engine_version":"V21.5_REAL_HANDWRITING_ENGINE"
```

## Rebuild glyphs

```bash
curl -X POST http://localhost:8000/sbd-intelligence/build-glyphs \
  -H "Content-Type: application/json" \
  -d '{
    "reference_image":"runtime/handwriting_glyph_source/alphabet.png",
    "force":true
  }'
```

Expected: `saved_glyphs` close to 62.

## Run completion

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V21-5-REAL-HANDWRITING",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "glyph_reference_image":"runtime/handwriting_glyph_source/alphabet.png",
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
open runtime/tender_form_intelligence/completed_forms/TEST-V21-5-REAL-HANDWRITING__v21_5_real_handwriting_completed.pdf
```
