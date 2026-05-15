
# LMCP V21.1 Real Ink + Field Locator

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v21_1_real_ink_field_locator.zip -d .
```

## Permanent dependency fix

```bash
grep -qxF "pymupdf" requirements.txt || echo "pymupdf" >> requirements.txt
grep -qxF "pillow" requirements.txt || echo "pillow" >> requirements.txt
```

## Rebuild

```bash
docker compose down
docker compose up -d --build
sleep 8
curl http://localhost:8000/sbd-intelligence/status
```

Expected:

```json
"engine_version":"V21.1_REAL_INK_FIELD_LOCATOR"
```

## Test manual placement

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V21-1-MANUAL",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "reference_image":"runtime/handwriting_simulation/clean_ink_cropped.png",
    "ink_color":"black",
    "debug":true,
    "fields":[
      {
        "page":1,
        "x":80,
        "y":760,
        "w":420,
        "h":30,
        "text":"Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "name":"company_name",
        "font_size":14
      },
      {
        "page":1,
        "x":80,
        "y":795,
        "w":260,
        "h":30,
        "text":"Lechesa Manaba",
        "name":"director_name",
        "font_size":14
      }
    ]
  }'
```

Open:

```bash
open runtime/tender_form_intelligence/completed_forms/TEST-V21-1-MANUAL__v21_1_real_ink_completed_form.pdf
```

## Test field locator

```bash
curl -X POST http://localhost:8000/sbd-intelligence/locate-fields \
  -H "Content-Type: application/json" \
  -d '{
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "page":1,
    "limit":20
  }'
```
