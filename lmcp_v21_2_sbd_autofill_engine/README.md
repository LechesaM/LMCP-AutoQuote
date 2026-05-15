
# LMCP V21.2 SBD Auto-Fill Decision Engine

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v21_2_sbd_autofill_engine.zip -d .
cp lmcp_v21_2_sbd_autofill_engine/app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py
cp lmcp_v21_2_sbd_autofill_engine/app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py
grep -qxF "pymupdf" requirements.txt || echo "pymupdf" >> requirements.txt
grep -qxF "pillow" requirements.txt || echo "pillow" >> requirements.txt
docker compose restart api
sleep 5
curl http://localhost:8000/sbd-intelligence/status
```

Expected:

```json
"engine_version":"V21.2_SBD_AUTOFILL_DECISION_ENGINE"
```

## Detect SBD pages

```bash
curl -X POST http://localhost:8000/sbd-intelligence/detect-sbd \
  -H "Content-Type: application/json" \
  -d '{"input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf"}'
```

## Run auto-fill

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V21-2-SBD-AUTO",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "reference_image":"runtime/handwriting_simulation/clean_ink_cropped.png",
    "signature_image":"runtime/handwriting_simulation/signature.png",
    "ink_color":"black",
    "debug":true,
    "auto_fill":true,
    "buyer_name":"iSIMANGALISO WETLAND PARK AUTHORITY",
    "bid_description":"Supply and Delivery of Corporate Gift Packs"
  }'
```

Open:

```bash
open runtime/tender_form_intelligence/completed_forms/TEST-V21-2-SBD-AUTO__v21_2_sbd_autofilled.pdf
```
