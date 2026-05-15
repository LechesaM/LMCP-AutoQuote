
# LMCP V21.4 Glyph Handwriting Engine

This version uses your handwritten alphabet image as a glyph source.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v21_4_glyph_handwriting_engine.zip -d .
cp lmcp_v21_4_glyph_handwriting_engine/app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py
cp lmcp_v21_4_glyph_handwriting_engine/app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py
docker compose restart api
sleep 5
curl http://localhost:8000/sbd-intelligence/status
```

Expected:

```json
"engine_version":"V21.4_GLYPH_HANDWRITING_ENGINE"
```

## Save your handwriting image in the project

Put your handwriting alphabet image here:

```bash
mkdir -p runtime/handwriting_glyph_source
```

Copy the image to:

```text
runtime/handwriting_glyph_source/alphabet.png
```

## Build glyph library

```bash
curl -X POST http://localhost:8000/sbd-intelligence/build-glyphs \
  -H "Content-Type: application/json" \
  -d '{
    "reference_image":"runtime/handwriting_glyph_source/alphabet.png",
    "force":true
  }'
```

## Run glyph training-map completion

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V21-4-GLYPH",
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
open runtime/tender_form_intelligence/completed_forms/TEST-V21-4-GLYPH__v21_4_glyph_completed.pdf
```
